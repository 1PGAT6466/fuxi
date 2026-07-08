<template>
  <div class="bagua-grid" role="grid" aria-label="伏羲八卦九宫格">
    <!-- 按后天八卦位置 1-9 渲染 -->
    <template v-for="pos in 9" :key="pos">
      <!-- 中宫 (position === 5) 特殊渲染 -->
      <BaguaCell
        v-if="pos === 5"
        :item="zhonggongItem"
        :status="getCellStatus(zhonggongItem.id)"
        :grid-position="pos"
        :is-center="true"
        :evolution-level="evolutionLevel"
        :evolution-progress="evolutionProgress"
        @click="handleCellClick(zhonggongItem)"
      />
      <!-- 普通卦格 -->
      <BaguaCell
        v-else
        :item="getCellItem(pos)"
        :status="getCellStatus(getCellItem(pos)?.id ?? '')"
        :grid-position="pos"
        @click="handleCellClick(getCellItem(pos)!)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import BaguaCell from './BaguaCell.vue';
import {
  BAGUA_GRID,
  ZHONGGONG,
  type BaguaItem,
  type BaguaStatus,
  type TrigramStatus,
  type ZhonggongData,
} from '@/constants/bagua';

const props = withDefaults(
  defineProps<{
    /** 八卦状态映射 */
    statuses?: BaguaStatus[];
    /** 中宫进化等级 */
    evolutionLevel?: number;
    /** 中宫进化进度 (0-100) */
    evolutionProgress?: number;
  }>(),
  {
    statuses: () => [],
    evolutionLevel: 1,
    evolutionProgress: 0,
  },
);

const router = useRouter();

/** 中宫数据 */
const zhonggongItem = computed<ZhonggongData>(() => ZHONGGONG);

/** 按位置获取卦项 */
function getCellItem(pos: number): BaguaItem | null {
  return BAGUA_GRID[pos] ?? null;
}

/** 按卦 ID 获取状态 */
function getCellStatus(trigramId: string): TrigramStatus {
  const found = props.statuses.find((s) => s.trigramId === trigramId);
  return found?.status ?? 'healthy';
}

/** 点击卦格导航 */
function handleCellClick(item: BaguaItem): void {
  router.push(item.route);
}
</script>

<style scoped>
.bagua-grid {
  /* 纯 CSS Grid — 零 JS 布局计算 */
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
  gap: 24px;
  padding: 32px;
  max-width: 960px;
  margin: 0 auto;
  min-height: 640px;
  align-content: center;
  justify-content: center;
}

/* ────── 响应式 ────── */
/* 平板：缩小间距 */
@media (max-width: 1023px) {
  .bagua-grid {
    gap: 16px;
    padding: 24px 16px;
    min-height: 520px;
  }
}

/* 手机：单列 */
@media (max-width: 767px) {
  .bagua-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
    gap: 12px;
    padding: 16px;
    min-height: auto;
    max-width: 400px;
  }
}
</style>
