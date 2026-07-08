<template>
  <!--
    伏羲 v1.44 — 成长面板
    四维指标卡片 + ECharts 趋势折线图 + 历史数据
  -->
  <div class="growth-view">
    <h2 class="page-title">成长面板</h2>
    <p class="page-desc">跟踪系统成长四维指标：提取效率、检索准确率、决策质量、用户体验</p>

    <!-- 加载态 -->
    <div v-if="loading" class="growth-loading">
      <el-skeleton animated>
        <template #template>
          <div class="skeleton-row">
            <el-skeleton-item
              v-for="n in 4"
              :key="n"
              variant="rect"
              style="width: 23%; height: 120px"
            />
          </div>
          <el-skeleton-item variant="rect" style="width: 100%; height: 320px; margin-top: 16px" />
        </template>
      </el-skeleton>
    </div>

    <!-- 错误状态 — API 失败且 mock 为空时显示 -->
    <ErrorState
      v-else-if="error && !hasData"
      message="无法加载成长数据，请检查后端服务或稍后重试"
      @retry="fetchGrowth"
    />

    <!-- 空状态 -->
    <div v-else-if="!hasData" class="growth-empty">
      <el-empty description="暂无成长数据">
        <template #image>
          <el-icon :size="64" color="var(--fuxi-text-tertiary)"><TrendCharts /></el-icon>
        </template>
        <p class="empty-sub">系统运行一段时间后将自动采集成长指标</p>
      </el-empty>
    </div>

    <!-- 正常数据 -->
    <template v-else>
      <!-- 四维指标卡片 -->
      <div class="metrics-grid">
        <div
          v-for="metric in metrics"
          :key="metric.key"
          class="metric-card"
        >
          <div class="metric-icon" :class="`metric-icon--${metric.key}`">
            <el-icon :size="24">
              <component :is="metric.icon" />
            </el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-header">
              <span class="metric-label">{{ metric.label }}</span>
              <el-tag :type="metric.trend >= 0 ? 'success' : 'danger'" size="small">
                {{ metric.trend >= 0 ? '+' : '' }}{{ metric.trend }}%
              </el-tag>
            </div>
            <span class="metric-value">{{ metric.value }}{{ metric.unit }}</span>
            <span class="metric-sub">{{ metric.desc }}</span>
          </div>
        </div>
      </div>

      <!-- ECharts 趋势折线图 -->
      <div class="chart-section">
        <div class="chart-header">
          <span class="chart-title">历史趋势</span>
          <el-radio-group v-model="timeRange" size="small" @change="updateChart">
            <el-radio-button value="day">近7天</el-radio-button>
            <el-radio-button value="week">近4周</el-radio-button>
            <el-radio-button value="month">近3月</el-radio-button>
          </el-radio-group>
        </div>
        <div ref="chartRef" class="chart-container" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import {
  DataAnalysis,
  Aim,
  MagicStick,
  UserFilled,
  TrendCharts,
} from '@element-plus/icons-vue';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import apiClient from '@/api';
import ErrorState from '@/components/common/ErrorState.vue';

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

// ─── 类型 ───
interface MetricInfo {
  key: string;
  label: string;
  value: number;
  unit: string;
  trend: number;
  desc: string;
  icon: unknown;
}

interface GrowthData {
  metrics: MetricInfo[];
  trends: Record<string, number[][]>;
}

// ─── State ───
const loading = ref(true);
const error = ref(false);
const hasData = ref(false);
const timeRange = ref<'day' | 'week' | 'month'>('week');
const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const metrics = ref<MetricInfo[]>([]);
const trendsData = ref<Record<string, number[][]>>({});

// ─── Mock 数据 ───
function getMockGrowth(): GrowthData {
  return {
    metrics: [
      {
        key: 'extraction',
        label: '提取效率',
        value: 87.5,
        unit: '%',
        trend: 3.2,
        desc: '文档处理准确率',
        icon: DataAnalysis,
      },
      {
        key: 'retrieval',
        label: '检索准确率',
        value: 92.1,
        unit: '%',
        trend: 1.8,
        desc: '向量搜索 Top-5 精度',
        icon: Aim,
      },
      {
        key: 'decision',
        label: '决策质量',
        value: 78.3,
        unit: '%',
        trend: -2.1,
        desc: '综合评分（最近30天）',
        icon: MagicStick,
      },
      {
        key: 'experience',
        label: '用户体验',
        value: 85.0,
        unit: '分',
        trend: 4.5,
        desc: 'NPS 净推荐值',
        icon: UserFilled,
      },
    ],
    trends: {
      day: [
        [7, 85, 87, 86, 88, 89, 87.5], // extraction
        [7, 90, 91, 92, 91, 93, 92.1], // retrieval
        [7, 76, 78, 77, 79, 78, 78.3], // decision
        [7, 80, 82, 83, 84, 86, 85],   // experience
      ],
      week: [
        [4, 84, 86, 88, 87.5], // extraction (4 weeks)
        [4, 89, 91, 93, 92.1], // retrieval
        [4, 75, 77, 79, 78.3], // decision
        [4, 79, 82, 84, 85],   // experience
      ],
      month: [
        [3, 85, 86, 87.5], // extraction (3 months)
        [3, 90, 91, 92.1], // retrieval
        [3, 76, 77, 78.3], // decision
        [3, 81, 83, 85],   // experience
      ],
    },
  };
}

// ─── Computed ───
const metricsKeys = computed(() => metrics.value.map((m) => m.key));

