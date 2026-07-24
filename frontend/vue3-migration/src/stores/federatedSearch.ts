/**
 * 伏羲 v2.1 — 联邦搜索 Store
 *
 * 集中管理联邦搜索的：
 * - 搜索源列表与状态
 * - 搜索结果缓存
 * - 查询历史
 * - 筛选器状态
 * - 搜索建议
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  FederatedSearchRequest,
  FederatedSearchResponse,
  FederatedSearchResult,
  ResultFilter,
  ResultCategory,
  SearchSource,
  SearchSuggestion,
  SourceStats,
} from '@/types/federated-search';
import { getSearchSources, federatedSearch, mockSearchSources, mockFederatedSearch } from '@/api/federated-search';

/** 最大缓存查询数 */
const MAX_HISTORY = 50;
/** 缓存有效期 ms (5 分钟) */
const CACHE_TTL = 5 * 60 * 1000;

export const useFederatedSearchStore = defineStore('federatedSearch', () => {
  // ═══════════════════════════════════════════
  // 状态
  // ═══════════════════════════════════════════

  /** 搜索源列表 */
  const sources = ref<SearchSource[]>([]);
  /** 搜索源是否已加载 */
  const sourcesLoaded = ref(false);
  /** 当前搜索结果 */
  const results = ref<FederatedSearchResult[]>([]);
  /** 搜索结果总数 */
  const total = ref(0);
  /** 去重前总数 */
  const rawTotal = ref(0);
  /** 各源统计 */
  const sourceStats = ref<SourceStats[]>([]);
  /** 分类计数 */
  const categoryCounts = ref<Record<ResultCategory, number>>({
    document: 0,
    wiki: 0,
    chat: 0,
    tool: 0,
    file: 0,
    database: 0,
    external: 0,
  });
  /** 总耗时 */
  const tookMs = ref(0);
  /** 搜索中 */
  const searching = ref(false);
  /** 当前查询 */
  const currentQuery = ref('');
  /** 查询建议 */
  const suggestions = ref<SearchSuggestion[]>([]);
  /** 查询历史 */
  const queryHistory = ref<string[]>([]);
  /** 缓存 { queryKey -> { results, timestamp } } */
  const resultCache = ref<Map<string, { results: FederatedSearchResponse; timestamp: number }>>(new Map());

  /** 激活的筛选器 */
  const activeFilters = ref<ResultFilter[]>([
    { type: 'source', value: 'all', label: '全部来源', active: true },
    { type: 'category', value: 'all', label: '全部分类', active: true },
  ]);

  /** 选中结果的 ID */
  const selectedResultId = ref<string | null>(null);

  // ═══════════════════════════════════════════
  // 计算属性
  // ═══════════════════════════════════════════

  /** 可用（在线）的搜索源 */
  const activeSources = computed(() =>
    sources.value.filter((s) => s.enabled && s.status === 'online'),
  );

  /** 按权重排序的搜索源 */
  const sortedSources = computed(() =>
    [...sources.value].sort((a, b) => b.weight - a.weight),
  );

  /** 是否有搜索结果 */
  const hasResults = computed(() => results.value.length > 0);

  /** 按分类分组的结果 */
  const resultsByCategory = computed(() => {
    const grouped: Record<ResultCategory, FederatedSearchResult[]> = {
      document: [],
      wiki: [],
      chat: [],
      tool: [],
      file: [],
      database: [],
      external: [],
    };
    for (const r of results.value) {
      grouped[r.category]?.push(r);
    }
    return grouped;
  });

  /** 按来源分组的结果 */
  const resultsBySource = computed(() => {
    const grouped: Record<string, FederatedSearchResult[]> = {};
    for (const r of results.value) {
      if (!grouped[r.sourceId]) grouped[r.sourceId] = [];
      grouped[r.sourceId].push(r);
    }
    return grouped;
  });

  /** 当前查询的缓存 key */
  const cacheKey = computed(() => {
    if (!currentQuery.value) return '';
    return `federated:${currentQuery.value.trim().toLowerCase()}`;
  });

  // ═══════════════════════════════════════════
  // 方法
  // ═══════════════════════════════════════════

  /** 加载搜索源 */
  async function loadSources(): Promise<void> {
    try {
      const res = await getSearchSources();
      sources.value = res.sources;
    } catch {
      // 后端不可用，使用 mock
      const mock = await mockSearchSources();
      sources.value = mock.sources;
    } finally {
      sourcesLoaded.value = true;
    }
  }

  /**
   * 执行联邦搜索
   * @param query 搜索查询
   * @param opts 可选请求参数
   */
  async function search(
    query: string,
    opts?: Partial<FederatedSearchRequest>,
  ): Promise<FederatedSearchResponse> {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      return {
        query: '',
        results: [],
        rawTotal: 0,
        total: 0,
        tookMs: 0,
        sourceStats: [],
        categoryCounts: {
          document: 0, wiki: 0, chat: 0, tool: 0, file: 0, database: 0, external: 0,
        },
        truncated: false,
      };
    }

    // 检查缓存
    const key = `federated:${trimmedQuery.toLowerCase()}`;
    const cached = resultCache.value.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      currentQuery.value = trimmedQuery;
      applyResponse(cached.results);
      return cached.results;
    }

    searching.value = true;
    currentQuery.value = trimmedQuery;

    // 记录查询历史
    addToHistory(trimmedQuery);

    const request: FederatedSearchRequest = {
      query: trimmedQuery,
      limit: opts?.limit ?? 50,
      deduplicate: opts?.deduplicate ?? true,
      deduplicateThreshold: opts?.deduplicateThreshold ?? 0.85,
      sortBy: opts?.sortBy ?? 'relevance',
      sortOrder: opts?.sortOrder ?? 'desc',
      sourceIds: opts?.sourceIds,
      sourceTypes: opts?.sourceTypes,
      minScore: opts?.minScore ?? 0.1,
      categories: opts?.categories,
      offset: opts?.offset ?? 0,
    };

    let response: FederatedSearchResponse;
    try {
      response = await federatedSearch(request);
    } catch {
      // 降级：使用本地聚合的 mock 搜索
      console.warn('[联邦搜索] 后端 API 不可用，使用前端降级方案');
      response = await mockFederatedSearch(request);
    }

    // 缓存结果
    resultCache.value.set(key, { results: response, timestamp: Date.now() });

    // 清理旧缓存
    if (resultCache.value.size > 100) {
      purgeCache();
    }

    applyResponse(response);
    searching.value = false;
    return response;
  }

  /** 应用搜索结果到状态 */
  function applyResponse(response: FederatedSearchResponse): void {
    results.value = response.results;
    total.value = response.total;
    rawTotal.value = response.rawTotal;
    sourceStats.value = response.sourceStats;
    categoryCounts.value = response.categoryCounts;
    tookMs.value = response.tookMs;
    suggestions.value = (response.suggestions || []).map((s) => ({
      text: s,
      type: 'related' as const,
    }));
  }

  /** 添加查询到历史 */
  function addToHistory(queryStr: string): void {
    // 去重：移除已有相同查询
    const idx = queryHistory.value.indexOf(queryStr);
    if (idx !== -1) {
      queryHistory.value.splice(idx, 1);
    }
    queryHistory.value.unshift(queryStr);
    // 限制数量
    if (queryHistory.value.length > MAX_HISTORY) {
      queryHistory.value = queryHistory.value.slice(0, MAX_HISTORY);
    }
  }

  /** 清除查询历史 */
  function clearHistory(): void {
    queryHistory.value = [];
  }

  /** 清除结果缓存 */
  function purgeCache(): void {
    const now = Date.now();
    for (const [key, val] of resultCache.value.entries()) {
      if (now - val.timestamp > CACHE_TTL) {
        resultCache.value.delete(key);
      }
    }
  }

  /** 重置搜索结果 */
  function resetResults(): void {
    results.value = [];
    total.value = 0;
    rawTotal.value = 0;
    sourceStats.value = [];
    categoryCounts.value = {
      document: 0, wiki: 0, chat: 0, tool: 0, file: 0, database: 0, external: 0,
    };
    tookMs.value = 0;
    currentQuery.value = '';
    suggestions.value = [];
    selectedResultId.value = null;
  }

  /** 设置激活的筛选器 */
  function setFilter(filter: ResultFilter): void {
    const idx = activeFilters.value.findIndex((f) => f.type === filter.type);
    if (idx !== -1) {
      activeFilters.value[idx] = { ...filter, active: true };
    } else {
      activeFilters.value.push({ ...filter, active: true });
    }
  }

  /** 清除某个类型的筛选器 */
  function clearFilter(filterType: 'source' | 'category' | 'score' | 'date'): void {
    const idx = activeFilters.value.findIndex((f) => f.type === filterType);
    if (idx !== -1) {
      activeFilters.value.splice(idx, 1);
    }
  }

  /** 重置所有筛选器 */
  function resetFilters(): void {
    activeFilters.value = [
      { type: 'source', value: 'all', label: '全部来源', active: true },
      { type: 'category', value: 'all', label: '全部分类', active: true },
    ];
  }

  return {
    // 状态
    sources,
    sourcesLoaded,
    results,
    total,
    rawTotal,
    sourceStats,
    categoryCounts,
    tookMs,
    searching,
    currentQuery,
    suggestions,
    queryHistory,
    activeFilters,
    selectedResultId,
    // 计算
    activeSources,
    sortedSources,
    hasResults,
    resultsByCategory,
    resultsBySource,
    // 方法
    loadSources,
    search,
    resetResults,
    setFilter,
    clearFilter,
    resetFilters,
    clearHistory,
    purgeCache,
  };
});
