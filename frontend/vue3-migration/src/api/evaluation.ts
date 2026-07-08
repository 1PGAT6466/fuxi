/**
 * 伏羲 v2.1 — 评测 API
 * 路径对齐：所有评测接口统一使用 /api/evaluation/*
 * 后端实际路由：evaluation.py 提供 overview，eval_automation 提供 run/report/history
 */

import apiClient from './index';

// ============================
// 评测概览
// ============================

/** 获取评测概览 → /api/evaluation/overview（后端有） */
export function getEvaluationOverview() {
  return apiClient.get('/api/evaluation/overview');
}

// ============================
// 数据集管理（后端暂无，调用时返回 501 占位响应）
// 方案要求后端实现 /api/evaluation/datasets
// ============================

/** 获取评测数据集列表 */
export function getEvaluationDatasets() {
  return apiClient.get('/api/evaluation/datasets');
}

/** 创建评测 */
export function createEvaluation(data: any) {
  return apiClient.post('/api/evaluation', data);
}

// ============================
// 评测任务管理（后端暂无）
// ============================

/** 获取评测任务列表 */
export function getEvaluationTasks() {
  return apiClient.get('/api/evaluation/tasks');
}

/** 获取评测结果 */
export function getEvaluationResults() {
  return apiClient.get('/api/evaluation/results');
}

// ============================
// 评测自动化（/api/eval/*，由 server.py @app 直连）
// ============================

/** 运行评测 */
export function runEvaluation() {
  return apiClient.post('/api/eval/run');
}

/** 获取最新评测报告 */
export function getEvalReport() {
  return apiClient.get('/api/eval/report');
}

/** 获取评测历史 */
export function getEvalHistory() {
  return apiClient.get('/api/eval/history');
}
