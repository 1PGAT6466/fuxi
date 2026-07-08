/**
 * 伏羲 v2.1 — Chat API 封装
 * 会话管理 + 消息发送（SSE 流式）+ 天线搜索
 */
import { TOKEN_KEY } from '@/constants/storage-keys';
import TokenManager from '@/utils/TokenManager';
import apiClient from './index';
import type {
  ChatSession,
  ChatSessionListResponse,
  ChatSendRequest,
  ChatStreamChunk,
  ChatReference,
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
 * 发送消息并接收 SSE 流式响应
 * 使用 ReadableStream 处理 SSE 事件
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

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('不支持流式响应');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // 保留最后一个不完整的行
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;

        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const chunk: ChatStreamChunk = JSON.parse(jsonStr);
          onChunk(chunk);
        } catch (err) {
          console.error('[Chat API] SSE JSON 解析失败', err, '原始数据:', jsonStr);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ============================
// Mock 数据（后端不可用时的兜底）
// ============================

const MOCK_SESSIONS: ChatSession[] = [
  {
    id: 'mock-1',
    title: '关于伏羲系统的讨论',
    lastMessage: '伏羲系统支持哪些文档格式？',
    createdAt: Date.now() - 86400000 * 3,
    updatedAt: Date.now() - 3600000,
    messageCount: 12,
  },
  {
    id: 'mock-2',
    title: 'API 接口设计',
    lastMessage: '如何认证 API 请求？',
    createdAt: Date.now() - 86400000 * 5,
    updatedAt: Date.now() - 7200000,
    messageCount: 8,
  },
  {
    id: 'mock-3',
    title: '前端性能优化',
    lastMessage: '懒加载的最佳实践？',
    createdAt: Date.now() - 86400000 * 7,
    updatedAt: Date.now() - 86400000,
    messageCount: 15,
  },
];

const MOCK_REFERENCES: ChatReference[] = [
  {
    id: 'ref-1',
    title: '伏羲系统技术白皮书 v2.0',
    type: 'document',
    url: '/files/whitepaper.pdf',
    snippet: '第三章 文档索引流水线...',
  },
  {
    id: 'ref-2',
    title: 'RAG 检索增强生成综述',
    type: 'knowledge',
    snippet: '检索增强生成(RAG)是一种将信息检索与语言模型...',
  },
];

const MOCK_STREAM_CONTENT =
  '伏羲系统支持 PDF、DOCX、XLSX、TXT、Markdown、CSV 等多种常见文档格式。上传后系统会自动进行文本提取、分块和向量化处理。';

/** 获取 Mock 会话列表 */
export function getMockSessions(): ChatSession[] {
  return [...MOCK_SESSIONS];
}

/** 创建 Mock 会话 */
export function getMockNewSession(): ChatSession {
  return {
    id: `mock-${Date.now()}`,
    title: '新对话',
    lastMessage: '',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messageCount: 0,
  };
}

/** Mock 流式输出 */
export async function mockSendMessageStream(
  onChunk: (chunk: ChatStreamChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const chars = MOCK_STREAM_CONTENT.split('');
  for (let i = 0; i < chars.length; i++) {
    if (signal?.aborted) break;
    await new Promise((resolve) => setTimeout(resolve, 50));
    onChunk({ type: 'content', content: chars[i] });
  }
  await new Promise((resolve) => setTimeout(resolve, 300));
  onChunk({ type: 'references', references: MOCK_REFERENCES });
  await new Promise((resolve) => setTimeout(resolve, 200));
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
