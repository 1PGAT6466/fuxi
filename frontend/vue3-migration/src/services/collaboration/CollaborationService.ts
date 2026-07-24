/**
 * 伏羲 v2.1 — 实时协作服务
 *
 * 使用 Yjs (CRDT) 实现多人实时协作编辑。
 *
 * 核心能力：
 * - Yjs 文档同步（Y.Doc + Y.Text）
 * - WebSocket 连接管理（自动重连、心跳）
 * - Awareness 协议（光标位置、在线状态广播）
 * - 编辑历史记录追踪
 * - 冲突自动解决（CRDT 保证最终一致性）
 *
 * 协议层：
 * - 传输：WebSocket over Binary
 * - 同步：Yjs Sync Protocol (sync-step1/step2)
 * - 感知：Yjs Awareness Protocol
 * - 客户端消息：JSON 包装的用户层消息
 */

import * as Y from 'yjs';
import { createLogger } from '@/utils/logger';
import type {
  CollaborationConfig,
  CollaborationMessage,
  CollaborationMessageUnion,
  ConnectionStatus,
  Collaborator,
  CursorPosition,
  EditOperation,
  EditOperationType,
  SyncRequestMessage,
  SyncResponseMessage,
  SyncUpdateMessage,
  AwarenessUpdateMessage,
  CursorUpdateMessage,
  UserJoinMessage,
  UserLeaveMessage,
  RoomStateMessage,
  PingMessage,
  PongMessage,
} from './types';
import { COLLABORATOR_COLORS } from './types';

const logger = createLogger('CollabService');

// ============================
// 默认配置
// ============================

const DEFAULT_CONFIG: CollaborationConfig = {
  wsUrl: `ws://${window.location.host}/api/collaboration/ws`,
  reconnectInterval: 2000,
  maxReconnectAttempts: 10,
  pingInterval: 15000,
  pingTimeout: 5000,
};

// ============================
// 协作事件类型
// ============================

export interface CollaborationEventHandlers {
  onDocumentUpdate?: (text: string) => void;
  onCursorUpdate?: (userId: string, position: CursorPosition) => void;
  onUserJoin?: (user: Collaborator) => void;
  onUserLeave?: (userId: string) => void;
  onRoomState?: (participants: Collaborator[]) => void;
  onConnectionChange?: (status: ConnectionStatus) => void;
  onError?: (error: Error) => void;
  onHistoryUpdate?: (operations: EditOperation[]) => void;
}

/**
 * 实时协作服务类（单实例，每个房间一个实例）。
 *
 * 生命周期：
 *   1. 构造 → connect(roomId, userId) → 建立 WS 连接 + Yjs 同步
 *   2. 编辑 → ydoc.text 操作自动触发 sync-update → 广播
 *   3. 光标 → sendCursorChange → 通过 awareness 广播
 *   4. 断开 → disconnect() → 清理连接
 */
export class CollaborationService {
  // ── Yjs CRDT ──
  private ydoc: Y.Doc;
  private ytext: Y.Text;

  // ── WebSocket ──
  private ws: WebSocket | null = null;
  private config: CollaborationConfig;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private pongTimer: ReturnType<typeof setTimeout> | null = null;
  private lastPingTime = 0;

  // ── 会话状态 ──
  private roomId: string | null = null;
  private userId: string | null = null;
  private userName: string | null = null;
  private avatarColor: string | null = null;
  private connectionStatus: ConnectionStatus = 'disconnected';
  private documentVersion = 0;

  // ── 用户与历史 ──
  private participants: Map<string, Collaborator> = new Map();
  private editHistory: EditOperation[] = [];
  private maxHistorySize = 100;

  // ── 事件回调 ──
  private handlers: CollaborationEventHandlers = {};

  // ── 本地变更缓冲（防止循环广播） ──
  private isRemoteUpdate = false;

  // ── 批量发送缓冲 ──
  private pendingUpdates: Uint8Array[] = [];
  private batchTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly batchInterval = 50; // ms

  constructor(config?: Partial<CollaborationConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    // 创建 Yjs 文档
    this.ydoc = new Y.Doc();
    this.ytext = this.ydoc.getText('content');

    // 监听 Yjs 文档变更
    this.ydoc.on('update', this.handleYjsUpdate.bind(this));

    // 监听文本变更，通知 UI
    this.ytext.observe(this.handleTextChange.bind(this));
  }

  // ═══════════════════════════════════════════
  // 连接管理
  // ═══════════════════════════════════════════

