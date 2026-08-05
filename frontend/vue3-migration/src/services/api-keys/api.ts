/**
 * 伏羲 v2.1 — API Key 管理 API 封装
 *
 * 封装 6 个端点：
 * - GET     /api/api-keys          — 获取 Key 列表
 * - POST    /api/api-keys          — 创建 Key
 * - GET     /api/api-keys/:id      — 获取 Key 详情
 * - PUT     /api/api-keys/:id      — 更新 Key
 * - DELETE  /api/api-keys/:id      — 删除 Key
 * - GET     /api/api-keys/:id/usage — 获取使用量统计
 */

import apiClient from '@/api';
import type {
  ApiKey,
  ApiKeyListResponse,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  ApiKeyUsageResponse,
  UsagePeriod,
  ApiKeyActionResult,
} from './types';

// ───── 常量 ─────

const API_BASE = '/api/api-keys';

/**
 * 后端返回格式: { status: 'success', data: T }
 * apiClient 响应拦截器已返回 response.data，所以这里拿到的是 { status, data } 包装
 * 需要提取 .data 字段
 */
interface ApiResponse<T> {
  status: string;
  data: T;
}

function extractData<T>(resp: unknown): T {
  if (resp && typeof resp === 'object' && 'data' in resp) {
    return (resp as ApiResponse<T>).data;
  }
  return resp as T;
}

// ═══════════════════════════════════════════
// CRUD 端点
// ═══════════════════════════════════════════

/** 获取 API Key 列表 */
export async function getApiKeys(): Promise<ApiKeyListResponse> {
  try {
    const resp = await apiClient.get(API_BASE);
    return extractData<ApiKeyListResponse>(resp);
  } catch (e) {
    console.error('[api-keys-api] getApiKeys 失败:', e);
    return { keys: [], total: 0 };
  }
}

/** 获取单个 API Key 详情 */
export async function getApiKey(id: string): Promise<ApiKey> {
  const resp = await apiClient.get(`${API_BASE}/${id}`);
  return extractData<ApiKey>(resp);
}

/** 创建 API Key */
export async function createApiKey(
  data: CreateApiKeyRequest,
): Promise<ApiKeyActionResult & { key: ApiKey }> {
  const resp = await apiClient.post(API_BASE, data);
  return extractData<ApiKeyActionResult & { key: ApiKey }>(resp);
}

/** 更新 API Key */
export async function updateApiKey(
  id: string,
  data: UpdateApiKeyRequest,
): Promise<ApiKeyActionResult> {
  const resp = await apiClient.put(`${API_BASE}/${id}`, data);
  return extractData<ApiKeyActionResult>(resp);
}

/** 删除 API Key */
export async function deleteApiKey(id: string): Promise<ApiKeyActionResult> {
  const resp = await apiClient.delete(`${API_BASE}/${id}`);
  return extractData<ApiKeyActionResult>(resp);
}

// ═══════════════════════════════════════════
// 使用量端点
// ═══════════════════════════════════════════

/** 获取 API Key 使用量统计 */
export async function getApiKeyUsage(
  id: string,
  period: UsagePeriod = 'week',
): Promise<ApiKeyUsageResponse> {
  const resp = await apiClient.get(`${API_BASE}/${id}/usage`, {
    params: { period },
  });
  return extractData<ApiKeyUsageResponse>(resp);
}
