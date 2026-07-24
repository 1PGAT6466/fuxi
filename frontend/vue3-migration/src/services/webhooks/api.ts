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

// ═══════════════════════════════════════════
// CRUD 端点
// ═══════════════════════════════════════════

/** 获取 Webhook 列表 */
export async function getWebhooks(): Promise<WebhookListResponse> {
  return apiClient.get(API_BASE) as Promise<WebhookListResponse>;
}

/** 获取单个 Webhook 详情 */
export async function getWebhook(id: string): Promise<Webhook> {
  return apiClient.get(`${API_BASE}/${id}`) as Promise<Webhook>;
}

/** 创建 Webhook */
export async function createWebhook(
  data: CreateWebhookRequest,
): Promise<WebhookActionResult & { webhook: Webhook }> {
  return apiClient.post(API_BASE, data) as Promise<WebhookActionResult & { webhook: Webhook }>;
}

/** 更新 Webhook */
export async function updateWebhook(
  id: string,
  data: UpdateWebhookRequest,
): Promise<WebhookActionResult> {
  return apiClient.put(`${API_BASE}/${id}`, data) as Promise<WebhookActionResult>;
}

/** 删除 Webhook */
export async function deleteWebhook(id: string): Promise<WebhookActionResult> {
  return apiClient.delete(`${API_BASE}/${id}`) as Promise<WebhookActionResult>;
}

// ═══════════════════════════════════════════
// 功能端点
// ═══════════════════════════════════════════

/** 测试 Webhook 发送 */
export async function testWebhook(
  id: string,
  data?: TestWebhookRequest,
): Promise<TestWebhookResponse> {
  return apiClient.post(`${API_BASE}/${id}/test`, data || {}) as Promise<TestWebhookResponse>;
}

/** 获取 Webhook 投递记录 */
export async function getWebhookDeliveries(
  id: string,
  page?: number,
  pageSize?: number,
): Promise<WebhookDeliveryListResponse> {
  return apiClient.get(`${API_BASE}/${id}/deliveries`, {
    params: { page, pageSize },
  }) as Promise<WebhookDeliveryListResponse>;
}

/** 验证签名 */
export async function verifySignature(
  payload: string,
  signature: string,
  secret: string,
  algorithm?: string,
): Promise<{ valid: boolean }> {
  return apiClient.post(`${API_BASE}/verify-signature`, {
    payload,
    signature,
    secret,
    algorithm: algorithm || 'sha256',
  }) as Promise<{ valid: boolean }>;
}
