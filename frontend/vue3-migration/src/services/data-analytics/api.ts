/**
 * 伏羲 v2.1 — 数据分析 API 封装
 * 封装端点：stats / trends / report / storage-dist / export / templates / share
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
  ReportTemplate,
  ShareConfig,
  ShareResponse,
  SharedReport,
} from './types';

// ───── 错误处理 ─────

const API_BASE = '/api/analytics';

// ───── 统计相关 ─────

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

// ───── 导出相关 ─────

/** 导出数据（支持 PDF/Excel/CSV/JSON） */
export async function exportData(config: ExportConfig): Promise<ExportResponse> {
  return apiClient.post(`${API_BASE}/export`, config) as Promise<ExportResponse>;
}

// ───── 报表模板 ─────

/** 获取模板列表 */
export async function getTemplates(): Promise<ReportTemplate[]> {
  return apiClient.get(`${API_BASE}/templates`) as Promise<ReportTemplate[]>;
}

/** 创建模板 */
export async function createTemplate(data: Omit<ReportTemplate, 'id' | 'created_at' | 'updated_at'>): Promise<ReportTemplate> {
  return apiClient.post(`${API_BASE}/templates`, data) as Promise<ReportTemplate>;
}

/** 更新模板 */
export async function updateTemplate(id: string, data: Partial<ReportTemplate>): Promise<ReportTemplate> {
  return apiClient.put(`${API_BASE}/templates/${id}`, data) as Promise<ReportTemplate>;
}

/** 删除模板 */
export async function deleteTemplate(id: string): Promise<void> {
  return apiClient.delete(`${API_BASE}/templates/${id}`) as Promise<void>;
}

// ───── 报表分享 ─────

/** 生成分享链接 */
export async function shareReport(config: ShareConfig): Promise<ShareResponse> {
  return apiClient.post('/api/reports/share', config) as Promise<ShareResponse>;
}

/** 通过 token 访问分享的报表 */
export async function getSharedReport(token: string): Promise<SharedReport> {
  return apiClient.get(`/api/reports/${token}`) as Promise<SharedReport>;
}

/** 撤销分享 */
export async function revokeShare(token: string): Promise<void> {
  return apiClient.delete(`/api/reports/share/${token}`) as Promise<void>;
}
