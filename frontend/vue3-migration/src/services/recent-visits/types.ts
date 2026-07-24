/**
 * 伏羲 v2.1 — 最近访问 / 历史记录类型定义
 * P2 增强：访问追踪 & 历史记录
 */

// ═══════════════════════════════════════════
// 访问记录类型
// ═══════════════════════════════════════════

/** 访问目标的资源类型 */
export type VisitItemType = 'chat' | 'document' | 'knowledge_base';

/** 访问类型的中文标签映射 */
export const VISIT_TYPE_LABELS: Record<VisitItemType, string> = {
  chat: '对话',
  document: '文档',
  knowledge_base: '知识库',
};

/** 访问类型的图标映射（Element Plus icon 名称） */
export const VISIT_TYPE_ICONS: Record<VisitItemType, string> = {
  chat: 'ChatDotRound',
  document: 'Document',
  knowledge_base: 'Collection',
};

/** 访问类型的颜色映射 */
export const VISIT_TYPE_COLORS: Record<VisitItemType, string> = {
  chat: '#FF6700',
  document: '#4a7c59',
  knowledge_base: '#3a6b8c',
};

/** 单条访问记录 */
export interface VisitRecord {
  /** 记录唯一标识 */
  id: string;
  /** 用户 ID */
  userId: string | number;
  /** 被访问的资源 ID */
  itemId: string;
  /** 资源类型 */
  type: VisitItemType;
  /** 资源名称/标题（用于展示） */
  title: string;
  /** 资源描述/摘要 */
  description?: string;
  /** 跳转路由路径 */
  route?: string;
  /** 访问时间戳 (ISO 8601) */
  visitedAt: string;
  /** 访问次数（同一 item 的重复访问累加） */
  visitCount?: number;
}

// ═══════════════════════════════════════════
// API 请求/响应类型
// ═══════════════════════════════════════════

/** 记录访问请求 */
export interface RecordVisitRequest {
  userId: string | number;
  itemId: string;
  type: VisitItemType;
  title: string;
  description?: string;
  route?: string;
}

/** 获取最近访问请求参数 */
export interface GetRecentVisitsParams {
  userId: string | number;
  limit?: number;
  type?: VisitItemType;
}

/** 删除历史请求 */
export interface DeleteHistoryParams {
  userId: string | number;
}

/** 删除单条历史请求 */
export interface DeleteSingleHistoryParams {
  userId: string | number;
  id: string;
}

// ═══════════════════════════════════════════
// 筛选器
// ═══════════════════════════════════════════

/** 类型筛选项 */
export interface TypeFilterOption {
  label: string;
  value: VisitItemType | 'all';
  icon: string;
  color: string;
}

/** 全部类型筛选项 */
export const ALL_TYPE_FILTER: TypeFilterOption = {
  label: '全部',
  value: 'all',
  icon: 'Grid',
  color: '#999999',
};

/** 默认类型筛选项列表 */
export const TYPE_FILTER_OPTIONS: TypeFilterOption[] = [
  ALL_TYPE_FILTER,
  {
    label: '对话',
    value: 'chat',
    icon: VISIT_TYPE_ICONS.chat,
    color: VISIT_TYPE_COLORS.chat,
  },
  {
    label: '文档',
    value: 'document',
    icon: VISIT_TYPE_ICONS.document,
    color: VISIT_TYPE_COLORS.document,
  },
  {
    label: '知识库',
    value: 'knowledge_base',
    icon: VISIT_TYPE_ICONS.knowledge_base,
    color: VISIT_TYPE_COLORS.knowledge_base,
  },
];
