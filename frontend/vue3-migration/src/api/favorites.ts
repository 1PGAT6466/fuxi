/**
 * 伏羲 v2.1 — 收藏夹/置顶 API 封装
 * P2 增强：收藏夹和置顶功能
 */
import apiClient from './index';
import { createLogger } from '@/utils/logger';
import type {
  AddFavoriteRequest,
  FavoriteItem,
  FavoriteListResponse,
  FavoriteActionResult,
  TogglePinRequest,
} from '@/services/favorites/types';

const logger = createLogger('FavoritesAPI');

// ═══════════════════════════════════════════
// 收藏 CRUD
// ═══════════════════════════════════════════

/** 添加收藏 */
export async function addFavorite(
  data: AddFavoriteRequest,
): Promise<FavoriteActionResult> {
  const res = (await apiClient.post('/api/favorites', data)) as FavoriteActionResult;
  return res;
}

/** 取消收藏 */
export async function removeFavorite(
  userId: string,
  itemId: string,
): Promise<FavoriteActionResult> {
  const res = (await apiClient.delete(`/api/favorites/${encodeURIComponent(itemId)}`, {
    params: { userId },
  })) as FavoriteActionResult;
  return res;
}

/** 获取收藏列表 */
export async function listFavorites(
  userId: string,
  type?: string,
): Promise<FavoriteListResponse> {
  const res = (await apiClient.get('/api/favorites', {
    params: { userId, type },
  })) as FavoriteListResponse;
  return res;
}

/** 切换置顶 */
export async function togglePin(
  data: TogglePinRequest,
): Promise<FavoriteActionResult> {
  const res = (await apiClient.put('/api/favorites/toggle-pin', data)) as FavoriteActionResult;
  return res;
}

/** 更新收藏标题/摘要 */
export async function updateFavorite(
  itemId: string,
  updates: { title?: string; summary?: string },
): Promise<FavoriteActionResult> {
  const res = (await apiClient.patch(`/api/favorites/${encodeURIComponent(itemId)}`, updates)) as FavoriteActionResult;
  return res;
}
