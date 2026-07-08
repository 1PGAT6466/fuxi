/**
 * 伏羲 v2.1 — 文档工具类型定义
 */

// ───── 格式转换 ─────

export type SourceFormat =
  'pdf' | 'docx' | 'doc' | 'txt' | 'png' | 'jpg' | 'jpeg' | 'webp' | 'xlsx' | 'pptx';
export type TargetFormat =
  'pdf' | 'docx' | 'doc' | 'txt' | 'png' | 'jpg' | 'webp' | 'xlsx' | 'pptx';

export interface ConvertRequest {
  source_format: SourceFormat;
  target_format: TargetFormat;
}

export interface ConvertResponse {
  id: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  source_filename: string;
  target_filename: string;
  download_url?: string;
  error?: string;
}

// ───── 工具通用 ─────

export interface ToolFile {
  id: string;
  name: string;
  size: number;
  type: string;
  file?: File;
}

export interface ProgressInfo {
  id: string;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}

// ───── PDF 合并 ─────

export interface MergeResponse {
  id: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number;
  filename: string;
  download_url?: string;
  page_count?: number;
}

// ───── PDF 拆分 ─────

export interface SplitRange {
  start: number;
  end: number;
}

export interface SplitPageInfo {
  range: string;
  filename: string;
  page_count: number;
  download_url: string;
}

export interface SplitResponse {
  id: string;
  status: 'processing' | 'completed' | 'failed';
  parts: SplitPageInfo[];
}

// ───── 压缩 ─────

export interface CompressOptions {
  quality: 'high' | 'medium' | 'low';
  resolution?: 'original' | '1080p' | '720p' | '480p';
}

export interface CompressResult {
  original_size: number;
  compressed_size: number;
  ratio: number; // 压缩比
  preview_url?: string;
  download_url: string;
}

// ───── 图片信息 ─────

export interface ImageMeta {
  width: number;
  height: number;
  format: string;
  dpi: number;
  exif: Record<string, string>;
  file_size: number;
  aspect_ratio: string;
  color_space: string;
  filename: string;
}

// ───── 文本提取 ─────

export interface TextExtractResult {
  text: string;
  page_count: number;
  char_count: number;
  language: string;
}

// ───── 最近记录 ─────

export interface RecentRecord {
  id: string;
  tool: string;
  timestamp: number;
  filename: string;
  status: 'completed' | 'failed';
  details?: string;
}
