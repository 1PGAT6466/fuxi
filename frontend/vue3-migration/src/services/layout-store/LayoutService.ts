/**
 * 伏羲 v2.1 — 窗口布局持久化服务
 *
 * LayoutService 是布局方案管理的核心业务逻辑层：
 * - 窗口位置/大小快照创建与恢复
 * - 布局方案的 CRUD（创建、读取、更新、删除）
 * - 多显示器适配与配置检测
 * - 布局导入/导出
 * - 本地存储降级（网络不可用时使用 localStorage 缓存）
 *
 * 架构：
 *   LayoutService (业务逻辑)
 *     ├── api/layout.ts (后端通信)
 *     ├── stores/layout.ts (Pinia Store - 响应式状态)
 *     └── stores/windowManager.ts (窗口管理集成)
 */

import { createLogger } from '@/utils/logger';
import type {
  DisplayInfo,
  DisplayConfiguration,
  WindowSnapshot,
  LayoutPlan,
  LayoutExport,
  SaveLayoutRequest,
  LayoutActionResult,
  LayoutListResponse,
} from '@/types/layout';
import type { ServiceWindow, WindowState } from '@/types/service-manifest';
import * as layoutApi from '@/api/layout';

const logger = createLogger('LayoutService');

// ============================
// 本地存储 Key
// ============================

const LOCAL_CACHE_KEY = 'fuxi-layout-cache';
const LAST_ACTIVE_KEY = 'fuxi-last-active-layout';
const MAX_LOCAL_CACHE = 10;

// ============================
// LayoutService 类
// ============================

class LayoutService {
  /** 变更监听器 */
  private listeners: Array<(event: { action: string; layout: LayoutPlan }) => void> = [];

  // ═══════════════════════════════════════════
  // 显示器检测
  // ═══════════════════════════════════════════

  /**
   * 检测当前显示器配置
   *
   * 浏览器端无法通过标准 API 获取物理多显示器信息，
   * 因此通过 window.screen 和 window.screen.isExtended (Chrome 100+)
   * 来推断当前显示器的基本信息。
   *
   * @returns 显示器配置信息
   */
  detectDisplayConfiguration(): DisplayConfiguration {
    const screenInfo = window.screen;
    const primaryDisplay: DisplayInfo = {
      id: `display-primary-${screenInfo.width}x${screenInfo.height}`,
      name: '主显示器',
      availWidth: screenInfo.availWidth,
      availHeight: screenInfo.availHeight,
      width: screenInfo.width,
      height: screenInfo.height,
      left: 0,
      top: 0,
      isPrimary: true,
      devicePixelRatio: window.devicePixelRatio || 1,
    };

    const displays: DisplayInfo[] = [primaryDisplay];

    // Chrome 100+ 支持 Screen Details API（需要权限）
    if ('isExtended' in screenInfo && (screenInfo as any).isExtended) {
      // 尝试通过 getScreenDetails 获取更多信息（需要用户授权）
      // 降级方案：标记为扩展显示器模式
      displays[0]!.name = '扩展显示器模式';
    }

    // 通过 window.innerWidth/innerHeight 感知窗口在不同显示器上的尺寸变化
    const totalBounds = {
      left: 0,
      top: 0,
      right: Math.max(window.innerWidth, screenInfo.width),
      bottom: Math.max(window.innerHeight, screenInfo.height),
    };

    // 生成配置指纹
    const fingerprint = this.generateDisplayFingerprint(displays);

    return {
      count: displays.length,
      displays,
      totalBounds,
      fingerprint,
    };
  }

  /**
   * 生成显示器配置指纹
   */
  generateDisplayFingerprint(displays: DisplayInfo[]): string {
    const parts = displays.map(
      (d) => `${d.width}x${d.height}:${d.devicePixelRatio}`,
    );
    return parts.join('|');
  }

  /**
   * 判断布局方案是否与当前显示器配置兼容
   *
   * @param layout - 布局方案
   * @param currentFingerprint - 当前配置指纹
   * @returns 是否兼容
   */
  isLayoutCompatible(
    layout: LayoutPlan,
    currentFingerprint?: string,
  ): boolean {
    const fp = currentFingerprint || this.detectDisplayConfiguration().fingerprint;
    return layout.displayFingerprint === fp;
  }

  // ═══════════════════════════════════════════
  // 窗口快照
  // ═══════════════════════════════════════════