  /**
   * 连接到协作房间
   *
   * @param roomId - 协作房间 ID
   * @param userId - 当前用户 ID
   * @param userName - 当前用户显示名称
   */
  connect(roomId: string, userId: string, userName: string): void {
    if (this.connectionStatus === 'connected' || this.connectionStatus === 'connecting') {
      logger.warn('已有连接，先断开再重连');
      this.disconnect();
    }

    this.roomId = roomId;
    this.userId = userId;
    this.userName = userName;
    this.avatarColor = this.pickAvatarColor(userId);
    this.reconnectAttempts = 0;

    this.setStatus('connecting');
    this.openWebSocket();
    this.startPing();
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.clearTimers();
    this.setStatus('disconnected');

    if (this.ws) {
      // 发送离开消息
      this.sendUserLeave();
      this.ws.close();
      this.ws = null;
    }

    this.roomId = null;
    this.participants.clear();
    this.editHistory = [];
  }

  /**
   * 获取当前连接状态
   */
  getStatus(): ConnectionStatus {
    return this.connectionStatus;
  }

  /**
   * 获取所有参与者
   */
  getParticipants(): Collaborator[] {
    return Array.from(this.participants.values());
  }

  /**
   * 获取编辑历史
   */
  getEditHistory(): EditOperation[] {
    return this.editHistory;
  }

  /**
   * 获取 Yjs 文档，用于外部集成
   */
  getYDoc(): Y.Doc {
    return this.ydoc;
  }

  /**
   * 获取 Y.Text，用于绑定编辑器
   */
  getYText(): Y.Text {
    return this.ytext;
  }

  /**
   * 获取当前文本内容
   */
  getContent(): string {
    return this.ytext.toString();
  }

  // ═══════════════════════════════════════════
  // 事件注册
  // ═══════════════════════════════════════════

  on<K extends keyof CollaborationEventHandlers>(
    event: K,
    handler: NonNullable<CollaborationEventHandlers[K]>,
  ): () => void {
    this.handlers[event] = handler;
    return () => {
      if (this.handlers[event] === handler) {
        delete this.handlers[event];
      }
    };
  }

  // ═══════════════════════════════════════════
  // 文本操作
  // ═══════════════════════════════════════════

  /**
   * 插入文本
   */
  insertText(index: number, text: string): void {
    this.ytext.insert(index, text);
    this.recordEditHistory('insert', `插入 "${text.slice(0, 20)}${text.length > 20 ? '...' : ''}"`);
  }

  /**
   * 删除文本
   */
  deleteText(index: number, length: number): void {
    const deleted = this.ytext.toString().slice(index, index + length);
    this.ytext.delete(index, length);
    this.recordEditHistory(
      'delete',
      `删除 "${deleted.slice(0, 20)}${deleted.length > 20 ? '...' : ''}"`,
    );
  }

  /**
   * 替换文本
   */
  replaceText(index: number, length: number, text: string): void {
    this.deleteText(index, length);
    this.insertText(index, text);
  }

  /**
   * 设置完整文档内容（通常用于初始化）
   */
  setContent(text: string): void {
    this.isRemoteUpdate = true;
    this.ytext.delete(0, this.ytext.length);
    this.ytext.insert(0, text);
    this.isRemoteUpdate = false;
  }

  // ═══════════════════════════════════════════
  // 光标同步
  // ═══════════════════════════════════════════

  /**
   * 发送光标位置更新
   */
  sendCursorChange(cursor: CursorPosition): void {
    if (!this.userId || !this.roomId || !this.ws) return;
    if (this.connectionStatus !== 'connected') return;

    const message: CursorUpdateMessage = {
      type: 'cursor-update',
      roomId: this.roomId,
      senderId: this.userId,
      timestamp: Date.now(),
      position: cursor,
      userName: this.userName || '未知用户',
      avatarColor: this.avatarColor || '#FF6700',
    };

    this.sendMessage(message);
  }

  // ═══════════════════════════════════════════
  // WebSocket 内部实现
  // ═══════════════════════════════════════════

  private openWebSocket(): void {
    if (!this.roomId || !this.userId) {
      logger.error('缺少 roomId 或 userId，无法建立连接');
      return;
    }

    const url = `${this.config.wsUrl}?room=${encodeURIComponent(this.roomId)}&userId=${encodeURIComponent(this.userId)}&userName=${encodeURIComponent(this.userName || this.userId)}&color=${encodeURIComponent(this.avatarColor || '#FF6700')}`;

    logger.info(`WebSocket 连接: ${url}`);

    try {
      this.ws = new WebSocket(url);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = this.handleWSOpen.bind(this);
      this.ws.onmessage = this.handleWSMessage.bind(this);
      this.ws.onclose = this.handleWSClose.bind(this);
      this.ws.onerror = this.handleWSError.bind(this);
    } catch (err) {
      logger.error('WebSocket 创建失败', err);
      this.setStatus('error');
      this.handlers.onError?.(new Error('无法创建 WebSocket 连接'));
    }
  }

