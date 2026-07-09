/**
 * 伏羲 v2.1 — Chat Store
 * 会话管理 + 消息发送 + SSE 流式处理
 */
import { defineStore } from 'pinia';
import { ref, shallowRef, computed } from 'vue';
import type { ChatSession, ChatMessage, ChatReference, ChatStreamChunk, SAGRetrievalTrace } from '@/types';
import {
  fetchSessions,
  createSession,
  deleteSession,
  sendMessageStream,
} from '@/api/chat';
import { ElMessage } from 'element-plus';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ChatStore');

const MAX_MESSAGES: number = Number(import.meta.env.VITE_CHAT_MAX_MESSAGES) || 100;

export const useChatStore = defineStore('chat', () => {
  // ============================
  // 会话状态
  // ============================
  // P0-4: 大数组改用 shallowRef 避免深度响应式开销
  const sessions = shallowRef<ChatSession[]>([]);
  const activeSessionId = ref<string | null>(null);
  const sessionsLoading = ref(false);

  // ============================
  // 消息状态
  // ============================
  const messages = shallowRef<ChatMessage[]>([]);
  const streaming = ref<boolean>(false);
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);
  /** SAG 检索追踪数据（当前活跃的追踪） */
  const sagTrace = ref<SAGRetrievalTrace | null>(null);

  // AbortController for cancelling stream
  let streamController: AbortController | null = null;

  // ============================
  // 计算属性
  // ============================

  const activeSession = computed<ChatSession | null>(() => {
    if (!activeSessionId.value) return null;
    return sessions.value.find((s) => s.id === activeSessionId.value) || null;
  });

  const hasSessions = computed(() => sessions.value.length > 0);

  // ============================
  // 会话管理
  // ============================

  async function loadSessions(): Promise<void> {
    sessionsLoading.value = true;
    try {
      sessions.value = await fetchSessions();
    } catch {
      ElMessage.warning('加载会话列表失败，使用本地数据');
    } finally {
      sessionsLoading.value = false;
    }
  }

  async function addSession(title?: string): Promise<ChatSession | null> {
    try {
      const session = await createSession(title || '新对话');
      sessions.value = [session, ...sessions.value];
      await switchSession(session.id);
      return session;
    } catch {
      ElMessage.warning('创建会话失败');
      return null;
    }
  }

  async function removeSession(sessionId: string): Promise<void> {
    try {
      await deleteSession(sessionId);
      sessions.value = sessions.value.filter((s) => s.id !== sessionId);
      if (activeSessionId.value === sessionId) {
        // 切换到最近的会话
        const nextSession = sessions.value[0];
        if (nextSession) {
          await switchSession(nextSession.id);
        } else {
          activeSessionId.value = null;
          messages.value = [];
        }
      }
    } catch {
      ElMessage.error('删除会话失败');
      throw new Error('删除会话失败');
    }
  }

  async function switchSession(sessionId: string): Promise<void> {
    // 取消当前流
    cancelStream();

    activeSessionId.value = sessionId;
    messages.value = [];
    error.value = null;

    // TODO: 从后端加载该会话的历史消息
    // 当前先清空，等后端实现 getSessionMessages API
  }

  // ============================
  // 消息发送（SSE 流式）
  // ============================

  function cancelStream(): void {
    if (streamController) {
      streamController.abort();
      streamController = null;
    }
    streaming.value = false;
  }

  async function sendMessage(query: string): Promise<void> {
    if (!query.trim() || !activeSessionId.value) return;

    loading.value = true;
    error.value = null;
    streaming.value = false;

    // 添加用户消息
    const userMsg: ChatMessage = {
      role: 'user',
      content: query,
      timestamp: Date.now(),
    };
    messages.value = [...messages.value, userMsg];
    enforceMaxMessages();

    // 准备 AI 消息占位
    const aiMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    };
    messages.value = [...messages.value, aiMsg];
    const aiIndex = messages.value.length - 1;

    streamController = new AbortController();

    // 调用流式 API（后端 JSON 或 SSE）
    streaming.value = true;
    loading.value = false;

    try {
      await sendMessageStream(
        { sessionId: activeSessionId.value, query },
        (chunk: ChatStreamChunk) => {
          handleStreamChunk(chunk, aiIndex);
        },
        streamController.signal,
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : String(err);
      logger.error('发送消息失败', errMsg);
      error.value = errMsg || '发送消息失败';
      streaming.value = false;
    }

    streaming.value = false;
    streamController = null;

    // 更新会话最后消息
    if (activeSessionId.value) {
      const idx = sessions.value.findIndex((s) => s.id === activeSessionId.value);
      if (idx !== -1) {
        const session = sessions.value[idx];
        sessions.value[idx] = {
          ...session,
          lastMessage: query.slice(0, 50),
          updatedAt: Date.now(),
          messageCount: (session.messageCount || 0) + 2,
        };
        sessions.value = [...sessions.value];
      }
    }

    // 如果 AI 消息为空，标记错误
    if (!error.value && !messages.value[aiIndex].content) {
      error.value = '未收到有效的 AI 回复';
    }
  }

  function handleStreamChunk(chunk: ChatStreamChunk, aiIndex: number): void {
    if (!messages.value[aiIndex]) return;

    switch (chunk.type) {
      case 'content':
        // 【修复 HIGH-1】shallowRef 不追踪深层属性变更，需创建新对象触发响应
        messages.value[aiIndex] = {
          ...messages.value[aiIndex],
          content: messages.value[aiIndex].content + (chunk.content || ''),
        };
        break;
      case 'references':
        // 【修复 HIGH-2】shallowRef 不追踪深层属性变更，需创建新对象触发响应
        messages.value[aiIndex] = {
          ...messages.value[aiIndex],
          references: chunk.references,
        };
        break;
      case 'sag_trace':
        sagTrace.value = chunk.sag_trace || null;
        break;
      case 'done':
        // 流结束，无需额外处理
        break;
      case 'error':
        error.value = chunk.error || '流式响应错误';
        streaming.value = false;
        break;
    }
  }

  function retryLastMessage(): void {
    if (messages.value.length < 2) return;

    // 找到最后一条用户消息
    let lastUserIdx = -1;
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'user') {
        lastUserIdx = i;
        break;
      }
    }
    if (lastUserIdx === -1) return;

    const lastUserMsg = messages.value[lastUserIdx];
    // 移除用户消息之后的所有消息
    messages.value = messages.value.slice(0, lastUserIdx);
    error.value = null;

    // 重新发送
    sendMessage(lastUserMsg.content);
  }

  // ============================
  // 工具方法
  // ============================

  /** 确保消息数不超过 MAX_MESSAGES，溢出时保留最后 N 条 */
  function enforceMaxMessages(): void {
    if (messages.value.length > MAX_MESSAGES) {
      messages.value = messages.value.slice(-MAX_MESSAGES);
    }
  }

  function clearMessages(): void {
    messages.value = [];
    error.value = null;
    cancelStream();
  }

  return {
    // 状态
    sessions,
    activeSessionId,
    sessionsLoading,
    messages,
    streaming,
    loading,
    error,
    sagTrace,
    // 计算
    activeSession,
    hasSessions,
    // 方法
    loadSessions,
    addSession,
    removeSession,
    switchSession,
    sendMessage,
    retryLastMessage,
    enforceMaxMessages,
    clearMessages,
    cancelStream,
  };
});
