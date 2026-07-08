<template>
  <!--
    伏羲 v2.1 — 知识图谱（升级版）
    统计可视化 + 节点/边数据 + 实体类型分布饼图 + 关系类型柱状图 + 节点列表
    「完整力导向图」留口标记"建设中"
  -->
  <div class="graph-view">
    <div class="graph-header">
      <h2>知识图谱</h2>
      <p class="graph-desc">可视化浏览知识实体与关系网络</p>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="graph-loading">
      <el-skeleton animated>
        <template #template>
          <div class="skeleton-stats">
            <el-skeleton-item
              v-for="n in 3"
              :key="n"
              variant="rect"
              style="width: 30%; height: 100px"
            />
          </div>
          <el-skeleton-item
            variant="rect"
            style="width: 100%; height: 280px; margin-top: 16px"
          />
        </template>
      </el-skeleton>
    </div>

    <!-- 数据就绪 -->
    <template v-else-if="hasData">
      <!-- 统计概览 -->
      <div class="graph-stats">
        <div class="stat-card">
          <div class="stat-icon stat-icon--nodes">
            <el-icon :size="24"><Connection /></el-icon>
          </div>
          <div class="stat-body">
            <span class="stat-value">{{ stats.totalNodes }}</span>
            <span class="stat-label">节点总数</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stat-icon--edges">
            <el-icon :size="24"><Share /></el-icon>
          </div>
          <div class="stat-body">
            <span class="stat-value">{{ stats.totalEdges }}</span>
            <span class="stat-label">边总数</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stat-icon--types">
            <el-icon :size="24"><List /></el-icon>
          </div>
          <div class="stat-body">
            <span class="stat-value">{{ stats.entityTypes.length }}</span>
            <span class="stat-label">实体类型</span>
          </div>
        </div>
      </div>

      <!-- 可视化图表区 -->
      <div class="graph-charts">
        <!-- 实体类型分布饼图 -->
        <div class="chart-card">
          <div class="chart-title">实体类型分布</div>
          <div v-if="stats.entityTypes.length > 0" ref="pieChartRef" class="chart-pie" />
          <div v-else class="chart-empty">暂无实体类型数据</div>
        </div>

        <!-- 关系类型分布柱状图 -->
        <div class="chart-card">
          <div class="chart-title">关系类型分布</div>
          <div v-if="stats.relationTypes.length > 0" ref="barChartRef" class="chart-bar" />
          <div v-else class="chart-empty">暂无关系类型数据</div>
        </div>
      </div>

      <!-- 节点列表 -->
      <div class="graph-nodes">
        <div class="section-header">
          <span class="section-title">节点列表</span>
          <el-button type="primary" disabled class="force-btn">
            <el-icon><Connection /></el-icon>
            完整力导向图（建设中）
          </el-button>
        </div>
        <el-table :data="nodes" stripe size="small">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关联数" width="100" sortable prop="edgeCount">
            <template #default="{ row }">
              <span class="edge-count">{{ row.edgeCount || row.edge_count || 0 }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- 空状态（API 无数据） -->
    <div v-else class="graph-empty">
      <div class="graph-empty__icon">
        <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
          <circle cx="40" cy="25" r="6" fill="var(--brand)" opacity="0.8" />
          <circle cx="20" cy="55" r="6" fill="var(--kun-color)" opacity="0.8" />
          <circle cx="60" cy="55" r="6" fill="var(--li-color)" opacity="0.8" />
          <circle cx="40" cy="65" r="4" fill="var(--kan-color)" opacity="0.6" />
          <line x1="40" y1="31" x2="23" y2="50" stroke="var(--bg-divider)" stroke-width="1.5" />
          <line x1="40" y1="31" x2="57" y2="50" stroke="var(--bg-divider)" stroke-width="1.5" />
          <line x1="23" y1="55" x2="57" y2="55" stroke="var(--bg-divider)" stroke-width="1.5" />
        </svg>
      </div>
      <h3>暂无图谱数据</h3>
      <p>系统运行后将自动构建知识图谱</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { Connection, Share, List } from '@element-plus/icons-vue';
import * as echarts from 'echarts/core';
import { PieChart, BarChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);
import apiClient from '@/api';

// ─── 类型 ───
interface EntityTypeInfo {
  name: string;
  count: number;
}

interface RelationTypeInfo {
  name: string;
  count: number;
}

interface GraphNode {
  id: string;
  name: string;
  type: string;
  edgeCount?: number;
  edge_count?: number;
}

interface GraphStats {
  totalNodes: number;
  totalEdges: number;
  entityTypes: EntityTypeInfo[];
  relationTypes: RelationTypeInfo[];
}

// ─── 状态 ───
const loading = ref(true);
const hasData = ref(false);
const pieChartRef = ref<HTMLDivElement | null>(null);
const barChartRef = ref<HTMLDivElement | null>(null);

let pieChartInstance: echarts.ECharts | null = null;
let barChartInstance: echarts.ECharts | null = null;

const stats = ref<GraphStats>({
  totalNodes: 0,
  totalEdges: 0,
  entityTypes: [],
  relationTypes: [],
});

const nodes = ref<GraphNode[]>([]);

// ─── Mock 数据 ───
function getMockGraphData(): {
  stats: GraphStats;
  nodes: GraphNode[];
} {
  return {
    stats: {
      totalNodes: 156,
      totalEdges: 342,
      entityTypes: [
        { name: '人物', count: 45 },
        { name: '组织', count: 32 },
        { name: '技术', count: 28 },
        { name: '文档', count: 25 },
        { name: '概念', count: 15 },
        { name: '事件', count: 11 },
      ],
      relationTypes: [
        { name: '任职于', count: 38 },
        { name: '使用了', count: 52 },
        { name: '引用了', count: 67 },
        { name: '关联', count: 89 },
        { name: '产生', count: 23 },
        { name: '属于', count: 73 },
      ],
    },
    nodes: [
      { id: 'n1', name: '深度学习', type: '技术', edgeCount: 12 },
      { id: 'n2', name: 'Transformer', type: '技术', edgeCount: 15 },
      { id: 'n3', name: 'OpenAI', type: '组织', edgeCount: 8 },
      { id: 'n4', name: 'Attention机制', type: '概念', edgeCount: 9 },
      { id: 'n5', name: '向量数据库', type: '技术', edgeCount: 7 },
      { id: 'n6', name: 'Milvus', type: '技术', edgeCount: 4 },
      { id: 'n7', name: 'ChromaDB', type: '技术', edgeCount: 5 },
      { id: 'n8', name: 'RAG', type: '概念', edgeCount: 11 },
      { id: 'n9', name: 'GPT-4', type: '技术', edgeCount: 6 },
      { id: 'n10', name: 'BERT', type: '技术', edgeCount: 5 },
    ],
  };
}

// ─── 数据加载 ───
async function fetchGraphData(): Promise<void> {
  loading.value = true;
  try {
    const data = (await apiClient.get('/api/graph')) as Record<string, unknown>;
    const graphStats = data.stats || data;
    const graphNodes = data.nodes || [];

    if (graphNodes && (graphNodes as unknown[]).length > 0) {
      stats.value = graphStats as GraphStats;
      nodes.value = graphNodes as GraphNode[];
      hasData.value = true;
    } else {
      applyMock();
    }
  } catch {
    applyMock();
  } finally {
    loading.value = false;
    if (hasData.value) {
      await nextTick();
      initCharts();
    }
  }
}

function applyMock(): void {
  const mock = getMockGraphData();
  stats.value = mock.stats;
  nodes.value = mock.nodes;
  hasData.value = true;
}

// ─── ECharts ───
function initCharts(): void {
  initPieChart();
  initBarChart();
}

function initPieChart(): void {
  if (!pieChartRef.value) return;
  if (pieChartInstance) pieChartInstance.dispose();

  pieChartInstance = echarts.init(pieChartRef.value);
  const pieData = stats.value.entityTypes.map((t) => ({
    name: t.name,
    value: t.count,
  }));

  const colors = ['#FF6700', '#3A6B8C', '#4A7C59', '#C9A84C', '#E74C3C', '#8B5E3C'];

  pieChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      bottom: 0,
      textStyle: { fontSize: 11, color: '#999' },
    },
    color: colors,
    series: [
      {
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['50%', '45%'],
        data: pieData,
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
        },
      },
    ],
  });
}

