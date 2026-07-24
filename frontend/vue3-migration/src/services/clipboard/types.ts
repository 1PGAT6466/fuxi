/**
 * 伏羲 v2.1 — 跨窗口剪贴板 类型定义
 *
 * 定义剪贴板内容结构、同步协议、面板配置等核心类型。
 */

// ═══════════════════════════════════════════
// 剪贴板内容类型枚举
// ═══════════════════════════════════════════

/** 剪贴板内容格式 */
export type ClipboardContentFormat = 'text' | 'html' | 'json' | 'image-ref' | 'file-ref';

/** 剪贴板数据 MIME 映射 */
export const CLIPBOARD_MIME_MAP: Record<ClipboardContentFormat, string> = {
  'text': 'text/plain',
  'html': 'text/html',
  'json': 'application/json',
  'image-ref': 'application/x-fuxi-image-ref',
  'file-ref': 'application/x-fuxi-file-ref',
};

// ═══════════════════════════════════════════
// 剪贴板条目
// ═══════════════════════════════════════════

/** 单个剪贴板条目 */
export interface ClipboardEntry {
  /** 条目唯一 ID */
  id: string;
  /** 内容格式 */
  format: ClipboardContentFormat;
  /** 原始文本内容（所有格式都保留原文以便搜索/预览） */
  plainText: string;
  /** 格式化后的内容（html/json 等格式下存储格式化版本） */
  formattedContent?: string;
  /** 文件/图片引用的路径 */
  referencePath?: string;
  /** 来源窗口 ID（跨窗口同步时标识来源） */
  sourceWindowId?: string;
  /** 来源应用/服务名 */
  sourceService?: string;
  /** 是否已收藏（固定到顶部） */
  isFavorite: boolean;
  /** 创建时间（ISO 字符串） */
  createdAt: string;
  /** 文件大小（字节，可选） */
  size?: number;
  /** 额外元数据 */
  metadata?: Record<string, unknown>;
}

// ═══════════════════════════════════════════
// 剪贴板同步协议
// ═══════════════════════════════════════════

/** 剪贴板同步请求 */
export interface ClipboardSyncRequest {
  /** 发起同步的窗口 ID */
  windowId: string;
  /** 发起同步的服务名 */
  serviceName?: string;
  /** 要同步的剪贴板条目 */
  entry: Omit<ClipboardEntry, 'id' | 'createdAt' | 'isFavorite'>;
}

/** 剪贴板同步响应 */
export interface ClipboardSyncResponse {
  success: boolean;
  /** 同步后的服务端条目 ID */
  entryId?: string;
  /** 当前剪贴板历史总数 */
  totalCount?: number;
  message?: string;
}

// ═══════════════════════════════════════════
// 剪贴板历史查询
// ═══════════════════════════════════════════

/** 剪贴板历史查询参数 */
export interface ClipboardHistoryQuery {
  /** 每页数量 */
  limit?: number;
  /** 偏移量 */
  offset?: number;
  /** 格式过滤 */
  format?: ClipboardContentFormat;
  /** 仅收藏项 */
  favoritesOnly?: boolean;
  /** 搜索关键词 */
  search?: string;
}

/** 剪贴板历史查询响应 */
export interface ClipboardHistoryResponse {
  entries: ClipboardEntry[];
  total: number;
  /** 当前缓存条目数 */
  cached: number;
}

/** 批量操作请求 */
export interface ClipboardBatchRequest {
  /** 要操作的条目 ID 列表 */
  entryIds: string[];
}

/** 批量操作响应 */
export interface ClipboardBatchResponse {
  success: boolean;
  affectedCount: number;
  message?: string;
}

// ═══════════════════════════════════════════
// 剪贴板配置
// ═══════════════════════════════════════════

/** 剪贴板面板配置 */
export interface ClipboardPanelConfig {
  /** 最大历史条目数 */
  maxHistorySize: number;
  /** 条目过期时间（秒），0 = 不过期 */
  expirySeconds: number;
  /** 是否启用跨窗口同步 */
  enableCrossWindowSync: boolean;
  /** 是否自动收藏常用内容 */
  enableAutoFavorite: boolean;
  /** 面板快捷键 */
  shortcutKey: string;
}

/** 默认剪贴板面板配置 */
export const DEFAULT_CLIPBOARD_CONFIG: ClipboardPanelConfig = {
  maxHistorySize: 100,
  expirySeconds: 86400, // 24h
  enableCrossWindowSync: true,
  enableAutoFavorite: false,
  shortcutKey: 'shift+v',
};

// ═══════════════════════════════════════════
// 剪贴板事件
// ═══════════════════════════════════════════

/** 剪贴板变更事件 */
export interface ClipboardChangedEvent {
  action: 'copied' | 'pasted' | 'removed' | 'favorited' | 'unfavorited' | 'synced' | 'cleared';
  entry?: ClipboardEntry;
  /** 批量操作时的条目列表 */
  entries?: ClipboardEntry[];
  /** 同步来源窗口 */
  sourceWindowId?: string;
}

// ═══════════════════════════════════════════
// 格式转换工具类型
// ═══════════════════════════════════════════

/** 格式转换器接口 */
export interface FormatConverter {
  /** 输入格式 */
  from: ClipboardContentFormat;
  /** 输出格式 */
  to: ClipboardContentFormat;
  /** 转换函数 */
  convert: (content: string, options?: Record<string, unknown>) => string;
  /** 转换器优先级（数值越小越优先） */
  priority: number;
}
