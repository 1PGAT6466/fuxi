/**
 * 伏羲 v2.1 — 知识图谱 Store
 *
 * 功能：
 * - 从 /api/graph/overview 获取图谱完整数据
 * - 支持节点搜索、关系查询
 * - 支持图谱布局切换（力导向/层次/圆形）
 * - 支持节点详情面板
 * - 图谱数据缓存
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getGraphOverview, searchGraph, getGraphRelations } from '@/api/graph';
import { createLogger } from '@/utils/logger';

const logger = createLogger('KnowledgeGraphStore');

/** 缓存有效期 3 分钟 */
const CACHE_TTL = 3 * 60 * 1000;

// ============================
// 类型定义
// ============================

/** 图谱节点 */
export interface GraphNode {
  /** 节点 ID */
  id: string;
  /** 节点名称 */
  name: string;
  /** 节点类型 */
  type: string;
  /** 关联边数 */
  edgeCount?: number;
  /** 兼容字段 */
  edge_count?: number;
  /** 节点属性（扩展数据） */
  properties?: Record<string, unknown>;
  /** 节点描述 */
  description?: string;
  /** 用于布局算法的坐标 */
  x?: number;
  y?: number;
  /** 节点大小（根据关联数计算） */
  size?: number;
  /** 节点颜色（根据类型分配） */
  color?: string;
}

/** 图谱边/关系 */
export interface GraphEdge {
  /** 边 ID */
  id: string;
  /** 源节点 ID */
  source: string;
  /** 目标节点 ID */
  target: string;
  /** 关系类型 */
  type: string;
  /** 关系权重 */
  weight?: number;
  /** 关系属性 */
  properties?: Record<string, unknown>;
}

/** 图谱统计 */
export interface GraphStats {
  totalNodes: number;
  totalEdges: number;
  entityTypes: { name: string; count: number }[];
  relationTypes: { name: string; count: number }[];
}

/** 图谱布局类型 */
export type GraphLayout = 'force' | 'hierarchical' | 'circular';

/** 节点详情面板状态 */
export interface NodeDetailPanel {
  /** 是否打开 */
  visible: boolean;
  /** 选中的节点 */
  node: GraphNode | null;
  /** 该节点的关联节点 */
  relatedNodes: GraphNode[];
  /** 该节点的关联边 */
  relatedEdges: GraphEdge[];
}

/** 图谱完整数据 */
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

