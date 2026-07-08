import apiClient from './index';
import TokenManager from '@/utils/TokenManager';
import type { SearchResult, EventReference, SAGRetrievalTrace, EntityTag } from '@/types';

// ============================
// 传统 RAG 检索
// ============================

/**
 * @deprecated 使用 fetchSearch 替代，支持传统 RAG 的完整参数
 */
export function ragSearch(query: string) {
  return apiClient.post('/api/rag/search', { query });
}

// ============================
// 响应类型定义
// ============================

/** 传统 RAG 检索响应（/api/rag/search） */
export interface TraditionalSearchResponse {
  results: SearchResult[];
  total: number;
}

/** SAG Event 粒度检索响应（/api/rag/sag-search） */
export interface EventSearchResponse {
  results: SearchResult[];
  events?: EventReference[];
  total: number;
  granularity: 'chunk' | 'event' | 'auto';
}

/** SAG Event 粒度检索参数 */
export interface EventSearchParams {
  query: string;
  top_k?: number;
  granularity?: 'chunk' | 'event' | 'auto';
  score_threshold?: number;
  mode?: 'semantic' | 'keyword' | 'hybrid';
}

/** 实体扩展响应 */
export interface EntityExpandResponse {
  entity_name: string;
  expanded_entities: { name: string; type: string; similarity: number }[];
  total: number;
}

// ============================
// 传统 RAG 检索 API
// ============================

/**
 * 传统 RAG 检索 — 调用 /api/rag/search
 * 返回 TraditionalSearchResponse（不含 SAG 特有字段）
 */
export async function fetchSearch(
  query: string,
  options?: {
    top_k?: number;
    mode?: 'semantic' | 'keyword' | 'hybrid';
    score_threshold?: number;
  },
): Promise<TraditionalSearchResponse> {
  const data = (await apiClient.post('/api/rag/search', {
    query,
    top_k: options?.top_k ?? 5,
    mode: options?.mode ?? 'semantic',
    score_threshold: options?.score_threshold ?? 0,
  })) as TraditionalSearchResponse;
  return data;
}

// ============================
// SAG 增强检索 API
// ============================

/**
 * SAG Event 粒度检索 — 调用 /api/rag/sag-search
 * 支持 chunk/event/auto 三种粒度
 */
export async function fetchEventSearch(
  query: string,
  top_k: number = 5,
  granularity: 'chunk' | 'event' | 'auto' = 'auto',
): Promise<EventSearchResponse> {
  const data = (await apiClient.post('/api/rag/sag-search', {
    query,
    top_k,
    granularity,
  })) as EventSearchResponse;
  return data;
}

/**
 * 高级 SAG 检索（完整参数） — 调用 /api/rag/sag-search
 */
export async function fetchSAGSearch(params: EventSearchParams): Promise<EventSearchResponse> {
  const data = (await apiClient.post('/api/rag/sag-search', params)) as EventSearchResponse;
  return data;
}

/**
 * 实体向量扩展
 * 输入实体名，返回向量相似度排序的扩展实体
 */
export async function fetchEntityExpand(
  entity_name: string,
): Promise<EntityExpandResponse> {
  const data = (await apiClient.get('/api/rag/entity-expand', {
    params: { entity_name },
  })) as EntityExpandResponse;
  return data;
}

// ============================
// SAG 检索追踪 SSE 监听
// ============================

/**
 * 订阅 SAG 检索追踪 SSE 流
 * 实时接收三阶段流水线数据
 */
export async function subscribeToSearchTrace(
  sessionId: string,
  onTrace: (trace: SAGRetrievalTrace) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = TokenManager.getToken();

  const response = await fetch('/api/rag/sag-trace', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ session_id: sessionId }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('不支持流式响应');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  // 【修复 MEDIUM-3】SSE 读取前检查 abort 状态
  signal?.throwIfAborted();

  try {
    while (true) {
      // 每次 read 前检查是否已被 abort
      signal?.throwIfAborted();

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;

        const jsonStr = line.slice(5).trim();
        if (!jsonStr || jsonStr === '[DONE]') continue;

        try {
          const trace: SAGRetrievalTrace = JSON.parse(jsonStr);
          onTrace(trace);
        } catch (err) {
          console.error('[SAG Trace] JSON 解析失败', err, '原始数据:', jsonStr);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
