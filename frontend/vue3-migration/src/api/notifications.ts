/**
 * 伏羲 v2.1 — 通知中心 API
 * 对接方案规划的后端 /api/notifications（当前后端为占位实现）
 *
 * 方案要求：通知中心 API，支持通知列表、标记已读、推送配置
 * 当前状态：后端尚未实现完整通知中心，前端 API 层预备对接
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
