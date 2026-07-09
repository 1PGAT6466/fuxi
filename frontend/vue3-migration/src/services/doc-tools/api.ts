/**
 * 伏羲 v2.1 — 文档工具 API 封装
 * 封装 7 个端点：convert / merge / split / compress / compress-image / image-info / extract-text
 * 数据来源：后端 API，失败时抛出错误，不返回兜底 mock
 */

import apiClient from '@/api';
import type {
  ConvertResponse,
  MergeResponse,
  SplitResponse,
  CompressOptions,
  CompressResult,
  ImageMeta,
  TextExtractResult,
} from './types';

// ───── 错误处理 ─────

const API_BASE = '/api/tools';

// ───── 端点封装 ─────

/** 健康检查 */
export async function health() {
  return apiClient.get(`${API_BASE}/health`);
}

/** 格式转换 */
export async function convertFile(file: File, targetFormat: string): Promise<ConvertResponse> {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('target_format', targetFormat);
  return apiClient.post(`${API_BASE}/convert`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  }) as Promise<ConvertResponse>;
}

/** PDF 合并 */
export async function mergePdfs(files: File[]): Promise<MergeResponse> {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  return apiClient.post(`${API_BASE}/merge`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<MergeResponse>;
}

/** PDF 拆分 */
export async function splitPdf(
  file: File,
  startPage: number,
  endPage: number,
): Promise<SplitResponse> {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('start_page', String(startPage));
  fd.append('end_page', String(endPage));
  return apiClient.post(`${API_BASE}/split`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<SplitResponse>;
}

/** 文件压缩 */
export async function compressFile(file: File, options: CompressOptions): Promise<CompressResult> {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('quality', options.quality);
  if (options.resolution) fd.append('resolution', options.resolution);
  return apiClient.post(`${API_BASE}/compress`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<CompressResult>;
}

/** 图片压缩（简化版） */
export async function compressImage(
  file: File,
  quality: 'high' | 'medium' | 'low',
  maxW?: number,
  maxH?: number,
): Promise<CompressResult> {
  const options: CompressOptions = { quality };
  if (maxW && maxH) options.resolution = 'original';
  return compressFile(file, options);
}

/** 获取图片信息 */
export async function getImageInfo(file: File): Promise<ImageMeta> {
  const fd = new FormData();
  fd.append('file', file);
  return apiClient.post(`${API_BASE}/image-info`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<ImageMeta>;
}

/** 文本提取 */
export async function extractText(file: File): Promise<TextExtractResult> {
  const fd = new FormData();
  fd.append('file', file);
  return apiClient.post(`${API_BASE}/text-extract`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<TextExtractResult>;
}
