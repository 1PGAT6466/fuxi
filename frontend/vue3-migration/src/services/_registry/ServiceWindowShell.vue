<template>
  <Teleport to="body">
    <transition name="window-fade" @after-leave="$emit('closed')">
      <div
        v-if="window.state !== 'closed' && visible"
        :ref="
          (el) => {
            windowEl = el as HTMLElement | null;
          }
        "
        class="service-window-shell"
        :class="windowClasses"
        :style="windowStyle"
        :aria-label="`${window.title} 窗口`"
        role="dialog"
        :aria-modal="props.modal ? 'true' : 'false'"
        @mousedown="handleFocus"
      >
        <!-- 标题栏 -->
        <div class="window-titlebar" @mousedown="handleDragStart" @dblclick="handleToggleMaximize">
          <div class="titlebar-left">
            <el-icon class="titlebar-icon" :size="18">
              <component :is="window.icon" v-if="window.icon" />
            </el-icon>
            <span class="titlebar-title">{{ window.title }}</span>
          </div>
          <div class="titlebar-actions">
            <button
              class="titlebar-btn"
              :aria-label="'最小化'"
              title="最小化"
              @click.stop="$emit('minimize')"
            >
              <el-icon :size="16"><Minus /></el-icon>
            </button>
            <button
              class="titlebar-btn"
              :aria-label="window.state === 'maximized' ? '还原' : '最大化'"
              :title="window.state === 'maximized' ? '还原' : '最大化'"
              @click.stop="handleToggleMaximize"
            >
              <el-icon :size="16">
                <CopyDocument v-if="window.state === 'maximized'" />
                <FullScreen v-else />
              </el-icon>
            </button>
            <button
              class="titlebar-btn titlebar-btn--close"
              aria-label="关闭"
              title="关闭"
              @click.stop="$emit('close')"
            >
              <el-icon :size="16"><Close /></el-icon>
            </button>
          </div>
        </div>

        <!-- 内容区 -->
        <div class="window-content">
          <slot />
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { Minus, FullScreen, Close, CopyDocument } from '@element-plus/icons-vue';
import type { ServiceWindow } from '@/types/service-manifest';

// ============================
// Props & Emits
// ============================

const props = defineProps<{
  window: ServiceWindow;
  /** 是否可见（用于过渡动画） */
  visible?: boolean;
  /** 是否为模态窗口（阻止与页面其他内容交互） */
  modal?: boolean;
}>();

const emit = defineEmits<{
  (e: 'focus'): void;
  (e: 'minimize'): void;
  (e: 'maximize'): void;
  (e: 'close'): void;
  (e: 'closed'): void;
  (e: 'move', x: number, y: number): void;
  (e: 'resize', width: number, height: number): void;
}>();

// ============================
// 拖拽状态
// ============================

const windowEl = ref<HTMLElement | null>(null);
const isDragging = ref(false);
const dragStartX = ref(0);
const dragStartY = ref(0);
const dragStartPosX = ref(0);
const dragStartPosY = ref(0);

// ============================
// 窗口样式
// ============================

const windowClasses = computed(() => {
  const state = props.window.state;
  return {
    'window--normal': state === 'normal',
    'window--maximized': state === 'maximized',
    'window--minimized': state === 'minimized',
    'window--dragging': isDragging.value,
  };
});

const windowStyle = computed(() => {
  const w = props.window;
  const state = w.state;

  // 最大化：占满视口
  if (state === 'maximized') {
    return {
      width: '100vw',
      height: '100vh',
      left: '0px',
      top: '0px',
      zIndex: w.zIndex,
    };
  }

  // 最小化：缩小到任务栏大小，定位在视口底部
  if (state === 'minimized') {
    return {
      width: '200px',
      height: '42px',
      left: `${w.position.x}px`,
      top: 'calc(100vh - 42px)',
      zIndex: w.zIndex,
      overflow: 'hidden',
    };
  }

  // 正常状态
  return {
    width: typeof w.size.width === 'number' ? `${w.size.width}px` : w.size.width,
    height: typeof w.size.height === 'number' ? `${w.size.height}px` : w.size.height,
    left: `${w.position.x}px`,
    top: `${w.position.y}px`,
    zIndex: w.zIndex,
  };
});

// ============================
// 事件处理
// ============================

function handleFocus() {
  emit('focus');
}

