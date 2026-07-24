/**
 * 伏羲 v2.1 — 离线服务 (OfflineService)
 *
 * 核心功能：
 * - 离线状态检测（结合浏览器 navigator.onLine + 定时心跳检测）
 * - 数据缓存策略（cache-first / network-first / stale-while-revalidate）
 * - 离线操作队列（支持优先级、依赖、重试）
 * - 同步冲突解决（local/server/merge/manual）
 *
 * 使用方式：
 *   const offlineService = new OfflineService();
 *   await offlineService.init();
 *   offlineService.onStatusChange((status) => { ... });
 */

import { createLogger } from '@/utils/logger';
import type {
  ConnectionStatus,
  SyncStatus,
  OfflineOperation,
  SyncConflict,
  SyncResult,
  CacheEntry,
  CacheConfig,
  CacheStrategy,
  OfflineOperationType,
  OfflineState,
} from './types';

const logger = createLogger('OfflineService');

// ============================
// 默认配置
// ============================

const DEFAULT_CACHE_CONFIG: CacheConfig = {
  defaultTTL: 5 * 60 * 1000, // 5 分钟
  maxEntries: 500,
  maxSize: 50 * 1024 * 1024, // 50 MB
  enableMemoryCache: true,
  enableDiskCache: true,
};

const HEARTBEAT_INTERVAL = 30_000; // 30 秒心跳检测
const HEARTBEAT_URL = '/api/health';
const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // 1 秒基础延迟

// ============================
// OfflineService 单例
// ============================

class OfflineService {
  private config: CacheConfig;
  private memoryCache: Map<string, CacheEntry>;
  private operationQueue: OfflineOperation[];
  private conflicts: SyncConflict[];
  private connectionStatus: ConnectionStatus;
  private syncStatus: SyncStatus;
  private lastSyncTime: number | null;
  private lastOnlineTime: number | null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null;
  private statusListeners: Set<(status: ConnectionStatus) => void>;
  private syncListeners: Set<(state: OfflineState) => void>;
  private isInitialized: boolean;

  // IndexedDB 引用
  private db: IDBDatabase | null;
  private readonly DB_NAME = 'fuxi-offline';
  private readonly DB_VERSION = 1;

  constructor(config?: Partial<CacheConfig>) {
    this.config = { ...DEFAULT_CACHE_CONFIG, ...config };
    this.memoryCache = new Map();
    this.operationQueue = [];
    this.conflicts = [];
    this.connectionStatus = 'online';
    this.syncStatus = 'idle';
    this.lastSyncTime = null;
    this.lastOnlineTime = Date.now();
    this.heartbeatTimer = null;
    this.statusListeners = new Set();
    this.syncListeners = new Set();
    this.isInitialized = false;
    this.db = null;
  }

  // ============================
  // 初始化与销毁
  // ============================

  /**
   * 初始化离线服务
   * - 打开 IndexedDB
   * - 注册浏览器事件
   * - 启动心跳检测
   * - 恢复离线队列
   */
  async init(): Promise<void> {
    if (this.isInitialized) {
      logger.warn('OfflineService 已初始化，跳过重复调用');
      return;
    }

    logger.info('初始化离线服务...');

    try {
      // 1. 初始化 IndexedDB
      if (this.config.enableDiskCache) {
        await this.initIndexedDB();
      }

      // 2. 恢复持久化的操作队列
      await this.restoreQueue();

      // 3. 恢复冲突列表
      await this.restoreConflicts();

      // 4. 注册浏览器事件
      this.attachBrowserEvents();

      // 5. 启动心跳检测
      this.startHeartbeat();

      // 6. 检测当前状态
      this.connectionStatus = navigator.onLine ? 'online' : 'offline';
      if (this.connectionStatus === 'online') {
        this.lastOnlineTime = Date.now();
        // 自动触发同步
        this.syncPendingOperations().catch((err) =>
          logger.error('初始化同步失败', err),
        );
      }

      this.isInitialized = true;
      logger.info('离线服务初始化完成', { status: this.connectionStatus });
    } catch (err) {
      logger.error('离线服务初始化失败', err);
      throw err;
    }
  }

