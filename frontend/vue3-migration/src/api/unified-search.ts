/**
 * 伏羲 v2.1 — 统一搜索 API（伏羲令）
 * 对接方案规划的后端 /api/unified-search（当前后端为占位实现）
 *
 * 方案要求：跨服务统一搜索，支持自然语言查询
 * 当前状态：后端尚未实现完整统一搜索，前端 API 层预备对接
 */

import apiClient from './index';

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

/** 伏羲令统一搜索 */
export async function unifiedSearch(query: string): Promise<UnifiedSearchResponse> {
  return apiClient.get('/api/unified-search', {
    params: { q: query },
  }) as Promise<UnifiedSearchResponse>;
}
