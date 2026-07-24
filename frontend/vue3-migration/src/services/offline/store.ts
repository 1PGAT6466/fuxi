/**
 * 伏羲 v2.1 — 离线状态管理 (Pinia Store)
 *
 * 封装 OfflineService 的响应式状态，供 Vue 组件使用。
 * 提供离线操作、缓存管理、冲突解决等 action。
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { offlineService } from './OfflineService';
import type {
  OfflineState,
  ConnectionStatus,
  SyncStatus,
  OfflineOperation,
  SyncConflict,
  SyncResult,
  CacheStrategy,
} from './types';

export const useOfflineStore = defineStore('offline', () => {
  // ========== State ==========

  /** 当前离线状态快照 */
  const state = ref<OfflineState>(offlineService.getState());

  /** 冲突列表 */
  const conflicts = ref<SyncConflict[]>([]);

  /** 操作队列 */
  const queue = ref<OfflineOperation[]>([]);

  /** 上次同步结果 */
  const lastSyncResult = ref<SyncResult | null>(null);

  // ========== Getters ==========

  /** 当前连接状态 */
  const connectionStatus = computed<ConnectionStatus>(() => state.value.connectionStatus);

  /** 是否在线 */
  const isOnline = computed(() => state.value.connectionStatus === 'online');

  /** 是否正在重连 */
  const isReconnecting = computed(() => state.value.connectionStatus === 'reconnecting');

  /** 是否离线 */
  const isOffline = computed(() => state.value.connectionStatus === 'offline');

  /** 同步状态 */
  const syncStatus = computed<SyncStatus>(() => state.value.syncStatus);

  /** 是否正在同步 */
  const isSyncing = computed(() => state.value.syncStatus === 'syncing');

  /** 待处理操作数 */
  const pendingCount = computed(() => state.value.pendingCount);

  /** 是否有待处理操作 */
  const hasPendingOps = computed(() => state.value.pendingCount > 0);

  /** 冲突数量 */
  const conflictCount = computed(() => conflicts.value.length);

  /** 是否有冲突 */
  const hasConflicts = computed(() => conflicts.value.length > 0);

  /** 缓存条目数 */
  const cacheEntryCount = computed(() => state.value.cacheEntryCount);

  /** 上次同步时间（格式化） */
  const lastSyncTimeFormatted = computed(() => {
    if (!state.value.lastSyncTime) return '从未同步';
    return new Date(state.value.lastSyncTime).toLocaleString('zh-CN');
  });

  // ========== Actions ==========

  /**
   * 刷新状态快照
   */
  function refreshState(): void {
    state.value = offlineService.getState();
    conflicts.value = offlineService.getConflicts();
    queue.value = [...offlineService.getQueue()];
  }

  /**
   * 初始化离线服务
   */
  async function init(): Promise<void> {
    await offlineService.init();

    // 注册状态监听
    offlineService.onStatusChange((status) => {
      refreshState();
      if (status === 'online') {
        // 自动触发同步
        syncPending().catch((err) => {
          console.error('[OfflineStore] 自动同步失败', err);
        });
      }
    });

    offlineService.onSyncStateChange(() => {
      refreshState();
    });

    refreshState();
  }

  /**
   * 同步待处理操作
   */
  async function syncPending(): Promise<SyncResult> {
    const result = await offlineService.syncPendingOperations();
    lastSyncResult.value = result;
    refreshState();
    return result;
  }

  /**
   * 解决冲突
   */
  async function resolveConflict(
    conflictId: string,
    resolution: 'local' | 'server' | 'merge',
  ): Promise<void> {
    await offlineService.resolveConflict(conflictId, resolution);
    refreshState();
  }

  /**
   * 获取缓存数据
   */
  async function getCachedData<T>(
    key: string,
    fetchFn?: () => Promise<T>,
    strategy?: CacheStrategy,
    ttl?: number,
  ): Promise<T | null> {
    const data = await offlineService.getCachedData(key, fetchFn, strategy, ttl);
    refreshState();
    return data;
  }

  /**
   * 设置缓存
   */
  async function setCache<T>(key: string, data: T, strategy?: CacheStrategy, ttl?: number): Promise<void> {
    await offlineService.setCache(key, data, strategy, ttl);
    refreshState();
  }

  /**
   * 清除所有缓存
   */
  async function clearAllCache(): Promise<void> {
    await offlineService.clearAllCache();
    refreshState();
  }

  /**
   * 清除过期缓存
   */
  async function cleanExpiredCache(): Promise<number> {
    const count = await offlineService.cleanExpiredCache();
    refreshState();
    return count;
  }

  /**
   * 清空操作队列
   */
  async function clearQueue(): Promise<void> {
    await offlineService.clearQueue();
    refreshState();
  }

  /**
   * 销毁服务
   */
  function destroy(): void {
    offlineService.destroy();
  }

  return {
    // state
    state,
    conflicts,
    queue,
    lastSyncResult,

    // getters
    connectionStatus,
    isOnline,
    isReconnecting,
    isOffline,
    syncStatus,
    isSyncing,
    pendingCount,
    hasPendingOps,
    conflictCount,
    hasConflicts,
    cacheEntryCount,
    lastSyncTimeFormatted,

    // actions
    init,
    refreshState,
    syncPending,
    resolveConflict,
    getCachedData,
    setCache,
    clearAllCache,
    cleanExpiredCache,
    clearQueue,
    destroy,
  };
});
