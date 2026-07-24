/**
 * 伏羲 v2.1 — 协作服务端 WebSocket 模拟层
 *
 * 前端独立运行：在浏览器端模拟 WebSocket 服务器的行为。
 * 这样可以在没有后端支持的情况下进行前端开发和测试。
 *
 * 工作方式：
 *   - 拦截 WebSocket 连接，在客户端内部直接处理消息
 *   - 使用 BroadcastChannel 模拟多客户端的消息广播
 *   - 当真实后端可用时，删除此模块即可切换到真实 WebSocket
 */

import { createLogger } from '@/utils/logger';
import type {
  CollaborationMessageUnion,
  SyncRequestMessage,
  SyncResponseMessage,
  SyncUpdateMessage,
  UserJoinMessage,
  UserLeaveMessage,
  CursorUpdateMessage,
  RoomStateMessage,
  PingMessage,
  PongMessage,
  Collaborator,
} from './types';

const logger = createLogger('CollabServerMock');

// ============================
// 会话存储
// ============================

interface RoomState {
  roomId: string;
  participants: Map<string, Collaborator>;
  documentContent: string;
  version: number;
  updates: string[]; // 存储 base64 编码的 Yjs updates
}

/** 房间状态表：roomId → RoomState */
const rooms: Map<string, RoomState> = new Map();

/** 频道级广播：roomId → BroadcastChannel（用于本地多实例模拟） */
const broadcastChannels: Map<string, BroadcastChannel> = new Map();

// ============================
// 消息处理器类型
// ============================

type MessageSender = (message: CollaborationMessageUnion | ArrayBuffer) => void;

// ============================
// 模拟 WebSocket 服务器
// ============================

/**
 * 创建模拟 WebSocket 服务器。
 *
 * 在真实 WebSocket 连接前拦截，将消息路由到内存中的模拟服务器。
 *
 * @param url - 连接 URL（包含 ?room=xxx&userId=xxx 等参数）
 * @returns 一个对象，模拟 WebSocket 的 send/close 接口
 */
