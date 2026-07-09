/**
 * 伏羲 v2.1 — Chat API 封装
 * 会话管理 + 消息发送（SSE 流式）+ 天线搜索
 */
import TokenManager from '@/utils/TokenManager';
import apiClient from './index';
import { createLogger } from '@/utils/logger';
import type {
  ChatSession,
  ChatSessionListResponse,
  ChatSendRequest,
  ChatStreamChunk,
} from '@/types';

const logger = createLogger('ChatAPI');

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
 * 发送消息 — SSE 流式接收
 *
 * 优先使用 SSE (Accept: text/event-stream) 接收实时流式回复。
 * 若后端不支持 SSE（返回 JSON），自动降级为模拟流式输出。
 *
 * SSE 数据格式（每行是一个 SSE event）：
 *   data: {"type":"content","content":"文"}
 *   data: {"type":"content","content":"字"}
 *   data: {"type":"references","references":[...]}
 *   data: {"type":"done"}
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
      'Accept': 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(req),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  // 检测响应类型：SSE vs JSON
  const contentType = response.headers.get('Content-Type') || '';
  const isSSE = contentType.includes('text/event-stream');

  if (isSSE) {
    // ─── 真正的 SSE 流式接收 ───
    await processSSEStream(response, onChunk, signal);
  } else {
    // ─── 降级：JSON 响应模拟流式 ───
    logger.info('后端未返回 SSE，使用 JSON 模拟流式输出');
    await processJSONFallback(response, onChunk, signal);
  }

  if (signal?.aborted) return;
  onChunk({ type: 'done' });
}

/** SSE 流式解析 */
async function processSSEStream(
  response: Response,
  onChunk: (chunk: ChatStreamChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('浏览器不支持流式读取');
  }

  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      if (signal?.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // 按行解析 SSE
      const lines = buffer.split('\n');
      // 保留最后一个未完成的行
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(':')) continue; // 跳过空行和注释

        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const chunk = JSON.parse(jsonStr) as ChatStreamChunk;
            if (chunk.type === 'done') return;
            onChunk(chunk);
          } catch {
            // 非 JSON data 行（如 "data: [DONE]"），忽略
            logger.debug('SSE 跳过非 JSON 行:', jsonStr.slice(0, 50));
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/** JSON 降级：模拟流式输出 */
async function processJSONFallback(
  response: Response,
  onChunk: (chunk: ChatStreamChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const data = await response.json();

  if (signal?.aborted) return;

  // 后端返回 {answer, sources, mode}
  if (data.answer) {
    const answer = data.answer;
    // 以 10-30ms 间隔逐字输出，模拟流式效果
    const chunkSize = Math.max(1, Math.floor(answer.length / 100));
    for (let i = 0; i < answer.length; i += chunkSize) {
      if (signal?.aborted) break;
      await new Promise((resolve) => setTimeout(resolve, 30));
      onChunk({ type: 'content', content: answer.slice(i, i + chunkSize) });
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
    onChunk({ type: 'error', error: data.answer || data.message || '处理请求时发生错误' });
  }
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
