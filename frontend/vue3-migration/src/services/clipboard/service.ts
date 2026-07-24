/**
 * 伏羲 v2.1 — 剪贴板服务 (ClipboardService)
 *
 * 核心剪贴板引擎，负责：
 * 1. 系统级剪贴板集成（通过 navigator.clipboard API）
 * 2. 跨窗口复制粘贴（通过 LocalStorage + BroadcastChannel 广播）
 * 3. 历史记录管理（本地缓存 + 后端持久化）
 * 4. 格式转换（文本 ↔ HTML ↔ JSON）
 *
 * 架构：
 * ┌─────────────────────────────────────────┐
 * │  ClipboardService (单例)                 │
 * │  ├─ SystemClipboard (navigator.clipboard)│
 * │  ├─ HistoryManager (LRU 缓存)            │
 * │  ├─ FormatConverter (格式转换器链)        │
 * │  └─ CrossWindowSync (BroadcastChannel)   │
 * └─────────────────────────────────────────┘
 */

import type {
  ClipboardEntry,
  ClipboardContentFormat,
  FormatConverter,
  ClipboardChangedEvent,
  ClipboardSyncRequest,
} from './types';
import { CLIPBOARD_MIME_MAP, DEFAULT_CLIPBOARD_CONFIG } from './types';
import type { ClipboardPanelConfig } from './types';
import * as clipboardApi from '@/api/clipboard';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ClipboardService');

// ═══════════════════════════════════════════
// 单例服务类
// ═══════════════════════════════════════════

export class ClipboardService {
  // ── 配置 ──
  private config: ClipboardPanelConfig;

  // ── 历史记录（LRU 内存缓存） ──
  private history: ClipboardEntry[] = [];

  // ── 收藏条目 ──
  private favorites: Set<string> = new Set();

  // ── 格式转换器注册表 ──
  private converters: FormatConverter[] = [];

  // ── BroadcastChannel（跨窗口通信） ──
  private bc: BroadcastChannel | null = null;

  // ── 事件监听器 ──
  private listeners: Set<(event: ClipboardChangedEvent) => void> = new Set();

  // ── 系统剪贴轮询 ──
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private lastClipboardText = '';

  // ── 窗口 ID ──
  private windowId: string;

  // ── 是否已初始化 ──
  private initialized = false;

  constructor(windowId: string, config?: Partial<ClipboardPanelConfig>) {
    this.windowId = windowId;
    this.config = { ...DEFAULT_CLIPBOARD_CONFIG, ...config };

    // 注册内置格式转换器
    this.registerBuiltinConverters();

    // 注册 BroadcastChannel
    this.setupBroadcastChannel();
  }

  // ═══════════════════════════════════════════
  // 初始化 & 清理
  // ═══════════════════════════════════════════

  /** 初始化剪贴板服务 */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    // 从后端加载历史
    await this.loadHistoryFromServer();

    // 启动系统剪贴板轮询
    this.startClipboardPolling();

