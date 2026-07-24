<template>
  <!--
    MobileLayout — 移动端专用页面布局
    提供移动端优化的壳子：下拉刷新、安全区域、底部导航占位
  -->
  <MobileOptimization
    :enable-gesture-back="enableGestureBack"
    :show-perf-monitor="showPerfMonitor"
    :has-mobile-nav="hasMobileNav"
    @gesture-back="handleGestureBack"
    @breakpoint-change="handleBreakpointChange"
  >
    <!-- 顶部固定导航栏（可选） -->
    <header
      v-if="showTopBar"
      class="mobile-layout__topbar"
      :class="{ 'mobile-layout__topbar--bordered': topBarBordered }"
    >
      <!-- 返回按钮 -->
      <button
        v-if="showBackButton"
        class="mobile-layout__back-btn"
        :aria-label="backLabel"
        @click="handleBack"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      <!-- 标题 -->
      <h1 class="mobile-layout__title">
        <slot name="title">{{ title }}</slot>
      </h1>

      <!-- 右侧操作按钮（可选） -->
      <div v-if="$slots.actions" class="mobile-layout__actions">
        <slot name="actions" />
      </div>
    </header>

    <!-- 下拉刷新指示器 -->
    <div
      v-if="enablePullRefresh"
      ref="pullRefreshRef"
      class="mobile-layout__pull-refresh"
      :style="{ height: `${pullDistance}px`, opacity: pullProgress }"
    >
      <div class="pull-refresh__indicator" :class="{ 'pull-refresh__indicator--active': isRefreshing }">
        <svg
          v-if="!isRefreshing"
          class="pull-refresh__icon"
          :style="{ transform: `rotate(${pullDistance * 2}deg)` }"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="23 4 23 10 17 10" />
          <polyline points="1 20 1 14 7 14" />
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
        </svg>
        <!-- 刷新中动画 -->
        <svg
          v-else
          class="pull-refresh__icon pull-refresh__icon--spinning"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
      </div>
    </div>

    <!-- 主内容区（带虚拟滚动优化） -->
    <main
      ref="contentRef"
      class="mobile-layout__content"
      :style="contentStyle"
    >
      <slot />
    </main>

    <!-- 空状态 -->
    <div
      v-if="$slots.empty && isEmpty"
      class="mobile-layout__empty"
    >
      <slot name="empty" />
    </div>

    <!-- 底部导航栏插槽 -->
    <template #mobile-nav>
      <slot name="mobile-nav" />
    </template>
  </MobileOptimization>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useBreakpoint } from '@/composables/useBreakpoint';
import MobileOptimization from './MobileOptimization.vue';

// ============================
// Props & Emits
// ============================

const props = withDefaults(
  defineProps<{
    /** 页面标题 */
    title?: string;
    /** 是否显示顶部栏 */
    showTopBar?: boolean;
    /** 顶部栏是否需要底部分割线 */
    topBarBordered?: boolean;
    /** 是否显示返回按钮 */
    showBackButton?: boolean;
    /** 返回按钮 label */
    backLabel?: string;
    /** 是否启用手势返回 */
    enableGestureBack?: boolean;
    /** 是否启用下拉刷新 */
    enablePullRefresh?: boolean;
    /** 是否显示性能监控 */
    showPerfMonitor?: boolean;
    /** 是否有底部导航 */
    hasMobileNav?: boolean;
    /** 是否为空状态 */
    isEmpty?: boolean;
    /** 内容区顶部 padding (px) */
    contentPaddingTop?: number;
    /** 内容区底部 padding (px) */
    contentPaddingBottom?: number;
    /** 自定义返回行为（默认 router.back） */
    customBack?: () => void;
  }>(),
  {
    title: '',
    showTopBar: true,
    topBarBordered: false,
    showBackButton: false,
    backLabel: '返回',
    enableGestureBack: true,
    enablePullRefresh: false,
    showPerfMonitor: false,
    hasMobileNav: false,
    isEmpty: false,
    contentPaddingTop: 0,
    contentPaddingBottom: 0,
  },
);

const emit = defineEmits<{
  (e: 'refresh'): void;
  (e: 'back'): void;
  (e: 'breakpoint-change', bp: string): void;
}>();

// ============================
// Composables
// ============================

const router = useRouter();
const { isMobile } = useBreakpoint();

// ============================
// 下拉刷新
// ============================

const pullRefreshRef = ref<HTMLElement | null>(null);
const contentRef = ref<HTMLElement | null>(null);
const pullDistance = ref(0);
const pullProgress = ref(0);
const isRefreshing = ref(false);
const PULL_THRESHOLD = 80;
const MAX_PULL_DISTANCE = 120;