export const useKnowledgeGraphStore = defineStore('knowledgeGraph', () => {
  // ============================
  // 状态
  // ============================

  const nodes = ref<GraphNode[]>([]);
  const edges = ref<GraphEdge[]>([]);
  const stats = ref<GraphStats>({
    totalNodes: 0,
    totalEdges: 0,
    entityTypes: [],
    relationTypes: [],
  });

  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastFetchTime = ref<number>(0);

  /** 当前布局模式 */
  const layout = ref<GraphLayout>('force');

  /** 搜索关键词 */
  const searchQuery = ref('');
  /** 搜索结果节点 */
  const searchResults = ref<GraphNode[]>([]);
  /** 搜索中 */
  const searching = ref(false);

  /** 节点详情面板 */
  const nodeDetail = ref<NodeDetailPanel>({
    visible: false,
    node: null,
    relatedNodes: [],
    relatedEdges: [],
  });

  /** 高亮的节点 ID 集合 */
  const highlightedNodeIds = ref<Set<string>>(new Set());

  // ============================
  // 计算属性
  // ============================

  /** 是否有数据 */
  const hasData = computed(() => nodes.value.length > 0);

  /** 节点类型映射（type → count） */
  const nodeTypeMap = computed(() => {
    const map: Record<string, number> = {};
    for (const node of nodes.value) {
      map[node.type] = (map[node.type] || 0) + 1;
    }
    return map;
  });

  /** 关系类型映射（type → count） */
  const edgeTypeMap = computed(() => {
    const map: Record<string, number> = {};
    for (const edge of edges.value) {
      map[edge.type] = (map[edge.type] || 0) + 1;
    }
    return map;
  });

  /** 是否有搜索结果 */
  const hasSearchResults = computed(() => searchResults.value.length > 0);

  /** 数据是否过期 */
  const isStale = computed(() => {
    if (!lastFetchTime.value) return true;
    return Date.now() - lastFetchTime.value > CACHE_TTL;
  });

  // ============================
  // 数据获取
  // ============================

  /**
   * 获取图谱完整数据
   * @param force 是否强制刷新
   */
  async function fetchGraphData(force = false): Promise<void> {
    if (!force && !isStale.value && hasData.value) {
      logger.debug('使用缓存图谱数据');
      return;
    }

    loading.value = true;
    error.value = null;

    try {
      const [overviewRes, relationsRes] = await Promise.allSettled([
        getGraphOverview(),
        getGraphRelations(),
      ]);

      // 解析 overview 数据
      if (overviewRes.status === 'fulfilled') {
        const raw = extractPayload(overviewRes.value);
        const payload = raw as Record<string, unknown>;

        // 解析节点
        const rawNodes = Array.isArray(payload.nodes)
          ? payload.nodes
          : Array.isArray(payload)
            ? payload
            : [];
        nodes.value = (rawNodes as Record<string, unknown>[]).map(normalizeNode);

        // 解析统计
        stats.value = {
          totalNodes: Number(payload.totalNodes ?? payload.nodes_count ?? payload.total_nodes ?? nodes.value.length),
          totalEdges: Number(payload.totalEdges ?? payload.edges_count ?? payload.total_edges ?? 0),
          entityTypes: normalizeArray(payload.entityTypes ?? payload.entity_types, []),
          relationTypes: normalizeArray(payload.relationTypes ?? payload.relation_types, []),
        };
      }

      // 解析关系数据
      if (relationsRes.status === 'fulfilled') {
        const rawEdges = extractPayload(relationsRes.value);
        const edgeData = Array.isArray(rawEdges)
          ? rawEdges
          : (rawEdges as Record<string, unknown>)?.relations ??
            (rawEdges as Record<string, unknown>)?.edges ??
            [];
        edges.value = (edgeData as Record<string, unknown>[]).map(normalizeEdge);

        // 补充统计中的边数
        if (!stats.value.totalEdges) {
          stats.value.totalEdges = edges.value.length;
        }
      }

      lastFetchTime.value = Date.now();
      logger.info('图谱数据加载成功', { nodes: nodes.value.length, edges: edges.value.length });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      error.value = msg;
      logger.warn('获取图谱数据失败', msg);
    } finally {
      loading.value = false;
    }
  }

  // ============================
  // 搜索
  // ============================

  /**
   * 搜索节点
   * @param query 搜索关键词
   */
  async function searchNodes(query: string): Promise<void> {
    const trimmed = query.trim();
    searchQuery.value = trimmed;

    if (!trimmed) {
      searchResults.value = [];
      highlightedNodeIds.value = new Set();
      return;
    }

    // 本地优先搜索（已有数据时直接过滤）
    if (hasData.value) {
      const lower = trimmed.toLowerCase();
      searchResults.value = nodes.value.filter(
        (n) =>
          n.name.toLowerCase().includes(lower) ||
          n.type.toLowerCase().includes(lower) ||
          (n.description && n.description.toLowerCase().includes(lower)),
      );
      highlightedNodeIds.value = new Set(searchResults.value.map((n) => n.id));
      return;
    }

    // 本地无数据时调用后端搜索
    searching.value = true;
    try {
      const raw = await searchGraph(trimmed);
      const payload = extractPayload(raw);
      const results = Array.isArray(payload)
        ? payload
        : (payload as Record<string, unknown>)?.results ?? [];
      searchResults.value = (results as Record<string, unknown>[]).map(normalizeNode);
      highlightedNodeIds.value = new Set(searchResults.value.map((n) => n.id));
    } catch (err) {
      logger.warn('节点搜索失败', err);
      searchResults.value = [];
      highlightedNodeIds.value = new Set();
    } finally {
      searching.value = false;
    }
  }

  /** 清除搜索 */
  function clearSearch(): void {
    searchQuery.value = '';
    searchResults.value = [];
    highlightedNodeIds.value = new Set();
  }

  // ============================
  // 布局
  // ============================

  /** 切换布局模式 */
  function setLayout(newLayout: GraphLayout): void {
    layout.value = newLayout;
    logger.info('布局切换', { layout: newLayout });
  }

  // ============================
  // 节点详情
  // ============================

  /** 打开节点详情面板 */
  function openNodeDetail(nodeId: string): void {
    const node = nodes.value.find((n) => n.id === nodeId);
    if (!node) {
      logger.warn('未找到节点', { nodeId });
      return;
    }

    // 查找关联边和关联节点
    const relatedEdges = edges.value.filter(
      (e) => e.source === nodeId || e.target === nodeId,
    );
    const relatedNodeIds = new Set<string>();
    for (const edge of relatedEdges) {
      relatedNodeIds.add(edge.source === nodeId ? edge.target : edge.source);
    }
    const relatedNodes = nodes.value.filter((n) => relatedNodeIds.has(n.id));

    nodeDetail.value = {
      visible: true,
      node,
      relatedNodes,
      relatedEdges,
    };

    logger.debug('打开节点详情', { nodeId, relatedCount: relatedNodes.length });
  }

  /** 关闭节点详情面板 */
  function closeNodeDetail(): void {
    nodeDetail.value = {
      visible: false,
      node: null,
      relatedNodes: [],
      relatedEdges: [],
    };
  }

  // ============================
  // 高亮
  // ============================

  /** 高亮指定节点及其邻居 */
  function highlightNode(nodeId: string): void {
    const ids = new Set<string>([nodeId]);
    for (const edge of edges.value) {
      if (edge.source === nodeId) ids.add(edge.target);
      if (edge.target === nodeId) ids.add(edge.source);
    }
    highlightedNodeIds.value = ids;
  }

  /** 清除高亮 */
  function clearHighlight(): void {
    highlightedNodeIds.value = new Set();
  }

  // ============================
  // 重置
  // ============================

  function reset(): void {
    nodes.value = [];
    edges.value = [];
    stats.value = { totalNodes: 0, totalEdges: 0, entityTypes: [], relationTypes: [] };
    error.value = null;
    lastFetchTime.value = 0;
    clearSearch();
    closeNodeDetail();
    clearHighlight();
  }

  return {
    // 状态
    nodes,
    edges,
    stats,
    loading,
    error,
    lastFetchTime,
    layout,
    searchQuery,
    searchResults,
    searching,
    nodeDetail,
    highlightedNodeIds,
    // 计算属性
    hasData,
    nodeTypeMap,
    edgeTypeMap,
    hasSearchResults,
    isStale,
    // 方法
    fetchGraphData,
    searchNodes,
    clearSearch,
    setLayout,
    openNodeDetail,
    closeNodeDetail,
    highlightNode,
    clearHighlight,
    reset,
  };
});

