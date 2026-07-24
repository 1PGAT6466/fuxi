/**
 * 伏羲 v2.1 — 数据分析类型定义
 */

// ───── 统计概览 ─────

export interface StatItem {
  label: string;
  value: number;
  unit: string;
  change: number; // 环比变化百分比，正数为增长
  trend: number[]; // 迷你趋势图数据（最近 7 天）
}

export interface StatsResponse {
  stats: StatItem[];
  updated_at: string;
}

// ───── 趋势分析 ─────

export type TrendPeriod = 'day' | 'week' | 'month';

export interface TrendPoint {
  date: string;
  queries: number;
  documents: number;
  active_users: number;
}

export interface TrendsResponse {
  period: TrendPeriod;
  data: TrendPoint[];
}

// ───── 存储分布 ─────

export interface FileTypeItem {
  type: string;
  label: string;
  size: number; // GB
  count: number;
}

export interface CollectionStorageItem {
  collection: string;
  size: number; // GB
  document_count: number;
  vector_count: number;
}

export interface StorageDistResponse {
  by_file_type: FileTypeItem[];
  by_collection: CollectionStorageItem[];
}

// ───── 报表 ─────

export type ReportType = 'summary' | 'detailed';
export type ReportDimension = 'queries' | 'documents' | 'users' | 'storage' | 'vectors';

export interface ReportRequest {
  type: ReportType;
  period: string; // '7d' | '30d' | '90d' | '1y'
  dimensions: ReportDimension[];
}

export interface ReportResponse {
  id: string;
  type: ReportType;
  title: string;
  generated_at: string;
  period: string;
  sections: ReportSection[];
}

export interface ReportSection {
  title: string;
  content: string;
  chart_data?: unknown;
  metrics?: Record<string, number>;
}

// ───── 导出 ─────

export type ExportFormat = 'pdf' | 'excel' | 'csv' | 'json';

export interface ExportConfig {
  format: ExportFormat;
  fields: string[];
  date_range: {
    start?: string;
    end?: string;
  };
  /** 报表模板 ID（可选，使用模板预设字段） */
  template_id?: string;
  /** 导出标题 */
  title?: string;
}

export interface ExportResponse {
  download_url: string;
  filename: string;
  format: ExportFormat;
  size: number;
}

// ───── 报表模板 ─────

export interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  /** 预设字段 */
  default_fields: string[];
  /** 预设格式 */
  default_format: ExportFormat;
  created_at: string;
  updated_at: string;
}

// ───── 报表分享 ─────

export type SharePermission = 'view' | 'edit' | 'download';

export interface ShareConfig {
  /** 报表 ID */
  report_id: string;
  /** 分享权限 */
  permissions: SharePermission[];
  /** 过期时间（ISO 格式，可选） */
  expires_at?: string;
  /** 密码保护（可选） */
  password?: string;
  /** 备注 */
  note?: string;
}

export interface ShareResponse {
  /** 分享链接 */
  share_url: string;
  /** 访问令牌 */
  token: string;
  /** 过期时间 */
  expires_at: string;
  /** 权限列表 */
  permissions: SharePermission[];
  created_at: string;
}

export interface SharedReport {
  report_id: string;
  title: string;
  type: ReportType;
  generated_at: string;
  permissions: SharePermission[];
  sections: ReportSection[];
  owner_name: string;
  /** 是否密码保护 */
  password_protected: boolean;
}