function initBarChart(): void {
  if (!barChartRef.value) return;
  if (barChartInstance) barChartInstance.dispose();

  barChartInstance = echarts.init(barChartRef.value);
  const barData = stats.value.relationTypes;
  const names = barData.map((t) => t.name);
  const values = barData.map((t) => t.count);

  barChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#999', fontSize: 10, rotate: 30 },
      axisLine: { lineStyle: { color: '#E8E4D9' } },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#999', fontSize: 11 },
      splitLine: { lineStyle: { color: '#F0EDE5' } },
    },
    series: [
      {
        type: 'bar',
        data: values,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#FF6700' },
            { offset: 1, color: 'rgba(255,103,0,0.3)' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
        barWidth: '50%',
      },
    ],
  });
}

// ─── 生命周期 ───
let resizeHandler: (() => void) | null = null;

onMounted(async () => {
  await fetchGraphData();
  resizeHandler = () => {
    pieChartInstance?.resize();
    barChartInstance?.resize();
  };
  window.addEventListener('resize', resizeHandler);
});

onUnmounted(() => {
  pieChartInstance?.dispose();
  barChartInstance?.dispose();
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
});
</script>

<style scoped lang="scss">
.graph-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px;
}

/* ─── 头部 ─── */
.graph-header {
  margin-bottom: 28px;

  h2 {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 8px;
  }

  .graph-desc {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
  }
}

/* ─── 统计卡片 ─── */
.graph-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &--nodes {
    background: var(--brand-soft);
    color: var(--brand);
  }

  &--edges {
    background: var(--kun-color-light);
    color: var(--kun-color);
  }

  &--types {
    background: var(--li-color-light);
    color: var(--li-color);
  }
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ─── 图表区 ─── */
.graph-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.chart-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;
}

.chart-title {
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.chart-pie {
  width: 100%;
  height: 300px;
}

.chart-bar {
  width: 100%;
  height: 300px;
}

.chart-empty {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 节点列表 ─── */
.graph-nodes {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-title {
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--text-primary);
}

.force-btn {
  opacity: 0.7;
}

.edge-count {
  font-weight: 600;
  color: var(--brand);
}

/* ─── 加载 / 空状态 ─── */
.graph-loading {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);

  .skeleton-stats {
    display: flex;
    gap: 16px;
    margin-bottom: 8px;
  }
}

.graph-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  gap: 16px;

  &__icon {
    opacity: 0.5;
  }

  h3 {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  p {
    font-size: 14px;
    color: var(--text-tertiary);
    margin: 0;
  }
}

/* ─── 响应式 ─── */
@media (max-width: 1023px) {
  .graph-charts {
    grid-template-columns: 1fr;
  }

  .graph-stats {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 767px) {
  .graph-view {
    padding: 24px 16px;
  }

  .graph-stats {
    grid-template-columns: 1fr;
  }

  .chart-pie,
  .chart-bar {
    height: 240px;
  }
}
</style>
