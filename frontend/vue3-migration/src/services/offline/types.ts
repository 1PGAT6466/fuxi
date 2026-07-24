/**
 * 伏羲 v2.1 — 离线模式类型定义
 *
 * 定义离线操作队列、缓存策略、同步状态等核心接口
 */

// ============================
// 离线状态枚举
// ============================

/** 网络连接状态 */
export type ConnectionStatus = 'online' | 'offline' | 'reconnecting';

/** 同步状态 */
export type SyncStatus = 'idle' | 'syncing' | 'success' | 'error' | 'conflict';

/** 操作类型 */
export type OfflineOperationType = 'create' | 'update' | 'delete';

/** 缓存策略 */
export type CacheStrategy = 'cache-first' | 'network-first' | 'stale-while-revalidate' | 'network-only';

// ============================
// 离线操作队列
// ============================

/** 离线操作项 */
export interface OfflineOperation {
  /** 操作唯一 ID */
  id: string;
  /** 操作类型 */
  type: OfflineOperationType;
  /** API 端点路径 */
  endpoint: string;
  /** 请求方法 */
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  /** 请求体 */
  payload?: unknown;
  /** 请求头 */
  headers?: Record<string, string>;
  /** 创建时间戳 */
  createdAt: number;
  /** 重试次数 */
  retryCount: number;
  /** 最大重试次数 */
  maxRetries: number;
  /** 优先级（0 最高，数字越大优先级越低） */
  priority: number;
  /** 操作描述（用于UI展示） */
  description?: string;
  /** 关联资源 ID */
  resourceId?: string;
  /** 依赖的前置操作 ID */
  dependsOn?: string;
}

/** 同步冲突 */
export interface SyncConflict {
  /** 冲突 ID */
  id: string;
  /** 冲突的操作 */
  operation: OfflineOperation;
  /** 本地版本 */
  localVersion: unknown;
  /** 服务端版本 */
  serverVersion: unknown;
  /** 冲突描述 */
  description: string;
  /** 发生时间 */
  timestamp: number;
  /** 解决策略 */
  resolution?: 'local' | 'server' | 'merge' | 'manual';
}

/** 同步结果 */
export interface SyncResult {
  /** 是否成功 */
  success: boolean;
  /** 同步的操作数 */
  syncedCount: number;
  /** 失败的操作数 */
  failedCount: number;
  /** 冲突列表 */
  conflicts: SyncConflict[];
  /** 耗时（毫秒） */
  durationMs: number;
  /** 错误信息 */
  error?: string;
}

// ============================
// 缓存
// ============================

/** 缓存条目 */
export interface CacheEntry<T = unknown> {
  /** 缓存键 */
  key: string;
  /** 缓存数据 */
  data: T;
  /** 创建时间 */
  createdAt: number;
  /** 过期时间 */
  expiresAt: number;
  /** 缓存策略 */
  strategy: CacheStrategy;
  /** 数据大小（字节） */
  size: number;
  /** ETag（用于条件请求） */
  etag?: string;
  /** 最后请求时间 */
  lastAccessedAt: number;
}

/** 缓存配置 */
export interface CacheConfig {
  /** 默认过期时间（毫秒） */
  defaultTTL: number;
  /** 最大缓存条目数 */
  maxEntries: number;
  /** 最大缓存总大小（字节） */
  maxSize: number;
  /** 启用内存缓存 */
  enableMemoryCache: boolean;
  /** 启用 IndexedDB 持久化 */
  enableDiskCache: boolean;
}

// ============================
// 离线状态
// ============================

/** 离线服务状态 */
export interface OfflineState {
  /** 连接状态 */
  connectionStatus: ConnectionStatus;
  /** 同步状态 */
  syncStatus: SyncStatus;
  /** 离线操作队列长度 */
  queueLength: number;
  /** 待同步操作数 */
  pendingCount: number;
  /** 上次同步时间 */
  lastSyncTime: number | null;
  /** 上次在线时间 */
  lastOnlineTime: number | null;
  /** 缓存条目数 */
  cacheEntryCount: number;
  /** 是否正在初始化 */
  isInitializing: boolean;
}
