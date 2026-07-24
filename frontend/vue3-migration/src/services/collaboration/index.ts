/**
 * 伏羲 v2.1 — 实时协作服务入口
 *
 * 统一导出所有公开接口：
 * - Yjs CRDT 协作引擎
 * - WebSocket 连接管理
 * - 协作用户列表/光标/编辑历史
 * - 后端 WebSocket 模拟层（开发/测试用）
 * - Pinia Store
 */

// 类型
export type {
  CollaborationRoom,
  Collaborator,
  CursorPosition,
  EditOperationType,
  EditOperation,
  CollaborationMessageType,
  CollaborationMessage,
  CollaborationMessageUnion,
  SyncRequestMessage,
  SyncResponseMessage,
  SyncUpdateMessage,
  AwarenessUpdateMessage,
  CursorUpdateMessage,
  UserJoinMessage,
  UserLeaveMessage,
  RoomStateMessage,
  AckMessage,
  PingMessage,
  PongMessage,
  ConnectionStatus,
  CollaborationConfig,
} from './types';

export { COLLABORATOR_COLORS } from './types';

// 服务类
export {
  CollaborationService,
  getCollaborationService,
  removeCollaborationService,
  removeAllCollaborationServices,
  default as DefaultCollabService,
} from './CollaborationService';

export type { CollaborationEventHandlers } from './CollaborationService';

// Pinia Store
export { useCollaborationStore } from './store';

// 组件
export { default as CollaborationPanel } from './CollaborationPanel.vue';

// 模拟服务器（开发/测试）
export {
  createMockWSServer,
  enableMockMode,
  disableMockMode,
} from './CollaborationServerMock';
