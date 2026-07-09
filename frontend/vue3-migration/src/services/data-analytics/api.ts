/**
 * 伏羲 v2.1 — 数据分析 API 封装
 * 封装 5 个端点：stats / trends / report / storage-dist / export
 * 数据来源：后端 API，失败时抛出错误，不返回兜底 mock
 */

import apiClient from '@/api';
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

// ───── 端点封装 ─────

/** 健康检查 */
export async function health() {
  return apiClient.get(`${API_BASE}/health`);
}

/** 获取统计概览 */
export async function getStats(): Promise<StatsResponse> {
  return apiClient.get(`${API_BASE}/stats`) as Promise<StatsResponse>;
}

/** 获取趋势数据 */
export async function getTrends(period: TrendPeriod): Promise<TrendsResponse> {
  return apiClient.get(`${API_BASE}/trends`, { params: { period } }) as Promise<TrendsResponse>;
}

/** 生成报表 */
export async function getReport(params: ReportRequest): Promise<ReportResponse> {
  return apiClient.post(`${API_BASE}/report`, params) as Promise<ReportResponse>;
}

/** 获取存储分布 */
export async function getStorageDist(): Promise<StorageDistResponse> {
  return apiClient.get(`${API_BASE}/storage`) as Promise<StorageDistResponse>;
}

/** 导出数据 */
export async function exportData(config: ExportConfig): Promise<ExportResponse> {
  return apiClient.post(`${API_BASE}/export`, config) as Promise<ExportResponse>;
}
