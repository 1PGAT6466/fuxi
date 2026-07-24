/**
 * useTouchGesture 单元测试
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ref, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { h, defineComponent } from 'vue';
import { useTouchGesture } from '../useTouchGesture';

// ============================
// 测试辅助组件
// ============================

function createTestComponent() {
  return defineComponent({
    setup() {
      const containerRef = ref<HTMLElement | null>(null);
      const lastSwipe = ref<string>('');
      const longPressCount = ref(0);
      const doubleTapCount = ref(0);

      const {
        onSwipeLeft,
        onSwipeRight,
        onSwipeUp,
        onSwipeDown,
        onLongPress,
        onDoubleTap,
      } = useTouchGesture(containerRef, {
        swipeThreshold: 50,
        longPressDuration: 300,
        doubleTapInterval: 250,
      });

      onSwipeLeft(() => {
        lastSwipe.value = 'left';
      });
      onSwipeRight(() => {
        lastSwipe.value = 'right';
      });
      onSwipeUp(() => {
        lastSwipe.value = 'up';
      });
      onSwipeDown(() => {
        lastSwipe.value = 'down';
      });
      onLongPress(() => {
        longPressCount.value++;
      });
      onDoubleTap(() => {
        doubleTapCount.value++;
      });

      return () =>
        h('div', { ref: containerRef, 'data-testid': 'container' }, [
          h('span', { 'data-testid': 'swipe' }, lastSwipe.value),
          h('span', { 'data-testid': 'longpress' }, String(longPressCount.value)),
          h('span', { 'data-testid': 'doubletap' }, String(doubleTapCount.value)),
        ]);
    },
  });
}

// ============================
// 指针事件模拟工具
// ============================

interface PointerEventInit {
  clientX: number;
  clientY: number;
  pointerType?: string;
  isPrimary?: boolean;
}

function createPointerEvent(
  type: string,
  init: PointerEventInit,
): PointerEvent {
  const event = new PointerEvent(type, {
    bubbles: true,
    cancelable: true,
    clientX: init.clientX,
    clientY: init.clientY,
    pointerType: init.pointerType || 'touch',
    isPrimary: init.isPrimary !== false,
  });
  return event;
}

function simulateSwipe(
  el: HTMLElement,
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
  _duration: number = 200,
): void {
  el.dispatchEvent(
    createPointerEvent('pointerdown', { clientX: fromX, clientY: fromY }),
  );
  el.dispatchEvent(
    createPointerEvent('pointermove', { clientX: toX, clientY: toY }),
  );
  el.dispatchEvent(
    createPointerEvent('pointerup', { clientX: toX, clientY: toY }),
  );
}

// ============================
// Tests
// ============================

describe('useTouchGesture', () => {

  it('应该在左滑时触发 onSwipeLeft', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;
    simulateSwipe(container, 200, 100, 50, 100, 100);

    await nextTick();
    expect(wrapper.find('[data-testid="swipe"]').text()).toBe('left');
  });

  it('应该在右滑时触发 onSwipeRight', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;
    simulateSwipe(container, 50, 100, 200, 100, 100);

    await nextTick();
    expect(wrapper.find('[data-testid="swipe"]').text()).toBe('right');
  });

  it('应该在上滑时触发 onSwipeUp', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;
    simulateSwipe(container, 100, 300, 100, 200, 100);

    await nextTick();
    expect(wrapper.find('[data-testid="swipe"]').text()).toBe('up');
  });

  it('应该在下滑时触发 onSwipeDown', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;
    simulateSwipe(container, 100, 100, 100, 250, 100);

    await nextTick();
    expect(wrapper.find('[data-testid="swipe"]').text()).toBe('down');
  });

  it('应该在长按时触发 onLongPress', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;

    // Verify listeners are attached
    expect(container.style.touchAction).toBe('manipulation');

    // pointerdown — starts longPressTimer with setTimeout
    container.dispatchEvent(
      createPointerEvent('pointerdown', { clientX: 100, clientY: 100 }),
    );

    // Wait for longPressDuration (300ms) — pointerup NOT dispatched,
    // so clearLongPressTimer should NOT be called
    await new Promise((r) => setTimeout(r, 350));
    await nextTick();

    expect(wrapper.find('[data-testid="longpress"]').text()).toBe('1');
  });

  it('应该在双击时触发 onDoubleTap', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;

    // 第一次完整 tap
    container.dispatchEvent(
      createPointerEvent('pointerdown', { clientX: 100, clientY: 100 }),
    );
    container.dispatchEvent(
      createPointerEvent('pointerup', { clientX: 100, clientY: 100 }),
    );

    // 短暂等待
    await new Promise((r) => setTimeout(r, 50));

    // 第二次完整 tap（在 250ms doubleTapInterval 内）
    container.dispatchEvent(
      createPointerEvent('pointerdown', { clientX: 100, clientY: 100 }),
    );
    container.dispatchEvent(
      createPointerEvent('pointerup', { clientX: 100, clientY: 100 }),
    );
    await nextTick();

    expect(wrapper.find('[data-testid="doubletap"]').text()).toBe('1');
  });

  it('短距离滑动不应触发滑动', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;

    // 移动距离小于阈值
    simulateSwipe(container, 100, 100, 120, 105, 50);

    await nextTick();
    // 不应触发任何滑动
    expect(wrapper.find('[data-testid="swipe"]').text()).toBe('');
  });

  it('指针移动时应取消长按', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;

    container.dispatchEvent(
      createPointerEvent('pointerdown', { clientX: 100, clientY: 100 }),
    );

    // 先移动超过取消阈值
    container.dispatchEvent(
      createPointerEvent('pointermove', { clientX: 120, clientY: 100 }),
    );

    // 等待超过 longPressDuration
    await new Promise((r) => setTimeout(r, 350));

    container.dispatchEvent(
      createPointerEvent('pointerup', { clientX: 120, clientY: 100 }),
    );

    await nextTick();
    expect(wrapper.find('[data-testid="longpress"]').text()).toBe('0');
  });

  it('超时滑动不应触发滑动', async () => {
    const wrapper = mount(createTestComponent());
    await nextTick();

    const container = wrapper.find('[data-testid="container"]').element;

    container.dispatchEvent(
      createPointerEvent('pointerdown', { clientX: 200, clientY: 100 }),
    );
    container.dispatchEvent(
      createPointerEvent('pointermove', { clientX: 100, clientY: 100 }),
    );

    // 超过时间阈值 — 等待 swipeTimeThreshold (300ms) 以外的实际时间
    await new Promise((r) => setTimeout(r, 350));

    container.dispatchEvent(
      createPointerEvent('pointerup', { clientX: 100, clientY: 100 }),
    );

    await nextTick();
    expect(wrapper.find('[data-testid="swipe"]').text()).toBe('');
  });
});