let touchStartY = 0;
let isPulling = false;

function handleTouchStart(e: TouchEvent): void {
  if (!props.enablePullRefresh || isRefreshing.value) return;
  if (!contentRef.value) return;

  // 只有在顶部时才允许下拉
  if (contentRef.value.scrollTop > 0) return;

  touchStartY = e.touches[0].clientY;
  isPulling = true;
}

function handleTouchMove(e: TouchEvent): void {
  if (!isPulling) return;

  const currentY = e.touches[0].clientY;
  const distance = currentY - touchStartY;

  if (distance < 0) {
    isPulling = false;
    pullDistance.value = 0;
    pullProgress.value = 0;
    return;
  }

  // 阻尼效果
  pullDistance.value = Math.min(distance * 0.5, MAX_PULL_DISTANCE);
  pullProgress.value = Math.min(pullDistance.value / PULL_THRESHOLD, 1);
}

async function handleTouchEnd(): void {
  if (!isPulling) return;
  isPulling = false;

  if (pullDistance.value >= PULL_THRESHOLD) {
    isRefreshing.value = true;
    pullDistance.value = PULL_THRESHOLD;
    pullProgress.value = 1;

    emit('refresh');

    // 模拟刷新延迟
    await new Promise((resolve) => setTimeout(resolve, 1500));

    isRefreshing.value = false;
  }

  // 回弹
  pullDistance.value = 0;
  pullProgress.value = 0;
}

// ============================
// 方法
// ============================

function handleBack(): void {
  if (props.customBack) {
    props.customBack();
  } else {
    router.back();
  }
  emit('back');
}

function handleGestureBack(): void {
  handleBack();
}

function handleBreakpointChange(bp: string): void {
  emit('breakpoint-change', bp);
}

// ============================
// 内容区样式
// ============================

const contentStyle = computed(() => ({
  paddingTop: `${Math.max(props.contentPaddingTop, 44)}px`,
  paddingBottom: `${Math.max(props.contentPaddingBottom, props.hasMobileNav ? 56 : 16)}px`,
}));

// ============================
// 生命周期
// ============================

onMounted(() => {
  if (props.enablePullRefresh && contentRef.value) {
    const el = contentRef.value;
    el.addEventListener('touchstart', handleTouchStart, { passive: true });
    el.addEventListener('touchmove', handleTouchMove, { passive: true });
    el.addEventListener('touchend', handleTouchEnd, { passive: true });

    onUnmounted(() => {
      el.removeEventListener('touchstart', handleTouchStart);
      el.removeEventListener('touchmove', handleTouchMove);
      el.removeEventListener('touchend', handleTouchEnd);
    });
  }
});
</script>

<style scoped lang="scss">
/* ============================
   顶部栏
   ============================ */

.mobile-layout__topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 12px;
  background: var(--fuxi-bg-card, #ffffff);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);

  &--bordered {
    border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  }
}

.mobile-layout__back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin-right: 8px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--fuxi-primary, #ff6700);
  transition: background 0.2s ease;
  flex-shrink: 0;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
  }

  &:active {
    background: var(--fuxi-bg-subtle, #f0ede5);
  }
}

.mobile-layout__title {
  flex: 1;
  font-size: 17px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin: 0;
}

.mobile-layout__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* ============================
   下拉刷新
   ============================ */

.mobile-layout__pull-refresh {
  position: relative;
  z-index: 0;
  overflow: hidden;
  transition: height 0.2s ease;
}

.pull-refresh__indicator {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--fuxi-bg-card, #ffffff);
  box-shadow: var(--fuxi-shadow-sm, 0 1px 6px rgba(0, 0, 0, 0.04));
  color: var(--fuxi-primary, #ff6700);
  transition: all 0.2s ease;

  &--active {
    transform: translateX(-50%) scale(1.1);
  }
}

.pull-refresh__icon {
  display: block;

  &--spinning {
    animation: pull-spin 1s linear infinite;
  }
}

@keyframes pull-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* ============================
   主内容区
   ============================ */

.mobile-layout__content {
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  height: 100vh;
  height: 100dvh; /* dynamic viewport height — 更精确的移动端高度 */
  padding: 44px 16px 16px;

  &::-webkit-scrollbar {
    width: 0;
    height: 0;
  }
}

/* ============================
   空状态
   ============================ */

.mobile-layout__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 50vh;
  padding: 32px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

/* ============================
   安全区域适配
   ============================ */

@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .mobile-layout__content {
    padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  }
}
</style>
