/**
 * 伏羲 v2.1 — 窗口管理器 (Pinia Store)
 *
 * 功能：
 * - 管理所有服务窗口实例的生命周期
 * - 支持 open/focus/minimize/toggleMaximize/close/move/resize
 * - 支持布局模式：free / tiled / split
 * - singleton 检查 + zIndex 递增 + 关闭延迟删除
 */

import { defineStore } from 'pinia';
import { ref, shallowRef, computed } from 'vue';
import type {
  ServiceManifest,
  ServiceWindow,
  WindowState,
  WindowLayout,
  LayoutMode,
} from '@/types/service-manifest';

// ============================
// 辅助函数
// ============================

/** 生成唯一窗口 ID */
function generateWindowId(): string {
  return `window-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** 计算默认窗口位置（层叠偏移） */
function calculateNextPosition(windows: ServiceWindow[]): { x: number; y: number } {
  const BASE_X = 80;
  const BASE_Y = 40;
  const OFFSET = 30;
  const MAX_OFFSET = 5;

  // 按 zIndex 排序，找到最后一个正常窗口
  const normalWindows = windows
    .filter((w) => w.state !== 'closed' && w.state !== 'minimized')
    .sort((a, b) => a.zIndex - b.zIndex);

  const offsetIndex = Math.min(normalWindows.length, MAX_OFFSET);
  return {
    x: BASE_X + offsetIndex * OFFSET,
    y: BASE_Y + offsetIndex * OFFSET,
  };
}

// ============================
// Store 定义
// ============================

export const useWindowManager = defineStore('windowManager', () => {
  // ========== State ==========

  /** 所有窗口实例 - P0-4: 大数组改用 shallowRef */
  const windows = shallowRef<ServiceWindow[]>([]);

  /** 当前活跃（聚焦）窗口 ID */
  const activeWindowId = ref<string | null>(null);

  /** 下一个 zIndex（每次聚焦/打开递增） */
  const nextZIndex = ref<number>(100);

  /** 窗口布局配置 */
  const layout = ref<WindowLayout>({
    mode: 'free',
  });

  /** 即将关闭的窗口 ID（延迟删除） */
  const closingWindowIds = ref<Set<string>>(new Set());

  // ========== Getters ==========

  /** 当前活跃窗口 */
  const activeWindow = computed<ServiceWindow | null>(() => {
    if (!activeWindowId.value) return null;
    return windows.value.find((w) => w.id === activeWindowId.value) || null;
  });

  /** 可见窗口列表（排除 closed/closing/即将关闭的） */
  const visibleWindows = computed<ServiceWindow[]>(() => {
    return windows.value.filter(
      (w) => w.state !== 'closed' && w.state !== 'closing' && !closingWindowIds.value.has(w.id),
    );
  });

  /** 按服务 ID 分组窗口 */
  const windowsByService = computed<Record<string, ServiceWindow[]>>(() => {
    const map: Record<string, ServiceWindow[]> = {};
    for (const w of windows.value) {
      if (w.state === 'closed' || w.state === 'closing') continue;
      if (!map[w.serviceId]) map[w.serviceId] = [];
      map[w.serviceId].push(w);
    }
    return map;
  });

  // ========== Actions ==========

  /**
   * 打开服务窗口
   *
   * @param service - 服务清单
   * @param context - 可选的上下文数据（路由参数、查询参数等）
   * @returns 打开的窗口实例
   */
  function open(service: ServiceManifest, context?: Record<string, unknown>): ServiceWindow {
    // singleton 检查（排除 closed 和 closing 状态的窗口）
    if (service.singleton) {
      const existing = windows.value.find(
        (w) => w.serviceId === service.id && w.state !== 'closed' && w.state !== 'closing',
      );
      if (existing) {
        // 如果已存在，聚焦该窗口
        focus(existing.id);
        // 恢复最小化的窗口
        if (existing.state === 'minimized') {
          existing.state = 'normal';
        }
        // 更新上下文数据
        if (context) {
          existing.data = { ...existing.data, ...context };
        }
        return existing;
      }
    }

    const pos = calculateNextPosition(windows.value);
    const size = service.defaultSize || { width: 800, height: 600 };

    const window: ServiceWindow = {
      id: generateWindowId(),
      serviceId: service.id,
      title: service.name,
      icon: service.icon,
      state: service.windowMode === 'fullscreen' ? 'maximized' : 'normal',
      zIndex: ++nextZIndex.value,
      size: { ...size },
      position: pos,
      openedAt: Date.now(),
      data: context,
    };

    windows.value = [...windows.value, window];
    focus(window.id);
    return window;
  }

  /**
   * 聚焦窗口（提升 zIndex）
   */
  function focus(id: string): void {
    const window = windows.value.find((w) => w.id === id);
    if (!window || window.state === 'closed') return;
    if (window.state === 'minimized') {
      window.state = 'normal';
    }
    window.zIndex = ++nextZIndex.value;
    activeWindowId.value = id;
  }

  /**
   * 最小化窗口
   */
  function minimize(id: string): void {
    const window = windows.value.find((w) => w.id === id);
    if (!window || window.state === 'closed') return;
    window.state = 'minimized';

    // 如果最小化的是活跃窗口，切换到下一个
    if (activeWindowId.value === id) {
      const next = windows.value
        .filter((w) => w.state === 'normal' || w.state === 'maximized')
        .sort((a, b) => b.zIndex - a.zIndex);
      activeWindowId.value = next.length > 0 ? next[0].id : null;
    }
  }

  /**
   * 切换窗口最大化/正常状态
   */
  function toggleMaximize(id: string): void {
    const window = windows.value.find((w) => w.id === id);
    if (!window || window.state === 'closed') return;

    if (window.state === 'maximized') {
      window.state = 'normal';
    } else if (window.state === 'normal') {
      window.state = 'maximized';
    }
  }

  /**
   * 关闭窗口（延迟 300ms 删除，支持动画）
   */
  function close(id: string): void {
    const window = windows.value.find((w) => w.id === id);
    if (!window || window.state === 'closed' || window.state === 'closing') return;

    // 立即设置 closing 中间状态（状态机完善）
    window.state = 'closing';
    closingWindowIds.value.add(id);

    // 300ms 后真正删除
    setTimeout(() => {
      windows.value = windows.value.filter((w) => w.id !== id);
      closingWindowIds.value.delete(id);

      // 如果关闭的是活跃窗口，切换到下一个
      if (activeWindowId.value === id) {
        const next = windows.value
          .filter(
            (w) =>
              w.state !== 'closed' && w.state !== 'closing' && !closingWindowIds.value.has(w.id),
          )
          .sort((a, b) => b.zIndex - a.zIndex);
        activeWindowId.value = next.length > 0 ? next[0].id : null;
      }
    }, 300);
  }

  /**
   * 移动窗口（拖拽）
   */
  function move(id: string, x: number, y: number): void {
    const window = windows.value.find((w) => w.id === id);
    if (!window || window.state === 'closed') return;
    window.position = { x, y };
  }

  /**
   * 调整窗口尺寸
   */
  function resize(id: string, width: number, height: number): void {
    const window = windows.value.find((w) => w.id === id);
    if (!window || window.state === 'closed' || window.state === 'maximized') return;
    window.size = {
      width: Math.max(320, width),
      height: Math.max(240, height),
    };
  }

  /**
   * 设置窗口布局
   */
  function setLayout(layoutMode: LayoutMode, config?: Partial<WindowLayout>): void {
    layout.value = {
      mode: layoutMode,
      ...config,
    };

    // 应用布局
    if (layoutMode === 'tiled') {
      arrangeTiled();
    } else if (layoutMode === 'split') {
      arrangeSplit();
    }
  }

  /**
   * 平铺布局：将所有正常窗口在视口内均匀平铺
   */
  function arrangeTiled(): void {
    const normalWindows = windows.value.filter((w) => w.state === 'normal');
    if (normalWindows.length === 0) return;

    const cols = Math.ceil(Math.sqrt(normalWindows.length));
    const rows = Math.ceil(normalWindows.length / cols);

    const cellWidth = window.innerWidth / cols;
    const cellHeight = (window.innerHeight - 40) / rows; // 40px 留顶

    normalWindows.forEach((win, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      win.state = 'normal';
      win.position = {
        x: col * cellWidth,
        y: row * cellHeight + 40,
      };
      win.size = {
        width: cellWidth - 4,
        height: cellHeight - 4,
      };
    });
  }

  /**
   * 分栏布局：左右两栏
   */
  function arrangeSplit(ratios: number[] = [0.5, 0.5]): void {
    const normalWindows = windows.value.filter((w) => w.state === 'normal');
    if (normalWindows.length === 0) return;

    const totalRatio = ratios.reduce((a, b) => a + b, 0);
    let leftX = 0;

    normalWindows.forEach((win, index) => {
      const ratio = ratios[index % ratios.length] / totalRatio;
      const colWidth = window.innerWidth * ratio;
      win.state = 'normal';
      win.position = {
        x: leftX,
        y: 40,
      };
      win.size = {
        width: colWidth - 4,
        height: window.innerHeight - 44,
      };
      leftX += colWidth;
    });
  }

  /**
   * 计算下一个窗口的合适位置（层叠偏移，供外部使用）
   */
  function getNextPosition(): { x: number; y: number } {
    return calculateNextPosition(windows.value);
  }

  // ========== 返回 ==========

  return {
    // state
    windows,
    activeWindowId,
    nextZIndex,
    layout,
    closingWindowIds,

    // getters
    activeWindow,
    visibleWindows,
    windowsByService,

    // actions
    open,
    focus,
    minimize,
    toggleMaximize,
    close,
    move,
    resize,
    setLayout,
    arrangeTiled,
    arrangeSplit,
    getNextPosition,
  };
});
