/**
 * 伏羲 v2.1 — 文档工具 API 封装
 * 封装 7 个端点：convert / merge / split / compress / compress-image / image-info / extract-text
 * Mock 兜底：API 不可用时使用内置 mock 数据
 */

import apiClient from '@/api';
import { mockDocToolsResponse } from './mock';
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

/**
 * 带 mock 兜底的通用请求封装（POST multipart 使用）
 * 对于 FormData，直接尝试 API，失败后 fallback mock
 */
async function requestWithFallback<T>(
  endpoint: string,
  mockData: T,
  formData: FormData,
): Promise<T> {
  try {
    return (await apiClient.post(`${API_BASE}${endpoint}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })) as T;
  } catch (err) {
    console.warn(`[Doc Tools] API ${API_BASE}${endpoint} 不可用，使用 mock 数据`, err);
    return mockData;
  }
}

// ───── 端点封装 ─────

/** 健康检查 */
export async function health() {
  try {
    return await apiClient.get(`${API_BASE}/health`);
  } catch (err) {
    console.warn(`[Doc Tools] API ${API_BASE}/health 不可用`, err);
    return { status: 'degraded' };
  }
}

/** 格式转换 */
export async function convertFile(file: File, targetFormat: string): Promise<ConvertResponse> {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('target_format', targetFormat);
  return requestWithFallback<ConvertResponse>(
    '/convert',
    await mockDocToolsResponse.convert(file, targetFormat),
    fd,
  );
}

/** PDF 合并 */
export async function mergePdfs(files: File[]): Promise<MergeResponse> {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  return requestWithFallback<MergeResponse>(
    '/merge',
    await mockDocToolsResponse.mergePdfs(files),
    fd,
  );
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
  return requestWithFallback<SplitResponse>(
    '/split',
    await mockDocToolsResponse.splitPdf(file, startPage, endPage),
    fd,
  );
}

/** 文件压缩 */
export async function compressFile(file: File, options: CompressOptions): Promise<CompressResult> {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('quality', options.quality);
  if (options.resolution) fd.append('resolution', options.resolution);
  return requestWithFallback<CompressResult>(
    '/compress',
    await mockDocToolsResponse.compressFile(file, options),
    fd,
  );
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
  return requestWithFallback<ImageMeta>(
    '/image-info',
    await mockDocToolsResponse.getImageInfo(file),
    fd,
  );
}

/** 文本提取 */
export async function extractText(file: File): Promise<TextExtractResult> {
  const fd = new FormData();
  fd.append('file', file);
  return requestWithFallback<TextExtractResult>(
    '/text-extract',
    await mockDocToolsResponse.extractText(file),
    fd,
  );
}