  private handleWSOpen(): void {
    logger.info('WebSocket 连接已建立');
    this.setStatus('connected');
    this.reconnectAttempts = 0;

    // 发送同步请求
    this.sendSyncRequest();

    // 发送用户加入
    this.sendUserJoin();
  }

  private handleWSMessage(event: MessageEvent): void {
    try {
      const raw = event.data;

      // 处理二进制消息（Yjs sync protocol）
      if (raw instanceof ArrayBuffer) {
        const update = new Uint8Array(raw);
        this.applyRemoteUpdate(update);
        return;
      }

      // 处理文本消息（JSON 协议）
      if (typeof raw === 'string') {
        const message = JSON.parse(raw) as CollaborationMessageUnion;
        this.dispatchMessage(message);
        return;
      }

      // 处理 Blob
      if (raw instanceof Blob) {
        raw.arrayBuffer().then((buffer) => {
          const update = new Uint8Array(buffer);
          this.applyRemoteUpdate(update);
        }).catch((err) => {
          logger.error('Blob 解析失败', err);
        });
      }
    } catch (err) {
      logger.error('消息解析失败', err);
    }
  }

  private handleWSClose(event: CloseEvent): void {
    logger.info(`WebSocket 连接关闭: ${event.code} ${event.reason}`);
    this.setStatus('disconnected');

    // 自动重连
    if (
      this.roomId &&
      this.userId &&
      this.reconnectAttempts < this.config.maxReconnectAttempts
    ) {
      this.scheduleReconnect();
    }
  }

  private handleWSError(event: Event): void {
    logger.error('WebSocket 错误', event);
    this.setStatus('error');
    this.handlers.onError?.(new Error('WebSocket 连接错误'));
  }

  // ═══════════════════════════════════════════
  // 消息分发
  // ═══════════════════════════════════════════

  private dispatchMessage(message: CollaborationMessageUnion): void {
    switch (message.type) {
      case 'sync-response':
        this.handleSyncResponse(message as SyncResponseMessage);
        break;
      case 'sync-update':
        this.handleIncomingUpdate(message as SyncUpdateMessage);
        break;
      case 'awareness-update':
        this.handleAwarenessUpdate(message as AwarenessUpdateMessage);
        break;
      case 'cursor-update':
        this.handleCursorUpdate(message as CursorUpdateMessage);
        break;
      case 'user-join':
        this.handleUserJoin(message as UserJoinMessage);
        break;
      case 'user-leave':
        this.handleUserLeave(message as UserLeaveMessage);
        break;
      case 'room-state':
        this.handleRoomState(message as RoomStateMessage);
        break;
      case 'ping':
        this.handlePing(message as PingMessage);
        break;
      case 'pong':
        this.handlePong();
        break;
      case 'ack':
        // 确认消息，当前不需要额外处理
        break;
      default:
        logger.debug('未知消息类型:', (message as CollaborationMessage).type);
    }
  }

  private sendMessage(message: CollaborationMessageUnion): void {
    if (!this.ws || this.connectionStatus !== 'connected') {
      logger.debug('未连接，跳过发送消息');
      return;
    }
    try {
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      logger.error('消息发送失败', err);
    }
  }

  // ═══════════════════════════════════════════
  // 消息处理
  // ═══════════════════════════════════════════

  private sendSyncRequest(): void {
    if (!this.roomId || !this.userId) return;

    const message: SyncRequestMessage = {
      type: 'sync-request',
      roomId: this.roomId,
      senderId: this.userId,
      timestamp: Date.now(),
    };
    this.sendMessage(message);
  }

  private handleSyncResponse(message: SyncResponseMessage): void {
    try {
      logger.info('收到同步响应，加载文档快照');

      this.isRemoteUpdate = true;

      // 如果有文档快照，直接设置内容
      if (message.documentSnapshot !== undefined) {
        this.ytext.delete(0, this.ytext.length);
        this.ytext.insert(0, message.documentSnapshot);
      }

      this.isRemoteUpdate = false;
    } catch (err) {
      logger.error('同步响应处理失败', err);
    }
  }

