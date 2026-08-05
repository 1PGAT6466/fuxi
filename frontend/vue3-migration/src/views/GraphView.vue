<template>
  <!--
    伏羲 v2.1 — 知识图谱（升级版）
    统计可视化 + 节点/边数据 + 实体类型分布饼图 + 关系类型柱状图 + 节点列表 + 力导向图
  -->
  <div class="graph-view">
    <div class="graph-header">
      <div class="graph-header__left">
        <h2>知识图谱</h2>
        <p class="graph-desc">可视化浏览知识实体与关系网络</p>
      </div>
      <div class="graph-header__controls">
        <!-- 搜索栏 -->
        <div class="graph-search">
          <el-input
            v-model="searchInput"
            placeholder="搜索节点..."
            clearable
            :prefix-icon="Search"
            size="default"
            style="width: 220px"
            aria-label="搜索实体"
            @input="handleSearch"
            @clear="kgStore.clearSearch()"
          />
        </div>
        <!-- 布局切换 -->
        <el-radio-group v-model="currentLayout" size="small" role="group" aria-label="布局切换" @change="handleLayoutChange">
          <el-radio-button value="force">力导向</el-radio-button>
          <el-radio-button value="hierarchical">层次</el-radio-button>
          <el-radio-button value="circular">圆形</el-radio-button>
        </el-radio-group>
      </div>
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
      <div class="graph-charts" role="img" aria-label="知识图谱可视化">
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

      <!-- 力导向图区域 -->
      <div v-if="showForceGraph" class="graph-force-section">
        <div class="chart-card force-chart-card">
          <div class="chart-title">
            <span>知识网络 — {{ layoutLabel }}</span>
            <div class="force-controls">
              <el-button-group size="small">
                <el-button
                  :type="graphLayout === 'force' ? 'primary' : 'default'"
                  size="small"
                  @click="switchGraphLayout('force')"
                >力导向</el-button>
                <el-button
                  :type="graphLayout === 'circular' ? 'primary' : 'default'"
                  size="small"
                  @click="switchGraphLayout('circular')"
                >环形</el-button>
              </el-button-group>
              <el-button
                v-if="highlightedNodeId"
                size="small"
                text
                @click="clearGraphHighlight"
              >清除高亮</el-button>
            </div>
          </div>
          <div v-if="kgStore.nodes.length > 0" ref="forceGraphRef" class="chart-force" />
          <div v-else class="chart-empty">暂无图谱节点数据</div>
        </div>
      </div>

      <!-- 节点列表 -->
      <div class="graph-nodes">
        <div class="section-header">
          <span class="section-title">节点列表</span>
          <el-button type="primary" @click="toggleForceGraph">
            <el-icon><Connection /></el-icon>
            {{ showForceGraph ? '隐藏力导向图' : '显示力导向图' }}
          </el-button>
        </div>
        <!-- 搜索结果提示 -->
        <div v-if="kgStore.searchQuery && kgStore.hasSearchResults" class="search-banner">
          搜索 "{{ kgStore.searchQuery }}" 找到 {{ kgStore.searchResults.length }} 个节点
          <el-button text size="small" @click="kgStore.clearSearch()">清除搜索</el-button>
        </div>
        <el-table :data="displayNodes" stripe size="small" @row-click="handleNodeClick">
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

      <!-- 节点详情面板 -->
      <el-drawer
        v-model="kgStore.nodeDetail.visible"
        title="节点详情"
        size="360px"
        direction="rtl"
      >
        <template v-if="kgStore.nodeDetail.node">
          <div class="node-detail">
            <div class="node-detail__header">
              <span class="node-detail__name">{{ kgStore.nodeDetail.node.name }}</span>
              <el-tag size="small">{{ kgStore.nodeDetail.node.type }}</el-tag>
            </div>
            <p v-if="kgStore.nodeDetail.node.description" class="node-detail__desc">
              {{ kgStore.nodeDetail.node.description }}
            </p>
            <div class="node-detail__stats">
              <span>关联节点：{{ kgStore.nodeDetail.relatedNodes.length }}</span>
              <span>关联边：{{ kgStore.nodeDetail.relatedEdges.length }}</span>
            </div>
            <div v-if="kgStore.nodeDetail.relatedNodes.length > 0" class="node-detail__related">
              <h4>关联节点</h4>
              <div
                v-for="rn in kgStore.nodeDetail.relatedNodes"
                :key="rn.id"
                class="related-node-item"
                @click="kgStore.openNodeDetail(rn.id)"
              >
                <span class="related-node-name">{{ rn.name }}</span>
                <el-tag size="small" type="info">{{ rn.type }}</el-tag>
              </div>
            </div>
          </div>
        </template>
      </el-drawer>
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
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { Connection, Share, List, Search } from '@element-plus/icons-vue';
import * as echarts from 'echarts/core';
import { PieChart, BarChart, GraphChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([PieChart, BarChart, GraphChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);
import { useKnowledgeGraphStore, type GraphLayout } from '@/stores/knowledgeGraph';
import { createLogger } from '@/utils/logger';

const logger = createLogger('GraphView');
const kgStore = useKnowledgeGraphStore();

// ─── 搜索与布局 ───
const searchInput = ref('');
const currentLayout = ref<GraphLayout>('force');

/** 防抖搜索 */
let searchDebounce: ReturnType<typeof setTimeout> | null = null;
function handleSearch(value: string): void {
  if (searchDebounce) clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    kgStore.searchNodes(value);
  }, 300);
}

