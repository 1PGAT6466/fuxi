/**
 * 伏羲 v2.1 — 实时协作 Pinia Store
 *
 * 管理协作会话的状态：连接、参与者、光标、编辑历史。
 * 与 CollaborationService 配合使用，提供响应式状态。
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';
import { CollaborationService, getCollaborationService, removeCollaborationService } from './CollaborationService';
import type {
  ConnectionStatus,
  Collaborator,
  CursorPosition,
  EditOperation,
} from './types';

const logger = createLogger('CollaborationStore');

export const useCollaborationStore = defineStore('collaboration', () => {
  // ══════════════════════════════════════
  // 状态
  // ══════════════════════════════════════

  /** 当前协作服务实例（一个文档一个） */
  let collaborationService: CollaborationService | null = null;

  /** 连接状态 */
  const connectionStatus = ref<ConnectionStatus>('disconnected');

  /** 当前文档 ID */
  const documentId = ref<string>('');

  /** 当前房间 ID */
  const roomId = ref<string>('');

  /** 当前用户 ID */
  const currentUserId = ref<string>('');

  /** 当前用户名 */
  const currentUserName = ref<string>('');

  /** 协作者列表（在线 + 离线） */
  const participants = ref<Collaborator[]>([]);

  /** 其他用户光标位置映射：userId → CursorPosition */
  const remoteCursors = ref<Map<string, CursorPosition>>(new Map());

  /** 编辑操作历史 */
  const editHistory = ref<EditOperation[]>([]);

  /** 文档当前内容 */
  const documentContent = ref<string>('');

  /** 错误信息 */
  const errorMessage = ref<string | null>(null);

  /** 通知消息 */
  const notification = ref<{ message: string; type: 'info' | 'success' | 'warning' | 'error' } | null>(null);

  // ══════════════════════════════════════
  // 计算属性
  // ══════════════════════════════════════

  /** 是否已连接 */
  const isConnected = computed(() => connectionStatus.value === 'connected');

  /** 正在连接中 */
  const isConnecting = computed(
    () => connectionStatus.value === 'connecting' || connectionStatus.value === 'reconnecting',
  );

  /** 在线参与者 */
  const onlineParticipants = computed(() =>
    participants.value.filter((p) => p.online),
  );

  /** 在线参与者数量 */
  const onlineCount = computed(() => onlineParticipants.value.length);

  /** 参与者的其他用户（排除自己） */
  const otherParticipants = computed(() =>
    participants.value.filter((p) => p.userId !== currentUserId.value),
  );

  /** 获取指定用户的光标 */
  function getCursor(userId: string): CursorPosition | undefined {
    return remoteCursors.value.get(userId);
  }

  // ══════════════════════════════════════
  // 操作
  // ══════════════════════════════════════

  /**
   * 初始化并加入协作房间
   *
   * @param _documentId - 文档 ID
   * @param userId - 用户 ID
   * @param userName - 用户名
   * @param _roomId - 房间 ID（可选，默认与 documentId 相同）
   */
  async function joinRoom(
    _documentId: string,
    userId: string,
    userName: string,
    _roomId?: string,
  ): Promise<void> {
    documentId.value = _documentId;
    roomId.value = _roomId || _documentId;
    currentUserId.value = userId;
    currentUserName.value = userName;
    errorMessage.value = null;

    try {
      // 创建或获取协作服务
      collaborationService = getCollaborationService(_documentId);

      // 注册事件监听器
      collaborationService.on('onDocumentUpdate', handleDocumentUpdate);
      collaborationService.on('onCursorUpdate', handleCursorUpdate);
      collaborationService.on('onUserJoin', handleUserJoin);
      collaborationService.on('onUserLeave', handleUserLeave);
      collaborationService.on('onRoomState', handleRoomState);
      collaborationService.on('onConnectionChange', handleConnectionChange);
      collaborationService.on('onError', handleError);
      collaborationService.on('onHistoryUpdate', handleHistoryUpdate);

      // 连接到房间
      collaborationService.connect(roomId.value, userId, userName);

      logger.info(`加入协作房间: ${roomId.value}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加入房间失败';
      errorMessage.value = msg;
      logger.error(msg, err);
    }
  }

  /**
   * 离开房间
   */
  function leaveRoom(): void {
    if (collaborationService) {
      collaborationService.disconnect();
    }

    if (documentId.value) {
      removeCollaborationService(documentId.value);
    }

    collaborationService = null;
    participants.value = [];
    remoteCursors.value = new Map();
    editHistory.value = [];
    documentId.value = '';
    roomId.value = '';
    connectionStatus.value = 'disconnected';
    documentContent.value = '';

    logger.info('已离开协作房间');
  }

  /**
   * 发送光标更新
   */
  function sendCursorPosition(cursor: CursorPosition): void {
    collaborationService?.sendCursorChange(cursor);
  }

  /**
   * 插入文本
   */
  function insertText(index: number, text: string): void {
    collaborationService?.insertText(index, text);
  }

  /**
   * 删除文本
   */
  function deleteText(index: number, length: number): void {
    collaborationService?.deleteText(index, length);
  }

  /**
   * 替换文本
   */
  function replaceText(index: number, length: number, text: string): void {
    collaborationService?.replaceText(index, length, text);
  }

  /**
   * 获取 Y.Doc，用于绑定编辑器（如 CodeMirror/TipTap）
   */
  function getYDoc() {
    return collaborationService?.getYDoc() ?? null;
  }

  /**
   * 获取 Y.Text
   */
  function getYText() {
    return collaborationService?.getYText() ?? null;
  }

  /** 清除通知 */
  function clearNotification(): void {
    notification.value = null;
  }

  // ══════════════════════════════════════
  // 事件处理器
  // ══════════════════════════════════════

  function handleDocumentUpdate(text: string): void {
    documentContent.value = text;
  }

  function handleCursorUpdate(userId: string, position: CursorPosition): void {
    const newCursors = new Map(remoteCursors.value);
    newCursors.set(userId, position);
    remoteCursors.value = newCursors;
  }

  function handleUserJoin(user: Collaborator): void {
    const existing = participants.value.find((p) => p.userId === user.userId);
    if (existing) {
      // 更新已有用户状态
      const idx = participants.value.indexOf(existing);
      participants.value[idx] = user;
    } else {
      participants.value.push(user);
    }
    showNotification(`${user.userName} 加入了协作`);
  }

  function handleUserLeave(userId: string): void {
    const user = participants.value.find((p) => p.userId === userId);
    if (user) {
      user.online = false;
      // 移除其光标
      const newCursors = new Map(remoteCursors.value);
      newCursors.delete(userId);
      remoteCursors.value = newCursors;

      showNotification(`${user.userName} 离开了协作`);
    }
  }

  function handleRoomState(state: Collaborator[]): void {
    participants.value = state.map((p) => ({
      ...p,
      online: true,
    }));
  }

  function handleConnectionChange(status: ConnectionStatus): void {
    connectionStatus.value = status;

    if (status === 'connected') {
      showNotification('已连接协作服务器', 'success');
    } else if (status === 'reconnecting') {
      showNotification('正在重新连接...', 'warning');
    } else if (status === 'error') {
      showNotification('连接失败', 'error');
    }
  }

  function handleError(error: Error): void {
    errorMessage.value = error.message;
    logger.error('协作错误', error);
  }

  function handleHistoryUpdate(operations: EditOperation[]): void {
    editHistory.value = operations;
  }

  function showNotification(
    message: string,
    type: 'info' | 'success' | 'warning' | 'error' = 'info',
  ): void {
    notification.value = { message, type };
    // 3 秒后自动清除
    setTimeout(() => {
      if (notification.value?.message === message) {
        notification.value = null;
      }
    }, 3000);
  }

  return {
    // state
    connectionStatus,
    documentId,
    roomId,
    currentUserId,
    currentUserName,
    participants,
    remoteCursors,
    editHistory,
    documentContent,
    errorMessage,
    notification,
    // computed
    isConnected,
    isConnecting,
    onlineParticipants,
    onlineCount,
    otherParticipants,
    getCursor,
    // actions
    joinRoom,
    leaveRoom,
    sendCursorPosition,
    insertText,
    deleteText,
    replaceText,
    getYDoc,
    getYText,
    clearNotification,
  };
});
