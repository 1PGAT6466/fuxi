/**
 * 伏羲 v2.1 — 收藏夹/置顶 类型定义
 * P2 增强：收藏夹和置顶功能
 */

// ═══════════════════════════════════════════
// 收藏项类型枚举
// ═══════════════════════════════════════════

/** 可收藏的实体类型 */
export type FavoriteType = 'conversation' | 'document' | 'knowledge_base';

/** 所有可收藏类型标签映射 */
export const FAVORITE_TYPE_LABELS: Record<FavoriteType, string> = {
  conversation: '对话',
  document: '文档',
  knowledge_base: '知识库',
};

// ═══════════════════════════════════════════
// 收藏项
// ═══════════════════════════════════════════

/** 收藏项 */
export interface FavoriteItem {
  /** 收藏记录唯一 ID */
  id: string;
  /** 用户 ID */
  userId: string;
  /** 被收藏实体 ID */
  itemId: string;
  /** 收藏类型 */
  type: FavoriteType;
  /** 显示标题 */
  title: string;
  /** 摘要/描述 */
  summary: string;
  /** 是否置顶 */
  pinned: boolean;
  /** 置顶时间（ISO 字符串） */
  pinnedAt?: string;
  /** 收藏时间（ISO 字符串） */
  createdAt: string;
  /** 更新时间（ISO 字符串） */
  updatedAt: string;
  /** 跳转链接（可选） */
  url?: string;
  /** 图标（可选） */
  icon?: string;
  /** 扩展元数据 */
  metadata?: Record<string, unknown>;
}

// ═══════════════════════════════════════════
// API 请求/响应
// ═══════════════════════════════════════════

/** 添加收藏请求 */
export interface AddFavoriteRequest {
  userId: string;
  itemId: string;
  type: FavoriteType;
  title?: string;
  summary?: string;
  url?: string;
  icon?: string;
  metadata?: Record<string, unknown>;
}

/** 切换置顶请求 */
export interface TogglePinRequest {
  userId: string;
  itemId: string;
}

/** 收藏列表响应 */
export interface FavoriteListResponse {
  favorites: FavoriteItem[];
  pinned: FavoriteItem[];
  total: number;
}

/** 操作结果 */
export interface FavoriteActionResult {
  success: boolean;
  favorite?: FavoriteItem;
  message?: string;
}

// ═══════════════════════════════════════════
// 事件类型（用于 ServiceEventBus）
// ═══════════════════════════════════════════

/** 收藏变更事件 */
export interface FavoriteChangedEvent {
  action: 'added' | 'removed' | 'pinned' | 'unpinned';
  item: FavoriteItem;
}
