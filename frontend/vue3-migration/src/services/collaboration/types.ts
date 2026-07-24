/**
 * 伏羲 v2.1 — 实时协作类型定义
 *
 * 定义协作服务的核心数据类型：
 * - 协作用户、光标、编辑操作、房间状态等
 */

// ============================
// 协作房间
// ============================

/** 协作房间 */
export interface CollaborationRoom {
  id: string;
  name: string;
  documentId: string;
  documentName: string;
  createdAt: number;
  participants: Collaborator[];
}

/** 协作用户 */
export interface Collaborator {
  userId: string;
  userName: string;
  avatarColor: string;
  joinedAt: number;
  /** 当前光标位置 */
  cursor?: CursorPosition;
  /** 是否在线 */
  online: boolean;
}

// ============================
// 光标位置
// ============================

/** 光标位置（基于 Yjs relative position） */
export interface CursorPosition {
  /** 段落/行索引 */
  line: number;
  /** 列/字符索引 */
  column: number;
  /** 选中区域起始（可选） */
  selectionStart?: { line: number; column: number };
  /** 选中区域结束（可选） */
  selectionEnd?: { line: number; column: number };
}

// ============================
// 编辑操作
// ============================

/** 编辑操作类型 */
export type EditOperationType = 'insert' | 'delete' | 'replace';

/** 编辑操作记录 */
export interface EditOperation {
  id: string;
  userId: string;
  userName: string;
  type: EditOperationType;
  timestamp: number;
  /** 操作的 Yjs Update 序列化字节（Uint8Array） */
  update: number[];
  /** 可选的摘要信息 */
  summary?: string;
}

// ============================
// WebSocket 消息协议
// ============================

/** WebSocket 消息类型 */
export type CollaborationMessageType =
  | 'sync-request'
  | 'sync-response'
  | 'sync-update'
  | 'awareness-update'
  | 'cursor-update'
  | 'user-join'
  | 'user-leave'
  | 'room-state'
  | 'ack'
  | 'ping'
  | 'pong';

/** 协作消息基类 */
export interface CollaborationMessage {
  type: CollaborationMessageType;
  roomId: string;
  /** 发送者 ID */
  senderId: string;
  /** 消息时间戳 */
  timestamp: number;
}

/** 同步请求（客户端首次连接时请求全文） */
export interface SyncRequestMessage extends CollaborationMessage {
  type: 'sync-request';
}

/** 同步响应（服务端返回全文状态向量） */
export interface SyncResponseMessage extends CollaborationMessage {
  type: 'sync-response';
  /** 序列化的 Yjs Doc update（base64 编码） */
  stateVector: string;
  /** 当前文档内容快照 */
  documentSnapshot: string;
}

/** 增量同步更新 */
export interface SyncUpdateMessage extends CollaborationMessage {
  type: 'sync-update';
  /** 序列化的 Yjs Doc update（base64 编码） */
  update: string;
  /** 更新版本号 */
  version: number;
}

/** 感知状态更新（在线状态、光标等） */
export interface AwarenessUpdateMessage extends CollaborationMessage {
  type: 'awareness-update';
  /** 序列化的 awareness states */
  states: string;
}

/** 光标位置更新 */
export interface CursorUpdateMessage extends CollaborationMessage {
  type: 'cursor-update';
  /** 光标位置 */
  position: CursorPosition;
  /** 用户名称 */
  userName: string;
  /** 头像颜色 */
  avatarColor: string;
}

/** 用户加入 */
export interface UserJoinMessage extends CollaborationMessage {
  type: 'user-join';
  user: Collaborator;
}

/** 用户离开 */
export interface UserLeaveMessage extends CollaborationMessage {
  type: 'user-leave';
  userId: string;
}

/** 房间状态 */
export interface RoomStateMessage extends CollaborationMessage {
  type: 'room-state';
  /** 当前参与者列表 */
  participants: Collaborator[];
  /** 文档版本号 */
  version: number;
}

/** 确认消息 */
export interface AckMessage extends CollaborationMessage {
  type: 'ack';
  /** 被确认的消息类型 */
  ackType: CollaborationMessageType;
  /** 被确认的消息时间戳 */
  ackTimestamp: number;
}

/** 心跳 PING */
export interface PingMessage extends CollaborationMessage {
  type: 'ping';
}

/** 心跳 PONG */
export interface PongMessage extends CollaborationMessage {
  type: 'pong';
}

/** 联合消息类型 */
export type CollaborationMessageUnion =
  | SyncRequestMessage
  | SyncResponseMessage
  | SyncUpdateMessage
  | AwarenessUpdateMessage
  | CursorUpdateMessage
  | UserJoinMessage
  | UserLeaveMessage
  | RoomStateMessage
  | AckMessage
  | PingMessage
  | PongMessage;

// ============================
// 连接状态
// ============================

/** WebSocket 连接状态 */
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

/** CollaborationService 配置 */
export interface CollaborationConfig {
  /** WebSocket 服务器 URL */
  wsUrl: string;
  /** 重连间隔（毫秒） */
  reconnectInterval: number;
  /** 最大重连次数 */
  maxReconnectAttempts: number;
  /** 心跳间隔（毫秒） */
  pingInterval: number;
  /** 心跳超时（毫秒） */
  pingTimeout: number;
}

// ============================
// 用户头像颜色预设
// ============================

/** 协作用户头像颜色色板 */
export const COLLABORATOR_COLORS: string[] = [
  '#FF6700', // 伏羲橙
  '#1890FF', // 蓝
  '#52C41A', // 绿
  '#EB2F96', // 粉
  '#722ED1', // 紫
  '#13C2C2', // 青
  '#FA8C16', // 金橙
  '#A0D911', // 黄绿
  '#F5222D', // 红
  '#2F54EB', // 靛蓝
  '#FAAD14', // 金
  '#1EB9B9', // 深青
];
