/**
 * 伏羲 v2.1 — 联邦搜索类型定义
 *
 * 定义联邦搜索（Federated Search）的完整类型体系：
 * - 搜索源（SearchSource）
 * - 搜索请求/响应
 * - 聚合结果与去重
 * - 权限过滤
 */

// ============================
// 枚举类型
// ============================

/** 搜索源类型 */
export type SearchSourceType = 'local_kb' | 'external_api' | 'database' | 'wiki' | 'chat' | 'file';

/** 搜索源状态 */
export type SearchSourceStatus = 'online' | 'offline' | 'degraded' | 'maintenance';

/** 搜索结果分类（前端展示用） */
export type ResultCategory = 'document' | 'wiki' | 'chat' | 'tool' | 'file' | 'database' | 'external';

/** 来源健康状态 */
export type SourceHealth = 'healthy' | 'warning' | 'error' | 'offline';

// ============================
// 搜索源定义
// ============================

/** 单个搜索源 */
export interface SearchSource {
  /** 来源唯一标识 */
  id: string;
  /** 来源名称 */
  name: string;
  /** 来源类型 */
  type: SearchSourceType;
  /** 图标 (emoji 或 icon 名称) */
  icon: string;
  /** 来源描述 */
  description: string;
  /** 是否启用 */
  enabled: boolean;
  /** 当前状态 */
  status: SearchSourceStatus;
  /** 权重（用于排序优先级，值越大越靠前） */
  weight: number;
  /** 超时时间 (ms) */
  timeout: number;
  /** 该源可搜索的条件（权限过滤器） */
  requiredPermissions?: string[];
  /** 结果数量上限 */
  resultLimit: number;
  /** 最后检测时间 */
  lastHealthCheck?: number;
  /** 平均响应时间 (ms) */
  avgResponseTime?: number;
  /** 来源标签 */
  tags?: string[];
}

/** 获取搜索源列表响应 */
export interface SearchSourcesResponse {
  sources: SearchSource[];
  /** 活跃源数量 */
  activeCount: number;
  /** 离线源数量 */
  offlineCount: number;
}

// ============================
// 搜索结果
// ============================

/** 联邦搜索结果项 */
export interface FederatedSearchResult {
  /** 全局唯一 ID（用于去重） */
  id: string;
  /** 标题 */
  title: string;
  /** 内容摘要 */
  snippet: string;
  /** 完整内容（可选） */
  content?: string;
  /** 来源搜索源 ID */
  sourceId: string;
  /** 来源搜索源名称 */
  sourceName: string;
  /** 来源类型 */
  sourceType: SearchSourceType;
  /** 来源图标 */
  sourceIcon: string;
  /** 相关性得分 0-1 */
  score: number;
  /** 结果 URL（可导航） */
  url?: string;
  /** 结果分类 */
  category: ResultCategory;
  /** 时间戳 */
  timestamp?: number;
  /** 附加元数据 */
  metadata?: Record<string, unknown>;
  /** 内容指纹（用于去重） */
  fingerprint: string;
  /** 该结果的访问权限 */
  accessLevel?: 'public' | 'internal' | 'restricted' | 'admin';
  /** 高亮片段 */
  highlights?: string[];
  /** 标签 */
  tags?: string[];
  /** 文件类型（文件结果时） */
  fileType?: string;
  /** 文件大小 */
  fileSize?: number;
}

// ============================
// 搜索请求/响应
// ============================

/** 联邦搜索请求 */
export interface FederatedSearchRequest {
  /** 搜索查询 */
  query: string;
  /** 指定搜索源 ID 列表（空=所有可用源） */
  sourceIds?: string[];
  /** 指定搜索源类型过滤 */
  sourceTypes?: SearchSourceType[];
  /** 返回结果数量上限 */
  limit?: number;
  /** 最低相关性阈值 0-1 */
  minScore?: number;
  /** 是否启用去重 */
  deduplicate?: boolean;
  /** 去重相似度阈值 0-1 */
  deduplicateThreshold?: number;
  /** 分类过滤 */
  categories?: ResultCategory[];
  /** 排序方式 */
  sortBy?: 'relevance' | 'date' | 'source';
  /** 排序方向 */
  sortOrder?: 'asc' | 'desc';
  /** 分页偏移 */
  offset?: number;
}

/** 来源级别统计 */
export interface SourceStats {
  sourceId: string;
  sourceName: string;
  sourceIcon: string;
  resultCount: number;
  responseTimeMs: number;
  status: 'success' | 'timeout' | 'error' | 'filtered';
  error?: string;
}

/** 联邦搜索响应 */
export interface FederatedSearchResponse {
  /** 原始查询 */
  query: string;
  /** 聚合去重后的结果 */
  results: FederatedSearchResult[];
  /** 去重前总数 */
  rawTotal: number;
  /** 去重后总数 */
  total: number;
  /** 总耗时 ms */
  tookMs: number;
  /** 各源统计 */
  sourceStats: SourceStats[];
  /** 分类统计 */
  categoryCounts: Record<ResultCategory, number>;
  /** 是否已截断 */
  truncated: boolean;
  /** 查询建议 */
  suggestions?: string[];
}

// ============================
// 前端聚合状态
// ============================

/** 快速筛选器 */
export interface ResultFilter {
  /** 筛选器类型 */
  type: 'source' | 'category' | 'score' | 'date';
  /** 筛选值 */
  value: string | number;
  /** 筛选标签 */
  label: string;
  /** 是否激活 */
  active: boolean;
  /** 匹配结果数 */
  count?: number;
}

/** 搜索建议 */
export interface SearchSuggestion {
  text: string;
  type: 'history' | 'popular' | 'related' | 'auto';
  score?: number;
}