  /**
   * 从当前窗口列表创建快照
   *
   * @param windows - 当前窗口实例列表
   * @returns 窗口快照列表
   */
  createWindowSnapshots(
    windows: ServiceWindow[],
  ): WindowSnapshot[] {
    const displayConfig = this.detectDisplayConfiguration();
    const primaryDisplay = displayConfig.displays[0];

    return windows
      .filter((w) => w.state !== 'closed' && w.state !== 'closing')
      .map((w) => ({
        windowId: w.id,
        serviceId: w.serviceId,
        title: w.title || '',
        state: w.state as Exclude<WindowState, 'closed' | 'closing'>,
        position: { ...w.position },
        size: {
          width:
            typeof w.size.width === 'number'
              ? w.size.width
              : parseInt(String(w.size.width), 10) || 800,
          height:
            typeof w.size.height === 'number'
              ? w.size.height
              : parseInt(String(w.size.height), 10) || 600,
        },
        zIndex: w.zIndex,
        displayId: primaryDisplay?.id || 'unknown',
        data: w.data ? { ...w.data } : undefined,
      }));
  }

  /**
   * 在当前显示器配置下调整窗口位置（防止溢出）
   *
   * @param snapshots - 窗口快照
   * @param displayConfig - 显示器配置
   */
  clampWindowPositions(
    snapshots: WindowSnapshot[],
    displayConfig?: DisplayConfiguration,
  ): WindowSnapshot[] {
    const config = displayConfig || this.detectDisplayConfiguration();
    const bounds = config.totalBounds;

    return snapshots.map((snapshot) => {
      const clampedPosition = { ...snapshot.position };
      const clampedSize = { ...snapshot.size };

      // 确保窗口不完全超出可视区域
      const minVisible = 80; // 至少保留 80px 可见

      if (clampedPosition.x + minVisible > bounds.right) {
        clampedPosition.x = Math.max(0, bounds.right - minVisible);
      }
      if (clampedPosition.y + minVisible > bounds.bottom) {
        clampedPosition.y = Math.max(0, bounds.bottom - minVisible);
      }
      if (clampedPosition.x + clampedSize.width < bounds.left + minVisible) {
        clampedPosition.x = bounds.left;
      }
      if (clampedPosition.y + clampedSize.height < bounds.top + minVisible) {
        clampedPosition.y = bounds.top;
      }

      // 确保窗口在最左和最上方
      clampedPosition.x = Math.max(bounds.left, clampedPosition.x);
      clampedPosition.y = Math.max(bounds.top, clampedPosition.y);

      // 确保尺寸不超出屏幕
      clampedSize.width = Math.min(clampedSize.width, bounds.right - bounds.left);
      clampedSize.height = Math.min(clampedSize.height, bounds.bottom - bounds.top);

      return {
        ...snapshot,
        position: clampedPosition,
        size: clampedSize,
      };
    });
  }

  // ═══════════════════════════════════════════
  // 布局方案 CRUD
  // ═══════════════════════════════════════════

  /**
   * 保存当前布局为方案
   *
   * @param name - 方案名称
   * @param windows - 当前窗口列表
   * @param options - 可选参数
   */
  async saveLayout(
    name: string,
    windows: ServiceWindow[],
    options?: {
      description?: string;
      tags?: string[];
      setActive?: boolean;
    },
  ): Promise<LayoutActionResult> {
    const displayConfig = this.detectDisplayConfiguration();
    const snapshots = this.createWindowSnapshots(windows);

    const request: SaveLayoutRequest = {
      name,
      description: options?.description,
      windows: snapshots.map((s) => ({
        windowId: s.windowId,
        serviceId: s.serviceId,
        title: s.title,
        state: s.state,
        position: s.position,
        size: s.size,
        zIndex: s.zIndex,
        data: s.data,
      })),
      displayConfiguration: displayConfig,
      tags: options?.tags,
    };

    // 尝试保存到后端
    const result = await layoutApi.saveLayout(request);

    if (result.success && result.layout) {
      // 后端保存成功，更新本地缓存
      this.updateLocalCache(result.layout.id, result.layout);
      this.notifyListeners('saved', result.layout);

      if (options?.setActive) {
        this.setLastActive(result.layout.id);
      }
    } else {
      // 降级：保存到本地存储
      logger.warn('后端保存失败，降级到本地存储');
      const localLayout = this.createLocalLayout(name, request);
      this.updateLocalCache(localLayout.id, localLayout);
      return {
        success: true,
        layout: localLayout,
        message: '已保存到本地存储（离线模式）',
      };
    }

    return result;
  }

