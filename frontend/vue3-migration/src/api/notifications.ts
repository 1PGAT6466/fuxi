/**
 * 伏羲 v2.1 — 通知中心 API
 * 对接方案规划的后端 /api/notifications（当前后端为占位实现）
 *
 * 方案要求：通知中心 API，支持通知列表、标记已读、推送配置
 * 当前状态：后端尚未实现完整通知中心，前端 API 层预备对接
 *
 * P2 增强：新增推送订阅/发送 API
 */

import apiClient from './index';

export interface Notification {
  id: string;
  title: string;
  body: string;
  type: 'info' | 'warning' | 'error' | 'success';
  read: boolean;
  created_at: string;
}

export interface NotificationsListResponse {
  data: {
    notifications: Notification[];
    unread_count: number;
    total: number;
  };
}

/** 推送订阅信息 */
export interface PushSubscriptionInfo {
  userId: string;
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

/** 发送通知请求 */
export interface SendNotificationRequest {
  userId?: string;
  title: string;
  body: string;
  type?: 'info' | 'warning' | 'error' | 'success';
  data?: Record<string, unknown>;
}

/** 获取通知列表 */
export async function fetchNotifications(params?: {
  page?: number;
  page_size?: number;
  unread_only?: boolean;
}): Promise<NotificationsListResponse> {
  return apiClient.get('/api/notifications', { params }) as Promise<NotificationsListResponse>;
}

/** 标记通知为已读 */
export async function markNotificationRead(id: string): Promise<void> {
  await apiClient.put(`/api/notifications/${id}/read`);
}

/** 标记全部已读 */
export async function markAllNotificationsRead(): Promise<void> {
  await apiClient.put('/api/notifications/read-all');
}

// ═══════════════════════════════════════════
// P2 增强：推送通知 API
// ═══════════════════════════════════════════

/**
 * 订阅推送通知
 * 将浏览器 PushSubscription 信息发送到后端保存
 */
export async function subscribePush(subscription: PushSubscriptionInfo): Promise<{ success: boolean }> {
  return apiClient.post('/api/notifications/subscribe', subscription) as Promise<{ success: boolean }>;
}

/**
 * 取消推送订阅
 */
export async function unsubscribePush(userId: string, endpoint: string): Promise<{ success: boolean }> {
  return apiClient.post('/api/notifications/unsubscribe', {
    userId,
    endpoint,
  }) as Promise<{ success: boolean }>;
}

/**
 * 发送推送通知（后端 -> 用户）
 */
export async function sendNotification(request: SendNotificationRequest): Promise<{ success: boolean; id: string }> {
  return apiClient.post('/api/notifications/send', request) as Promise<{ success: boolean; id: string }>;
}
