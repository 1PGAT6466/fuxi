/**
 * 伏羲 v2.1 — Webhook 配置管理 API 封装
 *
 * 封装 8 个端点：
 * - GET     /api/webhooks               — 获取 Webhook 列表
 * - POST    /api/webhooks               — 创建 Webhook
 * - GET     /api/webhooks/:id           — 获取 Webhook 详情
 * - PUT     /api/webhooks/:id           — 更新 Webhook
 * - DELETE  /api/webhooks/:id           — 删除 Webhook
 * - POST    /api/webhooks/:id/test      — 测试发送
 * - GET     /api/webhooks/:id/deliveries — 获取投递记录
 * - POST    /api/webhooks/verify-signature — 验证签名
 */

import apiClient from '@/api';
import type {
  Webhook,
  WebhookListResponse,
  CreateWebhookRequest,
  UpdateWebhookRequest,
  TestWebhookRequest,
  TestWebhookResponse,
  WebhookActionResult,
  WebhookDeliveryListResponse,
} from './types';

// ───── 常量 ─────

const API_BASE = '/api/webhooks';

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

/** 获取 Webhook 列表 */
export async function getWebhooks(): Promise<WebhookListResponse> {
  try {
    const resp = await apiClient.get(API_BASE);
    return extractData<WebhookListResponse>(resp);
  } catch (e) {
    console.error('[webhooks-api] getWebhooks 失败:', e);
    return { webhooks: [], total: 0 };
  }
}

/** 获取单个 Webhook 详情 */
export async function getWebhook(id: string): Promise<Webhook> {
  const resp = await apiClient.get(`${API_BASE}/${id}`);
  return extractData<Webhook>(resp);
}

/** 创建 Webhook */
export async function createWebhook(
  data: CreateWebhookRequest,
): Promise<WebhookActionResult & { webhook: Webhook }> {
  const resp = await apiClient.post(API_BASE, data);
  return extractData<WebhookActionResult & { webhook: Webhook }>(resp);
}

/** 更新 Webhook */
export async function updateWebhook(
  id: string,
  data: UpdateWebhookRequest,
): Promise<WebhookActionResult> {
  const resp = await apiClient.put(`${API_BASE}/${id}`, data);
  return extractData<WebhookActionResult>(resp);
}

/** 删除 Webhook */
export async function deleteWebhook(id: string): Promise<WebhookActionResult> {
  const resp = await apiClient.delete(`${API_BASE}/${id}`);
  return extractData<WebhookActionResult>(resp);
}

// ═══════════════════════════════════════════
// 功能端点
// ═══════════════════════════════════════════

/** 测试 Webhook 发送 */
export async function testWebhook(
  id: string,
  data?: TestWebhookRequest,
): Promise<TestWebhookResponse> {
  const resp = await apiClient.post(`${API_BASE}/${id}/test`, data || {});
  return extractData<TestWebhookResponse>(resp);
}

/** 获取 Webhook 投递记录 */
export async function getWebhookDeliveries(
  id: string,
  page?: number,
  pageSize?: number,
): Promise<WebhookDeliveryListResponse> {
  const resp = await apiClient.get(`${API_BASE}/${id}/deliveries`, {
    params: { page, pageSize },
  });
  return extractData<WebhookDeliveryListResponse>(resp);
}

/** 验证签名 */
export async function verifySignature(
  payload: string,
  signature: string,
  secret: string,
  algorithm?: string,
): Promise<{ valid: boolean }> {
  const resp = await apiClient.post(`${API_BASE}/verify-signature`, {
    payload,
    signature,
    secret,
    algorithm: algorithm || 'sha256',
  });
  return extractData<{ valid: boolean }>(resp);
}
