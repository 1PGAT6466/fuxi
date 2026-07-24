/**
 * 伏羲 v2.1 — 收藏夹服务 API（Service 层封装）
 * P2 增强：收藏夹和置顶功能
 *
 * 这也是 api/ 层 favorites.ts 的薄封装，供 service 内部使用。
 * 外部组件应直接使用 @/api/favorites。
 */

export {
  addFavorite,
  removeFavorite,
  listFavorites,
  togglePin,
  updateFavorite,
} from '@/api/favorites';
