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

// ═══════════════════════════════════════════
// CRUD 端点
// ═══════════════════════════════════════════

/** 获取 API Key 列表 */
export async function getApiKeys(): Promise<ApiKeyListResponse> {
  return apiClient.get(API_BASE) as Promise<ApiKeyListResponse>;
}

/** 获取单个 API Key 详情 */
export async function getApiKey(id: string): Promise<ApiKey> {
  return apiClient.get(`${API_BASE}/${id}`) as Promise<ApiKey>;
}

/** 创建 API Key */
export async function createApiKey(
  data: CreateApiKeyRequest,
): Promise<ApiKeyActionResult & { key: ApiKey }> {
  return apiClient.post(API_BASE, data) as Promise<ApiKeyActionResult & { key: ApiKey }>;
}

/** 更新 API Key */
export async function updateApiKey(
  id: string,
  data: UpdateApiKeyRequest,
): Promise<ApiKeyActionResult> {
  return apiClient.put(`${API_BASE}/${id}`, data) as Promise<ApiKeyActionResult>;
}

/** 删除 API Key */
export async function deleteApiKey(id: string): Promise<ApiKeyActionResult> {
  return apiClient.delete(`${API_BASE}/${id}`) as Promise<ApiKeyActionResult>;
}

// ═══════════════════════════════════════════
// 使用量端点
// ═══════════════════════════════════════════

/** 获取 API Key 使用量统计 */
export async function getApiKeyUsage(
  id: string,
  period: UsagePeriod = 'week',
): Promise<ApiKeyUsageResponse> {
  return apiClient.get(`${API_BASE}/${id}/usage`, {
    params: { period },
  }) as Promise<ApiKeyUsageResponse>;
}
