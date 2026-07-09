<template>
  <!--
    伏羲 v2.1 — 系统仪表板
    4 核心指标卡片 + 服务健康列表 + 最近操作日志 + API 调用量趋势图（ECharts）
  -->
  <div class="dashboard-view">
    <h2 class="page-title">系统仪表板</h2>

    <!-- 4 个核心指标卡片 -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon metric-icon--api">
          <el-icon :size="22"><Connection /></el-icon>
        </div>
        <div class="metric-body">
          <span class="metric-value">{{ formatNumber(dashboard.api_calls) }}</span>
          <span class="metric-label">API 调用量</span>
          <span class="metric-sub">过去 24 小时</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon metric-icon--storage">
          <el-icon :size="22"><Coin /></el-icon>
        </div>
        <div class="metric-body">
          <span class="metric-value">{{ dashboard.storage_usage }}</span>
          <span class="metric-label">存储用量</span>
          <span class="metric-sub">剩余 {{ dashboard.storage_remaining }}</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon metric-icon--users">
          <el-icon :size="22"><User /></el-icon>
        </div>
        <div class="metric-body">
          <span class="metric-value">{{ dashboard.active_users }}</span>
          <span class="metric-label">活跃用户数</span>
          <span class="metric-sub">总共 {{ dashboard.total_users }} 用户</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon metric-icon--health">
          <el-icon :size="22"><Monitor /></el-icon>
        </div>
        <div class="metric-body">
          <span class="metric-value" :class="healthClass">{{ healthLabel }}</span>
          <span class="metric-label">服务健康状态</span>
          <span class="metric-sub"
            >{{ healthyCount }}/{{ dashboard.services?.length || 0 }} 正常</span
          >
        </div>
      </div>
    </div>

    <!-- 服务健康列表 + API 趋势图 -->
    <div class="dashboard-grid">
      <!-- 服务健康列表 -->
      <div class="dashboard-card">
        <h3 class="card-title">
          <el-icon :size="16"><Monitor /></el-icon>
          服务健康
        </h3>
        <div class="service-list">
          <div v-for="svc in dashboard.services" :key="svc.name" class="service-item">
            <span class="status-dot" :class="`status-dot--${svc.status}`" />
            <span class="service-name">{{ svc.name }}</span>
            <el-tag :type="statusTagType(svc.status)" size="small" class="service-tag">
              {{ statusLabel(svc.status) }}
            </el-tag>
            <span class="service-uptime">{{ svc.uptime }}</span>
          </div>
          <div v-if="(dashboard.services?.length || 0) === 0" class="service-empty">
            暂无服务数据
          </div>
        </div>
      </div>

      <!-- 最近操作日志 -->
      <div class="dashboard-card">
        <h3 class="card-title">
          <el-icon :size="16"><Clock /></el-icon>
          最近操作日志
        </h3>
        <div class="log-list">
          <div v-for="log in dashboard.recent_logs" :key="log.id" class="log-item">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-user">{{ log.user }}</span>
            <span class="log-action">{{ log.action }}</span>
            <el-tag
              :type="log.result === '成功' ? 'success' : 'danger'"
              size="small"
              class="log-result"
            >
              {{ log.result }}
            </el-tag>
          </div>
          <div v-if="(dashboard.recent_logs?.length || 0) === 0" class="log-empty">
            暂无操作日志
          </div>
        </div>
      </div>
    </div>

    <!-- API 调用量趋势图 -->
    <div class="dashboard-card dashboard-card--full">
      <div class="card-header">
        <h3 class="card-title">
          <el-icon :size="16"><TrendCharts /></el-icon>
          API 调用量趋势
        </h3>
        <el-radio-group v-model="timeRange" size="small">
          <el-radio-button value="hour">按小时</el-radio-button>
          <el-radio-button value="day">按天</el-radio-button>
          <el-radio-button value="week">按周</el-radio-button>
        </el-radio-group>
      </div>
      <div ref="chartRef" class="chart-container" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { Connection, Coin, User, Monitor, Clock, TrendCharts } from '@element-plus/icons-vue';
// P0-3: 按需导入 echarts
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);
import apiClient from '@/api';

// ─── 类型 ───
interface ServiceInfo {
  name: string;
  status: 'online' | 'degraded' | 'offline';
  uptime: string;
}

interface LogEntry {
  id: string;
  time: string;
  user: string;
  action: string;
  result: string;
}

interface DashboardData {
  api_calls: number;
  storage_usage: string;
  storage_remaining: string;
  active_users: number;
  total_users: number;
  services: ServiceInfo[];
  recent_logs: LogEntry[];
  api_trend: Record<string, number[]>;
}

