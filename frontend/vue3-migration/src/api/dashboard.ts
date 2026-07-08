/**
 * 伏羲 v2.1 — 仪表板 API
 * 路径对齐：后端 /api/dashboard 已存在，/api/admin/dashboard 不存在
 */

import apiClient from './index';

/** 获取仪表板数据 → /api/dashboard（后端 dashboard.py） */
export function getDashboardStats() {
  return apiClient.get('/api/dashboard');
}

/** @deprecated 管理员仪表板可走 /api/admin/metrics-summary（后端 server.py @app 直连） */
export function getAdminMetricsSummary() {
  return apiClient.get('/api/admin/metrics-summary');
}
