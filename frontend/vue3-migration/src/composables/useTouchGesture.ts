/**
 * useTouchGesture — 触摸手势 composable
 *
 * 提供移动端触摸手势支持：滑动（Swipe）、长按（LongPress）、双击（DoubleTap）。
 * 基于 Pointer Events 实现，兼容触摸和鼠标输入。
 *
 * 用法：
 * ```ts
 * const { onSwipeLeft, onLongPress, onDoubleTap } = useTouchGesture(refEl)
 * onSwipeLeft(() => router.back())
 * ```
 */

import { ref, onMounted, onUnmounted, type Ref, type MaybeRef, toValue } from 'vue';

// ============================
// 类型定义
// ============================

/** 手势回调 */
export type GestureCallback = (event: PointerEvent) => void;

/** 滑动方向 */
export type SwipeDirection = 'left' | 'right' | 'up' | 'down';

/** 触摸手势配置 */
export interface TouchGestureOptions {
  /** 滑动触发最小距离 (px)，默认 50 */
  swipeThreshold?: number;
  /** 滑动触发最大时间 (ms)，默认 300 */
  swipeTimeThreshold?: number;
  /** 长按触发时间 (ms)，默认 500 */
  longPressDuration?: number;
  /** 双击最大间隔 (ms)，默认 300 */
  doubleTapInterval?: number;
  /** 双击最大位移容差 (px)，默认 10 */
  doubleTapTolerance?: number;
}

/** 默认配置 */
const DEFAULT_OPTIONS: Required<TouchGestureOptions> = {
  swipeThreshold: 50,
  swipeTimeThreshold: 300,
  longPressDuration: 500,
  doubleTapInterval: 300,
  doubleTapTolerance: 10,
};

// ============================
// 内部状态
// ============================

interface PointerState {
  startX: number;
  startY: number;
  startTime: number;
  moved: boolean;
}

