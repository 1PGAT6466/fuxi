import apiClient from './index';

/** 获取图谱概览 → /api/graph/overview（包含节点、边、统计的完整数据） */
export function getGraphOverview<T = Record<string, unknown>>(): Promise<T> {
  return apiClient.get('/api/graph/overview') as Promise<T>;
}

/** 获取图谱统计 → /api/graph/stats */
export function getGraphStats<T = Record<string, unknown>>(): Promise<T> {
  return apiClient.get('/api/graph/stats') as Promise<T>;
}

/** 获取图谱节点 → /api/graph/nodes */
export function getGraphNodes<T = unknown[]>(): Promise<T> {
  return apiClient.get('/api/graph/nodes') as Promise<T>;
}

/** 获取图谱关系 → /api/graph/auto-edges */
export function getGraphRelations<T = unknown[]>(): Promise<T> {
  return apiClient.get('/api/graph/auto-edges') as Promise<T>;
}

/** 搜索图谱 → /api/graph/search?q=... */
export function searchGraph<T = unknown>(query: string): Promise<T> {
  return apiClient.get('/api/graph/search', {
    params: { q: query },
  }) as Promise<T>;
}
