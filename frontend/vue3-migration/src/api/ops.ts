/**
 * 伏羲 v2.1 — 运维 API
 *
 * 后端路由：
 *   GET  /api/ops/sync/plugins/status   → 插件源状态列表
 *   POST /api/ops/sync/plugins/trigger  → 触发同步
 *   GET  /api/ops/metrics               → 实时指标
 *   GET  /api/ops/metrics/aggregated    → 聚合指标（趋势）
 *   GET  /api/ops/alerts                → 告警历史
 *   GET  /api/ops/alerts/rules          → 告警规则
 *   GET  /api/ops/health                → 健康检查
 */

import apiClient from './index';

// ─── 类型定义 ───

/** 插件源 */
export interface PluginSource {
  id: string;
  name: string;
  type: string;        // git / npm / pypi / custom
  url: string;
  status: 'active' | 'error' | 'syncing' | 'idle';
  lastSync: string | null;
  lastError?: string;
  config?: Record<string, unknown>;
}

/** 同步历史记录 */
export interface SyncHistory {
  id: string;
  sourceId: string;
  sourceName: string;
  startTime: string;
  endTime: string | null;
  status: 'success' | 'failed' | 'running';
  itemsSynced: number;
  error?: string;
}

/** 系统指标快照 */
export interface SystemMetrics {
  cpu: number;         // 百分比 0-100
  memory: number;      // 百分比 0-100
  disk: number;        // 百分比 0-100
  network: {
    in: number;        // bytes/s
    out: number;       // bytes/s
  };
  timestamp: string;
}

/** 聚合指标（趋势数据） */
export interface AggregatedMetrics {
  timestamps: string[];
  cpu: number[];
  memory: number[];
  requestCount: number[];
  responseTime: number[];
}

/** 告警 */
export interface Alert {
  id: string;
  ruleId: string;
  ruleName: string;
  level: 'info' | 'warning' | 'critical';
  message: string;
  metric: string;
  value: number;
  threshold: number;
  timestamp: string;
  resolved: boolean;
  resolvedAt?: string;
}

/** 告警规则 */
export interface AlertRule {
  id: string;
  name: string;
  metric: string;        // cpu / memory / disk / response_time
  condition: string;     // gt / lt / eq
  threshold: number;
  level: 'info' | 'warning' | 'critical';
  enabled: boolean;
  notifyChannels: string[];
  createdAt: string;
}

/** 健康检查 */
export interface HealthCheckResult {
  status: 'healthy' | 'degraded' | 'unhealthy';
  checks: Array<{
    name: string;
    status: 'pass' | 'fail' | 'warn';
    message?: string;
    latency?: number;
  }>;
  timestamp: string;
}

// ─── 插件源管理 ───

/** 获取插件源状态列表 */
export function getPluginSources(): Promise<PluginSource[]> {
  return apiClient.get('/api/ops/sync/plugins/status') as Promise<PluginSource[]>;
}

/** 触发插件源同步 */
export function triggerPluginSync(sourceId: string): Promise<{ success: boolean; message: string }> {
  return apiClient.post('/api/ops/sync/plugins/trigger', { sourceId }) as Promise<{ success: boolean; message: string }>;
}

/** 测试插件源连接 */
export function testPluginConnection(sourceId: string): Promise<{ success: boolean; latency: number; message: string }> {
  return apiClient.post(`/api/ops/sync/plugins/${sourceId}/test`) as Promise<{ success: boolean; latency: number; message: string }>;
}

/** 添加插件源 */
export function addPluginSource(data: Omit<PluginSource, 'id' | 'status' | 'lastSync'>): Promise<PluginSource> {
  return apiClient.post('/api/ops/sync/plugins', data) as Promise<PluginSource>;
}

/** 更新插件源 */
export function updatePluginSource(id: string, data: Partial<PluginSource>): Promise<PluginSource> {
  return apiClient.put(`/api/ops/sync/plugins/${id}`, data) as Promise<PluginSource>;
}

/** 删除插件源 */
export function deletePluginSource(id: string): Promise<{ success: boolean }> {
  return apiClient.delete(`/api/ops/sync/plugins/${id}`) as Promise<{ success: boolean }>;
}

/** 获取同步历史 */
export function getSyncHistory(): Promise<SyncHistory[]> {
  return apiClient.get('/api/ops/sync/history') as Promise<SyncHistory[]>;
}

// ─── 监控指标 ───

/** 获取实时系统指标 */
export function getSystemMetrics(): Promise<SystemMetrics> {
  return apiClient.get('/api/ops/metrics') as Promise<SystemMetrics>;
}

/** 获取聚合指标（趋势） */
export function getAggregatedMetrics(params?: { range?: string; interval?: string }): Promise<AggregatedMetrics> {
  return apiClient.get('/api/ops/metrics/aggregated', { params }) as Promise<AggregatedMetrics>;
}

// ─── 告警 ───

/** 获取告警历史 */
export function getAlerts(params?: { level?: string; resolved?: boolean; limit?: number }): Promise<Alert[]> {
  return apiClient.get('/api/ops/alerts', { params }) as Promise<Alert[]>;
}

/** 获取告警规则 */
export function getAlertRules(): Promise<AlertRule[]> {
  return apiClient.get('/api/ops/alerts/rules') as Promise<AlertRule[]>;
}

// ─── 健康检查 ───

/** 获取健康检查状态 */
export function getOpsHealth(): Promise<HealthCheckResult> {
  return apiClient.get('/api/ops/health') as Promise<HealthCheckResult>;
}
