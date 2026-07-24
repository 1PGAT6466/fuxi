/**
 * 伏羲 v2.1 — 收藏夹/置顶 Pinia Store
 * P2 增强：收藏夹和置顶功能
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';
import type { FavoriteItem, FavoriteType } from './types';
import { FAVORITE_TYPE_LABELS } from './types';
import * as favoritesApi from '@/api/favorites';

const logger = createLogger('FavoritesStore');

export const useFavoritesStore = defineStore('favorites', () => {
  // ══════════════════════════════════════
  // 状态
  // ══════════════════════════════════════

  /** 全部收藏列表 */
  const favorites = ref<FavoriteItem[]>([]);

  /** 置顶收藏列表 */
  const pinned = ref<FavoriteItem[]>([]);

  /** 当前用户 ID（由外部注入或从 auth store 获取） */
  const currentUserId = ref<string>('');

  /** 当前过滤类型 */
  const activeTypeFilter = ref<FavoriteType | null>(null);

  /** 加载状态 */
  const isLoading = ref(false);

  /** 错误信息 */
  const errorMessage = ref<string | null>(null);

  /** 搜索关键词 */
  const searchQuery = ref('');

  // ══════════════════════════════════════
  // 计算属性
  // ══════════════════════════════════════

  /** 收藏总数 */
  const totalCount = computed(() => favorites.value.length);

  /** 置顶数量 */
  const pinnedCount = computed(() => pinned.value.length);

  /** 非置顶收藏 */
  const unpinnedFavorites = computed(() =>
    favorites.value.filter((f) => !f.pinned),
  );

  /** 按类型分组 */
  const groupedByType = computed(() => {
    const groups: Record<string, FavoriteItem[]> = {};
    for (const item of favorites.value) {
      const label = FAVORITE_TYPE_LABELS[item.type] || item.type;
      if (!groups[label]) groups[label] = [];
      groups[label].push(item);
    }
    return groups;
  });

  /** 过滤并搜索后的列表 */
  const filteredFavorites = computed(() => {
    let list = favorites.value;

    // 类型过滤
    if (activeTypeFilter.value) {
      list = list.filter((f) => f.type === activeTypeFilter.value);
    }

    // 关键词搜索
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.title.toLowerCase().includes(q) ||
          f.summary.toLowerCase().includes(q),
      );
    }

    return list;
  });

  /** 是否已收藏指定 itemId（用于快速判断收藏状态） */
  function isFavorited(itemId: string): boolean {
    return favorites.value.some((f) => f.itemId === itemId);
  }

  /** 是否已置顶指定 itemId */
  function isPinned(itemId: string): boolean {
    return pinned.value.some((f) => f.itemId === itemId);
  }

  /** 获取指定 itemId 的收藏项 */
  function getFavoriteByItemId(itemId: string): FavoriteItem | undefined {
    return favorites.value.find((f) => f.itemId === itemId);
  }

  // ══════════════════════════════════════
  // 操作
  // ══════════════════════════════════════

  /** 设置当前用户 */
  function setUser(userId: string): void {
    currentUserId.value = userId;
  }

  // ── 加载收藏列表 ──

  async function loadFavorites(type?: FavoriteType): Promise<void> {
    if (!currentUserId.value) {
      logger.warn('未设置当前用户，跳过加载收藏');
      return;
    }

    isLoading.value = true;
    errorMessage.value = null;

    try {
      const data = await favoritesApi.listFavorites(
        currentUserId.value,
        type,
      );
      favorites.value = data.favorites || [];
      pinned.value = data.pinned || [];
      logger.info(`加载收藏列表: ${favorites.value.length} 条, 置顶 ${pinned.value.length} 条`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载收藏列表失败';
      errorMessage.value = msg;
      logger.error(msg, err);
    } finally {
      isLoading.value = false;
    }
  }

  // ── 添加收藏 ──

  async function addFavorite(
    itemId: string,
    type: FavoriteType,
    meta?: { title?: string; summary?: string; url?: string; icon?: string },
  ): Promise<boolean> {
    if (!currentUserId.value) return false;

    try {
      const result = await favoritesApi.addFavorite({
        userId: currentUserId.value,
        itemId,
        type,
        ...(meta || {}),
      });

      if (result.success && result.favorite) {
        favorites.value.unshift(result.favorite);
        if (result.favorite.pinned) {
          pinned.value.unshift(result.favorite);
        }
        return true;
      }
      return false;
    } catch (err) {
      logger.error('添加收藏失败', err);
      return false;
    }
  }

  // ── 取消收藏 ──

  async function removeFavorite(itemId: string): Promise<boolean> {
    if (!currentUserId.value) return false;

    try {
      const result = await favoritesApi.removeFavorite(
        currentUserId.value,
        itemId,
      );

      if (result.success) {
        favorites.value = favorites.value.filter((f) => f.itemId !== itemId);
        pinned.value = pinned.value.filter((f) => f.itemId !== itemId);
        return true;
      }
      return false;
    } catch (err) {
      logger.error('取消收藏失败', err);
      return false;
    }
  }

  // ── 切换置顶 ──

  async function togglePin(itemId: string): Promise<boolean> {
    if (!currentUserId.value) return false;

    try {
      const result = await favoritesApi.togglePin({
        userId: currentUserId.value,
        itemId,
      });

      if (result.success && result.favorite) {
        // 更新本地列表
        const idx = favorites.value.findIndex((f) => f.itemId === itemId);
        if (idx > -1) {
          favorites.value[idx] = result.favorite;
        }

        if (result.favorite.pinned) {
          // 添加到置顶列表
          if (!pinned.value.some((f) => f.itemId === itemId)) {
            pinned.value.unshift(result.favorite);
          }
        } else {
          // 从置顶列表移除
          pinned.value = pinned.value.filter((f) => f.itemId !== itemId);
        }
        return true;
      }
      return false;
    } catch (err) {
      logger.error('切换置顶失败', err);
      return false;
    }
  }

  // ── 更新收藏信息 ──

  async function updateFavorite(
    itemId: string,
    updates: { title?: string; summary?: string },
  ): Promise<boolean> {
    try {
      const result = await favoritesApi.updateFavorite(itemId, updates);
      if (result.success && result.favorite) {
        const idx = favorites.value.findIndex((f) => f.itemId === itemId);
        if (idx > -1) {
          favorites.value[idx] = { ...favorites.value[idx], ...result.favorite };
        }
        const pinIdx = pinned.value.findIndex((f) => f.itemId === itemId);
        if (pinIdx > -1) {
          pinned.value[pinIdx] = { ...pinned.value[pinIdx], ...result.favorite };
        }
        return true;
      }
      return false;
    } catch (err) {
      logger.error('更新收藏失败', err);
      return false;
    }
  }

  // ── 过滤与搜索 ──

  function setTypeFilter(type: FavoriteType | null): void {
    activeTypeFilter.value = type;
  }

  function setSearchQuery(query: string): void {
    searchQuery.value = query;
  }

  // ── 初始化 ──

  async function init(userId?: string): Promise<void> {
    if (userId) {
      setUser(userId);
    }
    if (currentUserId.value) {
      await loadFavorites();
    }
  }

  return {
    // state
    favorites,
    pinned,
    currentUserId,
    activeTypeFilter,
    isLoading,
    errorMessage,
    searchQuery,
    // computed
    totalCount,
    pinnedCount,
    unpinnedFavorites,
    groupedByType,
    filteredFavorites,
    isFavorited,
    isPinned,
    getFavoriteByItemId,
    // actions
    setUser,
    loadFavorites,
    addFavorite,
    removeFavorite,
    togglePin,
    updateFavorite,
    setTypeFilter,
    setSearchQuery,
    init,
  };
});
