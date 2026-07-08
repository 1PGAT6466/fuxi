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

export type ExportFormat = 'csv' | 'excel';

export interface ExportConfig {
  format: ExportFormat;
  fields: string[];
  date_range: {
    start?: string;
    end?: string;
  };
}

export interface ExportResponse {
  download_url: string;
  filename: string;
  format: ExportFormat;
  size: number;
}
