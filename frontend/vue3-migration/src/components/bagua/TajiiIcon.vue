<template>
  <button
    class="taiji-icon-wrapper"
    :class="[`taiji-icon--${size}`, { 'taiji-icon--clickable': clickable }]"
    :aria-label="isYang ? '点击切换为阴模式' : '点击切换为阳模式'"
    :title="isYang ? '切换至阴模式' : '切换至阳模式'"
    @click="handleClick"
  >
    <svg
      class="taiji-icon"
      :class="{ 'taiji-icon--spinning': spinning }"
      :width="pixelSize"
      :height="pixelSize"
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      role="img"
    >
      <!-- 外圆 -->
      <circle cx="32" cy="32" r="31" :fill="bgColor" :stroke="strokeColor" stroke-width="2" />

      <!-- 太极图案 -->
      <g>
        <!-- 左半：阳（主色） -->
        <path
          d="M32,1 A31,31 0 0,1 32,63 A15.5,15.5 0 0,1 32,32 A15.5,15.5 0 0,0 32,1 Z"
          :fill="activeColor"
        />
        <!-- 右半：阴（浅色） -->
        <path
          d="M32,1 A31,31 0 0,0 32,63 A15.5,15.5 0 0,0 32,32 A15.5,15.5 0 0,1 32,1 Z"
          :fill="inactiveColor"
        />
      </g>

      <!-- 上方小圆（阴中之阳 / 阳中之阴） -->
      <circle cx="32" cy="16.5" r="5.5" :fill="activeColor" />
      <circle cx="32" cy="16.5" r="2.5" :fill="inactiveColor" />

      <!-- 下方小圆（阳中之阴 / 阴中之阳） -->
      <circle cx="32" cy="47.5" r="5.5" :fill="inactiveColor" />
      <circle cx="32" cy="47.5" r="2.5" :fill="activeColor" />
    </svg>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useThemeStore } from '@/stores/theme';

const props = withDefaults(
  defineProps<{
    /** 尺寸预设: sm/md/lg */
    size?: 'sm' | 'md' | 'lg';
    /** 是否旋转动画（60s 自转一圈） */
    spinning?: boolean;
    /** 是否可点击切换阴阳模式 */
    clickable?: boolean;
    /** 阳色（主品牌色），不传则使用 Pinia store 中的 primaryColor */
    activeColor?: string;
    /** 阴色（浅色），不传则自动根据模式选择 */
    inactiveColor?: string;
    /** 外圈背景 */
    bgColor?: string;
    /** 外圈描边 */
    strokeColor?: string;
    /** 自定义像素尺寸（覆盖 size 预设） */
    customSize?: number;
  }>(),
  {
    size: 'md',
    spinning: true,
    clickable: true,
    bgColor: 'transparent',
    strokeColor: 'rgba(255,255,255,0.2)',
  },
);

const emit = defineEmits<{
  (e: 'toggle', mode: 'yang' | 'yin'): void;
}>();

const themeStore = useThemeStore();

/** 尺寸映射 */
const sizeMap: Record<string, number> = {
  sm: 32,
  md: 48,
  lg: 72,
};

/** 实际像素尺寸 */
const pixelSize = computed(() => props.customSize ?? sizeMap[props.size]);

/** 是否为阳模式 */
const isYang = computed(() => themeStore.isYang);

/** 点击切换 */
function handleClick(): void {
  if (!props.clickable) return;
  themeStore.toggleMode();
  emit('toggle', themeStore.mode);
}
</script>

<style scoped>
.taiji-icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  cursor: default;
  padding: 0;
  border-radius: 50%;
  transition: box-shadow var(--duration-normal, 350ms) ease;
}

/* 尺寸预设 */
.taiji-icon--sm {
  width: 32px;
  height: 32px;
}

.taiji-icon--md {
  width: 48px;
  height: 48px;
}

.taiji-icon--lg {
  width: 72px;
  height: 72px;
}

/* 可点击状态 */
.taiji-icon--clickable {
  cursor: pointer;
}

/* 悬停发光效果 */
.taiji-icon--clickable:hover {
  box-shadow: 0 0 20px rgba(255, 103, 0, 0.35);
}

.taiji-icon--clickable:active {
  box-shadow: 0 0 12px rgba(255, 103, 0, 0.25);
}

/* 太极旋转动画 — 60s 自转一圈 */
.taiji-icon--spinning {
  animation: taiji-rotate 60s linear infinite;
  transform-origin: center center;
}

@keyframes taiji-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* SVG 内联样式 */
.taiji-icon {
  display: block;
  flex-shrink: 0;
}
</style>
