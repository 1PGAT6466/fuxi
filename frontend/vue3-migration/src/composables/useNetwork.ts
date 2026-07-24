/**
 * 伏羲 v2.1 — 全局网络状态侦听（离线增强版）
 *
 * 功能：
 * - 监听 browser online/offline 事件
 * - 集成 OfflineService 进行深度检测
 * - 暴露响应式 isOnline ref
 * - 支持网络质量检测（连接类型/速度）
 * - 供 MainLayout 顶部离线横幅使用
 */

import { ref, onMounted, onUnmounted, shallowRef } from 'vue';
import { offlineService } from '@/services/offline/OfflineService';
import type { ConnectionStatus } from '@/services/offline/types';

// ============================
// 全局状态
// ============================

/** 全局在线状态（浏览器级别） */
const isOnline = ref<boolean>(navigator.onLine);

/** 深度连接状态（来自 OfflineService） */
const connectionStatus = shallowRef<ConnectionStatus>(
  navigator.onLine ? 'online' : 'offline',
);

/** 网络连接类型 */
const connectionType = ref<string>('unknown');

/** 网络下行速度（Mbps），-1 表示未知 */
const downlink = ref<number>(-1);

/** 网络延迟 RTT（ms），-1 表示未知 */
const rtt = ref<number>(-1);

/** 是否按流量计费 */
const saveData = ref<boolean>(false);

let listenersAttached = false;
let offlineServiceUnsub: (() => void) | null = null;
let serviceInitialized = false;

// ============================
// 事件处理器
// ============================

function onOnline(): void {
  isOnline.value = true;
}

function onOffline(): void {
  isOnline.value = false;
}

/**
 * 更新网络连接信息（Navigator.connection API）
 */
function updateConnectionInfo(): void {
  const conn =
    (navigator as any).connection ||
    (navigator as any).mozConnection ||
    (navigator as any).webkitConnection;

  if (conn) {
    connectionType.value = conn.effectiveType || conn.type || 'unknown';
    downlink.value = conn.downlink ?? -1;
    rtt.value = conn.rtt ?? -1;
    saveData.value = conn.saveData ?? false;
  }
}

function onConnectionChange(): void {
  updateConnectionInfo();
}

function attachListeners(): void {
  if (listenersAttached) return;

  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);

  const conn =
    (navigator as any).connection ||
    (navigator as any).mozConnection ||
    (navigator as any).webkitConnection;

  if (conn) {
    conn.addEventListener('change', onConnectionChange);
  }

  // 初始获取连接信息
  updateConnectionInfo();

  listenersAttached = true;
}

function detachListeners(): void {
  window.removeEventListener('online', onOnline);
  window.removeEventListener('offline', onOffline);

  const conn =
    (navigator as any).connection ||
    (navigator as any).mozConnection ||
    (navigator as any).webkitConnection;

  if (conn) {
    conn.removeEventListener('change', onConnectionChange);
  }

  listenersAttached = false;
}

// ============================
// 初始化 OfflineService
// ============================

async function initOfflineService(): Promise<void> {
  if (serviceInitialized) return;

  try {
    await offlineService.init();

    // 同步初始状态
    connectionStatus.value = offlineService.status;

    // 注册状态变更监听
    offlineServiceUnsub = offlineService.onStatusChange((status) => {
      connectionStatus.value = status;
      isOnline.value = status === 'online' || status === 'reconnecting';
    });

    serviceInitialized = true;
  } catch (err) {
    console.error('[useNetwork] OfflineService 初始化失败，降级到浏览器原生检测', err);
  }
}

// ============================
// Composable
// ============================

/**
 * 全局网络状态 composable
 *
 * 用法：
 * ```ts
 * const { isOnline, connectionStatus, connectionType, downlink } = useNetwork()
 * ```
 */
export function useNetwork() {
  onMounted(() => {
    attachListeners();
    initOfflineService();
  });

  onUnmounted(() => {
    // 不主动 detach，保持全局监听
  });

  return {
    /** 是否在线（浏览器原生检测） */
    isOnline,
    /** 深度连接状态（来自 OfflineService 心跳检测） */
    connectionStatus,
    /** 网络连接类型（4g/3g/2g/slow-2g） */
    connectionType,
    /** 下行速度 (Mbps) */
    downlink,
    /** 往返延迟 (ms) */
    rtt,
    /** 是否按流量计费 */
    saveData,
    /** 获取 OfflineService 实例 */
    offlineService,
  };
}

/**
 * 手动释放全局监听器（仅测试场景使用）
 */
export function disposeNetwork(): void {
  detachListeners();
  if (offlineServiceUnsub) {
    offlineServiceUnsub();
    offlineServiceUnsub = null;
  }
  serviceInitialized = false;
}

export default useNetwork;