// ─── State ───
const chartRef = ref<HTMLDivElement | null>(null);
const timeRange = ref<'hour' | 'day' | 'week'>('day');
let chartInstance: echarts.ECharts | null = null;

const dashboard = ref<DashboardData>({
  api_calls: 0,
  storage_usage: '0 GB',
  storage_remaining: '0 GB',
  active_users: 0,
  total_users: 0,
  services: [],
  recent_logs: [],
  api_trend: {},
});

// ─── Computed ───
const healthyCount = computed(
  () => dashboard.value.services?.filter((s) => s.status === 'online').length || 0,
);

const allOnline = computed(
  () =>
    dashboard.value.services?.length > 0 && healthyCount.value === dashboard.value.services.length,
);

const healthLabel = computed(() => {
  if (dashboard.value.services.length === 0) return '—';
  return allOnline.value ? '健康' : '降级';
});

const healthClass = computed(() => (allOnline.value ? 'text-success' : 'text-warning'));

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'online':
      return 'success';
    case 'degraded':
      return 'warning';
    case 'offline':
      return 'danger';
    default:
      return 'info';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'online':
      return '在线';
    case 'degraded':
      return '降级';
    case 'offline':
      return '离线';
    default:
      return status;
  }
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

// ─── Mock 数据 ───
function getMockDashboard(): DashboardData {
  return {
    api_calls: 128450,
    storage_usage: '24.6 GB',
    storage_remaining: '475.4 GB',
    active_users: 86,
    total_users: 342,
    services: [
      { name: 'API Gateway', status: 'online', uptime: '15天 6小时' },
      { name: 'LLM Service', status: 'online', uptime: '15天 6小时' },
      { name: 'Vector Store', status: 'online', uptime: '12天 3小时' },
      { name: 'RAG Pipeline', status: 'degraded', uptime: '7天 18小时' },
      { name: 'Auth Service', status: 'online', uptime: '15天 6小时' },
      { name: 'File Storage', status: 'offline', uptime: '—' },
    ],
    recent_logs: [
      { id: '1', time: '14:32:15', user: 'admin', action: '更新功能开关 chat_v2', result: '成功' },
      {
        id: '2',
        time: '13:18:42',
        user: 'zhangsan',
        action: '上传文档 技术方案_v3',
        result: '成功',
      },
      { id: '3', time: '12:05:09', user: 'lisi', action: '创建评测任务 Eval-042', result: '失败' },
      {
        id: '4',
        time: '10:47:33',
        user: 'admin',
        action: '修改用户角色 wangwu → 管理员',
        result: '成功',
      },
      { id: '5', time: '09:15:20', user: 'system', action: '自动索引任务完成', result: '成功' },
      { id: '6', time: '08:00:00', user: 'system', action: '定时备份数据库', result: '成功' },
    ],
    api_trend: {
      hour: [
        320, 280, 450, 520, 680, 710, 890, 760, 920, 850, 780, 650, 580, 620, 710, 830, 950, 1020,
        890, 760, 680, 550, 420, 380,
      ],
      day: [
        12800, 14500, 13200, 15800, 16200, 14900, 17200, 16800, 15500, 14300, 15200, 16100, 14800,
        17000,
      ],
      week: [89000, 95000, 88000, 102000],
    },
  };
}

// ─── API 请求 ───
async function fetchDashboard(): Promise<void> {
  try {
    // 并行请求多个 API
    const [healthData, usersData, growthData] = await Promise.all([
      apiClient.get('/api/health').catch(() => null),
      apiClient.get('/api/admin/users').catch(() => null),
      apiClient.get('/api/growth/overview').catch(() => null),
    ]);

    // 合并数据到仪表板
    const merged: DashboardData = getMockDashboard(); // 先填充基础 mock 结构

    if (healthData) {
      const h = healthData as Record<string, unknown>;
      merged.services = (h.services as ServiceInfo[]) || [];
      if (h.bagua) {
        // 从八卦状态构建服务列表
        const bagua = h.bagua as Record<string, string>;
        const guaMap: Record<string, string> = {
          qian: '乾·大脑 / AI 对话', kun: '坤·脾 / 知识库', zhen: '震·肝 / 文档消化',
          xun: '巽·肺 / 知识检索', kan: '坎·肾 / 数据精炼', li: '离·心 / 决策引擎',
          gen: '艮·皮肤 / 系统守卫', dui: '兑·鼻 / 响应呈现',
        };
        merged.services = Object.entries(bagua).map(([key, status]) => ({
          name: guaMap[key] || key,
          status: status === 'healthy' ? 'online' : status === 'warning' ? 'degraded' : 'offline',
          uptime: status === 'healthy' ? '正常' : status,
        }));
      }
    }

    if (usersData) {
      const u = usersData as { total?: number; users?: unknown[] };
      merged.total_users = u.total || (u.users || []).length || 0;
    }

    if (growthData) {
      const g = growthData as { summary?: { total_queries?: number } };
      if (g.summary?.total_queries !== undefined) {
        merged.api_calls = g.summary.total_queries;
      }
    }

    dashboard.value = merged;
    await nextTick();
    initChart();
  } catch (err) {
    console.warn('[Dashboard] API 不可用，使用 mock 数据', err);
    dashboard.value = getMockDashboard();
    await nextTick();
    initChart();
  }
}