function handleLayoutChange(layout: GraphLayout): void {
  kgStore.setLayout(layout);
}

/** 显示的节点列表（搜索时显示搜索结果，否则显示全部） */
const displayNodes = computed(() => {
  if (kgStore.searchQuery && kgStore.hasSearchResults) {
    return kgStore.searchResults;
  }
  return kgStore.nodes;
});

/** 节点点击 -> 打开详情面板 */
function handleNodeClick(row: { id: string }): void {
  kgStore.openNodeDetail(row.id);
}

// ─── 本地状态（兼容原有图表） ───
const loading = computed(() => kgStore.loading);
const hasData = computed(() => kgStore.hasData);
const stats = computed(() => kgStore.stats);

const pieChartRef = ref<HTMLDivElement | null>(null);
const barChartRef = ref<HTMLDivElement | null>(null);
const forceGraphRef = ref<HTMLDivElement | null>(null);

let pieChartInstance: echarts.ECharts | null = null;
let barChartInstance: echarts.ECharts | null = null;
let forceGraphInstance: echarts.ECharts | null = null;

// ─── 力导向图状态 ───
const showForceGraph = ref(false);
const graphLayout = ref<'force' | 'circular'>('force');
const highlightedNodeId = ref<string | null>(null);

const layoutLabel = computed(() => (graphLayout.value === 'force' ? '力导向布局' : '环形布局'));

/** 实体类型 → 颜色映射（与饼图颜色方案一致） */
const entityTypeColors: Record<string, string> = {};
const COLOR_PALETTE = ['#FF6700', '#3A6B8C', '#4A7C59', '#C9A84C', '#E74C3C', '#8B5E3C', '#6C5CE7', '#E67E22', '#1ABC9C', '#3498DB'];

function getEntityColor(type: string, index: number): string {
  if (!entityTypeColors[type]) {
    const keys = Object.keys(entityTypeColors);
    entityTypeColors[type] = COLOR_PALETTE[keys.length % COLOR_PALETTE.length];
  }
  return entityTypeColors[type];
}

const edgeTypeColors: Record<string, string> = {};
const EDGE_COLORS = ['#95A5A6', '#BDC3C7', '#7F8C8D', '#AAB7B8', '#99A3A4', '#85929E'];

function getEdgeColor(type: string): string {
  if (!edgeTypeColors[type]) {
    const keys = Object.keys(edgeTypeColors);
    edgeTypeColors[type] = EDGE_COLORS[keys.length % EDGE_COLORS.length];
  }
  return edgeTypeColors[type];
}

function toggleForceGraph(): void {
  showForceGraph.value = !showForceGraph.value;
  if (showForceGraph.value) {
    nextTick(() => initForceGraph());
  } else {
    forceGraphInstance?.dispose();
    forceGraphInstance = null;
  }
}

function switchGraphLayout(layout: 'force' | 'circular'): void {
  graphLayout.value = layout;
  if (showForceGraph.value && forceGraphInstance) {
    updateForceGraphOption();
  }
}

function clearGraphHighlight(): void {
  highlightedNodeId.value = null;
  kgStore.clearHighlight();
  if (forceGraphInstance) {
    updateForceGraphOption();
  }
}

