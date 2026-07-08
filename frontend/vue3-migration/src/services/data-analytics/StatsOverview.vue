<template>
  <!--
    伏羲 v2.1 — 统计概览卡片
    4 个统计卡片：文档总数/用户数/向量数/存储用量
    每卡片显示数值 + 环比变化百分比 + 迷你趋势图
  -->
  <div class="stats-overview">
    <div
      v-for="(stat, idx) in stats"
      :key="stat.label"
      class="stat-card"
      :class="`stat-card--${cards[idx].colorClass}`"
    >
      <div class="stat-card__header">
        <div class="stat-card__icon" :style="{ background: cards[idx].iconBg }">
          <el-icon :size="20">
            <component :is="cards[idx].icon" />
          </el-icon>
        </div>
        <span class="stat-card__label">{{ stat.label }}</span>
      </div>

      <div class="stat-card__value">
        <span class="stat-card__number">{{ formatNumber(stat.value) }}</span>
        <span class="stat-card__unit">{{ stat.unit }}</span>
      </div>

      <div class="stat-card__footer">
        <span class="stat-card__change" :class="stat.change >= 0 ? 'trend--up' : 'trend--down'">
          <el-icon :size="14">
            <CaretTop v-if="stat.change >= 0" />
            <CaretBottom v-else />
          </el-icon>
          {{ Math.abs(stat.change) }}%
        </span>
        <span class="stat-card__change-label">环比</span>
      </div>

      <!-- 迷你趋势图 -->
      <div ref="sparklineRefs" class="stat-card__sparkline">
        <canvas
          :ref="(el) => setSparklineRef(idx, el)"
          width="120"
          height="36"
          class="sparkline-canvas"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, type Component } from 'vue';
import {
  Document,
  UserFilled,
  DataBoard,
  Coin,
  CaretTop,
  CaretBottom,
} from '@element-plus/icons-vue';
import type { StatItem } from './types';

const props = defineProps<{
  stats: StatItem[];
}>();

const sparklineRefs = ref<{ [key: number]: HTMLCanvasElement | null }>({});

function setSparklineRef(idx: number, el: unknown) {
  sparklineRefs.value[idx] = el as HTMLCanvasElement | null;
}

// 卡片配置
const cards = [
  { colorClass: 'docs', iconBg: 'var(--fuxi-primary-light)', icon: Document as Component },
  { colorClass: 'users', iconBg: 'var(--xun-color-light)', icon: UserFilled as Component },
  { colorClass: 'vectors', iconBg: 'var(--kan-color-light)', icon: DataBoard as Component },
  { colorClass: 'storage', iconBg: 'var(--li-color-light)', icon: Coin as Component },
];

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 10000) return (n / 10000).toFixed(1) + '万';
  if (n >= 1000) return n.toLocaleString('zh-CN');
  return n.toFixed(1);
}

// 绘制迷你趋势图
function drawSparkline(canvas: HTMLCanvasElement, data: number[]) {
  const ctx = canvas.getContext('2d');
  if (!ctx || !data.length) return;

  const dpr = window.devicePixelRatio || 1;
  const w = canvas.width / dpr;
  const h = canvas.height / dpr;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 4;

  const points = data.map((v, i) => ({
    x: padding + (i / (data.length - 1)) * (w - padding * 2),
    y: h - padding - ((v - min) / range) * (h - padding * 2),
  }));

  // 渐变填充
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, 'rgba(255, 103, 0, 0.15)');
  gradient.addColorStop(1, 'rgba(255, 103, 0, 0.01)');

  ctx.beginPath();
  ctx.moveTo(points[0].x, h - padding);
  for (const p of points) {
    ctx.lineTo(p.x, p.y);
  }
  ctx.lineTo(points[points.length - 1].x, h - padding);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // 线条
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.strokeStyle = 'var(--fuxi-primary)';
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

watch(
  () => props.stats,
  () => {
    setTimeout(() => {
      props.stats.forEach((stat, idx) => {
        const canvas = sparklineRefs.value[idx];
        if (canvas) drawSparkline(canvas, stat.trend);
      });
    }, 100);
  },
  { immediate: true },
);

onMounted(() => {
  setTimeout(() => {
    props.stats.forEach((stat, idx) => {
      const canvas = sparklineRefs.value[idx];
      if (canvas) drawSparkline(canvas, stat.trend);
    });
  }, 200);
});
</script>

<style scoped lang="scss">
.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-md);
  margin-bottom: var(--space-lg);

  @media (max-width: 1024px) {
    grid-template-columns: repeat(2, 1fr);
  }

  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
}

.stat-card {
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--fuxi-radius);
  padding: 20px;
  transition: box-shadow var(--duration-fast) var(--ease-out);
  display: flex;
  flex-direction: column;
  gap: 10px;

  &:hover {
    box-shadow: var(--fuxi-shadow);
  }
}

.stat-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-card__icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--fuxi-primary);
}

.stat-card__label {
  font-size: var(--font-size-caption);
  color: var(--fuxi-text-secondary);
  font-weight: 500;
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-card__number {
  font-size: 28px;
  font-weight: 700;
  color: var(--fuxi-text);
  font-variant-numeric: tabular-nums;
}

.stat-card__unit {
  font-size: var(--font-size-caption);
  color: var(--fuxi-text-secondary);
}

.stat-card__footer {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-card__change {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--font-size-small);
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;

  &.trend--up {
    color: var(--fuxi-success);
    background: rgba(52, 199, 89, 0.08);
  }

  &.trend--down {
    color: var(--fuxi-error);
    background: var(--fuxi-error-bg);
  }
}

.stat-card__change-label {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}

.stat-card__sparkline {
  display: flex;
  justify-content: center;
  margin-top: 2px;
}

.sparkline-canvas {
  width: 120px;
  height: 36px;
}
</style>
