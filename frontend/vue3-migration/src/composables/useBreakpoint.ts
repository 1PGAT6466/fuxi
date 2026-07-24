/**
 * useBreakpoint — 响应式断点检测 composable
 *
 * 基于 CSS 媒体查询实时检测当前视口断点。
 * 提供响应式的断点状态，供组件条件渲染和移动端适配使用。
 *
 * 断点定义（与 responsive.scss 保持一致）：
 * - xs: < 480px
 * - sm: 480px - 576px
 * - md: 576px - 768px
 * - lg: 768px - 992px
 * - xl: 992px - 1200px
 * - xxl: >= 1200px
 *
 * 用法：
 * ```ts
 * const { breakpoint, isMobile, isTablet, isDesktop, isXs } = useBreakpoint()
 * ```
 */

import { ref, computed, onMounted, onUnmounted, type Ref } from 'vue';

/** 断点枚举 */
export type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'xxl';

/** 断点配置 */
interface BreakpointConfig {
  name: Breakpoint;
  query: string;
}

const BREAKPOINTS: readonly BreakpointConfig[] = Object.freeze([
  { name: 'xs', query: '(max-width: 479px)' },
  { name: 'sm', query: '(min-width: 480px) and (max-width: 575px)' },
  { name: 'md', query: '(min-width: 576px) and (max-width: 767px)' },
  { name: 'lg', query: '(min-width: 768px) and (max-width: 991px)' },
  { name: 'xl', query: '(min-width: 992px) and (max-width: 1199px)' },
  { name: 'xxl', query: '(min-width: 1200px)' },
]);

/** 当前激活的断点 */
const currentBreakpoint: Ref<Breakpoint> = ref('xxl');

/** 是否已初始化全局监听 */
let globalInitialized = false;

/** 各断点 MatchMedia 实例与清理引用 */
const mediaQueryLists: MediaQueryList[] = [];

/**
 * 根据当前匹配查询解析断点
 */
function resolveBreakpoint(): Breakpoint {
  for (const bp of BREAKPOINTS) {
    if (window.matchMedia(bp.query).matches) return bp.name;
  }
  return 'xxl';
}

/**
 * 注册全局断点监听（仅首次调用时执行）
 */
function initializeBreakpoints(): void {
  if (globalInitialized) return;
  globalInitialized = true;

  currentBreakpoint.value = resolveBreakpoint();

  // 为每个断点创建监听器
  for (const bp of BREAKPOINTS) {
    const mql = window.matchMedia(bp.query);
    mediaQueryLists.push(mql);

    mql.addEventListener('change', (e: MediaQueryListEvent) => {
      if (e.matches) {
        currentBreakpoint.value = bp.name;
      }
    });
  }

  // 窗口 resize 时做兜底校正（防抖）
  let resizeTimer: ReturnType<typeof setTimeout> | null = null;
  window.addEventListener('resize', () => {
    if (resizeTimer !== null) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      currentBreakpoint.value = resolveBreakpoint();
    }, 150);
  });
}

/**
 * 响应式断点 composable
 *
 * @returns 断点相关响应式状态和辅助判断
 */
export function useBreakpoint() {
  onMounted(() => {
    initializeBreakpoints();
  });

  // 无需在 onUnmounted 中清理 — 全局共享

  /** 当前断点名称 */
  const breakpoint = computed<Breakpoint>(() => currentBreakpoint.value);

  /** 是否为移动端（xs + sm） */
  const isMobile = computed(() =>
    currentBreakpoint.value === 'xs' || currentBreakpoint.value === 'sm',
  );

  /** 是否为平板端（md + lg） */
  const isTablet = computed(() =>
    currentBreakpoint.value === 'md' || currentBreakpoint.value === 'lg',
  );

  /** 是否为桌面端（xl + xxl） */
  const isDesktop = computed(() =>
    currentBreakpoint.value === 'xl' || currentBreakpoint.value === 'xxl',
  );

  /** 是否为小屏（< 576px）*/
  const isSmallScreen = computed(() =>
    currentBreakpoint.value === 'xs' || currentBreakpoint.value === 'sm',
  );

  /** 是否为 xs 断点 */
  const isXs = computed(() => currentBreakpoint.value === 'xs');

  /** 是否为 sm 断点 */
  const isSm = computed(() => currentBreakpoint.value === 'sm');

  /** 是否为 md 断点 */
  const isMd = computed(() => currentBreakpoint.value === 'md');

  /** 是否为 lg 及以上 */
  const isLgUp = computed(() =>
    ['lg', 'xl', 'xxl'].includes(currentBreakpoint.value),
  );

  /** 是否为 xl 及以上 */
  const isXlUp = computed(() =>
    ['xl', 'xxl'].includes(currentBreakpoint.value),
  );

  /**
   * 检测当前断点是否匹配指定断点
   * @param target 目标断点或断点列表
   */
  function isBreakpoint(target: Breakpoint | Breakpoint[]): boolean {
    const targets = Array.isArray(target) ? target : [target];
    return targets.includes(currentBreakpoint.value);
  }

  return {
    breakpoint,
    isMobile,
    isTablet,
    isDesktop,
    isSmallScreen,
    isXs,
    isSm,
    isMd,
    isLgUp,
    isXlUp,
    isBreakpoint,
  };
}

/**
 * 获取当前静态断点（非响应式，用于一次性判断）
 */
export function getCurrentBreakpoint(): Breakpoint {
  return resolveBreakpoint();
}

export default useBreakpoint;