  /**
   * 获取所有布局方案
   */
  async listLayouts(): Promise<LayoutListResponse> {
    // 尝试从后端获取
    const backendResult = await layoutApi.listLayouts();

    // 合并本地缓存（可能包含离线创建的布局）
    const localLayouts = this.getLocalCache();
    const allLayouts = [...backendResult.layouts];

    for (const local of localLayouts) {
      if (!allLayouts.find((l) => l.id === local.id)) {
        allLayouts.push(local);
      }
    }

    return {
      layouts: allLayouts,
      total: allLayouts.length,
      activeLayoutId:
        backendResult.activeLayoutId || this.getLastActive(),
    };
  }

  /**
   * 删除布局方案
   *
   * @param layoutId - 布局 ID
   */
  async deleteLayout(layoutId: string): Promise<LayoutActionResult> {
    // 尝试从后端删除
    const result = await layoutApi.deleteLayout(layoutId);

    // 同时从本地缓存删除
    this.removeLocalCache(layoutId);
    this.notifyListeners('deleted', { id: layoutId } as LayoutPlan);

    return result;
  }

  /**
   * 激活布局方案（应用到当前窗口）
   *
   * @param layoutId - 布局 ID
   * @returns 窗口快照列表（供 windowManager 恢复）
   */
  async activateLayout(
    layoutId: string,
  ): Promise<{ success: boolean; snapshots: WindowSnapshot[]; message?: string }> {
    // 尝试后端激活
    try {
      await layoutApi.activateLayout(layoutId);
    } catch {
      // 后端激活失败不影响本地恢复
      logger.warn('后端激活记录失败，继续本地恢复');
    }

    // 从本地缓存或列表获取布局详情
    const layouts = await this.listLayouts();
    const layout = layouts.layouts.find((l) => l.id === layoutId);
    const localCache = this.getLocalCache().find((l) => l.id === layoutId);

    const target = layout || localCache;
    if (!target) {
      return { success: false, snapshots: [], message: '布局方案不存在' };
    }

    const currentFingerprint = this.detectDisplayConfiguration().fingerprint;
    const isCompatible = this.isLayoutCompatible(target, currentFingerprint);

    // 调整窗口位置到当前显示器
    const clampedSnapshots = this.clampWindowPositions(target.windows);

    this.setLastActive(layoutId);

    return {
      success: true,
      snapshots: clampedSnapshots,
      message: isCompatible ? '布局已恢复' : '布局已恢复（已适配当前显示器）',
    };
  }

  // ═══════════════════════════════════════════
  // 导入/导出
  // ═══════════════════════════════════════════

  /**
   * 导出所有布局方案为 JSON 文件
   *
   * @returns Base64 编码的布局数据（用于下载）
   */
  async exportLayouts(): Promise<{
    success: boolean;
    data?: LayoutExport;
    json?: string;
    blobs?: Array<{ filename: string; content: string }>;
  }> {
    const layouts = await this.listLayouts();

    const exportData: LayoutExport = {
      formatVersion: 1,
      exportedAt: new Date().toISOString(),
      appVersion: '2.1',
      layouts: layouts.layouts,
    };

    const json = JSON.stringify(exportData, null, 2);

    return {
      success: true,
      data: exportData,
      json,
      blobs: [
        {
          filename: `fuxi-layouts-${this.formatDate()}.json`,
          content: json,
        },
      ],
    };
  }

