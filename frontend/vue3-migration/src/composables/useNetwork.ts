/**
 * 伏羲 v2.1 — 全局网络状态侦听
 *
 * 功能：
 * - 监听 browser online/offline 事件
 * - 暴露响应式 isOnline ref
 * - 供 MainLayout 顶部离线横幅使用
 */

import { ref, onMounted, onUnmounted } from 'vue';

/** 全局共享 — 所有组件引用同一个值 */
const isOnline = ref<boolean>(navigator.onLine);

let listenersAttached = false;

function onOnline(): void {
  isOnline.value = true;
}

function onOffline(): void {
  isOnline.value = false;
}

function attachListeners(): void {
  if (listenersAttached) return;
  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);
  listenersAttached = true;
}

function detachListeners(): void {
  window.removeEventListener('online', onOnline);
  window.removeEventListener('offline', onOffline);
  listenersAttached = false;
}

/**
 * 全局网络状态 composable
 *
 * 用法：
 * ```ts
 * const { isOnline } = useNetwork()
 * ```
 */
export function useNetwork() {
  // 每个调用者都会参与生命周期（组件卸载时不会移除全局监听器，
  // 因为 isOnline 是全局共享的；只在初始时 attach 一次）
  onMounted(() => {
    attachListeners();
  });

  // 注意：不在此处 detach（因为全局共享）
  // 如需清理可调用全局 dispose，但通常没必要
  onUnmounted(() => {
    // 不主动 detach — 保持全局侦听
  });

  return {
    isOnline,
  };
}

/**
 * 手动释放全局监听器（仅测试场景使用）
 */
export function disposeNetwork(): void {
  detachListeners();
}

export default useNetwork;