    this.initialized = true;
    logger.info('剪贴板服务已初始化', { windowId: this.windowId });
  }

  /** 销毁剪贴板服务 */
  destroy(): void {
    this.stopClipboardPolling();
    this.bc?.close();
    this.bc = null;
    this.listeners.clear();
    this.initialized = false;
    logger.info('剪贴板服务已销毁');
  }

  // ═══════════════════════════════════════════
  // 系统剪贴板集成
  // ═══════════════════════════════════════════

  /**
   * 从系统剪贴板读取内容
   *
   * @returns 剪贴板文本内容，或 null（读取失败或无权限）
   */
  async readSystemClipboard(): Promise<string | null> {
    try {
      if (!navigator.clipboard?.readText) {
        logger.debug('系统剪贴板 API 不可用');
        return null;
      }

      const text = await navigator.clipboard.readText();
      return text || null;
    } catch (err) {
      // 安全上下文下可能没有 clipboard-read 权限
      if ((err as Error).name === 'NotAllowedError') {
        logger.debug('剪贴板读取权限未授予');
      } else {
        logger.error('读取系统剪贴板失败', err);
      }
      return null;
    }
  }

  /**
   * 写入内容到系统剪贴板
   *
   * @param text - 要写入的文本内容
   * @returns 是否写入成功
   */
  async writeSystemClipboard(text: string): Promise<boolean> {
    try {
      if (!navigator.clipboard?.writeText) {
        logger.warn('系统剪贴板 API 不可用，使用 fallback');
        return this.writeClipboardFallback(text);
      }

      await navigator.clipboard.writeText(text);
      logger.debug('已写入系统剪贴板');
      return true;
    } catch (err) {
      logger.error('写入系统剪贴板失败', err);
      // fallback: 使用 execCommand
      return this.writeClipboardFallback(text);
    }
  }

  /**
   * 剪贴板 fallback：使用 document.execCommand
   */
  private writeClipboardFallback(text: string): boolean {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const success = document.execCommand('copy');
      document.body.removeChild(textarea);

      if (success) {
        logger.debug('已写入系统剪贴板 (fallback)');
      }
      return success;
    } catch (err) {
      logger.error('剪贴板 fallback 失败', err);
      return false;
    }
  }

  // ═══════════════════════════════════════════
  // 系统剪贴板轮询（检测外部复制操作）
  // ═══════════════════════════════════════════

  /** 启动系统剪贴板轮询 */
  private startClipboardPolling(): void {
    if (this.pollTimer) return;
    // 每 750ms 检测一次剪贴板变化
    this.pollTimer = setInterval(async () => {
      if (document.hidden) return; // 页面不可见时跳过
      const text = await this.readSystemClipboard();
      if (text && text !== this.lastClipboardText) {
        this.lastClipboardText = text;
        // 自动添加到历史
        this.addToHistory({
          format: 'text',
          plainText: text,
          sourceService: 'system',
        });
      }
    }, 750);
    logger.debug('系统剪贴板轮询已启动');
  }

  /** 停止系统剪贴板轮询 */
  private stopClipboardPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
      logger.debug('系统剪贴板轮询已停止');
    }
  }

  // ═══════════════════════════════════════════
  // 复制 & 粘贴 API
  // ═══════════════════════════════════════════

  /**
   * 复制内容到剪贴板
   *
   * 流程：
   * 1. 写入系统剪贴板
   * 2. 添加到本地历史
   * 3. 同步到 Backend（跨窗口）
   * 4. 通过 BroadcastChannel 通知同源窗口
   *
   * @param content - 文本内容
   * @param format - 内容格式（默认 text）
   * @param metadata - 附加元数据
   */
  async copy(
    content: string,
    format: ClipboardContentFormat = 'text',
    metadata?: Record<string, unknown>,
  ): Promise<ClipboardEntry | null> {
    // 1. 写入系统剪贴板
    const writeSuccess = await this.writeSystemClipboard(content);
    if (!writeSuccess) {
      logger.warn('写入系统剪贴板失败，但继续本地记录');
    }

    // 2. 添加到本地历史
    const entry = this.addToHistory({ format, plainText: content, metadata });

    // 3. 同步到后端
    if (this.config.enableCrossWindowSync) {
      this.syncToServer(entry).catch((err) => {
        logger.debug('后端同步失败，本地记录已保留', err);
      });
    }

    // 4. 广播到其他窗口
    this.broadcastToWindows({
      action: 'copied',
      entry,
    });

    // 更新内部轮询缓存，避免重复读取
    this.lastClipboardText = content;

    logger.info('复制成功', { entryId: entry.id, format, length: content.length });
    return entry;
  }

  /**
   * 粘贴剪贴板内容
   *
   * @param entryId - 可选：粘贴指定历史条目，不传则粘贴最新
   * @returns 明文内容
   */
  async paste(entryId?: string): Promise<string | null> {
    let entry: ClipboardEntry | undefined;

    if (entryId) {
      entry = this.history.find((e) => e.id === entryId);
    } else {
      // 取最新的条目
      entry = this.history[0];
    }

    if (!entry) {
      logger.warn('剪贴板为空，无内容可粘贴');
      return null;
    }

    // 写入系统剪贴板（让其他应用也可访问）
    await this.writeSystemClipboard(entry.plainText);

    // 触发粘贴事件
    this.broadcastToWindows({
      action: 'pasted',
      entry,
    });

    logger.info('粘贴成功', { entryId: entry.id });
    return entry.plainText;
  }

  // ═══════════════════════════════════════════
  // 历史记录管理
  // ═══════════════════════════════════════════

  /**
   * 添加条目到本地历史（LRU）
   */
  private addToHistory(
    data: Omit<ClipboardEntry, 'id' | 'createdAt' | 'isFavorite'> & {
      metadata?: Record<string, unknown>;
    },
  ): ClipboardEntry {
    const entry: ClipboardEntry = {
      id: this.generateEntryId(),
      format: data.format,
      plainText: data.plainText,
      formattedContent: data.formattedContent,
      referencePath: data.referencePath,
      sourceWindowId: data.sourceWindowId || this.windowId,
      sourceService: data.sourceService,
      isFavorite: false,
      createdAt: new Date().toISOString(),
      size: new Blob([data.plainText]).size,
      metadata: data.metadata,
    };

    // 去重：如果最近 5 秒内有相同内容，不重复添加
    const recentDuplicate = this.history.find(
      (e) =>
        e.plainText === entry.plainText &&
        Date.now() - new Date(e.createdAt).getTime() < 5000,
    );
    if (recentDuplicate) {
      // 更新已有条目的时间（相当于提到最前）
      this.history = [recentDuplicate, ...this.history.filter((e) => e.id !== recentDuplicate.id)];
      return recentDuplicate;
    }

    // 插入到最前面
    this.history.unshift(entry);

    // LRU 裁剪
    if (this.history.length > this.config.maxHistorySize) {
      const removed = this.history.splice(this.config.maxHistorySize);
      logger.debug(`LRU 裁剪: 移除了 ${removed.length} 条旧记录`);
    }

    return entry;
  }

  /** 获取历史列表 */
  getHistory(): ClipboardEntry[] {
    return [...this.history];
  }

  /** 获取收藏列表 */
  getFavorites(): ClipboardEntry[] {
    return this.history.filter((e) => e.isFavorite);
  }

  /** 删除单条历史 */
  deleteEntry(entryId: string): boolean {
    const idx = this.history.findIndex((e) => e.id === entryId);
    if (idx === -1) return false;

    const entry = this.history[idx];
    this.history.splice(idx, 1);

    // 同时取消收藏
    this.favorites.delete(entryId);

    // 异步通知后端
    clipboardApi.deleteClipboardEntry(entryId).catch((err) => {
      logger.debug('后端删除条目失败，本地已移除', err);
    });

    // 广播
    this.broadcastToWindows({
      action: 'removed',
      entry,
    });

    logger.info('已删除剪贴板条目', { entryId });
    return true;
  }

  /** 批量删除历史 */
  deleteEntries(entryIds: string[]): number {
    let count = 0;
    for (const id of entryIds) {
      if (this.deleteEntry(id)) count++;
    }
    return count;
  }

  /** 清空历史 */
  clearHistory(): void {
    const count = this.history.length;
    this.history = [];
    this.favorites.clear();

    // 异步通知后端
    clipboardApi.clearClipboardHistory().catch((err) => {
      logger.debug('后端清空历史失败', err);
    });

    // 广播
    this.broadcastToWindows({
      action: 'cleared',
    });

    logger.info(`已清空剪贴板历史 (${count} 条)`);
  }

  // ═══════════════════════════════════════════
  // 收藏管理
  // ═══════════════════════════════════════════

  /** 切换收藏状态 */
  toggleFavorite(entryId: string): boolean {
    const entry = this.history.find((e) => e.id === entryId);
    if (!entry) return false;

    entry.isFavorite = !entry.isFavorite;

    if (entry.isFavorite) {
      this.favorites.add(entryId);
    } else {
      this.favorites.delete(entryId);
    }

    // 异步同步到后端
    clipboardApi.toggleClipboardFavorite(entryId, entry.isFavorite).catch((err) => {
      logger.debug('后端同步收藏状态失败', err);
    });

    // 广播
    this.broadcastToWindows({
      action: entry.isFavorite ? 'favorited' : 'unfavorited',
      entry,
    });

    logger.info(`已${entry.isFavorite ? '收藏' : '取消收藏'}剪贴板条目`, { entryId });
    return entry.isFavorite;
  }

  /** 检查条目是否收藏 */
  isFavorite(entryId: string): boolean {
    return this.favorites.has(entryId);
  }

  // ═══════════════════════════════════════════
  // 跨窗口同步
  // ═══════════════════════════════════════════

  /** 设置 BroadcastChannel 用于跨窗口通信 */
  private setupBroadcastChannel(): void {
    if (!this.config.enableCrossWindowSync) return;

    try {
      this.bc = new BroadcastChannel('fuxi-clipboard');
      this.bc.onmessage = (event: MessageEvent) => {
        const { action, entry } = event.data as {
          action: string;
          entry?: ClipboardEntry;
        };

        // 忽略自己发出的消息
        if (entry?.sourceWindowId === this.windowId) return;

        switch (action) {
          case 'copied':
            if (entry) {
              this.history.unshift(entry);
              this.notifyListeners({ action: 'synced', entry, sourceWindowId: entry.sourceWindowId });
              logger.debug('收到跨窗口复制', { from: entry.sourceWindowId });
            }
            break;
          case 'removed':
            if (entry) {
              this.history = this.history.filter((e) => e.id !== entry.id);
              this.notifyListeners({ action: 'removed', entry });
            }
            break;
          case 'cleared':
            this.history = [];
            this.favorites.clear();
            this.notifyListeners({ action: 'cleared' });
            break;
          default:
            break;
        }
      };
      logger.debug('BroadcastChannel 已设置');
    } catch (err) {
      logger.warn('BroadcastChannel 不可用，跨窗口同步已降级', err);
      this.bc = null;
    }
  }

  /** 广播事件到其他窗口 */
  private broadcastToWindows(event: ClipboardChangedEvent): void {
    if (this.bc && this.config.enableCrossWindowSync) {
      try {
        this.bc.postMessage(event);
      } catch (err) {
        logger.debug('Broadcast 失败', err);
      }
    }
    this.notifyListeners(event);
  }

  /**
   * 同步到后端服务
   */
  private async syncToServer(entry: ClipboardEntry): Promise<void> {
    const request: ClipboardSyncRequest = {
      windowId: this.windowId,
      serviceName: entry.sourceService,
      entry: {
        format: entry.format,
        plainText: entry.plainText,
        formattedContent: entry.formattedContent,
        referencePath: entry.referencePath,
        sourceWindowId: this.windowId,
        sourceService: entry.sourceService,
        size: entry.size,
        metadata: entry.metadata,
      },
    };

    await clipboardApi.syncClipboard(request);
  }

  /**
   * 从后端加载历史记录
   */
  private async loadHistoryFromServer(): Promise<void> {
    try {
      const response = await clipboardApi.getClipboardHistory({ limit: this.config.maxHistorySize });
      if (response.entries?.length) {
        this.history = response.entries;
        // 重建收藏集
        this.favorites = new Set(
          response.entries.filter((e) => e.isFavorite).map((e) => e.id),
        );
        logger.info(`从后端加载了 ${response.entries.length} 条剪贴板历史`);
      }
    } catch (err) {
      // 后端不可用时，仅使用本地缓存
      logger.debug('从后端加载剪贴板历史失败，使用本地缓存', err);
    }
  }

  // ═══════════════════════════════════════════
  // 格式转换
  // ═══════════════════════════════════════════

  /** 注册内置格式转换器 */
  private registerBuiltinConverters(): void {
    // text → HTML
    this.registerConverter({
      from: 'text',
      to: 'html',
      priority: 1,
      convert: (content: string) => {
        return content
          .split('\n')
          .map((line) => `<p>${this.escapeHtml(line.trim())}</p>`)
          .join('\n');
      },
    });

    // HTML → text
    this.registerConverter({
      from: 'html',
      to: 'text',
      priority: 1,
      convert: (content: string) => {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = content;
        return tempDiv.textContent || tempDiv.innerText || content;
      },
    });

    // text → JSON（尝试解析）
    this.registerConverter({
      from: 'text',
      to: 'json',
      priority: 1,
      convert: (content: string) => {
        try {
          const parsed = JSON.parse(content);
          return JSON.stringify(parsed, null, 2);
        } catch {
          return JSON.stringify({ text: content });
        }
      },
    });

    // JSON → text
    this.registerConverter({
      from: 'json',
      to: 'text',
      priority: 1,
      convert: (content: string) => {
        try {
          return JSON.parse(content);
        } catch {
          return content;
        }
      },
    });
  }

  /** 注册自定义格式转换器 */
  registerConverter(converter: FormatConverter): void {
    this.converters.push(converter);
    // 按优先级排序
    this.converters.sort((a, b) => a.priority - b.priority);
    logger.debug(`已注册格式转换器: ${converter.from} → ${converter.to}`);
  }

  /**
   * 转换内容格式
   *
   * @param content - 原始内容
   * @param from - 来源格式
   * @param to - 目标格式
   * @returns 转换后的内容
   */
  convertFormat(
    content: string,
    from: ClipboardContentFormat,
    to: ClipboardContentFormat,
  ): string {
    if (from === to) return content;

    const converter = this.converters.find((c) => c.from === from && c.to === to);
    if (converter) {
      try {
        return converter.convert(content);
      } catch (err) {
        logger.error(`格式转换失败: ${from} → ${to}`, err);
      }
    }

    // 如果找不到直接转换器，尝试链式转换
    // 目前简单回退：返回原文
    logger.debug(`未找到 ${from} → ${to} 的转换器，返回原文`);
    return content;
  }

  /** 获取已注册的转换器列表 */
  getConverters(): FormatConverter[] {
    return [...this.converters];
  }

  // ═══════════════════════════════════════════
  // 事件系统
  // ═══════════════════════════════════════════

  /** 监听剪贴板变更事件 */
  on(event: 'change', listener: (event: ClipboardChangedEvent) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** 通知所有监听器 */
  private notifyListeners(event: ClipboardChangedEvent): void {
    this.listeners.forEach((listener) => {
      try {
        listener(event);
      } catch (err) {
        logger.error('剪贴板事件监听器异常', err);
      }
    });
  }

  // ═══════════════════════════════════════════
  // 工具方法
  // ═══════════════════════════════════════════

  /** 生成唯一条目 ID */
  private generateEntryId(): string {
    return `clip-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  }

  /** HTML 转义 */
  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /** 获取服务实例状态 */
  getStatus(): { initialized: boolean; historyCount: number; favoritesCount: number } {
    return {
      initialized: this.initialized,
      historyCount: this.history.length,
      favoritesCount: this.favorites.size,
    };
  }

  /** 搜索历史记录 */
  searchHistory(query: string): ClipboardEntry[] {
    const q = query.trim().toLowerCase();
    if (!q) return this.getHistory();

    return this.history.filter(
      (entry) =>
        entry.plainText.toLowerCase().includes(q) ||
        entry.formattedContent?.toLowerCase().includes(q) ||
        entry.sourceService?.toLowerCase().includes(q),
    );
  }
}

// ═══════════════════════════════════════════
// 全局单例管理
// ═══════════════════════════════════════════

let globalService: ClipboardService | null = null;

/**
 * 获取全局剪贴板服务单例
 *
 * @param windowId - 窗口标识符
 * @param config - 可选配置
 * @returns ClipboardService 实例
 */
export function getClipboardService(
  windowId: string,
  config?: Partial<ClipboardPanelConfig>,
): ClipboardService {
  if (!globalService) {
    globalService = new ClipboardService(windowId, config);
  }
  return globalService;
}

/**
 * 销毁全局剪贴板服务
 */
export function destroyClipboardService(): void {
  if (globalService) {
    globalService.destroy();
    globalService = null;
  }
}