  /**
   * 处理远端 Yjs update
   */
  private applyRemoteUpdate(update: Uint8Array): void {
    try {
      this.isRemoteUpdate = true;
      Y.applyUpdate(this.ydoc, update);
      this.isRemoteUpdate = false;
    } catch (err) {
      logger.error('应用远端更新失败', err);
    }
  }

  private handleIncomingUpdate(message: SyncUpdateMessage): void {
    try {
      this.documentVersion = message.version;
      const update = Uint8Array.from(atob(message.update), (c) => c.charCodeAt(0));
      this.applyRemoteUpdate(update);
    } catch (err) {
      logger.error('增量更新处理失败', err);
    }
  }

  private handleAwarenessUpdate(message: AwarenessUpdateMessage): void {
    try {
      logger.debug('收到感知状态更新');
      // awareness states 可以由服务端转发（简化实现）
    } catch (err) {
      logger.error('感知状态更新失败', err);
    }
  }

  private handleCursorUpdate(message: CursorUpdateMessage): void {
    if (message.senderId === this.userId) return; // 忽略自己的光标

    logger.debug(`光标更新: ${message.userName} → L${message.position.line}:C${message.position.column}`);
    this.handlers.onCursorUpdate?.(message.senderId, message.position);
  }

  private handleUserJoin(message: UserJoinMessage): void {
    if (message.user.userId === this.userId) return;

    this.participants.set(message.user.userId, message.user);
    logger.info(`用户加入: ${message.user.userName}`);
    this.handlers.onUserJoin?.(message.user);
  }

  private handleUserLeave(message: UserLeaveMessage): void {
    if (message.userId === this.userId) return;

    this.participants.delete(message.userId);
    logger.info(`用户离开: ${message.userId}`);
    this.handlers.onUserLeave?.(message.userId);
  }

  private handleRoomState(message: RoomStateMessage): void {
    logger.info(`房间状态更新: ${message.participants.length} 位参与者, 版本 ${message.version}`);
    this.documentVersion = message.version;

    this.participants.clear();
    for (const p of message.participants) {
      this.participants.set(p.userId, p);
    }

    this.handlers.onRoomState?.(message.participants);
  }

  private handlePing(_message: PingMessage): void {
    this.pongTimer = setTimeout(() => {
      // 发送 pong 响应
      if (!this.roomId || !this.userId) return;
      const pong: PongMessage = {
        type: 'pong',
        roomId: this.roomId,
        senderId: this.userId,
        timestamp: Date.now(),
      };
      this.sendMessage(pong);
    }, 0);
  }

  private handlePong(): void {
    logger.debug('收到 pong');
    // 心跳正常，不需要额外操作
  }

  // ═══════════════════════════════════════════
  // Yjs 文档变更处理
  // ═══════════════════════════════════════════

  private handleYjsUpdate = (update: Uint8Array, origin: unknown): void => {
    // 忽略自己触发的更新
    if (origin === this || this.isRemoteUpdate) return;

    // 发送 Yjs update 到服务端
    this.bufferUpdate(update);
  };

  private handleTextChange = (): void => {
    const newText = this.ytext.toString();
    this.handlers.onDocumentUpdate?.(newText);
  };

  // ═══════════════════════════════════════════
  // 更新缓冲（批量发送）
  // ═══════════════════════════════════════════

  private bufferUpdate(update: Uint8Array): void {
    this.pendingUpdates.push(update);

    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
    }