function handleToggleMaximize() {
  if (props.window.state === 'maximized') {
    emit('maximize'); // toggleMaximize 会处理
  } else {
    emit('maximize');
  }
}

// ============================
// 拖拽实现
// ============================

function handleDragStart(e: MouseEvent) {
  // 只在正常状态下允许拖拽，且忽略按钮点击
  if (props.window.state !== 'normal') return;
  if ((e.target as HTMLElement).closest('.titlebar-btn')) return;

  isDragging.value = true;
  dragStartX.value = e.clientX;
  dragStartY.value = e.clientY;
  dragStartPosX.value = props.window.position.x;
  dragStartPosY.value = props.window.position.y;

  document.addEventListener('mousemove', handleDragMove);
  document.addEventListener('mouseup', handleDragEnd);
  e.preventDefault();
}

function handleDragMove(e: MouseEvent) {
  if (!isDragging.value) return;

  const dx = e.clientX - dragStartX.value;
  const dy = e.clientY - dragStartY.value;

  // 约束在视口内
  const newX = Math.max(0, Math.min(dragStartPosX.value + dx, window.innerWidth - 200));
  const newY = Math.max(0, Math.min(dragStartPosY.value + dy, window.innerHeight - 100));

  emit('move', newX, newY);
}

function handleDragEnd() {
  isDragging.value = false;
  document.removeEventListener('mousemove', handleDragMove);
  document.removeEventListener('mouseup', handleDragEnd);
}

// ============================
// Resize 观察（边缘拖拽扩展）
// ============================

let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (windowEl.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (props.window.state === 'normal') {
          emit('resize', width, height);
        }
      }
    });
    resizeObserver.observe(windowEl.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
  document.removeEventListener('mousemove', handleDragMove);
  document.removeEventListener('mouseup', handleDragEnd);
});
</script>

<style scoped lang="scss">
.service-window-shell {
  position: fixed;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  transition:
    box-shadow var(--duration-fast) var(--ease-out),
    border-radius var(--duration-normal) var(--ease-out);

  border: 1px solid var(--bg-divider);

  &.window--dragging {
    box-shadow: var(--fuxi-shadow-popup, 0 4px 24px rgba(0, 0, 0, 0.12));
    transition: box-shadow var(--duration-fast) var(--ease-out);
    cursor: grabbing;

    .window-titlebar {
      cursor: grabbing;
    }
  }

  &.window--maximized {
    border-radius: 0;
    border: none;
  }

  &.window--minimized {
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
    pointer-events: auto;
  }
}

/* ============================
   标题栏
   ============================ */

.window-titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 40px;
  padding: 0 4px 0 12px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--bg-divider);
  user-select: none;
  flex-shrink: 0;

  .window--maximized & {
    border-radius: 0;
  }

  .window--normal & {
    cursor: grab;
  }

  .titlebar-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }

  .titlebar-icon {
    color: var(--brand);
    flex-shrink: 0;
  }

  .titlebar-title {
    font-size: var(--font-size-caption);
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
    margin-left: 8px;
  }

  .titlebar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 28px;
    border: none;
    background: transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all var(--duration-fast) var(--ease-out);

    &:hover {
      background: var(--bg-hover);
      color: var(--text-primary);
    }

    &--close:hover {
      background: var(--li-color);
      color: #fff;
    }
  }
}

/* ============================
   内容区
   ============================ */

.window-content {
  flex: 1;
  overflow: auto;
  position: relative;

  .window--minimized & {
    display: none;
  }
}

/* ============================
   移动端降级
   ============================ */

@media (max-width: 767px) {
  .service-window-shell {
    width: 100vw !important;
    height: 100vh !important;
    left: 0 !important;
    top: 0 !important;
    border-radius: 0;
    border: none;

    &.window--normal {
      pointer-events: auto;
    }
  }

  .window-titlebar {
    height: 48px;

    .window--normal & {
      cursor: default;
    }
  }

  /* 隐藏最大化/还原按钮（已强制全屏） */
  .titlebar-actions .titlebar-btn:not(.titlebar-btn--close) {
    display: none;
  }
}

/* ============================
   过渡动画
   ============================ */

.window-fade-enter-active {
  transition: all var(--duration-normal) var(--ease-out);
}

.window-fade-leave-active {
  transition: all var(--duration-fast) var(--ease-out);
}

.window-fade-enter-from {
  opacity: 0;
  transform: scale(0.92);
}

.window-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