// ============================
// 工具函数
// ============================

/** 从响应中提取 payload */
function extractPayload<T>(value: unknown): T {
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if ('data' in record && record.data !== undefined) {
      return record.data as T;
    }
  }
  return value as T;
}

/** 安全数组规范化 */
function normalizeArray<T>(value: unknown, fallback: T[]): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    for (const key of Object.keys(record)) {
      if (Array.isArray(record[key])) return record[key] as T[];
    }
  }
  return fallback;
}

/** 节点类型颜色映射 */
const TYPE_COLORS: Record<string, string> = {
  person: '#FF6700',
  organization: '#3A6B8C',
  location: '#4A7C59',
  concept: '#C9A84C',
  event: '#E74C3C',
  document: '#8B5E3C',
  technology: '#6C5CE7',
  default: '#95A5A6',
};

/** 规范化节点数据 */
function normalizeNode(raw: Record<string, unknown>): GraphNode {
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? raw.label ?? ''),
    type: String(raw.type ?? 'unknown'),
    edgeCount: Number(raw.edgeCount ?? raw.edge_count ?? 0),
    edge_count: Number(raw.edgeCount ?? raw.edge_count ?? 0),
    properties: (raw.properties as Record<string, unknown>) ?? undefined,
    description: raw.description ? String(raw.description) : undefined,
    size: Math.max(20, Math.min(60, 20 + (Number(raw.edgeCount ?? raw.edge_count ?? 0)) * 3)),
    color: TYPE_COLORS[String(raw.type)] ?? TYPE_COLORS.default,
  };
}

/** 规范化边数据 */
function normalizeEdge(raw: Record<string, unknown>): GraphEdge {
  return {
    id: String(raw.id ?? `${raw.source}-${raw.target}-${raw.type}`),
    source: String(raw.source ?? ''),
    target: String(raw.target ?? ''),
    type: String(raw.type ?? 'related'),
    weight: Number(raw.weight ?? 1),
    properties: (raw.properties as Record<string, unknown>) ?? undefined,
  };
}
