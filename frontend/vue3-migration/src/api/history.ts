/**
 * 伏羲 v2.1 — 历史记录 API 接口
 *
 * P2 增强：访问历史追踪的后端 API 封装。
 *
 * 接口列表：
 * - POST   /api/history/visit      记录访问
 * - GET    /api/history/recent     获取最近访问列表
 * - DELETE /api/history/clear      清除所有历史
 * - DELETE /api/history/:id        删除单条历史
 */

import apiClient from './index';

// ═══════════════════════════════════════════
// 类型定义
// ═══════════════════════════════════════════

/** 访问资源类型 */
export type HistoryItemType = 'chat' | 'document' | 'knowledge_base';

/** 访问记录 */
export interface HistoryRecord {
  id: string;
  userId: string | number;
  itemId: string;
  type: HistoryItemType;
  title: string;
  description?: string;
  route?: string;
  visitedAt: string;
  visitCount?: number;
}

/** 记录访问请求 */
export interface RecordVisitParams {
  userId: string | number;
  itemId: string;
  type: HistoryItemType;
  title: string;
  description?: string;
  route?: string;
}

/** 获取最近访问请求参数 */
export interface RecentVisitsParams {
  userId: string | number;
  limit?: number;
  type?: HistoryItemType;
}

/** 获取最近访问响应 */
export interface RecentVisitsResult {
  visits: HistoryRecord[];
  total: number;
}

// ═══════════════════════════════════════════
// API 函数
// ═══════════════════════════════════════════

/**
 * 记录一次访问
 */
export async function recordVisit(
  params: RecordVisitParams,
): Promise<HistoryRecord> {
  const res = (await apiClient.post('/api/history/visit', params)) as {
    data: HistoryRecord;
  };
  return res.data;
}

/**
 * 获取最近访问列表
 */
export async function getRecentVisits(
  params: RecentVisitsParams,
): Promise<RecentVisitsResult> {
  const res = (await apiClient.get('/api/history/recent', {
    params,
  })) as { data: RecentVisitsResult };
  return res.data;
}

/**
 * 清除指定用户的所有历史记录
 */
export async function clearHistory(
  userId: string | number,
): Promise<void> {
  await apiClient.delete('/api/history/clear', {
    params: { userId },
  });
}

/**
 * 删除单条历史记录
 */
export async function deleteHistoryItem(
  userId: string | number,
  id: string,
): Promise<void> {
  await apiClient.delete(`/api/history/${id}`, {
    params: { userId },
  });
}