/** 构建力导向图 option */
function buildForceGraphOption(): Record<string, unknown> {
  const allNodes = kgStore.nodes;
  const allEdges = kgStore.edges;
  const highlighted = highlightedNodeId.value;
  const highlightSet = new Set<string>();

  // 计算每个节点的 degree（根据边）
  const degreeMap: Record<string, number> = {};
  for (const node of allNodes) {
    degreeMap[node.id] = 0;
  }
  for (const edge of allEdges) {
    degreeMap[edge.source] = (degreeMap[edge.source] || 0) + 1;
    degreeMap[edge.target] = (degreeMap[edge.target] || 0) + 1;
  }

  // 高亮：选中节点 + 邻居
  if (highlighted) {
    highlightSet.add(highlighted);
    for (const edge of allEdges) {
      if (edge.source === highlighted) highlightSet.add(edge.target);
      if (edge.target === highlighted) highlightSet.add(edge.source);
    }
    kgStore.highlightNode(highlighted);
  }

  // 构建节点数据
  // 预先给类型分配颜色
  const typeIndexMap: Record<string, number> = {};
  allNodes.forEach((n) => {
    if (!(n.type in typeIndexMap)) {
      typeIndexMap[n.type] = Object.keys(typeIndexMap).length;
    }
  });

  const graphData = allNodes.map((node) => {
    const degree = degreeMap[node.id] || node.edgeCount || node.edge_count || 0;
    const color = getEntityColor(node.type, typeIndexMap[node.type]);
    const isHighlighted = !highlighted || highlightSet.has(node.id);
    const isCenter = highlighted === node.id;

    return {
      id: node.id,
      name: node.name,
      symbolSize: Math.max(14, Math.min(60, 12 + degree * 4)),
      itemStyle: {
        color: isHighlighted ? color : '#D5D8DC',
        borderColor: isCenter ? '#FF6700' : isHighlighted ? lightenColor(color, 0.3) : '#D5D8DC',
        borderWidth: isCenter ? 3 : isHighlighted ? 1.5 : 1,
        shadowBlur: isCenter ? 12 : 0,
        shadowColor: isCenter ? 'rgba(255,103,0,0.5)' : 'transparent',
        opacity: isHighlighted ? 1 : 0.25,
      },
      label: {
        show: isHighlighted,
        fontSize: isCenter ? 13 : 11,
        fontWeight: isCenter ? 'bold' : 'normal',
        color: isHighlighted ? '#333' : '#ccc',
      },
      draggable: true,
      type: node.type,
      desc: node.description || '',
      degree,
    };
  });

  // 构建边数据
  const graphEdges = allEdges.map((edge) => {
    const isRelatedToHighlight =
      !highlighted || edge.source === highlighted || edge.target === highlighted;
    const edgeColor = getEdgeColor(edge.type);

    return {
      source: edge.source,
      target: edge.target,
      label: {
        show: isRelatedToHighlight,
        formatter: edge.type,
        fontSize: 10,
        color: '#999',
      },
      lineStyle: {
        color: isRelatedToHighlight ? edgeColor : '#E8E8E8',
        opacity: isRelatedToHighlight ? 0.6 : 0.15,
        curveness: 0.1,
        width: isRelatedToHighlight && edge.source === highlighted ? 2 : 1,
      },
      type: edge.type,
    };
  });

  const isCircular = graphLayout.value === 'circular';

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: Record<string, unknown>) => {
        if (params.dataType === 'edge') {
          return `<strong>${params.data}</strong><br/>关系类型：${(params.data as Record<string, unknown>).type || '—'}`;
        }
        const d = params.data as Record<string, unknown>;
        return `<strong>${d.name}</strong><br/>类型：${d.type || '—'}<br/>关联数：${d.degree || 0}<br/>${d.desc ? `<span style="color:#999">${d.desc}</span>` : ''}`;
      },
    },
    animationDuration: 1500,
    animationEasingUpdate: 'quinticInOut',
    series: [
      {
        type: 'graph',
        layout: graphLayout.value,
        data: graphData,
        edges: graphEdges,
        roam: true,
        draggable: true,
        force: isCircular
          ? undefined
          : {
              repulsion: 200,
              edgeLength: 150,
              gravity: 0.1,
              layoutAnimation: true,
            },
        circular: isCircular
          ? { rotateLabel: true }
          : undefined,
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          color: '#666',
        },
        edgeLabel: {
          show: true,
          fontSize: 10,
          color: '#999',
        },
        lineStyle: {
          color: 'source',
          curveness: 0.1,
          opacity: 0.4,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
          itemStyle: { shadowBlur: 15, shadowColor: 'rgba(0,0,0,0.2)' },
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1,
          shadowBlur: 5,
          shadowColor: 'rgba(0,0,0,0.1)',
        },
      },
    ],
  };
}