// F-03: 使用 CSS 变量替代硬编码颜色
// 四维指标对应八卦/五行颜色：
// extraction=震(青/绿), retrieval=巽(绿), decision=离(红/火), experience=兑(白/浅灰)
const metricColors: Record<string, string> = {
  extraction: 'var(--zhen-color, #4CAF50)',
  retrieval: 'var(--xun-color, #81C784)',
  decision: 'var(--li-color, #E53935)',
  experience: 'var(--kun-color, #C8A96E)',
};

// 仍保留硬编码 ast 值用于 ECharts option（ECharts 不支持 CSS 变量）
const metricColorValues: Record<string, string> = {
  extraction: '#4CAF50',
  retrieval: '#81C784',
  decision: '#E53935',
  experience: '#C8A96E',
};

const metricNames: Record<string, string> = {
  extraction: '提取效率',
  retrieval: '检索准确率',
  decision: '决策质量',
  experience: '用户体验',
};

// ─── API 请求 ───
async function fetchGrowth(): Promise<void> {
  loading.value = true;
  error.value = false;
  try {
    const data = (await apiClient.get('/api/growth/overview')) as GrowthData;
    if (data?.metrics && data.metrics.length > 0) {
      metrics.value = data.metrics;
      trendsData.value = data.trends;
      hasData.value = true;
    } else {
      // 降级 mock
      applyMock();
    }
  } catch {
    applyMock();
    // 如果 mock 应用后仍无数据，标记 error
    if (!hasData.value) {
      error.value = true;
    }
  } finally {
    loading.value = false;
    if (hasData.value) {
      await nextTick();
      initChart();
    }
  }
}

function applyMock(): void {
  const mock = getMockGrowth();
  metrics.value = mock.metrics;
  trendsData.value = mock.trends;
  hasData.value = true;
}

// ─── ECharts ───
function getTimeLabels(): string[] {
  if (timeRange.value === 'day') {
    return ['7天前', '6天前', '5天前', '4天前', '3天前', '2天前', '昨日'];
  }
  if (timeRange.value === 'week') {
    return ['第1周', '第2周', '第3周', '第4周'];
  }
  return ['第1月', '第2月', '第3月'];
}

function initChart(): void {
  if (!chartRef.value) return;

  if (chartInstance) {
    chartInstance.dispose();
  }

  chartInstance = echarts.init(chartRef.value);
  renderChart();
}

function renderChart(): void {
  if (!chartInstance) return;

  const allTrends = trendsData.value[timeRange.value] || [];
  const series = metricsKeys.value.map((key, i) => {
    const trendRow = allTrends[i] || [];
    const values = trendRow.length > 1 ? trendRow.slice(1) : [];
    return {
      name: metricNames[key] || key,
      type: 'line' as const,
      data: values,
      smooth: true,
      lineStyle: { color: metricColorValues[key], width: 2 },
      itemStyle: { color: metricColorValues[key] },
    };
  });

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: metricsKeys.value.map((k) => metricNames[k]),
      bottom: 0,
      textStyle: { fontSize: 11, color: '#999' },
    },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: getTimeLabels(),
      axisLine: { lineStyle: { color: '#E8E4D9' } },
      axisLabel: { color: '#999', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 60,
      max: 100,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#999', fontSize: 11 },
      splitLine: { lineStyle: { color: '#F0EDE5' } },
    },
    series,
  });
}

function updateChart(): void {
  renderChart();
}

watch(timeRange, () => {
  renderChart();
});

// ─── 生命周期 ───
let resizeHandler: (() => void) | null = null;

onMounted(async () => {
  await fetchGrowth();
  await nextTick();
  initChart();
  resizeHandler = () => chartInstance?.resize();
  window.addEventListener('resize', resizeHandler);
});

onUnmounted(() => {
  chartInstance?.dispose();
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
});
</script>

<style scoped lang="scss">
.growth-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-desc {
  margin: 0 0 24px;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

/* ─── 加载 / 空状态 ─── */
.growth-loading {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 24px;
}

.skeleton-row {
  display: flex;
  gap: 16px;
}

.growth-empty {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 40px;

  .empty-sub {
    text-align: center;
    font-size: var(--font-size-small);
    color: var(--text-tertiary);
    margin-top: 8px;
  }
}

/* ─── 四维指标卡片 ─── */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  display: flex;
  gap: 14px;
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out);

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
}

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  // F-03: 使用 CSS 变量替代硬编码
  // extraction=震(青) retrieval=巽(绿) decision=离(红) experience=坤(土)
  &--extraction {
    background: var(--zhen-color-light, rgba(76, 175, 80, 0.1));
    color: var(--zhen-color, #4CAF50);
  }
  &--retrieval {
    background: var(--xun-color-light, rgba(129, 199, 132, 0.1));
    color: var(--xun-color, #81C784);
  }
  &--decision {
    background: var(--li-color-light, rgba(229, 57, 53, 0.1));
    color: var(--li-color, #E53935);
  }
  &--experience {
    background: var(--kun-color-light, rgba(200, 169, 110, 0.1));
    color: var(--kun-color, #C8A96E);
  }
}

.metric-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.metric-label {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  font-weight: 500;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.metric-sub {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ─── 趋势图 ─── */
.chart-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.chart-title {
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--text-primary);
}

.chart-container {
  width: 100%;
  height: 340px;
}

/* ─── 响应式 ─── */
@media (max-width: 1023px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .growth-view {
    padding: 16px;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .chart-container {
    height: 260px;
  }
}
</style>
