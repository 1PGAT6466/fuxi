/**
 * 伏羲 v2.1 — 通知中心服务 API
 * P2 增强：推送通知
 */

import apiClient from '@/api';
import type {
  NotificationItem,
  NotificationType,
  NotificationPreferences,
  PushSubscriptionInfo,
} from './types';

// ═══════════════════════════════════════════
// 通知列表
// ═══════════════════════════════════════════

interface NotificationListData {
  notifications: NotificationItem[];
  unread_count: number;
  total: number;
}

interface NotificationListResponse {
  data: NotificationListData;
}

export async function fetchNotifications(params?: {
  page?: number;
  page_size?: number;
  unread_only?: boolean;
  type?: NotificationType;
}): Promise<NotificationListData> {
  const res = (await apiClient.get('/api/notifications', {
    params,
  })) as NotificationListResponse;
  return res.data;
}

// ═══════════════════════════════════════════
// 已读操作
// ═══════════════════════════════════════════

export async function markAsRead(id: string): Promise<void> {
  await apiClient.put(`/api/notifications/${id}/read`);
}

export async function markAllAsRead(): Promise<void> {
  await apiClient.put('/api/notifications/read-all');
}

// ═══════════════════════════════════════════
// 推送订阅
// ═══════════════════════════════════════════

export async function subscribePush(
  subscription: PushSubscriptionInfo,
): Promise<{ success: boolean }> {
  return apiClient.post('/api/notifications/subscribe', subscription) as Promise<{
    success: boolean;
  }>;
}

export async function unsubscribePush(
  userId: string,
  endpoint: string,
): Promise<{ success: boolean }> {
  return apiClient.post('/api/notifications/unsubscribe', {
    userId,
    endpoint,
  }) as Promise<{ success: boolean }>;
}

// ═══════════════════════════════════════════
// 通知偏好设置
// ═══════════════════════════════════════════

export async function fetchPreferences(): Promise<NotificationPreferences> {
  const res = (await apiClient.get('/api/notifications/preferences')) as {
    data: NotificationPreferences;
  };
  return res.data;
}

export async function savePreferences(
  prefs: Partial<NotificationPreferences>,
): Promise<NotificationPreferences> {
  const res = (await apiClient.put('/api/notifications/preferences', prefs)) as {
    data: NotificationPreferences;
  };
  return res.data;
}

// ═══════════════════════════════════════════
// VAPID 公钥
// ═══════════════════════════════════════════

export async function fetchVapidPublicKey(): Promise<string> {
  const res = (await apiClient.get('/api/notifications/vapid-public-key')) as {
    data: { publicKey: string };
  };
  return res.data.publicKey;
}
