<template>
  <div
    class="bagua-cell"
    :class="{
      'bagua-cell--center': isCenter,
      [`bagua-cell--status-${status}`]: true,
      'bagua-cell--clickable': !!item,
      'animate-breathe': !isCenter && status === 'healthy',
    }"
    :style="cellStyle"
    role="gridcell"
    :tabindex="item ? 0 : -1"
    :aria-label="item ? `${item.label}卦 — ${item.functionDesc}` : ''"
    @click="$emit('click')"
    @keydown.enter="$emit('click')"
    @keydown.space.prevent="$emit('click')"
  >
    <!-- 状态指示灯（右上角） -->
    <div v-if="!isCenter" class="bagua-cell__status">
      <StatusIndicator :status="status" :size="10" />
    </div>

    <!-- 左侧卦色装饰线 -->
    <div v-if="!isCenter" class="bagua-cell__accent" :style="accentStyle" />

    <!-- 中宫特殊布局 -->
    <template v-if="isCenter">
      <div class="bagua-cell--center__inner">
        <!-- 太极图标 -->
        <TajiiIcon
          :size="56"
          :spinning="true"
          yin-yang-color="var(--bagua-dui, #FAFAFA)"
          yin-color="var(--fuxi-primary, #FF6700)"
          stroke-color="rgba(255,255,255,0.3)"
        />
        <!-- 卦符号 -->
        <div class="bagua-cell__symbol bagua-cell__symbol--center">
          {{ item?.symbol }}
        </div>
        <!-- 功能名 -->
        <div class="bagua-cell__label bagua-cell__label--center">
          {{ item?.functionDesc }}
        </div>
        <!-- 进化信息 -->
        <div class="bagua-cell__evolution">
          <span class="bagua-cell__evolution-level">Lv.{{ evolutionLevel }}</span>
          <div class="bagua-cell__evolution-bar">
            <div class="bagua-cell__evolution-fill" :style="{ width: `${clampedProgress}%` }" />
          </div>
        </div>
      </div>
    </template>

    <!-- 普通卦格布局 -->
    <template v-else>
      <!-- 卦符号 -->
      <div class="bagua-cell__symbol">{{ item?.symbol }}</div>
      <!-- 卦名 -->
      <div class="bagua-cell__label">{{ item?.label }}</div>
      <!-- 功能描述 -->
      <div class="bagua-cell__function">{{ item?.functionDesc }}</div>
      <!-- Emoji -->
      <div class="bagua-cell__emoji">{{ item?.emoji }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import StatusIndicator from './StatusIndicator.vue';
import TajiiIcon from './TajiiIcon.vue';
import type { BaguaItem, TrigramStatus } from '@/constants/bagua';

const props = withDefaults(
  defineProps<{
    item: BaguaItem | null;
    status?: TrigramStatus;
    gridPosition?: number;
    isCenter?: boolean;
    evolutionLevel?: number;
    evolutionProgress?: number;
  }>(),
  {
    status: 'healthy',
    gridPosition: 0,
    isCenter: false,
    evolutionLevel: 1,
    evolutionProgress: 0,
  },
);

defineEmits<{
  click: [];
}>();

/** 确保进度在 0-100 */
const clampedProgress = computed<number>(() => Math.min(100, Math.max(0, props.evolutionProgress)));

/** 卦格色相关样式 */
const cellStyle = computed<Record<string, string>>(() => {
  if (!props.item) return {};
  return {
    '--cell-color': props.item.color,
    '--cell-glow': props.item.glowColor,
  };
});

/** 左侧装饰线样式 */
const accentStyle = computed<Record<string, string>>(() => {
  if (!props.item) return {};
  return {
    backgroundColor: props.item.color,
  };
});
</script>

<style scoped>
/* ═══════════════════════════════════════════
   卦格容器 — 纯 CSS 实现
   ═══════════════════════════════════════════ */
.bagua-cell {
  position: relative;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);

  /* 小米去线化 — 用 padding 替代分割线 */
  padding: 32px 24px;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;

  /* 呼吸般的过渡 */
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out),
    background-color var(--duration-normal) var(--ease-out),
    border-color var(--duration-normal) var(--ease-out);

  cursor: pointer;
  border: 1.5px solid transparent;
  overflow: hidden;

  /* 点击反馈 */
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

