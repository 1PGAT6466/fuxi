/**
 * useVirtualScroll — 虚拟滚动 composable
 *
 * 移动端性能优化的虚拟列表，只渲染可视区域内的元素，
 * 大幅减少 DOM 节点数量，提升滚动性能。
 *
 * 用法：
 * ```ts
 * const { visibleItems, containerStyle, wrapperStyle, scrollTo } = useVirtualScroll({
 *   items: listData,
 *   itemHeight: 48,
 *   overscan: 5,
 * })
 * ```
 */

import { ref, computed, onMounted, onUnmounted, watch, type Ref, type MaybeRef, toValue } from 'vue';

export interface VirtualScrollOptions<T = unknown> {
  /** 数据源 */
  items: MaybeRef<T[]>;
  /** 单项高度 (px) */
  itemHeight: number;
  /** 预渲染的额外行数（可视区域外），默认 3 */
  overscan?: number;
  /** 容器 CSS 选择器或元素引用 */
  containerRef?: MaybeRef<HTMLElement | null>;
}

export interface VirtualScrollReturn<T = unknown> {
  /** 当前可见的数据项 */
  visibleItems: Ref<{ item: T; index: number; style: Record<string, string> }[]>;
  /** 容器总高度样式 */
  containerStyle: Ref<Record<string, string>>;
  /** 滚动到指定索引 */
  scrollTo: (index: number, behavior?: ScrollBehavior) => void;
  /** 滚动位置 ref */
  scrollTop: Ref<number>;
  /** 当前起始索引 */
  startIndex: Ref<number>;
  /** 当前结束索引 */
  endIndex: Ref<number>;
}

export function useVirtualScroll<T = unknown>(
  options: VirtualScrollOptions<T>,
): VirtualScrollReturn<T> {
  const {
    itemHeight,
    overscan = 3,
  } = options;

  // ── 状态 ──
  const scrollTop = ref(0);
  const containerHeight = ref(0);

  // ── 计算属性 ──
  const itemsArray = computed<T[]>(() => toValue(options.items));
  const totalHeight = computed(() => itemsArray.value.length * itemHeight);

  const startIndex = computed(() => {
    const start = Math.floor(scrollTop.value / itemHeight);
    return Math.max(0, start - overscan);
  });

  const endIndex = computed(() => {
    const end = Math.ceil((scrollTop.value + containerHeight.value) / itemHeight);
    return Math.min(itemsArray.value.length, end + overscan);
  });

  const visibleItems = computed(() => {
    const result: { item: T; index: number; style: Record<string, string> }[] = [];
    for (let i = startIndex.value; i < endIndex.value; i++) {
      result.push({
        item: itemsArray.value[i],
        index: i,
        style: {
          position: 'absolute',
          top: `${i * itemHeight}px`,
          left: '0',
          right: '0',
          height: `${itemHeight}px`,
        },
      });
    }
    return result;
  });

  const containerStyle = computed<Record<string, string>>(() => ({
    position: 'relative',
    height: `${totalHeight.value}px`,
    width: '100%',
  }));

  // ── 滚动处理 ──
  let scrollElement: HTMLElement | null = null;
  let resizeObserver: ResizeObserver | null = null;

  function handleScroll(): void {
    if (!scrollElement) return;
    scrollTop.value = scrollElement.scrollTop;
  }

  function initScrollElement(): void {
    const ref = options.containerRef ? toValue(options.containerRef) : null;
    scrollElement = ref || null;
    if (scrollElement) {
      scrollElement.addEventListener('scroll', handleScroll, { passive: true });
      containerHeight.value = scrollElement.clientHeight;

      resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          containerHeight.value = entry.contentRect.height;
        }
      });
      resizeObserver.observe(scrollElement);
    }
  }

  function scrollTo(index: number, behavior: ScrollBehavior = 'smooth'): void {
    if (!scrollElement) return;
    const top = index * itemHeight;
    scrollElement.scrollTo({ top, behavior });
  }

  // ── 监听数据变化 ──
  watch(itemsArray, () => {
    // 数据变化时无需特殊处理，computed 自动更新
  });

  // ── 生命周期 ──
  onMounted(() => {
    // 延迟初始化，确保 DOM 就绪
    setTimeout(initScrollElement, 0);
  });

  onUnmounted(() => {
    if (scrollElement) {
      scrollElement.removeEventListener('scroll', handleScroll);
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
  });

  return {
    visibleItems,
    containerStyle,
    scrollTo,
    scrollTop,
    startIndex,
    endIndex,
  };
}

export default useVirtualScroll;