  /**
   * 销毁离线服务
   */
  destroy(): void {
    this.stopHeartbeat();
    this.detachBrowserEvents();
    this.statusListeners.clear();
    this.syncListeners.clear();
    this.isInitialized = false;

    if (this.db) {
      this.db.close();
      this.db = null;
    }

    logger.info('离线服务已销毁');
  }

  // ============================
  // IndexedDB 管理
  // ============================

  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

      request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
        const db = (event.target as IDBOpenDBRequest).result;

        // 缓存存储
        if (!db.objectStoreNames.contains('cache')) {
          const cacheStore = db.createObjectStore('cache', { keyPath: 'key' });
          cacheStore.createIndex('expiresAt', 'expiresAt', { unique: false });
          cacheStore.createIndex('lastAccessedAt', 'lastAccessedAt', { unique: false });
        }

        // 操作队列存储
        if (!db.objectStoreNames.contains('operations')) {
          const opsStore = db.createObjectStore('operations', { keyPath: 'id' });
          opsStore.createIndex('createdAt', 'createdAt', { unique: false });
          opsStore.createIndex('priority', 'priority', { unique: false });
        }

        // 冲突存储
        if (!db.objectStoreNames.contains('conflicts')) {
          db.createObjectStore('conflicts', { keyPath: 'id' });
        }
      };

      request.onsuccess = (event: Event) => {
        this.db = (event.target as IDBOpenDBRequest).result;
        logger.debug('IndexedDB 初始化成功');
        resolve();
      };

      request.onerror = (event: Event) => {
        const error = (event.target as IDBOpenDBRequest).error;
        logger.error('IndexedDB 初始化失败', error);
        reject(error);
      };
    });
  }

  // ============================
  // 连接状态检测
  // ============================

  private attachBrowserEvents(): void {
    window.addEventListener('online', this.handleOnline);
    window.addEventListener('offline', this.handleOffline);
  }

  private detachBrowserEvents(): void {
    window.removeEventListener('online', this.handleOnline);
    window.removeEventListener('offline', this.handleOffline);
  }

  private handleOnline = (): void => {
    logger.info('浏览器报告网络恢复');
    this.setConnectionStatus('reconnecting');
    this.lastOnlineTime = Date.now();

    // 验证网络确实可用
    this.verifyConnectivity().then((reachable) => {
      if (reachable) {
        this.setConnectionStatus('online');
        this.syncPendingOperations().catch((err) =>
          logger.error('重连后同步失败', err),
        );
      }
    });
  };

  private handleOffline = (): void => {
    logger.warn('浏览器报告网络断开');
    this.setConnectionStatus('offline');
  };

  /**
   * 验证网络是否真正可达（避免浏览器误报）
   */
  private async verifyConnectivity(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(HEARTBEAT_URL, {
        method: 'HEAD',
        signal: controller.signal,
        cache: 'no-cache',
      });

      clearTimeout(timeoutId);
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * 启动心跳检测
   */
  private startHeartbeat(): void {
    if (this.heartbeatTimer) return;

    this.heartbeatTimer = setInterval(async () => {
      const reachable = await this.verifyConnectivity();

      if (reachable && this.connectionStatus !== 'online') {
        this.setConnectionStatus('online');
        this.syncPendingOperations().catch((err) =>
          logger.error('心跳恢复后同步失败', err),
        );
      } else if (!reachable && this.connectionStatus === 'online') {
        this.setConnectionStatus('offline');
      }
    }, HEARTBEAT_INTERVAL);
  }

  /**
   * 停止心跳检测
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private setConnectionStatus(status: ConnectionStatus): void {
    if (this.connectionStatus === status) return;

    this.connectionStatus = status;
    logger.info('连接状态变更', { status });

    // 通知所有监听器
    this.statusListeners.forEach((fn) => {
      try {
        fn(status);
      } catch (err) {
        logger.error('状态监听器错误', err);
      }
    });

    // 通知同步状态监听器
    this.notifySyncListeners();
  }

  // ============================
  // 事件监听
  // ============================

  /**
   * 注册连接状态变更回调
   */
  onStatusChange(callback: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(callback);
    return () => this.statusListeners.delete(callback);
  }

  /**
   * 注册同步状态变更回调
   */
  onSyncStateChange(callback: (state: OfflineState) => void): () => void {
    this.syncListeners.add(callback);
    return () => this.syncListeners.delete(callback);
  }

  private notifySyncListeners(): void {
    const state = this.getState();
    this.syncListeners.forEach((fn) => {
      try {
        fn(state);
      } catch (err) {
        logger.error('同步状态监听器错误', err);
      }
    });
  }

  // ============================
  // 当前状态
  // ============================

  /** 获取当前离线状态快照 */
  getState(): OfflineState {
    return {
      connectionStatus: this.connectionStatus,
      syncStatus: this.syncStatus,
      queueLength: this.operationQueue.length,
      pendingCount: this.operationQueue.length,
      lastSyncTime: this.lastSyncTime,
      lastOnlineTime: this.lastOnlineTime,
      cacheEntryCount: this.memoryCache.size,
      isInitializing: !this.isInitialized,
    };
  }

  /** 获取当前连接状态 */
  get isOnline(): boolean {
    return this.connectionStatus === 'online';
  }

  /** 获取当前连接状态 */
  get status(): ConnectionStatus {
    return this.connectionStatus;
  }

  // ============================
  // 操作队列
  // ============================

  /**
   * 将操作加入离线队列
   */
  async enqueue(
    type: OfflineOperationType,
    endpoint: string,
    payload?: unknown,
    options?: {
      method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
      headers?: Record<string, string>;
      priority?: number;
      maxRetries?: number;
      description?: string;
      resourceId?: string;
      dependsOn?: string;
    },
  ): Promise<OfflineOperation> {
    const operation: OfflineOperation = {
      id: `offline-op-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type: type,
      endpoint,
      method: options?.method || (type === 'delete' ? 'DELETE' : type === 'create' ? 'POST' : 'PUT'),
      payload,
      headers: options?.headers,
      createdAt: Date.now(),
      retryCount: 0,
      maxRetries: options?.maxRetries ?? MAX_RETRIES,
      priority: options?.priority ?? 0,
      description: options?.description,
      resourceId: options?.resourceId,
      dependsOn: options?.dependsOn,
    };

    this.operationQueue.push(operation);
    // 按优先级排序（低数值 = 高优先级）
    this.operationQueue.sort((a, b) => a.priority - b.priority);

    // 持久化
    await this.persistQueue();

    logger.debug('操作已加入离线队列', {
      id: operation.id,
      type: operation.type,
      endpoint: operation.endpoint,
      queueLength: this.operationQueue.length,
    });

    this.notifySyncListeners();

    // 如果当前在线，立即尝试同步
    if (this.connectionStatus === 'online') {
      this.syncPendingOperations().catch((err) =>
        logger.error('入队后自动同步失败', err),
      );
    }

    return operation;
  }

  /**
   * 同步待处理的操作队列
   */
  async syncPendingOperations(): Promise<SyncResult> {
    if (this.operationQueue.length === 0) {
      return {
        success: true,
        syncedCount: 0,
        failedCount: 0,
        conflicts: [],
        durationMs: 0,
      };
    }

    if (this.connectionStatus !== 'online') {
      return {
        success: false,
        syncedCount: 0,
        failedCount: this.operationQueue.length,
        conflicts: [],
        durationMs: 0,
        error: '当前处于离线状态',
      };
    }

    const startTime = Date.now();
    this.syncStatus = 'syncing';
    this.notifySyncListeners();

    logger.info('开始同步离线操作', { count: this.operationQueue.length });

    let syncedCount = 0;
    let failedCount = 0;
    const newConflicts: SyncConflict[] = [];

    // 按优先级和依赖排序
    const sorted = this.sortOperationsByDependency(this.operationQueue);

    for (const operation of sorted) {
      try {
        await this.executeOperation(operation);
        // 执行成功，从队列移除
        this.operationQueue = this.operationQueue.filter((op) => op.id !== operation.id);
        syncedCount++;
      } catch (err: any) {
        if (err?.status === 409) {
          // 冲突
          const conflict: SyncConflict = {
            id: `conflict-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            operation,
            localVersion: operation.payload,
            serverVersion: err?.serverVersion || null,
            description: err?.message || `操作 "${operation.description || operation.endpoint}" 发生冲突`,
            timestamp: Date.now(),
          };
          newConflicts.push(conflict);
          this.conflicts.push(conflict);

          // 从操作队列移除（转为冲突）
          this.operationQueue = this.operationQueue.filter((op) => op.id !== operation.id);
        } else {
          // 其他错误，增加重试计数
          operation.retryCount++;
          if (operation.retryCount >= operation.maxRetries) {
            // 达到最大重试次数，移除
            this.operationQueue = this.operationQueue.filter((op) => op.id !== operation.id);
            failedCount++;
            logger.error('操作同步失败（已达最大重试）', {
              id: operation.id,
              endpoint: operation.endpoint,
            });
          }
        }
      }
    }

    // 持久化
    await this.persistQueue();
    await this.persistConflicts();

    this.lastSyncTime = Date.now();
    this.syncStatus = newConflicts.length > 0 ? 'conflict' : failedCount > 0 ? 'error' : 'success';

    const result: SyncResult = {
      success: failedCount === 0 && newConflicts.length === 0,
      syncedCount,
      failedCount,
      conflicts: newConflicts,
      durationMs: Date.now() - startTime,
    };

    logger.info('离线操作同步完成', result);

    this.notifySyncListeners();
    return result;
  }

  /**
   * 执行单个操作
   */
  private async executeOperation(operation: OfflineOperation): Promise<Response> {
    const response = await fetch(operation.endpoint, {
      method: operation.method,
      headers: {
        'Content-Type': 'application/json',
        ...operation.headers,
      },
      body: operation.payload ? JSON.stringify(operation.payload) : undefined,
    });

    if (!response.ok) {
      const err: any = new Error(`HTTP ${response.status}: ${response.statusText}`);
      err.status = response.status;
      if (response.status === 409) {
        try {
          err.serverVersion = await response.json();
        } catch {
          // ignore
        }
      }
      throw err;
    }

    return response;
  }

  /**
   * 按依赖关系排序操作
   */
  private sortOperationsByDependency(operations: OfflineOperation[]): OfflineOperation[] {
    const sorted: OfflineOperation[] = [];
    const visited = new Set<string>();
    const inProgress = new Set<string>();

    function visit(op: OfflineOperation): void {
      if (visited.has(op.id)) return;
      if (inProgress.has(op.id)) {
        logger.warn('检测到循环依赖', { operationId: op.id });
        return;
      }

      inProgress.add(op.id);

      if (op.dependsOn) {
        const dep = operations.find((o) => o.id === op.dependsOn);
        if (dep && !visited.has(dep.id)) {
          visit(dep);
        }
      }

      inProgress.delete(op.id);
      visited.add(op.id);
      sorted.push(op);
    }

    // 先处理优先级的，同优先级按创建时间
    const sortedByPriority = [...operations].sort(
      (a, b) => a.priority - b.priority || a.createdAt - b.createdAt,
    );

    for (const op of sortedByPriority) {
      visit(op);
    }

    return sorted;
  }

  // ============================
  // 冲突解决
  // ============================

  /**
   * 解决同步冲突
   */
  async resolveConflict(conflictId: string, resolution: 'local' | 'server' | 'merge'): Promise<void> {
    const conflict = this.conflicts.find((c) => c.id === conflictId);
    if (!conflict) {
      logger.warn('未找到冲突', { conflictId });
      return;
    }

    conflict.resolution = resolution;

    switch (resolution) {
      case 'local':
        // 使用本地版本重新提交
        await this.enqueue(
          conflict.operation.type,
          conflict.operation.endpoint,
          conflict.localVersion,
          {
            method: conflict.operation.method,
            description: `(冲突解决-本地版本) ${conflict.operation.description || ''}`,
          },
        );
        break;

      case 'server':
        // 接受服务端版本，不做额外操作
        logger.info('接受服务端版本', { conflictId });
        break;

      case 'merge':
        // 合并后重新提交（需要实现合并逻辑）
        logger.info('合并冲突', { conflictId });
        // 可以通过注册自定义合并策略处理
        break;
    }

    // 从冲突列表移除
    this.conflicts = this.conflicts.filter((c) => c.id !== conflictId);
    await this.persistConflicts();

    this.notifySyncListeners();
  }

  /**
   * 获取当前冲突列表
   */
  getConflicts(): SyncConflict[] {
    return [...this.conflicts];
  }

  // ============================
  // 缓存策略
  // ============================

  /**
   * 使用指定策略获取缓存数据
   */
  async getCachedData<T>(
    key: string,
    fetchFn?: () => Promise<T>,
    strategy?: CacheStrategy,
    ttl?: number,
  ): Promise<T | null> {
    const effectiveStrategy = strategy || 'cache-first';
    const effectiveTTL = ttl || this.config.defaultTTL;

    switch (effectiveStrategy) {
      case 'cache-first':
        return this.cacheFirst<T>(key, fetchFn, effectiveTTL);
      case 'network-first':
        return this.networkFirst<T>(key, fetchFn, effectiveTTL);
      case 'stale-while-revalidate':
        return this.staleWhileRevalidate<T>(key, fetchFn, effectiveTTL);
      case 'network-only':
        return fetchFn ? fetchFn() : null;
      default:
        return null;
    }
  }

  /**
   * Cache-first 策略：优先返回缓存，缓存未命中时请求网络
   */
  private async cacheFirst<T>(
    key: string,
    fetchFn?: () => Promise<T>,
    ttl?: number,
  ): Promise<T | null> {
    // 1. 检查缓存
    const cached = await this.getFromCache<T>(key);
    if (cached) {
      logger.debug('缓存命中 (cache-first)', { key });
      return cached;
    }

    // 2. 缓存未命中，请求网络
    if (fetchFn && this.connectionStatus === 'online') {
      try {
        const data = await fetchFn();
        await this.setCache(key, data, 'cache-first', ttl);
        return data;
      } catch (err) {
        logger.warn('网络请求失败 (cache-first)', { key, err });
        return null;
      }
    }

    return null;
  }

  /**
   * Network-first 策略：优先请求网络，失败时使用缓存
   */
  private async networkFirst<T>(
    key: string,
    fetchFn?: () => Promise<T>,
    ttl?: number,
  ): Promise<T | null> {
    if (fetchFn && this.connectionStatus === 'online') {
      try {
        const data = await fetchFn();
        await this.setCache(key, data, 'network-first', ttl);
        return data;
      } catch (err) {
        logger.warn('网络请求失败，尝试使用缓存 (network-first)', { key });
        return this.getFromCache<T>(key);
      }
    }

    // 离线状态直接使用缓存
    return this.getFromCache<T>(key);
  }

  /**
   * Stale-while-revalidate 策略：立即返回缓存，同时后台更新
   */
  private async staleWhileRevalidate<T>(
    key: string,
    fetchFn?: () => Promise<T>,
    ttl?: number,
  ): Promise<T | null> {
    const cached = await this.getFromCache<T>(key);

    // 后台更新
    if (fetchFn && this.connectionStatus === 'online') {
      fetchFn()
        .then((data) => this.setCache(key, data, 'stale-while-revalidate', ttl))
        .catch((err) => logger.warn('后台更新缓存失败', { key, err }));
    }

    return cached || null;
  }

  /**
   * 设置缓存条目
   */
  async setCache<T>(key: string, data: T, strategy: CacheStrategy = 'cache-first', ttl?: number): Promise<void> {
    const effectiveTTL = ttl || this.config.defaultTTL;
    const dataStr = JSON.stringify(data);
    const size = new Blob([dataStr]).size;

    const entry: CacheEntry<T> = {
      key,
      data,
      createdAt: Date.now(),
      expiresAt: Date.now() + effectiveTTL,
      strategy,
      size,
      lastAccessedAt: Date.now(),
    };

    // 检查缓存容量
    await this.evictIfNeeded(size);

    // 内存缓存
    if (this.config.enableMemoryCache) {
      this.memoryCache.set(key, entry as CacheEntry);
    }

    // IndexedDB 持久化
    if (this.config.enableDiskCache && this.db) {
      try {
        await this.putInDB('cache', entry);
      } catch (err) {
        logger.error('IndexedDB 缓存写入失败', { key, err });
      }
    }

    this.notifySyncListeners();
  }

  /**
   * 从缓存获取数据
   */
  async getFromCache<T>(key: string): Promise<T | null> {
    // 1. 先查内存缓存
    const memEntry = this.memoryCache.get(key);
    if (memEntry) {
      if (memEntry.expiresAt > Date.now()) {
        memEntry.lastAccessedAt = Date.now();
        return memEntry.data as T;
      }
      // 过期，移除
      this.memoryCache.delete(key);
    }

    // 2. 查 IndexedDB
    if (this.config.enableDiskCache && this.db) {
      try {
        const dbEntry = await this.getFromDB<CacheEntry<T>>('cache', key);
        if (dbEntry && dbEntry.expiresAt > Date.now()) {
          // 回填内存缓存
          if (this.config.enableMemoryCache) {
            dbEntry.lastAccessedAt = Date.now();
            this.memoryCache.set(key, dbEntry);
          }
          return dbEntry.data;
        }
      } catch {
        // ignore
      }
    }

    return null;
  }

  /**
   * 清除过期缓存
   */
  async cleanExpiredCache(): Promise<number> {
    let cleaned = 0;
    const now = Date.now();

    // 清理内存缓存
    this.memoryCache.forEach((entry, key) => {
      if (entry.expiresAt <= now) {
        this.memoryCache.delete(key);
        cleaned++;
      }
    });

    // 清理 IndexedDB
    if (this.db) {
      try {
        const allEntries = await this.getAllFromDB<CacheEntry>('cache');
        for (const entry of allEntries) {
          if (entry.expiresAt <= now) {
            await this.deleteFromDB('cache', entry.key);
            cleaned++;
          }
        }
      } catch (err) {
        logger.error('清理过期缓存失败', err);
      }
    }

    logger.debug('缓存清理完成', { cleaned });
    return cleaned;
  }

  /**
   * 清除所有缓存
   */
  async clearAllCache(): Promise<void> {
    this.memoryCache.clear();

    if (this.db) {
      try {
        await this.clearDBStore('cache');
      } catch (err) {
        logger.error('清除缓存失败', err);
      }
    }

    logger.info('所有缓存已清除');
    this.notifySyncListeners();
  }

  /**
   * 缓存逐出策略（LRU + 大小限制）
   */
  private async evictIfNeeded(newEntrySize: number): Promise<void> {
    let currentCount = this.memoryCache.size;
    let currentSize = this.getCurrentCacheSize();

    // 按最后访问时间排序
    const entries = Array.from(this.memoryCache.entries())
      .sort(([, a], [, b]) => a.lastAccessedAt - b.lastAccessedAt);

    // 先移除过期的
    const now = Date.now();
    for (const [key, entry] of entries) {
      if (entry.expiresAt <= now) {
        this.memoryCache.delete(key);
        currentCount--;
        currentSize -= entry.size;
      }
    }

    // 如果仍超过限制，移除最少访问的
    const remainingEntries = Array.from(this.memoryCache.entries())
      .sort(([, a], [, b]) => a.lastAccessedAt - b.lastAccessedAt);

    for (const [key, entry] of remainingEntries) {
      if (currentCount < this.config.maxEntries && currentSize + newEntrySize < this.config.maxSize) {
        break;
      }
      this.memoryCache.delete(key);
      currentCount--;
      currentSize -= entry.size;
    }
  }

  private getCurrentCacheSize(): number {
    let size = 0;
    this.memoryCache.forEach((entry) => {
      size += entry.size;
    });
    return size;
  }

  // ============================
  // IndexedDB 辅助方法
  // ============================

  private putInDB(storeName: string, value: unknown): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));

      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.put(value);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  private getFromDB<T>(storeName: string, key: string): Promise<T | undefined> {
    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));

      const tx = this.db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      const request = store.get(key);

      request.onsuccess = () => resolve(request.result as T | undefined);
      request.onerror = () => reject(request.error);
    });
  }

  private getAllFromDB<T>(storeName: string): Promise<T[]> {
    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));

      const tx = this.db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result as T[]);
      request.onerror = () => reject(request.error);
    });
  }

  private deleteFromDB(storeName: string, key: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));

      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.delete(key);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  private clearDBStore(storeName: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.db) return reject(new Error('DB not initialized'));

      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.clear();

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  // ============================
  // 队列持久化
  // ============================

  private async persistQueue(): Promise<void> {
    if (this.config.enableDiskCache && this.db) {
      try {
        await this.clearDBStore('operations');
        for (const op of this.operationQueue) {
          await this.putInDB('operations', op);
        }
      } catch (err) {
        logger.error('持久化操作队列失败', err);
      }
    }
  }

  private async restoreQueue(): Promise<void> {
    if (this.config.enableDiskCache && this.db) {
      try {
        const savedOps = await this.getAllFromDB<OfflineOperation>('operations');
        this.operationQueue = savedOps.sort(
          (a, b) => a.priority - b.priority || a.createdAt - b.createdAt,
        );
        logger.info('恢复离线操作队列', { count: this.operationQueue.length });
      } catch (err) {
        logger.error('恢复操作队列失败', err);
      }
    }
  }

  private async persistConflicts(): Promise<void> {
    if (this.config.enableDiskCache && this.db) {
      try {
        await this.clearDBStore('conflicts');
        for (const conflict of this.conflicts) {
          await this.putInDB('conflicts', conflict);
        }
      } catch (err) {
        logger.error('持久化冲突列表失败', err);
      }
    }
  }

  private async restoreConflicts(): Promise<void> {
    if (this.config.enableDiskCache && this.db) {
      try {
        this.conflicts = await this.getAllFromDB<SyncConflict>('conflicts');
        logger.info('恢复冲突列表', { count: this.conflicts.length });
      } catch (err) {
        logger.error('恢复冲突列表失败', err);
      }
    }
  }

  // ============================
  // 调试工具
  // ============================

  /** 获取操作队列（只读） */
  getQueue(): ReadonlyArray<OfflineOperation> {
    return this.operationQueue;
  }

  /** 清空操作队列 */
  async clearQueue(): Promise<void> {
    this.operationQueue = [];
    await this.persistQueue();
    this.notifySyncListeners();
  }
}

// ============================
// 单例导出
// ============================

export const offlineService = new OfflineService();
export default offlineService;
