/**
 * 伏羲 v2.1 — 联邦搜索 Composable
 *
 * 提供联邦搜索的 Vue3 Composition API 封装：
 * - 搜索源状态轮询
 * - 防抖搜索
 * - 结果筛选与排序
 * - 快捷跳转
 */

import { ref, watch, onMounted, onUnmounted, computed, type Ref } from 'vue';
import { useRouter } from 'vue-router';
import { useFederatedSearchStore } from '@/stores/federatedSearch';
import type {
  FederatedSearchResult,
  FederatedSearchRequest,
  ResultCategory,
  ResultFilter,
  SearchSource,
  SearchSuggestion,
  SourceStats,
} from '@/types/federated-search';
import { createLogger } from '@/utils/logger';

const logger = createLogger('FederatedSearch');

export interface UseFederatedSearchOptions {
  /** 防抖延迟 ms */
  debounceMs?: number;
  /** 是否自动加载搜索源 */
  autoLoadSources?: boolean;
}

export function useFederatedSearch(options: UseFederatedSearchOptions = {}) {
  const { debounceMs = 250, autoLoadSources = true } = options;
  const store = useFederatedSearchStore();
  const router = useRouter();

  const localQuery = ref('');
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let sourcePollTimer: ReturnType<typeof setInterval> | null = null;

  // ═══════════════════════════════════════════
  // 计算属性
  // ═══════════════════════════════════════════

  /** 按分数排序的过滤后的结果 */
  const filteredResults = computed(() => {
    let items = [...store.results];

    // 应用筛选器
    for (const filter of store.activeFilters) {
      if (filter.active && filter.value !== 'all') {
        if (filter.type === 'source') {
          items = items.filter((r) => r.sourceId === filter.value);
        } else if (filter.type === 'category') {
          items = items.filter((r) => r.category === filter.value);
        }
      }
    }

    return items;
  });

  /** 生成来源筛选器选项 */
  const sourceFilters = computed<ResultFilter[]>(() => {
    const sourceMap = new Map<string, { name: string; count: number }>();
    for (const r of store.results) {
      const existing = sourceMap.get(r.sourceId);
      if (existing) {
        existing.count++;
      } else {
        sourceMap.set(r.sourceId, { name: r.sourceName, count: 1 });
      }
    }
    const filters: ResultFilter[] = [
      {
        type: 'source',
        value: 'all',
        label: `全部来源 (${store.total})`,
        active: true,
        count: store.total,
      },
    ];
    for (const [id, info] of sourceMap.entries()) {
      filters.push({
        type: 'source',
        value: id,
        label: `${info.name} (${info.count})`,
        active: false,
        count: info.count,
      });
    }
    return filters;
  });

  /** 生成分类筛选器选项 */
  const categoryFilters = computed<ResultFilter[]>(() => {
    const labels: Record<ResultCategory, string> = {
      document: '文档',
      wiki: 'Wiki',
      chat: '对话',
      tool: '工具',
      file: '文件',
      database: '数据库',
      external: '外部',
    };
    const filters: ResultFilter[] = [
      {
        type: 'category',
        value: 'all',
        label: `全部分类 (${store.total})`,
        active: true,
        count: store.total,
      },
    ];
    for (const [cat, count] of Object.entries(store.categoryCounts) as [ResultCategory, number][]) {
      if (count > 0) {
        filters.push({
          type: 'category',
          value: cat,
          label: `${labels[cat]} (${count})`,
          active: false,
          count,
        });
      }
    }
    return filters;
  });

  // ═══════════════════════════════════════════
  // 方法
  // ═══════════════════════════════════════════

  /**
   * 防抖搜索
   */
  function searchDebounced(query: string, opts?: Partial<FederatedSearchRequest>): void {
    localQuery.value = query;

    if (debounceTimer) clearTimeout(debounceTimer);

    if (!query.trim()) {
      store.resetResults();
      return;
    }

    debounceTimer = setTimeout(() => {
      store.search(query.trim(), opts);
    }, debounceMs);
  }

  /**
   * 立即搜索（不防抖）
   */
  async function searchNow(
    query: string,
    opts?: Partial<FederatedSearchRequest>,
  ): Promise<void> {
    localQuery.value = query;
    if (debounceTimer) clearTimeout(debounceTimer);

    if (!query.trim()) {
      store.resetResults();
      return;
    }

    await store.search(query.trim(), opts);
  }

  /**
   * 设置筛选器
   */
  function setFilter(type: 'source' | 'category', value: string): void {
    const label = type === 'source'
      ? sourceFilters.value.find((f) => f.value === value)?.label || value
      : categoryFilters.value.find((f) => f.value === value)?.label || value;
    store.setFilter({ type, value, label, active: value !== 'all' });
  }

  /**
   * 清除筛选
   */
  function clearFilter(type: 'source' | 'category'): void {
    store.clearFilter(type);
    // 重新设置为 "all"
    setFilter(type, 'all');
  }

  /**
   * 跳转到结果详情
   */
  function navigateToResult(result: FederatedSearchResult): void {
    store.selectedResultId = result.id;
    if (result.url) {
      router.push(result.url);
    }
  }

  /**
   * 加载搜索源（带自动重试和轮询）
   */
  function loadSources(): void {
    if (!store.sourcesLoaded) {
      store.loadSources();
    }
  }

  /**
   * 启动源健康检查轮询
   */
  function startSourcePolling(intervalMs: number = 60_000): void {
    if (sourcePollTimer) return;
    sourcePollTimer = setInterval(() => {
      store.loadSources().catch((err) => {
        logger.warn('搜索源健康检查轮询失败:', err);
      });
    }, intervalMs);
  }

  /**
   * 停止源健康检查轮询
   */
  function stopSourcePolling(): void {
    if (sourcePollTimer) {
      clearInterval(sourcePollTimer);
      sourcePollTimer = null;
    }
  }

  // ═══════════════════════════════════════════
  // 生命周期
  // ═══════════════════════════════════════════

  onMounted(() => {
    if (autoLoadSources) {
      loadSources();
    }
  });

  onUnmounted(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
    stopSourcePolling();
  });

  return {
    // 状态（从 store 直接暴露）
    query: localQuery,
    results: store.results,
    filteredResults,
    total: store.total,
    rawTotal: store.rawTotal,
    sourceStats: store.sourceStats,
    categoryCounts: store.categoryCounts,
    tookMs: store.tookMs,
    searching: store.searching,
    currentQuery: store.currentQuery,
    suggestions: store.suggestions,
    queryHistory: store.queryHistory,
    activeFilters: store.activeFilters,
    sources: store.sources,
    activeSources: store.activeSources,
    sortedSources: store.sortedSources,
    hasResults: store.hasResults,
    resultsByCategory: store.resultsByCategory,
    resultsBySource: store.resultsBySource,
    selectedResultId: store.selectedResultId,
    // 筛选器选项
    sourceFilters,
    categoryFilters,
    // 方法
    searchDebounced,
    searchNow,
    setFilter,
    clearFilter,
    resetFilters: store.resetFilters,
    resetResults: store.resetResults,
    navigateToResult,
    loadSources,
    clearHistory: store.clearHistory,
    startSourcePolling,
    stopSourcePolling,
  };
}
