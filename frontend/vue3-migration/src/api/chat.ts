/**
 * 伏羲 v2.1 — Chat API 封装
 * 会话管理 + 消息发送（SSE 流式）+ 天线搜索
 */
import TokenManager from '@/utils/TokenManager';
import apiClient from './index';
import type {
  ChatSession,
  ChatSessionListResponse,
  ChatSendRequest,
  ChatStreamChunk,
} from '@/types';

// ============================
// 会话管理
// ============================

/** 获取会话列表 */
export async function fetchSessions(): Promise<ChatSession[]> {
  const data = (await apiClient.get('/api/chat/sessions')) as ChatSessionListResponse;
  return data.sessions || [];
}

/** 创建新会话 */
export async function createSession(title?: string): Promise<ChatSession> {
  const data = (await apiClient.post('/api/chat/sessions', { title })) as ChatSession;
  return data;
}

/** 删除会话 */
export async function deleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/api/chat/sessions/${sessionId}`);
}

// ============================
// 消息发送 — SSE 流式
// ============================

/**
 * 发送消息（后端当前返回 JSON，非 SSE 流式）
 * 后端 POST /api/chat/send 返回 {answer, sources, mode}
 * 前端将 JSON 响应模拟为流式 chunks 以保持 UI 一致性
 */
export async function sendMessageStream(
  req: ChatSendRequest,
  onChunk: (chunk: ChatStreamChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = TokenManager.getToken();

  const response = await fetch('/api/chat/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(req),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();

  if (signal?.aborted) return;

  // 后端返回 {answer, sources, mode}
  if (data.answer) {
    // 将完整回答逐字流式输出以保持 UI 体验
    const answer = data.answer;
    for (let i = 0; i < answer.length; i++) {
      if (signal?.aborted) break;
      await new Promise((resolve) => setTimeout(resolve, 30));
      onChunk({ type: 'content', content: answer[i] });
    }

    // 发送引用来源
    if (data.sources && data.sources.length > 0) {
      const references = data.sources.slice(0, 10).map((s: string, idx: number) => ({
        id: `ref-${idx}`,
        title: s,
        type: 'document' as const,
        snippet: '',
      }));
      onChunk({ type: 'references', references });
    }
  } else if (data.mode === 'error') {
    // 错误响应
    onChunk({ type: 'error', error: data.answer || '处理请求时发生错误' });
    return;
  }

  onChunk({ type: 'done' });
}

// ============================
// 天线搜索（联网搜索）
// ============================

export interface AntennaSearchResult {
  results: Array<{
    title?: string;
    url?: string;
    snippet?: string;
    source?: string;
  }>;
  query: string;
  source: string;
  message?: string;
}

/** 天线搜索 — 调用 /api/antenna/search（后端 files_view.py） */
export async function antennaSearch(query: string): Promise<AntennaSearchResult> {
  return apiClient.get('/api/antenna/search', {
    params: { q: query },
  }) as Promise<AntennaSearchResult>;
}
