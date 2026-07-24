/**
 * 伏羲 v2.1 — 收藏夹服务入口
 * P2 增强：收藏夹/置顶功能
 *
 * 统一导出所有公开接口
 */

// 类型
export type {
  FavoriteItem,
  FavoriteType,
  AddFavoriteRequest,
  TogglePinRequest,
  FavoriteListResponse,
  FavoriteActionResult,
  FavoriteChangedEvent,
} from './types';

export { FAVORITE_TYPE_LABELS } from './types';

// 服务类
export { favoritesService, default as FavoritesService } from './FavoritesService';

// Pinia Store
export { useFavoritesStore } from './store';

// 组件
export { default as FavoritesPanel } from './FavoritesPanel.vue';
