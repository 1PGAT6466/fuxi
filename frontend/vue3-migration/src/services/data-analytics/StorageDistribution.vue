<template>
  <!--
    伏羲 v2.1 — 存储分布图表
    饼图（按文件类型）+ 柱状图（按知识集合），使用 ECharts
  -->
  <div class="storage-dist">
    <div class="storage-header">
      <h3 class="storage-title">存储分布</h3>
    </div>

    <div v-if="loading" class="storage-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="error" class="storage-error">
      <el-result icon="error" title="加载失败" sub-title="无法获取存储分布数据">
        <template #extra>
          <el-button type="primary" size="small" @click="loadData">重试</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="fileTypeData.length === 0 && collectionData.length === 0" class="storage-empty">
      <el-empty description="暂无存储分布数据" :image-size="80" />
    </div>

    <div v-else class="storage-charts">
      <!-- 饼图：按文件类型 -->
      <div class="chart-panel">
        <h4 class="chart-panel__title">按文件类型</h4>
        <div ref="pieChartRef" class="chart-panel__container" />
      </div>

      <!-- 柱状图：按知识集合 -->
      <div class="chart-panel">
        <h4 class="chart-panel__title">按知识集合</h4>
        <div ref="barChartRef" class="chart-panel__container" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
import * as echarts from 'echarts/core';
import { PieChart, BarChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import * as analyticsApi from './api';
import type { FileTypeItem, CollectionStorageItem } from './types';

echarts.use([
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
]);

const loading = ref(true);
const error = ref(false);
const fileTypeData = ref<FileTypeItem[]>([]);
const collectionData = ref<CollectionStorageItem[]>([]);

const pieChartRef = ref<HTMLDivElement | null>(null);
const barChartRef = ref<HTMLDivElement | null>(null);

let pieInstance: echarts.ECharts | null = null;
let barInstance: echarts.ECharts | null = null;

// 八卦色系
const PIE_COLORS = ['#FF6700', '#5B8C5A', '#3A6B8C', '#C44B3C', '#A68A6B'];

async function loadData() {
  loading.value = true;
  error.value = false;
  try {
    const res = await analyticsApi.getStorageDist();
    fileTypeData.value = res.by_file_type;
    collectionData.value = res.by_collection;
    await nextTick();
    renderPieChart();
    renderBarChart();
  } catch {
    error.value = true;
    console.warn('[StorageDist] 加载存储分布数据失败');
  } finally {
    loading.value = false;
  }
}

function renderPieChart() {
  if (!pieChartRef.value || !fileTypeData.value.length) return;
  if (!pieInstance) {
    pieInstance = echarts.init(pieChartRef.value);
  }
  pieInstance.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} GB ({d}%)',
      backgroundColor: 'var(--fuxi-bg-card)',
      borderColor: 'var(--fuxi-border)',
      textStyle: { color: 'var(--fuxi-text)' },
    },
    legend: {
      bottom: 0,
      textStyle: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
    },
    color: PIE_COLORS,
    series: [
      {
        type: 'pie',
        radius: ['50%', '75%'],
        center: ['50%', '48%'],
        avoidLabelOverlap: false,
        padAngle: 2,
        itemStyle: {
          borderRadius: 6,
          borderColor: 'var(--fuxi-bg-card)',
          borderWidth: 3,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
          scaleSize: 8,
        },
        data: fileTypeData.value.map((d) => ({
          name: d.label,
          value: d.size,
        })),
      },
    ],
  });
}

function renderBarChart() {
  if (!barChartRef.value || !collectionData.value.length) return;
  if (!barInstance) {
    barInstance = echarts.init(barChartRef.value);
  }
  const names = collectionData.value.map((d) => d.collection);
  const sizes = collectionData.value.map((d) => d.size);
  const docCounts = collectionData.value.map((d) => d.document_count);

  barInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'var(--fuxi-bg-card)',
      borderColor: 'var(--fuxi-border)',
      textStyle: { color: 'var(--fuxi-text)' },
    },
    legend: {
      data: ['存储 (GB)', '文档数'],
      bottom: 0,
      textStyle: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '14%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        color: 'var(--fuxi-text-secondary)',
        fontSize: 10,
        rotate: 25,
      },
      axisLine: { lineStyle: { color: 'var(--fuxi-border)' } },
    },
    yAxis: [
      {
        type: 'value',
        name: 'GB',
        splitLine: { lineStyle: { color: 'var(--fuxi-border)', type: 'dashed' } },
        axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 10 },
      },
      {
        type: 'value',
        name: '篇',
        splitLine: { show: false },
        axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 10 },
      },
    ],
    series: [
      {
        name: '存储 (GB)',
        type: 'bar',
        data: sizes,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#FF6700' },
            { offset: 1, color: '#E55A2B' },
          ]),
          borderRadius: [6, 6, 0, 0],
        },
        barWidth: '50%',
      },
      {
        name: '文档数',
        type: 'bar',
        data: docCounts,
        yAxisIndex: 1,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#3A6B8C' },
            { offset: 1, color: '#2D5270' },
          ]),
          borderRadius: [6, 6, 0, 0],
        },
        barWidth: '50%',
      },
    ],
  });
}

function handleResize() {
  pieInstance?.resize();
  barInstance?.resize();
}

onMounted(() => {
  window.addEventListener('resize', handleResize);
  loadData();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  pieInstance?.dispose();
  barInstance?.dispose();
});
</script>

<style scoped lang="scss">
.storage-dist {
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--fuxi-radius);
  padding: 20px;
  margin-bottom: var(--space-lg);
}

.storage-header {
  margin-bottom: var(--space-md);
}

.storage-title {
  margin: 0;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--fuxi-text);
}

.storage-loading {
  padding: 24px;
  min-height: 300px;
}

.storage-error {
  padding: 16px;
}

.storage-empty {
  padding: 24px;
  display: flex;
  justify-content: center;
}

.storage-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

.chart-panel {
  min-height: 320px;

  &__title {
    margin: 0 0 var(--space-sm) 0;
    font-size: var(--font-size-caption);
    font-weight: 600;
    color: var(--fuxi-text-secondary);
    text-align: center;
  }

  &__container {
    width: 100%;
    height: 300px;
  }
}
</style>
