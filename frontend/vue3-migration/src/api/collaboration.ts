/**
 * 伏羲 v2.1 — 实时协作 API 层
 *
 * 提供协作房间的 RESTful API 操作。
 * WebSocket 连接由 CollaborationService 管理。
 */

import apiClient from '@/api';
import type {
  CollaborationRoom,
  Collaborator,
} from './types';

// ============================
// 协作房间 API
// ============================

/**
 * 获取协作房间列表
 */
export async function listRooms(): Promise<CollaborationRoom[]> {
  const data = await apiClient.get('/api/collaboration/rooms') as CollaborationRoom[];
  return data;
}

/**
 * 创建协作房间
 */
export async function createRoom(name: string, documentId: string): Promise<CollaborationRoom> {
  const data = await apiClient.post('/api/collaboration/rooms', {
    name,
    documentId,
  }) as CollaborationRoom;
  return data;
}

/**
 * 获取房间详情
 */
export async function getRoom(roomId: string): Promise<CollaborationRoom> {
  const data = await apiClient.get(`/api/collaboration/rooms/${roomId}`) as CollaborationRoom;
  return data;
}

/**
 * 删除协作房间
 */
export async function deleteRoom(roomId: string): Promise<void> {
  await apiClient.delete(`/api/collaboration/rooms/${roomId}`);
}

/**
 * 获取房间参与者列表
 */
export async function getRoomParticipants(roomId: string): Promise<Collaborator[]> {
  const data = await apiClient.get(`/api/collaboration/rooms/${roomId}/participants`) as Collaborator[];
  return data;
}

/**
 * 获取文档编辑历史
 */
export async function getDocumentHistory(
  documentId: string,
  params?: { limit?: number; before?: number },
): Promise<{ operations: Array<{
  id: string;
  userId: string;
  userName: string;
  type: string;
  timestamp: number;
  summary: string;
}> }> {
  const data = await apiClient.get('/api/collaboration/history', {
    params: { documentId, ...params },
  }) as unknown;
  return data as {
    operations: Array<{
      id: string;
      userId: string;
      userName: string;
      type: string;
      timestamp: number;
      summary: string;
    }>;
  };
}