  /**
   * 从 JSON 导入布局方案
   *
   * @param jsonData - 导入的 JSON 字符串
   * @param overwrite - 是否覆盖同名布局
   */
  async importLayouts(
    jsonData: string,
    overwrite: boolean = false,
  ): Promise<LayoutActionResult> {
    try {
      const parsed: LayoutExport = JSON.parse(jsonData);

      if (!parsed.formatVersion || !parsed.layouts) {
        return { success: false, message: '无效的布局文件格式' };
      }

      // 尝试后端导入
      const b64Data = btoa(unescape(encodeURIComponent(jsonData)));
      const backendResult = await layoutApi.importLayouts({
        data: b64Data,
        overwrite,
      });

      if (backendResult.success) {
        this.notifyListeners('imported', backendResult.layout!);
        return backendResult;
      }

      // 降级：逐个添加到本地缓存
      let importedCount = 0;
      for (const layout of parsed.layouts) {
        // 生成新 ID 避免冲突
        if (!overwrite) {
          layout.id = `${layout.id}-imported-${Date.now()}`;
        }
        this.updateLocalCache(layout.id, layout);
        importedCount++;
      }

      return {
        success: true,
        message: `成功导入 ${importedCount} 个布局方案（离线模式）`,
      };
    } catch (err) {
      logger.error('导入布局失败', err);
      return { success: false, message: '布局文件解析失败' };
    }
  }

  /**
   * 创建空白布局模板
   *
   * @returns 默认布局模板
   */
  createDefaultLayout(): Omit<SaveLayoutRequest, 'windows'> {
    return {
      name: '默认布局',
      description: '伏羲 v2.1 默认窗口布局',
      displayConfiguration: this.detectDisplayConfiguration(),
      tags: ['默认'],
    };
  }

  // ═══════════════════════════════════════════
  // 事件监听
  // ═══════════════════════════════════════════

  /**
   * 注册变更监听器
   *
   * @param listener - 事件处理函数
   * @returns 取消订阅的函数
   */
  onChange(
    listener: (event: { action: string; layout: LayoutPlan }) => void,
  ): () => void {
    this.listeners.push(listener);
    return () => {
      const idx = this.listeners.indexOf(listener);
      if (idx > -1) this.listeners.splice(idx, 1);
    };
  }

  private notifyListeners(action: string, layout: LayoutPlan): void {
    for (const listener of this.listeners) {
      try {
        listener({ action, layout });
      } catch (err) {
        logger.error('Listener 执行异常', err);
      }
    }
  }

  // ═══════════════════════════════════════════
  // 私有辅助方法
  // ═══════════════════════════════════════════

  /**
   * 获取本地缓存的布局列表
   */
  private getLocalCache(): LayoutPlan[] {
    try {
      const cached = localStorage.getItem(LOCAL_CACHE_KEY);
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  }

  /**
   * 更新本地缓存
   */
  private updateLocalCache(layoutId: string, layout: LayoutPlan): void {
    const cached = this.getLocalCache();
    const idx = cached.findIndex((l) => l.id === layoutId);

    if (idx >= 0) {
      cached[idx] = layout;
    } else {
      cached.unshift(layout);
      // 限制最大数量
      if (cached.length > MAX_LOCAL_CACHE) {
        cached.pop();
      }
    }

    localStorage.setItem(LOCAL_CACHE_KEY, JSON.stringify(cached));
  }

  /**
   * 从本地缓存删除
   */
  private removeLocalCache(layoutId: string): void {
    const cached = this.getLocalCache().filter((l) => l.id !== layoutId);
    localStorage.setItem(LOCAL_CACHE_KEY, JSON.stringify(cached));
  }

  /**
   * 设置最后激活的布局
   */
  private setLastActive(layoutId: string): void {
    localStorage.setItem(LAST_ACTIVE_KEY, layoutId);
  }

  /**
   * 获取最后激活的布局
   */
  private getLastActive(): string | null {
    return localStorage.getItem(LAST_ACTIVE_KEY);
  }

  /**
   * 创建本地布局（降级方案）
   */
  private createLocalLayout(
    name: string,
    data: SaveLayoutRequest,
  ): LayoutPlan {
    const displayConfig = data.displayConfiguration;
    return {
      id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      name,
      description: data.description,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      displayFingerprint: displayConfig.fingerprint,
      displayConfiguration: displayConfig,
      windows: data.windows.map((w) => ({
        ...w,
        displayId: displayConfig.displays[0]?.id || 'unknown',
        state: w.state || 'normal',
      })),
      isActive: false,
      isDefault: false,
      tags: data.tags,
      version: 1,
    };
  }

  /**
   * 格式化日期（用于导出文件名）
   */
  private formatDate(): string {
    const d = new Date();
    const pad = (n: number): string => String(n).padStart(2, '0');
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
  }
}

// ═══════════════════════════════════════════
// 单例导出
// ═══════════════════════════════════════════

export const layoutService = new LayoutService();
export default layoutService;
