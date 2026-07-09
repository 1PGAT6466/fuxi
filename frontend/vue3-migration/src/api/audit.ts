/**
 * 伏羲 v2.1 — 审计日志 API
 * 对接后端 /api/audit/logs、/api/audit/stats
 */

import apiClient from './index';

export interface AuditLogEntry {
  timestamp: string;
  user: string;
  action: string;
  resource?: string;
  status?: string;
  details?: Record<string, unknown>;
  ip?: string;
}

export interface AuditLogsResponse {
  status: string;
  message: string;
  data: {
    entries: AuditLogEntry[];
    count: number;
  };
}

export interface AuditStatsResponse {
  data: Record<string, unknown>;
}

export interface AuditLogsParams {
  user?: string;
  action?: string;
  days?: number;
  limit?: number;
}

/** 查询审计日志 → GET /api/audit/logs */
export async function fetchAuditLogs(params?: AuditLogsParams): Promise<AuditLogsResponse> {
  const raw = (await apiClient.get('/api/audit/logs', { params })) as Record<string, unknown>;
  // 后端返回 {status, message, data: {entries, count}} 或直接 {data: {entries, count}}
  // apiClient 响应拦截器已提取 response.data

  // 情况1: 有 data 包装 → {status, message, data: {entries, count}}
  if (raw.data && typeof raw.data === 'object') {
    return raw as unknown as AuditLogsResponse;
  }
  // 情况2: 已被解包为 {entries, count} — 重新包装
  if (raw.entries || raw.count !== undefined) {
    return {
      status: 'success',
      message: 'ok',
      data: {
        entries: (raw.entries as AuditLogEntry[]) || [],
        count: (raw.count as number) || 0,
      },
    };
  }
  // 情况3: 标准格式 {status, message, data}
  return raw as unknown as AuditLogsResponse;
}

/** 获取审计日志统计 */
export async function fetchAuditStats(days?: number): Promise<AuditStatsResponse> {
  return apiClient.get('/api/audit/stats', { params: days ? { days } : undefined }) as Promise<AuditStatsResponse>;
}
