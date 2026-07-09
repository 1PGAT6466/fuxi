/**
 * 伏羲 v2.1 — 搜索 API
 * 后端 GET /api/search?q=xxx 返回：
 *   {wiki_results, chunk_results, results, query, page, page_size, total}
 */

import apiClient from './index';

// ── 后端实际返回的搜索条目 ──
export interface SearchResultItem {
  id?: string;
  title?: string;
  content?: string;
  score?: number;
  source?: string;
  chunk_id?: string;
  source_doc?: string;
}

export interface SearchResponse {
  wiki_results: SearchResultItem[];
  chunk_results: SearchResultItem[];
  results: SearchResultItem[];
  query: string;
  page: number;
  page_size: number;
  total: number;
}

// ── 前端统一搜索结果格式 ──
export interface UnifiedSearchResult {
  type: 'document' | 'wiki' | 'tool' | 'service' | 'gua' | 'chat';
  title: string;
  url: string;
  description?: string;
  icon?: string;
  score?: number;
}

export interface UnifiedSearchResponse {
  data: {
    query: string;
    matches: UnifiedSearchResult[];
    total: number;
    took_ms: number;
  };
}

/** 调用后端搜索 → GET /api/search?q=xxx */
export async function search(query: string, top_k?: number): Promise<SearchResponse> {
  return apiClient.get('/api/search', {
    params: { q: query, top_k: top_k ?? 10 },
  }) as Promise<SearchResponse>;
}

/** 伏羲令统一搜索（别名） */
export async function unifiedSearch(query: string): Promise<UnifiedSearchResponse> {
  const data = await apiClient.get('/api/unified-search', {
    params: { q: query },
  }) as UnifiedSearchResponse;
  return data;
}