export function createMockWSServer(
  url: string,
): {
  clientSend: (data: string | ArrayBuffer) => void;
  onServerMessage: (handler: MessageSender) => void;
  onServerClose: (handler: (code: number, reason: string) => void) => void;
  onServerError: (handler: (error: Event) => void) => void;
  close: () => void;
} {
  // 解析 URL 参数
  const parsedUrl = new URL(url, window.location.origin);
  const roomId = parsedUrl.searchParams.get('room') || 'default';
  const userId = parsedUrl.searchParams.get('userId') || 'anonymous';
  const userName = parsedUrl.searchParams.get('userName') || userId;
  const color = parsedUrl.searchParams.get('color') || '#FF6700';

  // 确保房间存在
  if (!rooms.has(roomId)) {
    rooms.set(roomId, {
      roomId,
      participants: new Map(),
      documentContent: '',
      version: 0,
      updates: [],
    });
  }

  const room = rooms.get(roomId)!;

  // 创建广播通道
  if (!broadcastChannels.has(roomId)) {
    const channel = new BroadcastChannel(`collab-${roomId}`);
    broadcastChannels.set(roomId, channel);
  }
  const channel = broadcastChannels.get(roomId)!;

  // 当前客户端加入房间
  const collaborator: Collaborator = {
    userId,
    userName,
    avatarColor: color,
    joinedAt: Date.now(),
    online: true,
  };
  room.participants.set(userId, collaborator);

  // 消息发送回调
  let serverMessageHandler: MessageSender | null = null;
  let serverCloseHandler: ((code: number, reason: string) => void) | null = null;
  let serverErrorHandler: ((error: Event) => void) | null = null;

  // 监听广播通道（来自其他客户端的消息）
  const broadcastHandler = (event: MessageEvent) => {
    if (event.data?.senderId === userId) return; // 忽略自己

    try {
      const { type, payload } = event.data as { type: string; payload: unknown };

      switch (type) {
        case 'sync-update':
          // 转发增量更新给当前客户端
          serverMessageHandler?.(JSON.stringify(payload));
          break;
        case 'cursor-update':
          // 转发光标更新
          serverMessageHandler?.(JSON.stringify(payload));
          break;
        case 'user-join': {
          const joinMsg = payload as UserJoinMessage;
          serverMessageHandler?.(JSON.stringify(joinMsg));
          // 发送当前房间状态
          sendRoomState(room, userId, serverMessageHandler);
          break;
        }
        case 'user-leave': {
          const leaveMsg = payload as UserLeaveMessage;
          serverMessageHandler?.(JSON.stringify(leaveMsg));
          sendRoomState(room, userId, serverMessageHandler);
          break;
        }
        case 'ping':
          serverMessageHandler?.(JSON.stringify({
            type: 'pong',
            roomId,
            senderId: 'server',
            timestamp: Date.now(),
          } as PongMessage));
          break;
      }
    } catch (err) {
      logger.debug('广播消息处理失败', err);
    }
  };

  channel.addEventListener('message', broadcastHandler);

  // 发送当前房间状态给新加入的客户端
  const joinMsg: UserJoinMessage = {
    type: 'user-join',
    roomId,
    senderId: 'server',
    timestamp: Date.now(),
    user: collaborator,
  };

  // 通过 BroadcastChannel 通知所有其他客户端
  if (rooms.get(roomId)!.participants.size > 1) {
    channel.postMessage({
      type: 'user-join',
      payload: joinMsg,
      senderId: userId,
    });
  }

  // 发送初始房间状态给当前客户端
  setTimeout(() => {
    sendRoomState(room, userId, serverMessageHandler);

    // 发送同步响应（当前文档内容）
    const syncResponse: SyncResponseMessage = {
      type: 'sync-response',
      roomId,
      senderId: 'server',
      timestamp: Date.now(),
      stateVector: '',
      documentSnapshot: room.documentContent,
    };
    serverMessageHandler?.(JSON.stringify(syncResponse));
  }, 50);

  // 返回客户端接口
  return {
    /**
     * 从客户端发送消息到服务器
     */
    clientSend(data: string | ArrayBuffer): void {
      try {
        // 二进制数据（Yjs update）→ 广播给其他客户端
        if (typeof data === 'string') {
          const message = JSON.parse(data) as CollaborationMessageUnion;

          switch (message.type) {
            case 'sync-request': {
              const syncReq = message as SyncRequestMessage;
              const syncResponse: SyncResponseMessage = {
                type: 'sync-response',
                roomId,
                senderId: 'server',
                timestamp: Date.now(),
                stateVector: '',
                documentSnapshot: room.documentContent,
              };
              serverMessageHandler?.(JSON.stringify(syncResponse));
              break;
            }

            case 'sync-update': {
              const syncMsg = message as SyncUpdateMessage;
              room.version = syncMsg.version;
              room.documentContent = syncMsg.update; // 存储最后一次 update
              room.updates.push(syncMsg.update);

              // 广播给其他客户端
              channel.postMessage({
                type: 'sync-update',
                payload: syncMsg,
                senderId: userId,
              });
              break;
            }

            case 'cursor-update': {
              const cursorMsg = message as CursorUpdateMessage;
              // 广播光标位置
              channel.postMessage({
                type: 'cursor-update',
                payload: cursorMsg,
                senderId: userId,
              });
              break;
            }

            case 'user-join': {
              const joinMsg = message as UserJoinMessage;
              channel.postMessage({
                type: 'user-join',
                payload: joinMsg,
                senderId: userId,
              });
              break;
            }

            case 'user-leave': {
              const leaveMsg = message as UserLeaveMessage;
              room.participants.delete(userId);
              channel.postMessage({
                type: 'user-leave',
                payload: leaveMsg,
                senderId: userId,
              });
              break;
            }

            case 'ping': {
              const pong: PongMessage = {
                type: 'pong',
                roomId,
                senderId: 'server',
                timestamp: Date.now(),
              };
              serverMessageHandler?.(JSON.stringify(pong));
              break;
            }
          }
        }
      } catch (err) {
        logger.error('消息处理失败', err);
      }
    },

    /**
     * 注册服务器消息回调
     */
    onServerMessage(handler: MessageSender): void {
      serverMessageHandler = handler;
    },

    /**
     * 注册服务器关闭回调
     */
    onServerClose(handler: (code: number, reason: string) => void): void {
      serverCloseHandler = handler;
    },

    /**
     * 注册服务器错误回调
     */
    onServerError(handler: (error: Event) => void): void {
      serverErrorHandler = handler;
    },

    /**
     * 关闭连接
     */
    close(): void {
      room.participants.delete(userId);

      // 通知其他客户端
      channel.postMessage({
        type: 'user-leave',
        payload: {
          type: 'user-leave',
          roomId,
          senderId: userId,
          timestamp: Date.now(),
          userId,
        } as UserLeaveMessage,
        senderId: userId,
      });

      channel.removeEventListener('message', broadcastHandler);

      // 如果房间没有参与者，清理房间
      if (room.participants.size === 0) {
        rooms.delete(roomId);
        channel.close();
        broadcastChannels.delete(roomId);
      }

      serverCloseHandler?.(1000, 'Client disconnected');
    },
  };
}

// ============================
// 辅助函数
// ============================

function sendRoomState(
  room: RoomState,
  targetUserId: string,
  handler: MessageSender | null,
): void {
  const state: RoomStateMessage = {
    type: 'room-state',
    roomId: room.roomId,
    senderId: 'server',
    timestamp: Date.now(),
    participants: Array.from(room.participants.values()),
    version: room.version,
  };
  handler?.(JSON.stringify(state));
}

/**
 * 启用模拟服务器模式。
 *
 * 调用此函数将使用 BroadcastChannel 模拟 WebSocket 通信，
 * 这样即使没有后端，前端也能完整运作。
 */
export function enableMockMode(): void {
  logger.info('协作模拟模式已启用（BroadcastChannel）');
}

/**
 * 禁用模拟服务器模式
 */
export function disableMockMode(): void {
  for (const [, channel] of broadcastChannels) {
    channel.close();
  }
  broadcastChannels.clear();
  rooms.clear();
  logger.info('协作模拟模式已禁用');
}