/** 辅助：颜色变亮 */
function lightenColor(hex: string, factor: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const lr = Math.min(255, Math.round(r + (255 - r) * factor));
  const lg = Math.min(255, Math.round(g + (255 - g) * factor));
  const lb = Math.min(255, Math.round(b + (255 - b) * factor));
  return `#${lr.toString(16).padStart(2, '0')}${lg.toString(16).padStart(2, '0')}${lb.toString(16).padStart(2, '0')}`;
}

/** 更新图 option（不重建实例） */
function updateForceGraphOption(): void {
  if (!forceGraphInstance) return;
  forceGraphInstance.setOption(buildForceGraphOption(), true);
}

// ─── ECharts ───
function initCharts(): void {
  initPieChart();
  initBarChart();
}

function initForceGraph(): void {
  if (!forceGraphRef.value) return;
  if (forceGraphInstance) forceGraphInstance.dispose();

  forceGraphInstance = echarts.init(forceGraphRef.value);

  // 点击节点 → 高亮邻居
  forceGraphInstance.on('click', (params: Record<string, unknown>) => {
    if ((params as { dataType?: string }).dataType === 'node') {
      const data = params.data as Record<string, unknown>;
      const nodeId = data.id as string;
      if (highlightedNodeId.value === nodeId) {
        clearGraphHighlight();
      } else {
        highlightedNodeId.value = nodeId;
        updateForceGraphOption();
      }
    }
  });

  // 双击节点 → 打开详情面板
  forceGraphInstance.on('dblclick', (params: Record<string, unknown>) => {
    if ((params as { dataType?: string }).dataType === 'node') {
      const data = params.data as Record<string, unknown>;
      kgStore.openNodeDetail(data.id as string);
    }
  });

  updateForceGraphOption();
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

// 当 store 数据加载完成后，初始化图表
watch(
  () => kgStore.hasData,
  async (val) => {
    if (val) {
      await nextTick();
      initCharts();
      if (showForceGraph.value) {
        initForceGraph();
      }
    }
  },
);

// 监听力导向图开关
watch(
  () => showForceGraph.value,
  async (val) => {
    if (val) {
      await nextTick();
      initForceGraph();
    }
  },
);

// ─── 生命周期 ───
let resizeHandler: (() => void) | null = null;

onMounted(async () => {
  await kgStore.fetchGraphData();
  resizeHandler = () => {
    pieChartInstance?.resize();
    barChartInstance?.resize();
    forceGraphInstance?.resize();
  };
  window.addEventListener('resize', resizeHandler);
});

// 窗口大小变化时同步调整
watch(
  () => [showForceGraph.value],
  () => {
    nextTick(() => {
      forceGraphInstance?.resize();
    });
  },
);

onUnmounted(() => {
  pieChartInstance?.dispose();
  barChartInstance?.dispose();
  forceGraphInstance?.dispose();
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  if (searchDebounce) clearTimeout(searchDebounce);
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
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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

  &__left {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  &__controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.search-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: var(--brand-soft);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-small);
  color: var(--brand);
}

/* ─── 节点详情面板 ─── */
.node-detail {
  padding: 0 4px;

  &__header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
  }

  &__name {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
  }

  &__desc {
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: 16px;
  }

  &__stats {
    display: flex;
    gap: 20px;
    font-size: 13px;
    color: var(--text-tertiary);
    margin-bottom: 20px;
  }

  &__related {
    h4 {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 10px;
    }
  }
}

.related-node-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
  }
}

.related-node-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
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

/* ─── 力导向图区域 ─── */
.graph-force-section {
  margin-bottom: 24px;
}

.force-chart-card {
  .chart-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .force-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.chart-force {
  width: 100%;
  height: 500px;
  background: linear-gradient(135deg, #faf9f6 0%, #f5f3ee 100%);
  border-radius: var(--radius-sm);
  border: 1px solid var(--bg-divider, #E8E4D9);
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

  .graph-header {
    flex-direction: column;
    gap: 16px;

    &__controls {
      width: 100%;
      flex-wrap: wrap;
    }
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
