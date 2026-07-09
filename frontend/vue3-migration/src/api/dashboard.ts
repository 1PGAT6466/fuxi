/**
 * 伏羲 v2.1 — 仪表板 API
 *
 * 后端实际路由：
 *   GET /api/dashboard       → {dashboard: {...}}（当前内容较空，含系统概览）
 *   GET /api/health          → {status, checks, bagua, ...}（健康检查详情）
 *   GET /api/admin/users     → {ok, users, total}
 *   GET /api/audit/logs      → {status, message, data: {entries, count}}
 *   GET /api/growth/overview → {symbols, summary, timestamp}
 */

import apiClient from './index';

// ─── 健康检查 → /api/health ───
export interface HealthCheck {
  status: string;
  checks?: Record<string, { status: string; timestamp: number }>;
  bagua?: Record<string, string>;
  engine?: string;
  intent_mode?: string;
  timestamp?: number;
}

export function getHealth(): Promise<HealthCheck> {
  return apiClient.get('/api/health') as Promise<HealthCheck>;
}

// ─── 仪表板概览 → /api/dashboard ───
export interface DashboardOverview {
  dashboard: Record<string, unknown>;
}

export function getDashboardStats(): Promise<DashboardOverview> {
  return apiClient.get('/api/dashboard') as Promise<DashboardOverview>;
}

// ─── 管理员指标汇总 → /api/admin/metrics-summary ───
export function getAdminMetricsSummary() {
  return apiClient.get('/api/admin/metrics-summary');
}
