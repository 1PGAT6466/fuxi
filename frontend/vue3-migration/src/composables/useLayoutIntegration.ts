/**
 * 伏羲 v2.1 — 布局管理器集成 Composable
 *
 * 连接 LayoutService/Store 与 WindowManager，
 * 提供窗口快照的恢复功能。
 *
 * 用法：
 *   const { applyLayoutSnapshots, autoSaveOnClose } = useLayoutIntegration();
 *   // 在 MainLayout 中监听 apply-snapshots 事件
 *   // 在窗口关闭时调用 autoSaveOnClose
 */

import { onMounted, onUnmounted, watch } from 'vue';
import { useLayoutStore } from '@/stores/layout';
import { useWindowManager } from '@/stores/windowManager';
import layoutService from '@/services/layout-store/LayoutService';
import type { WindowSnapshot, WindowState } from '@/types/layout';
import type { ServiceWindow } from '@/types/service-manifest';
import { serviceRegistry } from '@/services/_registry';
import { createLogger } from '@/utils/logger';

const logger = createLogger('LayoutIntegration');

/**
 * 布局集成 Hook
 */
export function useLayoutIntegration() {
  const layoutStore = useLayoutStore();
  const windowManager = useWindowManager();

  /**
   * 应用布局快照到当前窗口管理器
   *
   * 行为：
   * 1. 关闭所有现有窗口
   * 2. 根据快照重新打开窗口并设置位置/大小
   *
   * @param snapshots - 窗口快照列表
   */
  async function applyLayoutSnapshots(snapshots: WindowSnapshot[]): Promise<void> {
    logger.info(`应用布局快照: ${snapshots.length} 个窗口`);

    // 关闭所有现有窗口
    const currentWindows = [...windowManager.windows].filter(
      (w) => w.state !== 'closed' && w.state !== 'closing',
    );
    for (const win of currentWindows) {
      windowManager.close(win.id);
    }

    // 等待关闭动画完成
    await new Promise((resolve) => setTimeout(resolve, 400));

    // 按 zIndex 升序打开窗口（保留层级）
    const sortedSnapshots = [...snapshots].sort((a, b) => a.zIndex - b.zIndex);

    for (const snapshot of sortedSnapshots) {
      // 获取服务清单
      const manifest = serviceRegistry.getById(snapshot.serviceId);
      if (!manifest) {
        logger.warn(`快照中的服务 "${snapshot.serviceId}" 未注册，已跳过`);
        continue;
      }

      // 打开窗口
      const win = windowManager.open(manifest, snapshot.data);

      // 设置窗口位置和尺寸
      if (snapshot.state !== 'maximized') {
        windowManager.move(win.id, snapshot.position.x, snapshot.position.y);
        windowManager.resize(win.id, snapshot.size.width, snapshot.size.height);
      }

      // 设置窗口状态
      if (snapshot.state === 'maximized') {
        windowManager.toggleMaximize(win.id);
      } else if (snapshot.state === 'minimized') {
        windowManager.minimize(win.id);
      }
    }

    logger.info('布局恢复完成');
  }

  /**
   * 窗口关闭时自动保存当前布局
   *
   * 实现"最后状态记忆"：每次窗口变化时自动暂存最近状态
   */
  function autoSaveOnClose(closedWindowId: string): void {
    // 延迟保存，确保窗口状态已更新
    setTimeout(() => {
      const currentWindows = windowManager.windows.filter(
        (w) => w.state !== 'closed' && w.state !== 'closing' && w.id !== closedWindowId,
      );
      if (currentWindows.length > 0) {
        // 保存到 localStorage 作为"最近状态"
        const snapshots = layoutService.createWindowSnapshots(currentWindows);
        try {
          localStorage.setItem('fuxi-recent-layout', JSON.stringify(snapshots));
        } catch {
          // localStorage 满时忽略
        }
      }
    }, 100);
  }

  /**
   * 自动恢复上次会话的布局
   *
   * 在应用首次加载时调用，恢复上次关闭前的窗口状态
   */
  async function autoRestoreLastSession(): Promise<void> {
    try {
      const cached = localStorage.getItem('fuxi-recent-layout');
      if (!cached) return;

      const snapshots: WindowSnapshot[] = JSON.parse(cached);

      // 只在无活跃窗口时自动恢复
      const activeWindows = windowManager.windows.filter(
        (w) => w.state !== 'closed' && w.state !== 'closing',
      );
      if (activeWindows.length > 0) return;

      // 检查用户是否有手动保存的布局，优先使用
      const lastActive = localStorage.getItem('fuxi-last-active-layout');
      if (lastActive) {
        const result = await layoutStore.activateLayout(lastActive);
        if (result.success && result.snapshots.length > 0) {
          await applyLayoutSnapshots(result.snapshots);
          return;
        }
      }

      // 降级：使用最近状态
      if (snapshots.length > 0) {
        await applyLayoutSnapshots(snapshots);
        logger.info('已恢复上次会话窗口布局');
      }
    } catch (err) {
      logger.warn('恢复上次会话布局失败', err);
    }
  }

  /**
   * 监听显示器变化（窗口尺寸变化、设备像素比变化）
   */
  function watchDisplayChanges(): void {
    const handleResize = () => {
      layoutStore.refreshDisplayConfiguration();
    };

    // 监听窗口 resize（防抖）
    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    const debouncedResize = () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(handleResize, 500);
    };

    window.addEventListener('resize', debouncedResize);

    // matchMedia 检测设备像素比变化（更灵敏）
    const mediaQuery = window.matchMedia(
      `(resolution: ${window.devicePixelRatio}dppx)`,
    );
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', debouncedResize);
    }

    onUnmounted(() => {
      window.removeEventListener('resize', debouncedResize);
      if (resizeTimer) clearTimeout(resizeTimer);
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', debouncedResize);
      }
    });
  }

  return {
    applyLayoutSnapshots,
    autoSaveOnClose,
    autoRestoreLastSession,
    watchDisplayChanges,
  };
}
