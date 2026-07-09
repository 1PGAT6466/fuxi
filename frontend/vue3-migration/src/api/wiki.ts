import apiClient from './index';

// ── 后端 Wiki 页面格式 ──
export interface WikiPage {
  id: string;
  title: string;
  category: string;
  tags: string[];
  summary: string;
  content: string;
  sources: string[];
  version: number;
  quality_score: number;
  created_at: string;
  updated_at: string;
}

// ── 后端 Wiki 列表响应 ──
export interface WikiListResponse {
  ok: boolean;
  title: string;
  description: string;
  pages: WikiPage[];
  total: number;
  categories: string[];
}

/** 获取 Wiki 页面列表 → GET /api/wiki */
export function getWikiPages(): Promise<WikiListResponse> {
  return apiClient.get('/api/wiki') as Promise<WikiListResponse>;
}

/** 获取单个 Wiki 页面详情 → GET /api/wiki/{id} */
export function getWikiPage(id: string) {
  return apiClient.get(`/api/wiki/${id}`);
}

/** 创建 Wiki 页面 → POST /api/wiki */
export function createWikiPage(data: Record<string, unknown>) {
  return apiClient.post('/api/wiki', data);
}

/** 更新 Wiki 页面 → PUT /api/wiki/{id} */
export function updateWikiPage(id: string, data: Record<string, unknown>) {
  return apiClient.put(`/api/wiki/${id}`, data);
}
