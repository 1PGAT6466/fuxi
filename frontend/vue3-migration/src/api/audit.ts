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

/** 查询审计日志 */
export async function fetchAuditLogs(params?: AuditLogsParams): Promise<AuditLogsResponse> {
  return apiClient.get('/api/audit/logs', { params }) as Promise<AuditLogsResponse>;
}

/** 获取审计日志统计 */
export async function fetchAuditStats(days?: number): Promise<AuditStatsResponse> {
  return apiClient.get('/api/audit/stats', { params: days ? { days } : undefined }) as Promise<AuditStatsResponse>;
}
