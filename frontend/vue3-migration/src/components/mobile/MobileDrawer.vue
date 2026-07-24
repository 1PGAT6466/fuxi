<template>
  <!--
    MobileDrawer — 移动端抽屉式侧滑菜单
    支持左侧/右侧滑出、手势关闭、背景蒙层
  -->
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div
        v-if="modelValue"
        class="mobile-drawer-mask"
        :class="{ 'mobile-drawer-mask--dark': isDark }"
        aria-hidden="true"
        @click="handleClose"
        @touchstart.passive="handleMaskTouch"
      />
    </Transition>

    <Transition :name="`drawer-slide-${placement}`">
      <aside
        v-if="modelValue"
        ref="drawerRef"
        class="mobile-drawer"
        :class="[
          `mobile-drawer--${placement}`,
          { 'mobile-drawer--dark': isDark },
        ]"
        :style="{ width: drawerWidth }"
        role="dialog"
        aria-modal="true"
        :aria-label="ariaLabel"
      >
        <!-- 顶部区域 -->
        <div class="mobile-drawer__header">
          <slot name="header">
            <span class="mobile-drawer__title">{{ title }}</span>
          </slot>
          <button
            class="mobile-drawer__close-btn"
            :aria-label="closeLabel"
            @click="handleClose"
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
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <!-- 内容区域 -->
        <div class="mobile-drawer__body">
          <slot />
        </div>

        <!-- 底部区域（可选） -->
        <div v-if="$slots.footer" class="mobile-drawer__footer">
          <slot name="footer" />
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useTheme } from '@/composables/useTheme';
import useTouchGesture from '@/composables/useTouchGesture';

// ============================
// Props & Emits
// ============================

const props = withDefaults(
  defineProps<{
    /** 控制显示/隐藏 */
    modelValue: boolean;
    /** 抽屉标题 */
    title?: string;
    /** 滑出方向 */
    placement?: 'left' | 'right';
    /** 宽度 (CSS 值) */
    width?: string;
    /** 无障碍标签 */
    ariaLabel?: string;
    /** 关闭按钮 label */
    closeLabel?: string;
    /** 是否点击蒙层关闭 */
    closeOnClickMask?: boolean;
    /** 是否支持手势关闭（向 drawer 相反方向滑动） */
    gestureClose?: boolean;
  }>(),
  {
    title: '',
    placement: 'left',
    width: '280px',
    ariaLabel: '侧边菜单',
    closeLabel: '关闭菜单',
    closeOnClickMask: true,
    gestureClose: true,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'open'): void;
  (e: 'close'): void;
}>();

// ============================
// Composables
// ============================

const { isDark } = useTheme();
const drawerRef = ref<HTMLElement | null>(null);

const drawerWidth = computed(() => props.width);

// ============================
// 手势关闭
// ============================

const { onSwipeLeft, onSwipeRight } = useTouchGesture(drawerRef, {
  swipeThreshold: 80,
});

if (props.gestureClose) {
  if (props.placement === 'left') {
    onSwipeLeft(() => handleClose());
  } else {
    onSwipeRight(() => handleClose());
  }
}

// ============================
// 方法
// ============================

let isClosing = false;

function handleClose(): void {
  if (isClosing) return;
  isClosing = true;
  emit('update:modelValue', false);
  emit('close');
  setTimeout(() => {
    isClosing = false;
  }, 350);
}

function handleMaskTouch(): void {
  if (props.closeOnClickMask) {
    handleClose();
  }
}

// ============================
// 键盘支持
// ============================

function handleKeydown(e: KeyboardEvent): void {
  if (!props.modelValue) return;
  if (e.key === 'Escape') {
    handleClose();
  }
}

// ============================
// body 滚动锁定
// ============================

function lockBodyScroll(): void {
  document.body.style.overflow = 'hidden';
}

function unlockBodyScroll(): void {
  document.body.style.overflow = '';
}

// ============================
// 生命周期
// ============================

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
  if (props.modelValue) {
    lockBodyScroll();
    emit('open');
  }
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
  unlockBodyScroll();
});
</script>

<style scoped lang="scss">
/* ============================
   蒙层
   ============================ */

.mobile-drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);

  &--dark {
    background: rgba(0, 0, 0, 0.65);
  }
}

/* ============================
   抽屉主体
   ============================ */

.mobile-drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  z-index: 1001;
  display: flex;
  flex-direction: column;
  background: var(--fuxi-bg-card, #ffffff);
  box-shadow: var(--fuxi-shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.06));
  overflow: hidden;
  touch-action: manipulation;
  -webkit-overflow-scrolling: touch;

  &--dark {
    background: var(--fuxi-bg-card, #252542);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
  }

  &--left {
    left: 0;
  }

  &--right {
    right: 0;
  }
}

/* ============================
   头部
   ============================ */

.mobile-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

.mobile-drawer__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
}

.mobile-drawer__close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--fuxi-text-secondary, #999999);
  transition: all 0.2s ease;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
    color: var(--fuxi-text, #333333);
  }

  &:active {
    background: var(--fuxi-bg-subtle, #f0ede5);
  }
}

/* ============================
   内容
   ============================ */

.mobile-drawer__body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  padding: 0;

  &::-webkit-scrollbar {
    width: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 3px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

/* ============================
   底部
   ============================ */

.mobile-drawer__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

/* ============================
   过渡动画
   ============================ */

// 蒙层淡入淡出
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

// 左侧滑入滑出
.drawer-slide-left-enter-active,
.drawer-slide-left-leave-active {
  transition: transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.drawer-slide-left-enter-from,
.drawer-slide-left-leave-to {
  transform: translateX(-100%);
}

// 右侧滑入滑出
.drawer-slide-right-enter-active,
.drawer-slide-right-leave-active {
  transition: transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.drawer-slide-right-enter-from,
.drawer-slide-right-leave-to {
  transform: translateX(100%);
}

/* ============================
   preferred-reduced-motion
   ============================ */

@media (prefers-reduced-motion: reduce) {
  .drawer-fade-enter-active,
  .drawer-fade-leave-active,
  .drawer-slide-left-enter-active,
  .drawer-slide-left-leave-active,
  .drawer-slide-right-enter-active,
  .drawer-slide-right-leave-active {
    transition: none;
  }
}
</style>
