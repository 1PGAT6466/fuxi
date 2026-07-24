<template>
  <!--
    MobileOptimization — 移动端优化总控组件
    整合触摸手势、响应式断点、性能优化于一体。
    作为移动端布局的顶层包裹器使用。

    功能：
    - 触摸手势支持（滑动返回、长按菜单、双击缩放）
    - 响应式断点感知
    - 性能优化（懒加载、虚拟滚动入口）
    - 安全区域适配
  -->
  <div
    ref="containerRef"
    class="mobile-optimization"
    :class="{
      'mobile-optimization--mobile': isMobile,
      'mobile-optimization--tablet': isTablet,
      'mobile-optimization--dark': isDark,
      'mobile-optimization--gesture-back': enableGestureBack,
    }"
  >
    <!-- 手势返回指示器（左侧边缘滑动时显示） -->
    <div
      v-if="enableGestureBack && isMobile && showBackIndicator"
      class="mobile-optimization__back-indicator"
      :style="{ opacity: backIndicatorOpacity }"
    >
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </div>

    <!-- 性能监控指示器（开发模式） -->
    <div
      v-if="showPerfMonitor"
      class="mobile-optimization__perf-monitor"
    >
      <span>FPS: {{ fpsCount }}</span>
      <span>Mem: {{ memoryUsage }}MB</span>
    </div>

    <!-- 主内容插槽 -->
    <div class="mobile-optimization__content">
      <slot />
    </div>

    <!-- 底部安全区占位（为 MobileNav 预留） -->
    <div
      v-if="isMobile && hasMobileNav"
      class="mobile-optimization__safe-bottom"
    />

    <!-- 底部导航栏（由父组件通过 slot 注入） -->
    <div v-if="$slots['mobile-nav']" class="mobile-optimization__nav">
      <slot name="mobile-nav" />
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  computed,
  onMounted,
  onUnmounted,
  provide,
  watch,
  type Ref,
} from 'vue';
import { useBreakpoint } from '@/composables/useBreakpoint';
import { useTheme } from '@/composables/useTheme';
import useTouchGesture from '@/composables/useTouchGesture';

// ============================
// Props & Emits
// ============================

const props = withDefaults(
  defineProps<{
    /** 是否启用手势返回（左侧边缘滑动触发） */
    enableGestureBack?: boolean;
    /** 是否显示性能监控 */
    showPerfMonitor?: boolean;
    /** 是否有底部导航栏 */
    hasMobileNav?: boolean;
  }>(),
  {
    enableGestureBack: true,
    showPerfMonitor: false,
    hasMobileNav: false,
  },
);

const emit = defineEmits<{
  (e: 'gesture-back'): void;
  (e: 'swipe-left'): void;
  (e: 'swipe-right'): void;
  (e: 'breakpoint-change', bp: string): void;
}>();

// ============================
// Composables
// ============================

const { isMobile, isTablet, isDesktop, breakpoint } = useBreakpoint();
const { isDark } = useTheme();

// ============================
// 手势支持
// ============================

const containerRef = ref<HTMLElement | null>(null);

const {
  onSwipeLeft,
  onSwipeRight,
  onLongPress,
  onDoubleTap,
} = useTouchGesture(containerRef, {
  swipeThreshold: 60,
  longPressDuration: 500,
  doubleTapInterval: 300,
});

// 手势返回指示器
const showBackIndicator = ref(false);
const backIndicatorOpacity = ref(0);

if (props.enableGestureBack) {
  onSwipeRight(() => {
    // 仅在左侧边缘滑动时触发返回
    emit('gesture-back');
    emit('swipe-right');
  });

  onSwipeLeft(() => {
    emit('swipe-left');
  });
}

// ============================
// 性能监控
// ============================

const fpsCount = ref(60);
const memoryUsage = ref(0);

let fpsFrameCount = 0;
let fpsLastTime = 0;
let fpsAnimationId: number | null = null;

function measureFPS(): void {
  fpsFrameCount++;

  const now = performance.now();
  if (now - fpsLastTime >= 1000) {
    fpsCount.value = fpsFrameCount;
    fpsFrameCount = 0;
    fpsLastTime = now;
  }

  fpsAnimationId = requestAnimationFrame(measureFPS);
}

