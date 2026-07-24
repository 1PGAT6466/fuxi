/**
 * 伏羲 v2.1 — 服务市场类型定义
 */

// ───── 服务分类 ─────

export type MarketServiceCategory =
  | 'ai'
  | 'productivity'
  | 'engineering'
  | 'analytics'
  | 'media'
  | 'data'
  | 'devops'
  | 'other';

export const MARKET_CATEGORY_LABELS: Record<MarketServiceCategory, string> = {
  ai: 'AI 智能',
  productivity: '效率工具',
  engineering: '工程绘图',
  analytics: '数据分析',
  media: '媒体处理',
  data: '数据管理',
  devops: 'DevOps',
  other: '其他',
};

// ───── 排序方式 ─────

export type SortField = 'name' | 'rating' | 'downloads' | 'updatedAt' | 'installedAt';

export interface SortOption {
  field: SortField;
  label: string;
  direction: 'asc' | 'desc';
}

// ───── 服务条目 ─────

/** 服务截图 */
export interface ServiceScreenshot {
  url: string;
  alt?: string;
}

/** 用户评价 */
export interface ServiceReview {
  id: string;
  userId: string;
  userName: string;
  avatar?: string;
  rating: number; // 1-5
  content: string;
  createdAt: string;
}

/** 服务版本信息 */
export interface ServiceVersion {
  version: string;
  releaseDate: string;
  changelog: string;
  downloadSize: string; // e.g. "2.3 MB"
  minAppVersion: string;
}

/** 市场服务条目 */
export interface MarketService {
  id: string;
  name: string;
  icon: string;
  description: string;
  longDescription?: string;
  category: MarketServiceCategory;
  version: string;
  author: string;
  authorUrl?: string;
  homepage?: string;
  tags: string[];
  rating: number; // 1-5 平均分
  reviewCount: number;
  downloads: number;
  screenshots: ServiceScreenshot[];
  reviews: ServiceReview[];
  versions: ServiceVersion[];
  price: 'free' | 'paid';
  updatedAt: string;
  createdAt: string;
  /** 标记该服务是否被当前用户安装 */
  installed?: boolean;
  installedVersion?: string;
  installedAt?: string;
}

// ───── API 请求/响应类型 ─────

/** 获取服务列表请求参数 */
export interface MarketServiceListParams {
  category?: MarketServiceCategory;
  search?: string;
  sortField?: SortField;
  sortDirection?: 'asc' | 'desc';
  page?: number;
  pageSize?: number;
}

/** 获取服务列表响应 */
export interface MarketServiceListResponse {
  items: MarketService[];
  total: number;
  page: number;
  pageSize: number;
}

/** 安装服务请求 */
export interface InstallServiceRequest {
  serviceId: string;
  version?: string; // 不传则安装最新版本
}

/** 安装服务响应 */
export interface InstallServiceResponse {
  success: boolean;
  serviceId: string;
  installedVersion: string;
  installedAt: string;
  message?: string;
}

/** 卸载服务请求 */
export interface UninstallServiceRequest {
  serviceId: string;
}

/** 卸载服务响应 */
export interface UninstallServiceResponse {
  success: boolean;
  serviceId: string;
  message?: string;
}

/** 已安装服务项 */
export interface InstalledService {
  id: string;
  serviceId: string;
  name: string;
  icon: string;
  version: string;
  installedAt: string;
  hasUpdate: boolean;
  latestVersion?: string;
}

/** 版本列表响应 */
export interface ServiceVersionsResponse {
  serviceId: string;
  versions: ServiceVersion[];
}

// ───── 组件内部状态类型 ─────

export type DetailTab = 'overview' | 'screenshots' | 'reviews' | 'versions';

export type InstallStatus = 'not-installed' | 'installing' | 'installed' | 'error';
