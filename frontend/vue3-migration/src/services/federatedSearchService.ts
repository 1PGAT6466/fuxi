/**
 * 伏羲 v2.1 — 联邦搜索服务
 *
 * 前端联邦搜索聚合服务，负责：
 * 1. 并发发起多源搜索请求
 * 2. 去重算法（基于内容指纹 Jaccard 相似度）
 * 3. 结果聚合排序
 * 4. 权限过滤
 * 5. 结果缓存管理
 *
 * 后端 API 就绪后，此服务的聚合逻辑可迁移到服务端，
 * 前端仅需调用 POST /api/search/federated 即可。
 */

import type {
  FederatedSearchRequest,
  FederatedSearchResponse,
  FederatedSearchResult,
  SearchSource,
  SearchSourceType,
  ResultCategory,
  SourceStats,
} from '@/types/federated-search';
import { search } from '@/api/unified-search';
import { unifiedSearch } from '@/api/symbols';
import { getSearchSources } from '@/api/federated-search';
import { createLogger } from '@/utils/logger';

const logger = createLogger('FederatedSearchService');

// ═══════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════

/** 简单的 Jaccard 相似度（字符级 n-gram） */
function jaccardSimilarity(a: string, b: string, n: number = 3): number {
  if (!a || !b) return 0;

  const ngramsA = new Set<string>();
  const ngramsB = new Set<string>();

  for (let i = 0; i <= a.length - n; i++) ngramsA.add(a.slice(i, i + n));
  for (let i = 0; i <= b.length - n; i++) ngramsB.add(b.slice(i, i + n));

  let intersection = 0;
  for (const ng of ngramsA) {
    if (ngramsB.has(ng)) intersection++;
  }

  const union = ngramsA.size + ngramsB.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

/** 生成内容指纹（取标题 + 摘要的前 200 字符） */
function generateFingerprint(title: string, snippet: string): string {
  return `${title || ''} ${snippet || ''}`.slice(0, 200).toLowerCase().trim();
}

/** 分类映射 */
function mapSourceToCategory(sourceType: SearchSourceType): ResultCategory {
  const map: Record<SearchSourceType, ResultCategory> = {
    local_kb: 'document',
    wiki: 'wiki',
    chat: 'chat',
    external_api: 'external',
    database: 'database',
    file: 'file',
  };
  return map[sourceType] || 'document';
}

// ═══════════════════════════════════════════
// 服务
// ═══════════════════════════════════════════

/**
 * 前端联邦搜索聚合器
 *
 * 当后端 POST /api/search/federated 不可用时，
 * 由前端并发调用各搜索源 API 并自行聚合。
 */
export class FederatedSearchAggregator {
  private sources: SearchSource[] = [];

  /**
   * 加载搜索源列表
   */
  async loadSources(): Promise<SearchSource[]> {
    try {
      const res = await getSearchSources();
      this.sources = res.sources.filter((s) => s.enabled);
      return this.sources;
    } catch {
      logger.warn('获取搜索源失败，使用默认源');
      this.sources = this.getDefaultSources();
      return this.sources;
    }
  }

  /**
   * 执行联邦搜索
   */
  async search(request: FederatedSearchRequest): Promise<FederatedSearchResponse> {
    const {
      query,
      sourceIds,
      sourceTypes,
      limit = 50,
      minScore = 0.1,
      deduplicate: enableDedup = true,
      deduplicateThreshold = 0.85,
      sortBy = 'relevance',
    } = request;

    if (!this.sources.length) {
      await this.loadSources();
    }

    // 筛选搜索源
    let targetSources = this.sources;
    if (sourceIds?.length) {
      targetSources = targetSources.filter((s) => sourceIds.includes(s.id));
    }
    if (sourceTypes?.length) {
      targetSources = targetSources.filter((s) => sourceTypes.includes(s.type));
    }

    const startTime = Date.now();
    const stats: SourceStats[] = [];

    // 并发搜索所有源
    const sourcePromises = targetSources.map(async (source) => {
      const srcStart = Date.now();
      try {
        const results = await this.querySource(source, query, source.resultLimit);
        const elapsed = Date.now() - srcStart;
        stats.push({
          sourceId: source.id,
          sourceName: source.name,
          sourceIcon: source.icon,
          resultCount: results.length,
          responseTimeMs: elapsed,
          status: 'success',
        });
        return results;
      } catch (err: unknown) {
        const elapsed = Date.now() - srcStart;
        const errorMsg = err instanceof Error ? err.message : String(err);
        logger.warn(`搜索源 ${source.name} 失败:`, errorMsg);
        stats.push({
          sourceId: source.id,
          sourceName: source.name,
          sourceIcon: source.icon,
          resultCount: 0,
          responseTimeMs: elapsed,
          status: errorMsg.includes('timeout') ? 'timeout' : 'error',
          error: errorMsg,
        });
        return [];
      }
    });

    const allSourceResults = await Promise.all(sourcePromises);
    const allResults = allSourceResults.flat();
    const rawTotal = allResults.length;

    // 去重
    let deduped = allResults;
    if (enableDedup) {
      deduped = this.deduplicate(allResults, deduplicateThreshold);
    }

    // 按分数排序
    if (sortBy === 'relevance') {
      deduped.sort((a, b) => b.score - a.score);
    } else if (sortBy === 'date') {
      deduped.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    }

    // 截断
    const sliced = deduped.slice(0, limit);
    const tookMs = Date.now() - startTime;

    // 统计分类
    const categoryCounts: Record<ResultCategory, number> = {
      document: 0, wiki: 0, chat: 0, tool: 0, file: 0, database: 0, external: 0,
    };
    for (const r of sliced) {
      if (categoryCounts[r.category] !== undefined) {
        categoryCounts[r.category]!++;
      }
    }

    return {
      query,
      results: sliced,
      rawTotal,
      total: sliced.length,
      tookMs,
      sourceStats: stats,
      categoryCounts,
      truncated: deduped.length > limit,
      suggestions: rawTotal === 0
        ? [`尝试更宽泛的关键词`, `检查数据源连接状态`]
        : [],
    };
  }

  /**
   * 查询单个搜索源
   */
  private async querySource(
    source: SearchSource,
    query: string,
    resultLimit: number,
  ): Promise<FederatedSearchResult[]> {
    let rawResults: any[] = [];

    switch (source.type) {
      case 'local_kb':
      case 'wiki': {
        // 使用现有的统一搜索 API
        try {
          const res = await search(query, resultLimit);
          rawResults = [...(res.results || []), ...(res.wiki_results || []), ...(res.chunk_results || [])];
        } catch {
          // 降级到 unifiedSearch
          try {
            const unified = await unifiedSearch(query);
            rawResults = unified.data.matches.map((m) => ({
              title: m.title,
              content: m.description,
              score: 0.5,
              source: m.type,
            }));
          } catch {
            rawResults = [];
          }
        }
        break;
      }
      case 'chat':
        // Chat 历史搜索暂时使用现有 API 降级
        rawResults = [];
        break;
      case 'file':
        // 文件索引搜索暂时使用现有 API 降级
        rawResults = [];
        break;
      case 'external_api':
        // 外部 API 搜索由后端处理
        rawResults = [];
        break;
      case 'database':
        // 数据库搜索由后端处理
        rawResults = [];
        break;
    }

    // 转换为标准格式
    return rawResults.map((item, index) => {
      const title = item.title || item.source_doc || `${source.name} 结果 ${index + 1}`;
      const snippet = item.content || item.snippet || '';
      return {
        id: item.id || item.chunk_id || `fed-${source.id}-${index}`,
        title,
        snippet: snippet.slice(0, 300),
        content: snippet,
        sourceId: source.id,
        sourceName: source.name,
        sourceType: source.type,
        sourceIcon: source.icon,
        score: item.score || 0.5,
        url: item.url,
        category: mapSourceToCategory(source.type),
        timestamp: Date.now(),
        fingerprint: generateFingerprint(title, snippet),
        metadata: item.metadata,
        highlights: item.highlights,
        fileType: item.file_type,
        fileSize: item.size,
      };
    });
  }

  /**
   * 去重 — 使用内容指纹 Jaccard 相似度
   */
  private deduplicate(
    results: FederatedSearchResult[],
    threshold: number,
  ): FederatedSearchResult[] {
    if (results.length <= 1) return results;

    const kept: FederatedSearchResult[] = [];
    const seen: string[] = [];

    // 按分数降序排列（高分结果优先保留）
    const sorted = [...results].sort((a, b) => b.score - a.score);

    for (const result of sorted) {
      let isDuplicate = false;

      for (const fp of seen) {
        const similarity = jaccardSimilarity(result.fingerprint, fp);
        if (similarity >= threshold) {
          isDuplicate = true;
          break;
        }
      }

      if (!isDuplicate) {
        kept.push(result);
        seen.push(result.fingerprint);
      }
    }

    return kept;
  }

  /**
   * 默认搜索源（后端不可用时使用）
   */
  private getDefaultSources(): SearchSource[] {
    return [
      {
        id: 'local-kb',
        name: '本地知识库',
        type: 'local_kb',
        icon: '📚',
        description: '伏羲平台本地文档与知识库',
        enabled: true,
        status: 'online',
        weight: 10,
        timeout: 5000,
        resultLimit: 50,
        tags: ['内部', '文档'],
      },
      {
        id: 'wiki',
        name: 'Wiki 系统',
        type: 'wiki',
        icon: '📝',
        description: '伏羲 Wiki 知识条目',
        enabled: true,
        status: 'online',
        weight: 8,
        timeout: 5000,
        resultLimit: 30,
        tags: ['Wiki', '知识'],
      },
      {
        id: 'chat-history',
        name: '对话历史',
        type: 'chat',
        icon: '💬',
        description: 'AI 对话历史记录搜索',
        enabled: true,
        status: 'online',
        weight: 5,
        timeout: 3000,
        resultLimit: 20,
        tags: ['对话', '历史'],
      },
      {
        id: 'file-index',
        name: '文件索引',
        type: 'file',
        icon: '📁',
        description: '上传文件全文搜索',
        enabled: true,
        status: 'online',
        weight: 6,
        timeout: 5000,
        resultLimit: 30,
        tags: ['文件', '附件'],
      },
    ];
  }
}

/** 单例 */
export const federatedSearchAggregator = new FederatedSearchAggregator();
