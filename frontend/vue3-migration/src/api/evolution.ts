/**
 * 伏羲 v2.1 — 进化面板 API
 */

import apiClient from './index';

/** 获取进化概览 → /api/evolution/overview */
export function getEvolutionOverview() {
  return apiClient.get('/api/evolution/overview');
}

/** 获取进化状态 → /api/evolution/status */
export function getEvolutionStatus() {
  return apiClient.get('/api/evolution/status');
}

/** 获取进化规则 → /api/evolution/rules */
export function getEvolutionRules() {
  return apiClient.get('/api/evolution/rules');
}

/** 获取进化日志 → /api/evolution/logs */
export function getEvolutionLogs() {
  return apiClient.get('/api/evolution/logs');
}

/** 获取进化模式 → /api/evolution/patterns */
export function getEvolutionPatterns(category?: string) {
  const params = category ? `?category=${category}` : '';
  return apiClient.get(`/api/evolution/patterns${params}`);
}

/** 获取自校正记录 → /api/evolution/corrections */
export function getEvolutionCorrections(days: number = 7) {
  return apiClient.get(`/api/evolution/corrections?days=${days}`);
}

/** 获取情景记忆 → /api/evolution/episodes */
export function getEvolutionEpisodes(days: number = 7, skill?: string) {
  let url = `/api/evolution/episodes?days=${days}`;
  if (skill) url += `&skill=${skill}`;
  return apiClient.get(url);
}

/** 创建进化规则 → POST /api/evolution/rules */
export function createEvolutionRule(data: Record<string, unknown>) {
  return apiClient.post('/api/evolution/rules', data);
}

/** 更新进化规则 → PUT /api/evolution/rules/:id */
export function updateEvolutionRule(id: string, data: Record<string, unknown>) {
  return apiClient.put(`/api/evolution/rules/${id}`, data);
}

/** 删除进化规则 → DELETE /api/evolution/rules/:id */
export function deleteEvolutionRule(id: string) {
  return apiClient.delete(`/api/evolution/rules/${id}`);
}
