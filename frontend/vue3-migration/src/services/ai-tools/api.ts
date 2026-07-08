/**
 * 伏羲 v2.1 — AI 工具集 API 封装
 * 封装 6 个端点：health / summarize / translate / keywords / entities / classify
 * Mock 兜底：API 不可用时使用内置 mock 数据
 */

import apiClient from '@/api';
import { mockAiToolsResponse } from './mock';
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

/**
 * 带 mock 兜底的通用请求封装
 */
async function requestWithFallback<T>(
  endpoint: string,
  mockData: T,
  method: 'GET' | 'POST' = 'GET',
  body?: unknown,
): Promise<T> {
  try {
    if (method === 'GET') {
      return (await apiClient.get(`${API_BASE}${endpoint}`)) as T;
    }
    return (await apiClient.post(`${API_BASE}${endpoint}`, body)) as T;
  } catch (err) {
    console.warn(`[AI Tools] API ${API_BASE}${endpoint} 不可用，使用 mock 数据`, err);
    return mockData;
  }
}

// ───── 端点封装 ─────

/** 健康检查 */
export async function health(): Promise<AiHealthResponse> {
  return requestWithFallback<AiHealthResponse>('/health', mockAiToolsResponse.health());
}

/** 文本摘要 */
export async function summarize(
  text: string,
  maxLength?: 'short' | 'medium' | 'long',
): Promise<SummarizeResponse> {
  const body: SummarizeRequest = { text, max_length: maxLength };
  return requestWithFallback<SummarizeResponse>(
    '/summarize',
    mockAiToolsResponse.summarize(text, maxLength),
    'POST',
    body,
  );
}

/** 智能翻译 */
export async function translate(
  text: string,
  sourceLang: string,
  targetLang: string,
): Promise<TranslateResponse> {
  const body: TranslateRequest = { text, source_lang: sourceLang, target_lang: targetLang };
  return requestWithFallback<TranslateResponse>(
    '/translate',
    mockAiToolsResponse.translate(text, sourceLang, targetLang),
    'POST',
    body,
  );
}

/** 关键词提取 */
export async function keywords(text: string): Promise<KeywordsResponse> {
  return requestWithFallback<KeywordsResponse>(
    '/keywords',
    mockAiToolsResponse.keywords(text),
    'POST',
    { text },
  );
}

/** 实体识别 */
export async function entities(text: string): Promise<EntitiesResponse> {
  return requestWithFallback<EntitiesResponse>(
    '/entities',
    mockAiToolsResponse.entities(text),
    'POST',
    { text },
  );
}

/** 文本分类 */
export async function classify(text: string, categories?: string[]): Promise<ClassifyResponse> {
  const body: ClassifyRequest = { text, categories };
  return requestWithFallback<ClassifyResponse>(
    '/classify',
    mockAiToolsResponse.classify(text, categories),
    'POST',
    body,
  );
}
