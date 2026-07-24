/**
 * 伏羲 v2.1 — 通知中心 Store
 * P2 增强：推送通知 Pinia Store
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';
import type { NotificationItem, NotificationPreferences, PermissionStatus } from './types';
import { DEFAULT_PREFERENCES } from './types';
import * as notifyApi from './api';

const logger = createLogger('NotificationStore');

export const useNotificationStore = defineStore('notification-center', () => {
  // ══════════════════════════════════════
  // 通知列表
  // ══════════════════════════════════════
  const notifications = ref<NotificationItem[]>([]);
  const total = ref(0);
  const currentPage = ref(1);
  const pageSize = ref(20);
  const isLoading = ref(false);

  // ══════════════════════════════════════
  // 推送状态
  // ══════════════════════════════════════
  const permissionStatus = ref<PermissionStatus>('default');
  const isPushSubscribed = ref(false);

  // ══════════════════════════════════════
  // 偏好设置
  // ══════════════════════════════════════
  const preferences = ref<NotificationPreferences>({ ...DEFAULT_PREFERENCES });

  // ══════════════════════════════════════
  // 计算属性
  // ══════════════════════════════════════

  const unreadCount = computed(() => {
    return notifications.value.filter((n) => !n.read).length;
  });

  const hasUnread = computed(() => unreadCount.value > 0);

  const unreadNotifications = computed(() => {
    return notifications.value.filter((n) => !n.read);
  });

  const groupedByDate = computed(() => {
    const groups: Record<string, NotificationItem[]> = {};
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const todayStr = today.toLocaleDateString('zh-CN');
    const yesterdayStr = yesterday.toLocaleDateString('zh-CN');

    for (const item of notifications.value) {
      const date = new Date(item.created_at).toLocaleDateString('zh-CN');
      let label: string;
      if (date === todayStr) {
        label = '今天';
      } else if (date === yesterdayStr) {
        label = '昨天';
      } else {
        label = date;
      }
      if (!groups[label]) groups[label] = [];
      groups[label].push(item);
    }
    return groups;
  });

  // ══════════════════════════════════════
  // 通知列表操作
  // ══════════════════════════════════════

  async function loadNotifications(page = 1): Promise<void> {
    isLoading.value = true;
    try {
      const data = await notifyApi.fetchNotifications({
        page,
        page_size: pageSize.value,
      });
      notifications.value = data.notifications;
      total.value = data.total;
      currentPage.value = page;
    } catch (err) {
      logger.error('加载通知列表失败', err);
    } finally {
      isLoading.value = false;
    }
  }

  async function markRead(id: string): Promise<void> {
    try {
      await notifyApi.markAsRead(id);
      const item = notifications.value.find((n) => n.id === id);
      if (item) item.read = true;
    } catch (err) {
      logger.error('标记已读失败', err);
    }
  }

  async function markAllRead(): Promise<void> {
    try {
      await notifyApi.markAllAsRead();
      for (const item of notifications.value) {
        item.read = true;
      }
    } catch (err) {
      logger.error('全部标记已读失败', err);
    }
  }

  // ══════════════════════════════════════
  // 推送操作
  // ══════════════════════════════════════

  function checkPermission(): PermissionStatus {
    if (!('Notification' in window)) {
      logger.warn('浏览器不支持 Notification API');
      return 'denied';
    }
    const status = Notification.permission as PermissionStatus;
    permissionStatus.value = status;
    return status;
  }

  async function requestPermission(): Promise<PermissionStatus> {
    if (!('Notification' in window)) {
      logger.warn('浏览器不支持 Notification API');
      permissionStatus.value = 'denied';
      return 'denied';
    }
    try {
      const result = await Notification.requestPermission();
      permissionStatus.value = result as PermissionStatus;
      logger.info(`通知权限状态: ${result}`);
      return result as PermissionStatus;
    } catch (err) {
      logger.error('请求通知权限失败', err);
      permissionStatus.value = 'denied';
      return 'denied';
    }
  }

  // ══════════════════════════════════════
  // 偏好设置操作
  // ══════════════════════════════════════

  async function loadPreferences(): Promise<void> {
    try {
      const prefs = await notifyApi.fetchPreferences();
      preferences.value = { ...DEFAULT_PREFERENCES, ...prefs };
    } catch (err) {
      logger.warn('加载通知偏好失败，使用默认值', err);
      // 从 localStorage 恢复
      const saved = localStorage.getItem('fuxi-notification-preferences');
      if (saved) {
        try {
          preferences.value = { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) };
        } catch {
          // ignore
        }
      }
    }
  }

  async function savePreferences(
    partial: Partial<NotificationPreferences>,
  ): Promise<void> {
    const updated = { ...preferences.value, ...partial };
    try {
      const serverPrefs = await notifyApi.savePreferences(partial);
      preferences.value = { ...updated, ...serverPrefs };
    } catch {
      // 本地保存
      preferences.value = updated;
    }
    localStorage.setItem(
      'fuxi-notification-preferences',
      JSON.stringify(preferences.value),
    );
  }

  // ══════════════════════════════════════
  // 初始化
  // ══════════════════════════════════════

  async function init(): Promise<void> {
    checkPermission();
    await Promise.allSettled([loadNotifications(1), loadPreferences()]);
  }

  return {
    // state
    notifications,
    total,
    currentPage,
    pageSize,
    isLoading,
    permissionStatus,
    isPushSubscribed,
    preferences,
    // computed
    unreadCount,
    hasUnread,
    unreadNotifications,
    groupedByDate,
    // actions
    loadNotifications,
    markRead,
    markAllRead,
    checkPermission,
    requestPermission,
    loadPreferences,
    savePreferences,
    init,
  };
});
