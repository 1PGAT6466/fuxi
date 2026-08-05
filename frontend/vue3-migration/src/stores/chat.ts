/**
 * 伏羲 v2.1 — Chat Store
 * 会话管理 + 消息发送 + SSE 流式处理
 *
 * 增强功能（v2.1）：
 * - 消息状态管理：sending / streaming / done / error
 * - SSE 自动重连（指数退避，最多 3 次）
 * - 打字机效果回调支持
 */
import { defineStore } from 'pinia';
import { ref, shallowRef, computed } from 'vue';
import type { ChatSession, ChatMessage, ChatReference, ChatStreamChunk, SAGRetrievalTrace } from '@/types';
import {
  fetchSessions,
  createSession,
  deleteSession,
  sendMessageStream,
  fetchSessionMessages,
} from '@/api/chat';
import { ElMessage } from 'element-plus';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ChatStore');

const MAX_MESSAGES: number = Number(import.meta.env.VITE_CHAT_MAX_MESSAGES) || 100;

/** 消息状态类型 */
export type MessageStatus = 'sending' | 'streaming' | 'done' | 'error';

/** SSE 自动重连配置 */
const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_BASE_DELAY = 1000; // 1 秒基础延迟

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

  /** 消息状态映射（index → status） */
  const messageStatuses = ref<Map<number, MessageStatus>>(new Map());

  /** 打字机回调（外部组件可注册） */
  let typewriterCallback: ((char: string, index: number) => void) | null = null;

  /** 当前重连次数 */
  let reconnectAttempts = 0;

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
    } catch (err) {
      logger.warn('加载会话列表失败', err);
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
    } catch (err) {
      logger.error('创建会话失败', err);
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
    } catch (err) {
      logger.error('删除会话失败', err);
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

    // R5 蓝队修复：从后端加载该会话的历史消息
    try {
      const historyMessages = await fetchSessionMessages(sessionId);
      if (historyMessages && historyMessages.length > 0) {
        messages.value = historyMessages;
      }
    } catch (err) {
      // 历史消息加载失败不阻塞，静默处理
      logger.warn('加载会话历史消息失败', err);
    }
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
    reconnectAttempts = 0;
  }

  /** 注册打字机效果回调 */
  function onTypewriter(callback: (char: string, index: number) => void): void {
    typewriterCallback = callback;
  }

  /** 清除打字机回调 */
  function offTypewriter(): void {
    typewriterCallback = null;
  }

  /** 设置消息状态 */
  function setMessageStatus(index: number, status: MessageStatus): void {
    messageStatuses.value = new Map(messageStatuses.value).set(index, status);
  }

  /** 获取消息状态 */
  function getMessageStatus(index: number): MessageStatus {
    return messageStatuses.value.get(index) ?? 'done';
  }

  async function sendMessage(query: string): Promise<void> {
    if (!query.trim() || !activeSessionId.value) return;

    loading.value = true;
    error.value = null;
    streaming.value = false;
    reconnectAttempts = 0;

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
    setMessageStatus(aiIndex, 'sending');

    streamController = new AbortController();

    // 调用流式 API（后端 JSON 或 SSE）
    streaming.value = true;
    loading.value = false;
    setMessageStatus(aiIndex, 'streaming');

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

      // 自动重连：网络错误或超时时尝试重连
      if (shouldReconnect(errMsg) && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const delay = RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts - 1);
        logger.info(`SSE 自动重连 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})，${delay}ms 后重试`);
        setMessageStatus(aiIndex, 'sending');
        await new Promise((resolve) => setTimeout(resolve, delay));
        if (!streamController?.signal.aborted) {
          try {
            streamController = new AbortController();
            setMessageStatus(aiIndex, 'streaming');
            await sendMessageStream(
              { sessionId: activeSessionId.value, query },
              (chunk: ChatStreamChunk) => handleStreamChunk(chunk, aiIndex),
              streamController.signal,
            );
            reconnectAttempts = 0;
          } catch (retryErr) {
            const retryMsg = retryErr instanceof Error ? retryErr.message : String(retryErr);
            logger.error('SSE 重连失败', retryMsg);
            error.value = retryMsg || '重连失败';
            setMessageStatus(aiIndex, 'error');
            streaming.value = false;
          }
        }
      } else {
        error.value = errMsg || '发送消息失败';
        setMessageStatus(aiIndex, 'error');
        streaming.value = false;
      }
    }

    // 如果消息状态仍为 streaming，标记为 done
    if (getMessageStatus(aiIndex) === 'streaming') {
      setMessageStatus(aiIndex, 'done');
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
      setMessageStatus(aiIndex, 'error');
    }
  }

  function handleStreamChunk(chunk: ChatStreamChunk, aiIndex: number): void {
    if (!messages.value[aiIndex]) return;

    switch (chunk.type) {
      case 'content': {
        // 【修复 HIGH-1】shallowRef 不追踪深层属性变更，需创建新对象触发响应
        const prevContent = messages.value[aiIndex].content;
        const newPart = chunk.content || '';
        messages.value[aiIndex] = {
          ...messages.value[aiIndex],
          content: prevContent + newPart,
        };
        // 触发打字机效果回调
        if (typewriterCallback && newPart) {
          for (let i = 0; i < newPart.length; i++) {
            typewriterCallback(newPart[i], prevContent.length + i);
          }
        }
        break;
      }
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
        setMessageStatus(aiIndex, 'done');
        break;
      case 'error':
        error.value = chunk.error || '流式响应错误';
        streaming.value = false;
        setMessageStatus(aiIndex, 'error');
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

  // ============================
  // 重连判断
  // ============================

  /** 判断是否应该自动重连 */
  function shouldReconnect(errMsg: string): boolean {
    const reconnectable = [
      'network', 'fetch', 'Failed to fetch', 'NetworkError',
      'aborted', 'timeout', 'ERR_NETWORK', 'ERR_CONNECTION',
      'ECONNRESET', 'ECONNREFUSED', 'socket hang up',
    ];
    const lower = errMsg.toLowerCase();
    return reconnectable.some((kw) => lower.includes(kw.toLowerCase()));
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
    messageStatuses,
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
    // 消息状态
    setMessageStatus,
    getMessageStatus,
    // 打字机效果
    onTypewriter,
    offTypewriter,
  };
});