export function useTouchGesture(
  target: MaybeRef<HTMLElement | null | undefined>,
  options: TouchGestureOptions = {},
) {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // ─── 滑动状态 ───
  const pointerState: PointerState = {
    startX: 0,
    startY: 0,
    startTime: 0,
    moved: false,
  };

  // ─── 长按状态 ───
  let longPressTimer: ReturnType<typeof setTimeout> | null = null;
  let longPressTriggered = false;

  // ─── 双击状态 ───
  let lastTapTime = 0;
  let lastTapX = 0;
  let lastTapY = 0;

  // ─── 回调注册表 ───
  const swipeCallbacks = ref<Map<SwipeDirection, Set<GestureCallback>>>(new Map());
  const longPressCallbacks = ref<Set<GestureCallback>>(new Set());
  const doubleTapCallbacks = ref<Set<GestureCallback>>(new Set());

  // ─── 监听器引用（用于清理） ───
  const listeners: { el: HTMLElement; type: string; fn: EventListener }[] = [];

  function addListener(el: HTMLElement, type: string, fn: EventListener): void {
    el.addEventListener(type, fn);
    listeners.push({ el, type, fn });
  }

  // ============================
  // 事件处理
  // ============================

  function handlePointerDown(e: PointerEvent): void {
    pointerState.startX = e.clientX;
    pointerState.startY = e.clientY;
    pointerState.startTime = Date.now();
    pointerState.moved = false;
    longPressTriggered = false;

    // 启动长按定时器
    clearLongPressTimer();
    longPressTimer = setTimeout(() => {
      longPressTriggered = true;
      triggerCallbacks(longPressCallbacks.value, e);
    }, opts.longPressDuration);
  }

  function handlePointerMove(e: PointerEvent): void {
    const dx = Math.abs(e.clientX - pointerState.startX);
    const dy = Math.abs(e.clientY - pointerState.startY);

    // 移动超过阈值 → 取消长按
    if (dx > opts.swipeThreshold * 0.3 || dy > opts.swipeThreshold * 0.3) {
      pointerState.moved = true;
      clearLongPressTimer();
    }
  }

  function handlePointerUp(e: PointerEvent): void {
    clearLongPressTimer();

    // 长按已触发 → 不处理滑动/双击
    if (longPressTriggered) return;

    const dx = e.clientX - pointerState.startX;
    const dy = e.clientY - pointerState.startY;
    const elapsed = Date.now() - pointerState.startTime;
    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);

    // ─── 滑动检测 ───
    if (
      pointerState.moved &&
      elapsed <= opts.swipeTimeThreshold &&
      (absDx >= opts.swipeThreshold || absDy >= opts.swipeThreshold)
    ) {
      let direction: SwipeDirection;

      if (absDx >= absDy) {
        direction = dx > 0 ? 'right' : 'left';
      } else {
        direction = dy > 0 ? 'down' : 'up';
      }

      triggerCallbacks(swipeCallbacks.value, direction, e);
      return;
    }

    // ─── 双击检测 ───
    const now = Date.now();
    if (lastTapTime > 0 && now - lastTapTime <= opts.doubleTapInterval) {
      const tapDx = Math.abs(e.clientX - lastTapX);
      const tapDy = Math.abs(e.clientY - lastTapY);

      if (tapDx <= opts.doubleTapTolerance && tapDy <= opts.doubleTapTolerance) {
        triggerCallbacks(doubleTapCallbacks.value, e);
        lastTapTime = 0; // 重置，避免三次点击也触发双击
        return;
      }
    }

    // 记录本次点击
    lastTapTime = now;
    lastTapX = e.clientX;
    lastTapY = e.clientY;
  }

  function handlePointerCancel(): void {
    clearLongPressTimer();
  }

  // ============================
  // 辅助方法
  // ============================

  function clearLongPressTimer(): void {
    if (longPressTimer !== null) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
  }

  function triggerCallbacks(
    mapOrSet: Map<SwipeDirection, Set<GestureCallback>> | Set<GestureCallback>,
    keyOrEvent: SwipeDirection | PointerEvent,
    event?: PointerEvent,
  ): void {
    if (mapOrSet instanceof Map) {
      const direction = keyOrEvent as SwipeDirection;
      const callbacks = mapOrSet.get(direction);
      if (callbacks && event) {
        callbacks.forEach((cb) => cb(event));
      }
    } else {
      // Set 类型回调：第2个参数就是事件对象
      const evt = (keyOrEvent as PointerEvent) || event;
      if (evt) {
        (mapOrSet as Set<GestureCallback>).forEach((cb) => cb(evt));
      }
    }
  }

  // ============================
  // 注册方法
  // ============================

  function onSwipe(direction: SwipeDirection, callback: GestureCallback): void {
    let callbacks = swipeCallbacks.value.get(direction);
    if (!callbacks) {
      callbacks = new Set();
      swipeCallbacks.value.set(direction, callbacks);
    }
    callbacks.add(callback);
  }

  function onSwipeLeft(callback: GestureCallback): void {
    onSwipe('left', callback);
  }

  function onSwipeRight(callback: GestureCallback): void {
    onSwipe('right', callback);
  }

  function onSwipeUp(callback: GestureCallback): void {
    onSwipe('up', callback);
  }

  function onSwipeDown(callback: GestureCallback): void {
    onSwipe('down', callback);
  }

  function onLongPress(callback: GestureCallback): void {
    longPressCallbacks.value.add(callback);
  }

  function onDoubleTap(callback: GestureCallback): void {
    doubleTapCallbacks.value.add(callback);
  }

  // ============================
  // 卸载回调
  // ============================

  function offSwipe(direction: SwipeDirection, callback: GestureCallback): void {
    swipeCallbacks.value.get(direction)?.delete(callback);
  }

  function offLongPress(callback: GestureCallback): void {
    longPressCallbacks.value.delete(callback);
  }

  function offDoubleTap(callback: GestureCallback): void {
    doubleTapCallbacks.value.delete(callback);
  }

  // ============================
  // 生命周期
  // ============================

  onMounted(() => {
    const el = toValue(target);
    if (!el) return;

    addListener(el, 'pointerdown', handlePointerDown as EventListener);
    addListener(el, 'pointermove', handlePointerMove as EventListener);
    addListener(el, 'pointerup', handlePointerUp as EventListener);
    addListener(el, 'pointercancel', handlePointerCancel);
    addListener(el, 'pointerleave', handlePointerCancel);

    // 防止移动端默认行为（如页面拖动）
    el.style.touchAction = 'manipulation';
  });

  onUnmounted(() => {
    clearLongPressTimer();

    // 清理所有事件监听
    for (const { el, type, fn } of listeners) {
      el.removeEventListener(type, fn);
    }
    listeners.length = 0;

    // 清空回调
    swipeCallbacks.value.clear();
    longPressCallbacks.value.clear();
    doubleTapCallbacks.value.clear();
  });

  return {
    onSwipeLeft,
    onSwipeRight,
    onSwipeUp,
    onSwipeDown,
    onLongPress,
    onDoubleTap,
    offSwipe,
    offLongPress,
    offDoubleTap,
  };
}

export default useTouchGesture;
