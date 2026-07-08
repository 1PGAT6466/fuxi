/**
 * 伏羲 v2.1 — 成长面板 API
 * 读取后端 /api/growth/overview 获取四象成长指标
 */

import apiClient from './index';

export interface SymbolGrowth {
  query_count: number;
  avg_latency_ms: number;
  avg_confidence: number;
  trend: Array<{
    date: string;
    query_count: number;
    avg_latency_ms: number;
    avg_confidence: number;
  }>;
}

export interface GrowthOverviewResponse {
  symbols: Record<string, SymbolGrowth>;
  summary: {
    total_queries: number;
    avg_latency_ms: number;
    avg_confidence: number;
    cache_hit_rate: number;
  };
  timestamp: number;
}

/** 获取成长概览 */
export async function fetchGrowthOverview(): Promise<GrowthOverviewResponse> {
  return apiClient.get('/api/growth/overview') as Promise<GrowthOverviewResponse>;
}
