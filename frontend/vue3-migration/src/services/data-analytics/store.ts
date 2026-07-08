/**
 * 伏羲 v2.1 — 数据分析 Store
 * 管理统计缓存（5 分钟过期）+ 趋势时间范围选择
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { StatsResponse, TrendPeriod } from './types';

// ───── Store ─────

export const useDataAnalyticsStore = defineStore('data-analytics', () => {
  // 统计数据缓存
  const statsCache = ref<StatsResponse | null>(null);
  const statsCacheTime = ref<number>(0);
  const STATS_CACHE_MS = 5 * 60 * 1000; // 5 分钟

  // 趋势时间范围选择
  const trendPeriod = ref<TrendPeriod>('week');

  // 报表维度选择记忆
  const lastReportDimensions = ref<string[]>([]);

  // ───── Getters ─────

  /** 统计数据是否在缓存有效期 */
  const isStatsCacheValid = computed(() => {
    return statsCache.value && Date.now() - statsCacheTime.value < STATS_CACHE_MS;
  });

  // ───── Actions ─────

  /** 设置统计数据缓存 */
  function setStatsCache(data: StatsResponse): void {
    statsCache.value = data;
    statsCacheTime.value = Date.now();
  }

  /** 清除统计数据缓存 */
  function clearStatsCache(): void {
    statsCache.value = null;
    statsCacheTime.value = 0;
  }

  /** 设置趋势时间范围 */
  function setTrendPeriod(period: TrendPeriod): void {
    trendPeriod.value = period;
  }

  /** 记录报表维度选择 */
  function setReportDimensions(dimensions: string[]): void {
    lastReportDimensions.value = dimensions;
  }

  return {
    statsCache,
    statsCacheTime,
    trendPeriod,
    lastReportDimensions,
    isStatsCacheValid,
    setStatsCache,
    clearStatsCache,
    setTrendPeriod,
    setReportDimensions,
  };
});
