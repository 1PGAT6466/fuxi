/**
 * 伏羲 v2.1 — 离线模式模块统一导出
 */

export { offlineService, default as OfflineService } from './OfflineService';
export { useOfflineStore } from './store';
export { default as OfflineIndicator } from './OfflineIndicator.vue';
export type {
  ConnectionStatus,
  SyncStatus,
  OfflineOperationType,
  CacheStrategy,
  OfflineOperation,
  SyncConflict,
  SyncResult,
  CacheEntry,
  CacheConfig,
  OfflineState,
} from './types';
