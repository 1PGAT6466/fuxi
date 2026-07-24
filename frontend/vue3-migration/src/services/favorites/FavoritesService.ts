/**
 * 伏羲 v2.1 — 收藏夹服务
 * P2 增强：收藏夹和置顶功能
 *
 * 提供业务逻辑封装，作为 API 层和 Store 之间的中间层。
 * 该类也作为外部集成的统一入口。
 */

import { createLogger } from '@/utils/logger';
import type {
  FavoriteItem,
  FavoriteType,
  AddFavoriteRequest,
  FavoriteActionResult,
  FavoriteListResponse,
} from './types';
import * as favoritesApi from '@/api/favorites';

const logger = createLogger('FavoritesService');

/**
 * 收藏夹服务类（单例模式）
 *
 * 职责：
 * - 封装收藏添加/移除/列表操作
 * - 封装置顶切换逻辑
 * - 本地乐观更新 + 服务端同步
 * - 提供事件回调钩子
 */
class FavoritesService {
  /** 变更监听器 */
  private listeners: Array<(event: { action: string; item: FavoriteItem }) => void> = [];

  // ═══════════════════════════════════════════
  // 收藏操作
  // ═══════════════════════════════════════════

  /**
   * 添加收藏
   *
   * @param userId - 用户 ID
   * @param itemId - 要收藏的实体 ID
   * @param type - 收藏类型
   * @param meta - 可选的标题、摘要等元数据
   */
  async addFavorite(
    userId: string,
    itemId: string,
    type: FavoriteType,
    meta?: { title?: string; summary?: string; url?: string; icon?: string },
  ): Promise<FavoriteActionResult> {
    try {
      const request: AddFavoriteRequest = {
        userId,
        itemId,
        type,
        ...(meta || {}),
      };
      const result = await favoritesApi.addFavorite(request);
      logger.info(`收藏添加成功: ${type}:${itemId}`);
      if (result.favorite) {
        this.notifyListeners('added', result.favorite);
      }
      return result;
    } catch (err) {
      logger.error('添加收藏失败', err);
      return { success: false, message: '添加收藏失败' };
    }
  }

  /**
   * 取消收藏
   *
   * @param userId - 用户 ID
   * @param itemId - 实体 ID
   */
  async removeFavorite(userId: string, itemId: string): Promise<FavoriteActionResult> {
    try {
      const result = await favoritesApi.removeFavorite(userId, itemId);
      logger.info(`收藏已移除: ${itemId}`);
      if (result.favorite) {
        this.notifyListeners('removed', result.favorite);
      }
      return result;
    } catch (err) {
      logger.error('取消收藏失败', err);
      return { success: false, message: '取消收藏失败' };
    }
  }

  /**
   * 列出收藏
   *
   * @param userId - 用户 ID
   * @param type - 可选的类型过滤
   */
  async listFavorites(
    userId: string,
    type?: FavoriteType,
  ): Promise<FavoriteListResponse> {
    try {
      const result = await favoritesApi.listFavorites(userId, type);
      logger.info(`获取收藏列表: ${result.total} 条`);
      return result;
    } catch (err) {
      logger.error('获取收藏列表失败', err);
      return { favorites: [], pinned: [], total: 0 };
    }
  }

  // ═══════════════════════════════════════════
  // 置顶操作
  // ═══════════════════════════════════════════

  /**
   * 切换置顶状态
   *
   * @param userId - 用户 ID
   * @param itemId - 实体 ID
   */
  async togglePin(userId: string, itemId: string): Promise<FavoriteActionResult> {
    try {
      const result = await favoritesApi.togglePin({ userId, itemId });
      logger.info(`置顶状态切换: ${itemId}`);
      if (result.favorite) {
        const action = result.favorite.pinned ? 'pinned' : 'unpinned';
        this.notifyListeners(action, result.favorite);
      }
      return result;
    } catch (err) {
      logger.error('切换置顶失败', err);
      return { success: false, message: '切换置顶失败' };
    }
  }

  // ═══════════════════════════════════════════
  // 事件监听
  // ═══════════════════════════════════════════

  /**
   * 注册变更监听器
   *
   * @param listener - 事件处理函数
   * @returns 取消订阅的函数
   */
  onChange(listener: (event: { action: string; item: FavoriteItem }) => void): () => void {
    this.listeners.push(listener);
    return () => {
      const idx = this.listeners.indexOf(listener);
      if (idx > -1) this.listeners.splice(idx, 1);
    };
  }

  private notifyListeners(action: string, item: FavoriteItem): void {
    for (const listener of this.listeners) {
      try {
        listener({ action, item });
      } catch (err) {
        logger.error('Listener 执行异常', err);
      }
    }
  }
}

// ═══════════════════════════════════════════
// 单例导出
// ═══════════════════════════════════════════

export const favoritesService = new FavoritesService();
export default favoritesService;