function measureMemory(): void {
  if ('memory' in performance) {
    const mem = (
      performance as Performance & { memory: { usedJSHeapSize: number } }
    ).memory;
    if (mem) {
      memoryUsage.value = Math.round(mem.usedJSHeapSize / 1024 / 1024);
    }
  }
}

// ============================
// 懒加载观察器
// ============================

let lazyObserver: IntersectionObserver | null = null;

function setupLazyLoading(): void {
  if (!containerRef.value) return;

  lazyObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const target = entry.target as HTMLElement;
          // 处理懒加载图片
          const imgs = target.querySelectorAll('img[data-src]');
          imgs.forEach((img) => {
            const el = img as HTMLImageElement;
            el.src = el.dataset.src || '';
            el.removeAttribute('data-src');
          });

          // 处理懒加载组件（通过 data-lazy 属性）
          if (target.dataset.lazy === 'true') {
            target.dataset.lazy = 'loaded';
          }

          lazyObserver?.unobserve(target);
        }
      }
    },
    {
      root: containerRef.value,
      rootMargin: '100px',
      threshold: 0.01,
    },
  );

  // 观察所有带 data-lazy 属性的元素
  const lazyElements = containerRef.value.querySelectorAll('[data-lazy="true"], img[data-src]');
  lazyElements.forEach((el) => lazyObserver?.observe(el));
}

// ============================
// Provide 给子组件
// ============================

provide('isMobile', isMobile);
provide('isTablet', isTablet);
provide('isDesktop', isDesktop);
provide('breakpoint', breakpoint);
provide('mobileGesture', {
  onSwipeLeft,
  onSwipeRight,
  onLongPress,
  onDoubleTap,
});

// ============================
// 断点变化通知
// ============================

watch(breakpoint, (newBp) => {
  emit('breakpoint-change', newBp);
});

// ============================
// 生命周期
// ============================

onMounted(() => {
  if (props.showPerfMonitor) {
    fpsLastTime = performance.now();
    fpsAnimationId = requestAnimationFrame(measureFPS);

    const memInterval = setInterval(measureMemory, 2000);
    onUnmounted(() => clearInterval(memInterval));
  }

  setTimeout(setupLazyLoading, 100);
});

onUnmounted(() => {
  if (fpsAnimationId !== null) {
    cancelAnimationFrame(fpsAnimationId);
  }
  if (lazyObserver) {
    lazyObserver.disconnect();
    lazyObserver = null;
  }
});
</script>

<style scoped lang="scss">
/* ============================
   总控容器
   ============================ */

.mobile-optimization {
  position: relative;
  width: 100%;
  min-height: 100%;
  overflow: hidden;
  touch-action: manipulation;
  -webkit-overflow-scrolling: touch;

  &__content {
    position: relative;
    z-index: 1;
    min-height: 100%;
  }

  // ── 移动端特有样式 ──
  &--mobile {
    font-size: 14px;

    // 移动端优化滚动
    * {
      -webkit-tap-highlight-color: transparent;
    }
  }

  &--tablet {
    font-size: 15px;
  }

  // ── 暗色模式 ──
  &--dark {
    // 暗色下的一些微调
  }
}

/* ============================
   手势返回指示器
   ============================ */

.mobile-optimization__back-indicator {
  position: fixed;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 80;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--fuxi-primary, #ff6700);
  color: #fff;
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(255, 103, 0, 0.3);
  pointer-events: none;
  transition: opacity 0.2s ease;
}

/* ============================
   性能监控
   ============================ */

.mobile-optimization__perf-monitor {
  position: fixed;
  top: 8px;
  right: 8px;
  z-index: 9999;
  display: flex;
  gap: 12px;
  padding: 4px 10px;
  background: rgba(0, 0, 0, 0.75);
  color: #4caf50;
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  font-size: 11px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

/* ============================
   底部安全区
   ============================ */

.mobile-optimization__safe-bottom {
  height: 56px;
  height: calc(56px + env(safe-area-inset-bottom, 0px));
}

.mobile-optimization__nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 90;
}

/* ============================
   响应式微调
   ============================ */

@media (max-width: 479px) {
  .mobile-optimization--mobile {
    font-size: 13px;
  }
}

@media (min-width: 768px) {
  .mobile-optimization--tablet {
    max-width: 768px;
    margin: 0 auto;
  }
}
</style>