/* ────── Hover 效果 ────── */
.bagua-cell--clickable:hover {
  transform: translateY(-4px) scale(1.03);
  box-shadow: 0 4px 20px var(--cell-glow, rgba(0, 0, 0, 0.1));
  border-color: rgba(255, 103, 0, 0.15);
  background: var(--bg-hover);
}

.bagua-cell--clickable:active {
  transform: translateY(-2px) scale(1.01);
  transition: transform 100ms ease;
}

/* ────── 呼吸动画挂载 ────── */
/* animate-breathe 类由 animations.scss 全局定义，
   此处仅作用于健康状态的普通卦格 */

/* ────── 普通卦格 ────── */
.bagua-cell--status-healthy {
  /* 默认健康，无特殊样式 */
}

.bagua-cell--status-warning {
  border-color: rgba(255, 149, 0, 0.15);
  background: var(--status-warning-bg);
}

.bagua-cell--status-error {
  border-color: rgba(255, 59, 48, 0.15);
  background: var(--status-error-bg);
}

.bagua-cell--status-offline {
  opacity: 0.6;
}

/* ────── 中宫特殊样式 ────── */
.bagua-cell--center {
  background: var(--brand-gradient);
  color: var(--text-inverse);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  border: none;
  padding: 28px 24px;
}

.bagua-cell--center:hover {
  transform: translateY(-4px) scale(1.03);
  box-shadow: 0 6px 28px rgba(255, 103, 0, 0.3);
  border: none;
  background: var(--brand-gradient);
}

.bagua-cell--center__inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
}

/* ────── 状态指示器（右上角） ────── */
.bagua-cell__status {
  position: absolute;
  top: 14px;
  right: 14px;
}

/* ────── 左侧卦色装饰线 ────── */
.bagua-cell__accent {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 48px;
  border-radius: 0 2px 2px 0;
  transition: height var(--duration-normal) var(--ease-out);
}

.bagua-cell:hover .bagua-cell__accent {
  height: 60px;
}

/* ────── 卦符号 ────── */
.bagua-cell__symbol {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: 0.05em;
  color: var(--text-primary);
  transition: transform var(--duration-normal) var(--ease-out);
}

.bagua-cell:hover .bagua-cell__symbol {
  transform: scale(1.12);
}

.bagua-cell__symbol--center {
  font-size: 32px;
  color: var(--text-inverse);
}

/* ────── 卦名/标签 ────── */
.bagua-cell__label {
  font-size: var(--font-size-body, 16px);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.bagua-cell__label--center {
  font-size: var(--font-size-card-title, 18px);
  font-weight: 600;
  color: var(--text-inverse);
}

/* ────── 功能描述 ────── */
.bagua-cell__function {
  font-size: var(--font-size-caption, 14px);
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 0.03em;
}

/* ────── Emoji ────── */
.bagua-cell__emoji {
  font-size: 20px;
  line-height: 1;
  opacity: 0.6;
  transition: transform var(--duration-normal) var(--ease-out);
}

.bagua-cell:hover .bagua-cell__emoji {
  transform: scale(1.15);
  opacity: 0.8;
}

/* ────── 进化信息（中宫） ────── */
.bagua-cell__evolution {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 120px;
}

.bagua-cell__evolution-level {
  font-size: var(--font-size-caption, 14px);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.06em;
}

.bagua-cell__evolution-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 2px;
  overflow: hidden;
}

.bagua-cell__evolution-fill {
  height: 100%;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 2px;
  transition: width var(--duration-slow) var(--ease-out);
}

/* ────── 响应式 ────── */
@media (max-width: 1023px) {
  .bagua-cell {
    padding: 24px 16px;
    gap: 12px;
  }

  .bagua-cell__symbol {
    font-size: 24px;
  }
}

@media (max-width: 767px) {
  .bagua-cell {
    padding: 20px 16px;
    gap: 8px;
    border-radius: var(--radius-md);
  }

  .bagua-cell__symbol {
    font-size: 22px;
  }
}
</style>
