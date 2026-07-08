<template>
  <!--
    伏羲 v2.1 — 趋势图表
    查询趋势折线图/柱状图（日/周/月切换）
    使用 ECharts，显示多条趋势线（查询量/文档量/用户活跃度）
  -->
  <div class="trend-chart">
    <div class="trend-header">
      <h3 class="trend-title">趋势分析</h3>
      <div class="trend-controls">
        <el-radio-group v-model="currentPeriod" size="small" @change="handlePeriodChange">
          <el-radio-button value="day">日</el-radio-button>
          <el-radio-button value="week">周</el-radio-button>
          <el-radio-button value="month">月</el-radio-button>
        </el-radio-group>
        <el-button-group size="small">
          <el-button
            :type="chartType === 'line' ? 'primary' : 'default'"
            @click="chartType = 'line'"
          >
            折线图
          </el-button>
          <el-button :type="chartType === 'bar' ? 'primary' : 'default'" @click="chartType = 'bar'">
            柱状图
          </el-button>
        </el-button-group>
      </div>
    </div>

    <div v-if="loading" class="trend-chart__skeleton">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="error" class="trend-chart__error">
      <el-result icon="error" title="加载失败" sub-title="无法获取趋势数据">
        <template #extra>
          <el-button type="primary" size="small" @click="loadData">重试</el-button>
        </template>
      </el-result>
    </div>
    <div v-else-if="chartData.length === 0" class="trend-chart__empty">
      <el-empty description="暂无趋势数据" :image-size="80" />
    </div>
    <div v-else ref="chartRef" class="trend-chart__container" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as echarts from 'echarts/core';
import { LineChart, BarChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import * as analyticsApi from './api';
import { useDataAnalyticsStore } from './store';
import type { TrendPoint, TrendPeriod } from './types';

echarts.use([
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
]);

const store = useDataAnalyticsStore();

// 状态
const chartRef = ref<HTMLDivElement | null>(null);
const currentPeriod = ref<TrendPeriod>(store.trendPeriod);
const chartType = ref<'line' | 'bar'>('line');
const chartData = ref<TrendPoint[]>([]);
const loading = ref(false);
const error = ref(false);
let chartInstance: echarts.ECharts | null = null;

// 加载数据
async function loadData() {
  loading.value = true;
  error.value = false;
  try {
    const res = await analyticsApi.getTrends(currentPeriod.value);
    chartData.value = res.data;
    await nextTick();
    renderChart();
  } catch {
    error.value = true;
    console.warn('[TrendChart] 加载趋势数据失败');
  } finally {
    loading.value = false;
  }
}

function handlePeriodChange() {
  store.setTrendPeriod(currentPeriod.value);
  loadData();
}

// ECharts 配置
function getChartOption() {
  const dates = chartData.value.map((d) => d.date);
  const seriesColors = ['#FF6700', '#5B8C5A', '#3A6B8C'];
  const seriesNames = ['查询量', '文档量', '用户活跃度'];
  const seriesKeys: (keyof TrendPoint)[] = ['queries', 'documents', 'active_users'];

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'var(--fuxi-bg-card)',
      borderColor: 'var(--fuxi-border)',
      textStyle: { color: 'var(--fuxi-text)' },
    },
    legend: {
      data: seriesNames,
      bottom: 0,
      textStyle: { color: 'var(--fuxi-text-secondary)' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '12%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'var(--fuxi-border)' } },
      axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'var(--fuxi-border)', type: 'dashed' } },
      axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
    },
    series: seriesKeys.map((key, i) => ({
      name: seriesNames[i],
      type: chartType.value,
      data: chartData.value.map((d) => d[key]),
      smooth: true,
      itemStyle: { color: seriesColors[i] },
      areaStyle:
        chartType.value === 'line'
          ? {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: seriesColors[i] + '30' },
                { offset: 1, color: seriesColors[i] + '05' },
              ]),
            }
          : undefined,
    })),
  };
}

function renderChart() {
  if (!chartRef.value) return;
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }
  chartInstance.setOption(getChartOption());
}

// 窗口大小变化时重绘
function handleResize() {
  chartInstance?.resize();
}

onMounted(() => {
  window.addEventListener('resize', handleResize);
  loadData();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
});

watch(chartType, () => {
  if (chartData.value.length) renderChart();
});
</script>

<style scoped lang="scss">
.trend-chart {
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--fuxi-radius);
  padding: 20px;
  margin-bottom: var(--space-lg);
}

.trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
  flex-wrap: wrap;
  gap: var(--space-sm);

  @media (max-width: 600px) {
    flex-direction: column;
    align-items: flex-start;
  }
}

.trend-title {
  margin: 0;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--fuxi-text);
}

.trend-controls {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.trend-chart__container {
  width: 100%;
  height: 380px;
  min-height: 300px;
}

.trend-chart__skeleton {
  padding: 24px;
  min-height: 300px;
  display: flex;
  align-items: center;
}

.trend-chart__error {
  padding: 16px;
}

.trend-chart__empty {
  padding: 24px;
  display: flex;
  justify-content: center;
}
</style>
