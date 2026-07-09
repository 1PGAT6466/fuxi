/**
 * 伏羲 v2.1 — AI 工具集 API 封装
 * 封装 6 个端点：health / summarize / translate / keywords / entities / classify
 * 数据来源：后端 API，失败时抛出错误，不返回兜底 mock
 */

import apiClient from '@/api';
import type {
  AiHealthResponse,
  SummarizeRequest,
  SummarizeResponse,
  TranslateRequest,
  TranslateResponse,
  KeywordsResponse,
  EntitiesResponse,
  ClassifyRequest,
  ClassifyResponse,
} from './types';

// ───── 错误处理 ─────

const API_BASE = '/api/ai';

class ApiNotAvailableError extends Error {
  constructor(endpoint: string, originalError?: unknown) {
    super(`AI 工具 API ${endpoint} 暂不可用`);
    this.name = 'ApiNotAvailableError';
    if (originalError instanceof Error) {
      this.stack = originalError.stack;
    }
  }
}

/**
 * 通用请求封装（无 mock 兜底，失败即抛出错误）
 */
async function apiRequest<T>(
  endpoint: string,
  method: 'GET' | 'POST' = 'GET',
  body?: unknown,
): Promise<T> {
  if (method === 'GET') {
    return (await apiClient.get(`${API_BASE}${endpoint}`)) as T;
  }
  return (await apiClient.post(`${API_BASE}${endpoint}`, body)) as T;
}

// ───── 端点封装 ─────

/** 健康检查 */
export async function health(): Promise<AiHealthResponse> {
  return apiRequest<AiHealthResponse>('/health');
}

/** 文本摘要 */
export async function summarize(
  text: string,
  maxLength?: 'short' | 'medium' | 'long',
): Promise<SummarizeResponse> {
  const body: SummarizeRequest = { text, max_length: maxLength };
  return apiRequest<SummarizeResponse>('/summarize', 'POST', body);
}

/** 智能翻译 */
export async function translate(
  text: string,
  sourceLang: string,
  targetLang: string,
): Promise<TranslateResponse> {
  const body: TranslateRequest = { text, source_lang: sourceLang, target_lang: targetLang };
  return apiRequest<TranslateResponse>('/translate', 'POST', body);
}

/** 关键词提取 */
export async function keywords(text: string): Promise<KeywordsResponse> {
  return apiRequest<KeywordsResponse>('/keywords', 'POST', { text });
}

/** 实体识别 */
export async function entities(text: string): Promise<EntitiesResponse> {
  return apiRequest<EntitiesResponse>('/entities', 'POST', { text });
}

/** 文本分类 */
export async function classify(text: string, categories?: string[]): Promise<ClassifyResponse> {
  const body: ClassifyRequest = { text, categories };
  return apiRequest<ClassifyResponse>('/classify', 'POST', body);
}
