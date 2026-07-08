/**
 * 伏羲 v2.1 — 数据分析 API 封装
 * 封装 5 个端点：stats / trends / report / storage-dist / export
 * Mock 兜底：API 不可用时使用内置 mock 数据
 */

import apiClient from '@/api';
import { mockAnalyticsResponse } from './mock';
import type {
  StatsResponse,
  TrendsResponse,
  TrendPeriod,
  StorageDistResponse,
  ReportRequest,
  ReportResponse,
  ExportConfig,
  ExportResponse,
} from './types';

// ───── 错误处理 ─────

const API_BASE = '/api/analytics';

/**
 * 带 mock 兜底的通用请求封装
 */
async function requestWithFallback<T>(
  endpoint: string,
  mockData: T,
  method: 'GET' | 'POST' = 'GET',
  body?: unknown,
): Promise<T> {
  try {
    if (method === 'GET') {
      return (await apiClient.get(`${API_BASE}${endpoint}`)) as T;
    }
    return (await apiClient.post(`${API_BASE}${endpoint}`, body)) as T;
  } catch (err) {
    console.warn(`[Data Analytics] API ${API_BASE}${endpoint} 不可用，使用 mock 数据`, err);
    return mockData;
  }
}

// ───── 端点封装 ─────

/** 健康检查 */
export async function health() {
  try {
    return await apiClient.get(`${API_BASE}/health`);
  } catch (err) {
    console.warn(`[Data Analytics] API ${API_BASE}/health 不可用`, err);
    return { status: 'degraded' };
  }
}

/** 获取统计概览 */
export async function getStats(): Promise<StatsResponse> {
  return requestWithFallback<StatsResponse>('/stats', mockAnalyticsResponse.stats());
}

/** 获取趋势数据 */
export async function getTrends(period: TrendPeriod): Promise<TrendsResponse> {
  return requestWithFallback<TrendsResponse>(
    `/trends?period=${period}`,
    mockAnalyticsResponse.trends(period),
  );
}

/** 生成报表 */
export async function getReport(params: ReportRequest): Promise<ReportResponse> {
  return requestWithFallback<ReportResponse>(
    '/report',
    mockAnalyticsResponse.report(params),
    'POST',
    params,
  );
}

/** 获取存储分布 */
export async function getStorageDist(): Promise<StorageDistResponse> {
  return requestWithFallback<StorageDistResponse>('/storage', mockAnalyticsResponse.storageDist());
}

/** 导出数据 */
export async function exportData(config: ExportConfig): Promise<ExportResponse> {
  return requestWithFallback<ExportResponse>(
    '/export',
    mockAnalyticsResponse.exportData(config),
    'POST',
    config,
  );
}
