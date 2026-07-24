/**
 * 伏羲 v2.1 — 收藏夹 Composable
 * P2 增强：收藏夹/置顶功能
 *
 * 提供在任意组件中集成收藏/置顶能力的便捷 hook。
 * 使用 Vue3 Composition API，无需手动管理 store 实例。
 */

import { computed, onMounted, ref } from 'vue';
import { useFavoritesStore } from '@/services/favorites/store';
import type { FavoriteType } from '@/services/favorites/types';

/**
 * 收藏夹组合函数
 *
 * 用法：
 * ```ts
 * const { isFavorite, toggleFavorite, isPinned, togglePin } = useFavorites();
 * ```
 *
 * @param options.currentUserId - 当前用户 ID（可选，不传则从 store 获取）
 */
export function useFavorites(options?: { currentUserId?: string }) {
  const store = useFavoritesStore();
  const isReady = ref(false);

  // ══════════════════════════════════
  // 初始化
  // ══════════════════════════════════

  onMounted(async () => {
    if (options?.currentUserId) {
      store.setUser(options.currentUserId);
    }
    if (store.currentUserId) {
      await store.loadFavorites();
    }
    isReady.value = true;
  });

  // ══════════════════════════════════
  // 快捷判断
  // ══════════════════════════════════

  /**
   * 判断指定 itemId 是否已收藏
   */
  function isFavorite(itemId: string): boolean {
    return store.isFavorited(itemId);
  }

  /**
   * 判断指定 itemId 是否已置顶
   */
  function isPinned(itemId: string): boolean {
    return store.isPinned(itemId);
  }

  /** 收藏总数 */
  const favoriteCount = computed(() => store.totalCount);

  /** 置顶数量 */
  const pinnedCount = computed(() => store.pinnedCount);

  // ══════════════════════════════════
  // 操作
  // ══════════════════════════════════

  /**
   * 切换收藏状态
   *
   * @param itemId - 实体 ID
   * @param type - 收藏类型
   * @param meta - 可选的标题/摘要等
   * @returns 操作后的收藏状态（true = 已收藏，false = 已取消）
   */
  async function toggleFavorite(
    itemId: string,
    type: FavoriteType,
    meta?: { title?: string; summary?: string; url?: string },
  ): Promise<boolean> {
    if (store.isFavorited(itemId)) {
      const success = await store.removeFavorite(itemId);
      return !success; // 取消成功 → false
    } else {
      const success = await store.addFavorite(itemId, type, meta);
      return success; // 添加成功 → true
    }
  }

  /**
   * 切换置顶状态
   *
   * @param itemId - 实体 ID
   * @returns 操作后的置顶状态（true = 已置顶，false = 已取消置顶）
   */
  async function togglePin(itemId: string): Promise<boolean> {
    const success = await store.togglePin(itemId);
    if (success) {
      return store.isPinned(itemId);
    }
    return store.isPinned(itemId);
  }

  /**
   * 添加收藏（不做切换）
   */
  async function addFavorite(
    itemId: string,
    type: FavoriteType,
    meta?: { title?: string; summary?: string; url?: string },
  ): Promise<boolean> {
    return store.addFavorite(itemId, type, meta);
  }

  /**
   * 取消收藏（不做切换）
   */
  async function removeFavorite(itemId: string): Promise<boolean> {
    return store.removeFavorite(itemId);
  }

  // ══════════════════════════════════
  // 返回
  // ══════════════════════════════════

  return {
    // state
    store,
    isReady,
    // computed
    favoriteCount,
    pinnedCount,
    // check
    isFavorite,
    isPinned,
    // actions
    toggleFavorite,
    togglePin,
    addFavorite,
    removeFavorite,
  };
}
