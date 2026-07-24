/**
 * 伏羲 v2.1 — 通知中心类型定义
 * P2 增强：推送通知系统类型
 */

// ═══════════════════════════════════════════
// 通知项
// ═══════════════════════════════════════════

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  type: NotificationType;
  read: boolean;
  /** 关联数据（如跳转链接） */
  data?: NotificationData;
  created_at: string;
}

export type NotificationType = 'info' | 'warning' | 'error' | 'success';

export interface NotificationData {
  url?: string;
  serviceId?: string;
  taskId?: string;
  [key: string]: unknown;
}

// ═══════════════════════════════════════════
// 推送订阅
// ═══════════════════════════════════════════

export interface PushSubscriptionInfo {
  userId: string;
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

// ═══════════════════════════════════════════
// 通知设置
// ═══════════════════════════════════════════

export interface NotificationPreferences {
  /** 是否启用浏览器桌面通知 */
  desktopEnabled: boolean;
  /** 是否启用推送订阅 */
  pushEnabled: boolean;
  /** 是否启用声音提醒 */
  soundEnabled: boolean;
  /** 免打扰时间段（小时） */
  doNotDisturb: {
    enabled: boolean;
    startHour: number;
    endHour: number;
  };
  /** 按类型开关 */
  typeFilters: Record<NotificationType, boolean>;
}

export const DEFAULT_PREFERENCES: NotificationPreferences = {
  desktopEnabled: true,
  pushEnabled: false,
  soundEnabled: true,
  doNotDisturb: {
    enabled: false,
    startHour: 22,
    endHour: 8,
  },
  typeFilters: {
    info: true,
    warning: true,
    error: true,
    success: true,
  },
};

// ═══════════════════════════════════════════
// 权限状态
// ═══════════════════════════════════════════

export type PermissionStatus = 'default' | 'granted' | 'denied';

// ═══════════════════════════════════════════
// Web Push 公钥（VAPID）
// ═══════════════════════════════════════════

/** VAPID 公钥 — 由后端提供，前端用作 applicationServerKey */
export interface VapidKeys {
  publicKey: string;
}
