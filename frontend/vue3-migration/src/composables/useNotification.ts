/**
 * 伏羲 v2.1 — 通知服务 Composable
 * P2 增强：推送通知 NotificationService
 *
 * 功能：
 * - requestPermission() — 请求浏览器通知权限
 * - subscribe(userId) — 订阅 Web Push
 * - showNotification(title, body) — 显示本地桌面通知
 * - 注册 Service Worker 以支持离线通知
 */

import { ref, onMounted } from 'vue';
import { createLogger } from '@/utils/logger';
import type { PermissionStatus } from '@/services/notification-center/types';
import * as notifyApi from '@/services/notification-center/api';

const logger = createLogger('useNotification');

// ═══════════════════════════════════════════
// Service Worker 路径
// ═══════════════════════════════════════════

const SW_PATH = '/sw.js';

// ═══════════════════════════════════════════
// 全局单例状态
// ═══════════════════════════════════════════

let swRegistration: ServiceWorkerRegistration | null = null;
let isSwRegistered = false;

// ═══════════════════════════════════════════
// Composable
// ═══════════════════════════════════════════

export function useNotification() {
  const permissionStatus = ref<PermissionStatus>('default');
  const isSubscribed = ref(false);
  const isSupported = ref(false);

  // ════════════════════════════════════
  // 检查浏览器支持
  // ════════════════════════════════════

  function checkSupport(): boolean {
    const supported =
      'Notification' in window &&
      'serviceWorker' in navigator &&
      'PushManager' in window;
    isSupported.value = supported;
    if (!supported) {
      logger.warn('浏览器不支持 Web Push API');
    }
    return supported;
  }

  function updatePermissionStatus(): void {
    if ('Notification' in window) {
      permissionStatus.value = Notification.permission as PermissionStatus;
    } else {
      permissionStatus.value = 'denied';
    }
  }

  // ════════════════════════════════════
  // Service Worker 注册
  // ════════════════════════════════════

  async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
    if (isSwRegistered && swRegistration) return swRegistration;
    if (!('serviceWorker' in navigator)) {
      logger.warn('浏览器不支持 Service Worker');
      return null;
    }

    try {
      swRegistration = await navigator.serviceWorker.register(SW_PATH);
      isSwRegistered = true;
      logger.info('Service Worker 注册成功', swRegistration.scope);

      // 检查已有的推送订阅
      const subscription = await swRegistration.pushManager.getSubscription();
      isSubscribed.value = subscription !== null;

      return swRegistration;
    } catch (err) {
      logger.error('Service Worker 注册失败', err);
      return null;
    }
  }

  // ════════════════════════════════════
  // 权限管理
  // ════════════════════════════════════

  /**
   * 请求浏览器通知权限
   * @returns 权限状态：granted | denied | default
   */
  async function requestPermission(): Promise<PermissionStatus> {
    if (!('Notification' in window)) {
      permissionStatus.value = 'denied';
      return 'denied';
    }

    try {
      const result = await Notification.requestPermission();
      permissionStatus.value = result as PermissionStatus;
      logger.info(`通知权限请求结果: ${result}`);
      return result as PermissionStatus;
    } catch (err) {
      logger.error('请求通知权限出错', err);
      permissionStatus.value = 'denied';
      return 'denied';
    }
  }

  // ════════════════════════════════════
  // 推送订阅
  // ════════════════════════════════════

  /**
   * 订阅 Web Push
   * @param userId 用户标识
   * @returns 是否订阅成功
   */
  async function subscribe(userId: string): Promise<boolean> {
    if (!checkSupport()) return false;

    // 确保权限
    if (permissionStatus.value !== 'granted') {
      const perm = await requestPermission();
      if (perm !== 'granted') {
        logger.warn('未获得通知权限，无法订阅推送');
        return false;
      }
    }

    // 注册 Service Worker（如果尚未注册）
    const sw = await registerServiceWorker();
    if (!sw) {
      logger.error('Service Worker 未就绪，无法订阅');
      return false;
    }

    try {
      // 获取 VAPID 公钥
      let applicationServerKey: Uint8Array;
      try {
        const publicKey = await notifyApi.fetchVapidPublicKey();
        applicationServerKey = urlBase64ToUint8Array(publicKey);
      } catch {
        // 后端不可用时使用本地配置
        logger.warn('获取 VAPID 公钥失败，使用本地配置');
        // 生产环境应由后端下发
        const vapidKey = import.meta.env.VITE_VAPID_PUBLIC_KEY;
        if (!vapidKey) {
          logger.error('未配置 VAPID 公钥');
          return false;
        }
        applicationServerKey = urlBase64ToUint8Array(vapidKey);
      }

      const pushSubscription = await sw.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey,
      });

      // 提取关键信息
      const subJson = pushSubscription.toJSON();
      const subscriptionInfo = {
        userId,
        endpoint: subJson.endpoint!,
        keys: {
          p256dh: subJson.keys!.p256dh,
          auth: subJson.keys!.auth,
        },
      };

      // 发送到后端
      await notifyApi.subscribePush(subscriptionInfo);
      isSubscribed.value = true;
      logger.info('推送订阅成功');

      return true;
    } catch (err) {
      logger.error('推送订阅失败', err);
      return false;
    }
  }

  /**
   * 取消 Web Push 订阅
   */
  async function unsubscribe(userId: string): Promise<boolean> {
    if (!swRegistration) return false;

    try {
      const subscription = await swRegistration.pushManager.getSubscription();
      if (!subscription) return false;

      const subJson = subscription.toJSON();
      await notifyApi.unsubscribePush(userId, subJson.endpoint!);
      await subscription.unsubscribe();

      isSubscribed.value = false;
      logger.info('已取消推送订阅');
      return true;
    } catch (err) {
      logger.error('取消订阅失败', err);
      return false;
    }
  }

  // ════════════════════════════════════
  // 本地通知
  // ════════════════════════════════════

  /**
   * 显示本地桌面通知（忽略免打扰时段）
   */
  function showNotification(
    title: string,
    options?: NotificationOptions & { data?: Record<string, unknown> },
  ): void {
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;

    const notification = new Notification(title, {
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      ...options,
    });

    notification.onclick = () => {
      window.focus();
      if (options?.data?.url) {
        window.location.href = options.data.url;
      }
      notification.close();
    };
  }

  // ════════════════════════════════════
  // 工具函数
  // ════════════════════════════════════

  function urlBase64ToUint8Array(base64String: string): Uint8Array {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i++) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  // ════════════════════════════════════
  // 生命周期
  // ════════════════════════════════════

  onMounted(() => {
    checkSupport();
    updatePermissionStatus();
    registerServiceWorker();
  });

  return {
    // 状态
    permissionStatus,
    isSubscribed,
    isSupported,
    // 方法
    checkSupport,
    updatePermissionStatus,
    registerServiceWorker,
    requestPermission,
    subscribe,
    unsubscribe,
    showNotification,
  };
}
