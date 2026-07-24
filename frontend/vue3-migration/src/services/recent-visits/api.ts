/**
 * 伏羲 v2.1 — 最近访问服务 API
 * P2 增强：访问历史追踪
 */

import apiClient from '@/api';
import type {
  VisitRecord,
  RecordVisitRequest,
  GetRecentVisitsParams,
} from './types';

// ═══════════════════════════════════════════
// 记录访问
// ═══════════════════════════════════════════

interface VisitResponse {
  data: VisitRecord;
}

export async function recordVisit(
  params: RecordVisitRequest,
): Promise<VisitRecord> {
  const res = (await apiClient.post('/api/history/visit', params)) as VisitResponse;
  return res.data;
}

// ═══════════════════════════════════════════
// 获取最近访问列表
// ═══════════════════════════════════════════

interface RecentVisitsResponse {
  data: {
    visits: VisitRecord[];
    total: number;
  };
}

export async function getRecentVisits(
  params: GetRecentVisitsParams,
): Promise<{ visits: VisitRecord[]; total: number }> {
  const res = (await apiClient.get('/api/history/recent', {
    params,
  })) as RecentVisitsResponse;
  return res.data;
}

// ═══════════════════════════════════════════
// 清除所有历史
// ═══════════════════════════════════════════

export async function clearHistory(userId: string | number): Promise<void> {
  await apiClient.delete('/api/history/clear', {
    params: { userId },
  });
}

// ═══════════════════════════════════════════
// 删除单条历史
// ═══════════════════════════════════════════

export async function deleteHistoryItem(
  userId: string | number,
  id: string,
): Promise<void> {
  await apiClient.delete(`/api/history/${id}`, {
    params: { userId },
  });
}