// ─── ECharts ───
function getTimeLabels(): string[] {
  if (timeRange.value === 'hour') {
    return Array.from({ length: 24 }, (_, i) => `${i}时`);
  }
  if (timeRange.value === 'day') {
    return Array.from({ length: 14 }, (_, i) => `${i + 1}日`);
  }
  return ['第1周', '第2周', '第3周', '第4周'];
}

function initChart(): void {
  if (!chartRef.value) return;

  if (chartInstance) {
    chartInstance.dispose();
  }

  chartInstance = echarts.init(chartRef.value);
  const data = dashboard.value.api_trend[timeRange.value] || [];

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: getTimeLabels(),
      axisLine: { lineStyle: { color: '#E8E4D9' } }, // 米白配套网格线
      axisLabel: { color: '#999999', fontSize: 11 }, // 阴模式次要文字色
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#999999', fontSize: 11 }, // 阴模式次要文字色
      splitLine: { lineStyle: { color: '#F0EDE5' } }, // 阳模式边框亮色
    },
    series: [
      {
        name: 'API 调用量',
        type: 'line',
        data,
        smooth: true,
        lineStyle: { color: '#FF6700', width: 2 }, // 暖橙点缀色
        itemStyle: { color: '#FF6700' }, // 暖橙点缀色
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255,103,0,0.15)' },
            { offset: 1, color: 'rgba(255,103,0,0.01)' },
          ]),
        },
      },
    ],
  });
}

watch(timeRange, () => {
  nextTick(initChart);
});

// ─── 生命周期 ───
let resizeHandler: (() => void) | null = null;

onMounted(async () => {
  await fetchDashboard();
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
.dashboard-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 24px;
  font-size: var(--font-size-page-title);
  font-weight: 700;
  color: var(--text-primary);
}

/* ─── 指标卡片 ─── */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
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

  &--api {
    background: var(--kan-color-light);
    color: var(--kan-color);
  }
  &--storage {
    background: var(--kun-color-light);
    color: var(--kun-color);
  }
  &--users {
    background: var(--xun-color-light);
    color: var(--xun-color);
  }
  &--health {
    background: var(--zhen-color-light);
    color: var(--zhen-color);
  }
}

.metric-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;

  &.text-success {
    color: var(--status-healthy);
  }
  &.text-warning {
    color: var(--status-warning);
  }
}

.metric-label {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.metric-sub {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

/* ─── 双列布局 ─── */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.dashboard-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;

  &--full {
    grid-column: 1 / -1;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

/* ─── 服务列表 ─── */
.service-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.service-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
}

.service-name {
  flex: 1;
  font-size: var(--font-size-caption);
  font-weight: 500;
  color: var(--text-primary);
}

.service-tag {
  flex-shrink: 0;
}

.service-uptime {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  min-width: 80px;
  text-align: right;
}

.service-empty {
  text-align: center;
  padding: 32px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 日志列表 ─── */
.log-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 300px;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--bg-divider);
    border-radius: 4px;
  }
}

.log-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-caption);
}

.log-time {
  color: var(--text-tertiary);
  font-family: monospace;
  min-width: 56px;
}

.log-user {
  font-weight: 500;
  color: var(--text-primary);
  min-width: 60px;
}

.log-action {
  flex: 1;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-result {
  flex-shrink: 0;
}

.log-empty {
  text-align: center;
  padding: 32px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 图表 ─── */
.chart-container {
  width: 100%;
  height: 320px;
}

/* ─── 状态指示灯 ─── */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  &--online {
    background: var(--status-healthy);
    box-shadow: 0 0 6px rgba(52, 199, 89, 0.4);
  }
  &--degraded {
    background: var(--status-warning);
    box-shadow: 0 0 6px rgba(255, 149, 0, 0.4);
  }
  &--offline {
    background: var(--status-offline);
  }
}

/* ─── 响应式 ─── */
@media (max-width: 1023px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .dashboard-view {
    padding: 16px 12px;
  }
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