    this.batchTimer = setTimeout(() => {
      this.flushUpdates();
    }, this.batchInterval);
  }

  private flushUpdates(): void {
    if (this.pendingUpdates.length === 0) return;

    // 合并所有待发送的 updates
    const mergedUpdate = Y.mergeUpdates(this.pendingUpdates);
    this.pendingUpdates = [];

    // 发送合并后的 update
    if (this.roomId && this.userId) {
      const message: SyncUpdateMessage = {
        type: 'sync-update',
        roomId: this.roomId,
        senderId: this.userId,
        timestamp: Date.now(),
        update: this.uint8ArrayToBase64(mergedUpdate),
        version: ++this.documentVersion,
      };
      this.sendMessage(message);
    }
  }

  // ═══════════════════════════════════════════
  // 用户事件
  // ═══════════════════════════════════════════

  private sendUserJoin(): void {
    if (!this.roomId || !this.userId) return;

    const user: Collaborator = {
      userId: this.userId,
      userName: this.userName || this.userId,
      avatarColor: this.avatarColor || '#FF6700',
      joinedAt: Date.now(),
      online: true,
    };

    const message: UserJoinMessage = {
      type: 'user-join',
      roomId: this.roomId,
      senderId: this.userId,
      timestamp: Date.now(),
      user,
    };
    this.sendMessage(message);
  }

  private sendUserLeave(): void {
    if (!this.roomId || !this.userId) return;

    const message: UserLeaveMessage = {
      type: 'user-leave',
      roomId: this.roomId,
      senderId: this.userId,
      timestamp: Date.now(),
      userId: this.userId,
    };
    this.sendMessage(message);
  }

  // ═══════════════════════════════════════════
  // 编辑历史
  // ═══════════════════════════════════════════

  private recordEditHistory(type: EditOperationType, summary: string): void {
    const operation: EditOperation = {
      id: this.generateId(),
      userId: this.userId || 'unknown',
      userName: this.userName || '未知用户',
      type,
      timestamp: Date.now(),
      update: [], // Yjs update 已在同步时发送，历史记录仅存储摘要
      summary,
    };

    this.editHistory.unshift(operation);

    // 限制历史大小
    if (this.editHistory.length > this.maxHistorySize) {
      this.editHistory = this.editHistory.slice(0, this.maxHistorySize);
    }

    this.handlers.onHistoryUpdate?.(this.editHistory);
  }

  // ═══════════════════════════════════════════
  // 心跳
  // ═══════════════════════════════════════════

  private startPing(): void {
    this.pingTimer = setInterval(() => {
      if (this.connectionStatus !== 'connected' || !this.ws || !this.roomId || !this.userId)
        return;

      this.lastPingTime = Date.now();

      const ping: PingMessage = {
        type: 'ping',
        roomId: this.roomId,
        senderId: this.userId,
        timestamp: this.lastPingTime,
      };
      this.sendMessage(ping);
    }, this.config.pingInterval);
  }

  // ═══════════════════════════════════════════
  // 重连
  // ═══════════════════════════════════════════

  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay =
      this.config.reconnectInterval * Math.min(this.reconnectAttempts, 5);

    logger.info(
      `将在 ${delay}ms 后重连 (第 ${this.reconnectAttempts} 次, 最大 ${this.config.maxReconnectAttempts})`,
    );

    this.setStatus('reconnecting');

    this.reconnectTimer = setTimeout(() => {
      if (this.roomId && this.userId) {
        this.openWebSocket();
      }
    }, delay);
  }

  // ═══════════════════════════════════════════
  // 工具方法
  // ═══════════════════════════════════════════

  private setStatus(status: ConnectionStatus): void {
    this.connectionStatus = status;
    this.handlers.onConnectionChange?.(status);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }
  }

  private pickAvatarColor(userId: string): string {
    // 基于 userId 哈希选择一致的颜色
    let hash = 0;
    for (let i = 0; i < userId.length; i++) {
      hash = (hash * 31 + userId.charCodeAt(i)) & 0xffffffff;
    }
    const index = Math.abs(hash) % COLLABORATOR_COLORS.length;
    return COLLABORATOR_COLORS[index];
  }

  private generateId(): string {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
  }

  private uint8ArrayToBase64(arr: Uint8Array): string {
    let binary = '';
    for (let i = 0; i < arr.length; i++) {
      binary += String.fromCharCode(arr[i]);
    }
    return btoa(binary);
  }

  /**
   * 销毁服务实例，释放所有资源
   */
  destroy(): void {
    this.disconnect();
    this.ydoc.destroy();
  }
}

// ═══════════════════════════════════════════
// 单例工厂
// ═══════════════════════════════════════════

/** 每个文档一个协作实例 */
const serviceInstances: Map<string, CollaborationService> = new Map();

/**
 * 获取或创建协作服务实例
 * @param documentId - 文档 ID
 * @returns CollaborationService 实例
 */
export function getCollaborationService(documentId: string): CollaborationService {
  let instance = serviceInstances.get(documentId);
  if (!instance) {
    instance = new CollaborationService();
    serviceInstances.set(documentId, instance);
  }
  return instance;
}

/**
 * 清理指定文档的协作实例
 */
export function removeCollaborationService(documentId: string): void {
  const instance = serviceInstances.get(documentId);
  if (instance) {
    instance.destroy();
    serviceInstances.delete(documentId);
  }
}

/**
 * 清理所有协作实例
 */
export function removeAllCollaborationServices(): void {
  for (const [key, instance] of serviceInstances) {
    instance.destroy();
  }
  serviceInstances.clear();
}

export default CollaborationService;
