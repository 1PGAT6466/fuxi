/**
 * 伏羲 v2.1 — 进化面板 API
 * 路径对齐：后端实际路由为 /api/evolution/overview
 */

import apiClient from './index';

/** 获取进化概览 → /api/evolution/overview（后端有） */
export function getEvolutionOverview() {
  return apiClient.get('/api/evolution/overview');
}

/** @deprecated 使用 getEvolutionOverview 替代，后端无 /api/evolution 端点 */
export function getEvolutionStatus() {
  console.warn('[evolution.ts] /api/evolution 已废弃，请使用 /api/evolution/overview');
  return apiClient.get('/api/evolution/overview');
}
