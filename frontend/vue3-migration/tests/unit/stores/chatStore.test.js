/**
 * chatStore 测试
 * 测试消息发送、清理和错误处理
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

// Mock API client
const mockApiClient = {
  post: vi.fn(),
};

vi.mock('@/api', () => ({
  default: mockApiClient,
}));

// Mock import.meta.env
vi.stubGlobal('import', { meta: { env: { VITE_CHAT_MAX_MESSAGES: '50' } } });

describe('chatStore', () => {
  let chatStore;

  beforeEach(async () => {
    setActivePinia(createPinia());
    mockApiClient.post.mockReset();

    // 重新定义 import.meta.env 以便每次使用正确值
    vi.stubGlobal('import', { meta: { env: { VITE_CHAT_MAX_MESSAGES: '50' } } });

    const { useChatStore } = await import('@/stores/chat');
    chatStore = useChatStore();
  });

  describe('初始状态', () => {
    it('初始 messages 为空数组', () => {
      expect(chatStore.messages).toEqual([]);
    });

    it('初始 loading 为 false', () => {
      expect(chatStore.loading).toBe(false);
    });

    it('初始 error 为 null', () => {
      expect(chatStore.error).toBeNull();
    });
  });

  describe('sendMessage', () => {
    it('成功发送消息应添加用户消息和 AI 回复', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        answer: '你好！有什么可以帮助你的？',
        sources: [{ title: '文档1', url: '/doc/1' }],
        confidence: 0.95,
      });

      await chatStore.sendMessage('你好');

      expect(chatStore.messages).toHaveLength(2);
      expect(chatStore.messages[0].role).toBe('user');
      expect(chatStore.messages[0].content).toBe('你好');
      expect(chatStore.messages[1].role).toBe('assistant');
      expect(chatStore.messages[1].content).toBe('你好！有什么可以帮助你的？');
      expect(chatStore.messages[1].sources).toEqual([{ title: '文档1', url: '/doc/1' }]);
      expect(chatStore.messages[1].confidence).toBe(0.95);
    });

    it('用户消息应包含时间戳', async () => {
      mockApiClient.post.mockResolvedValueOnce({ answer: '回复' });

      await chatStore.sendMessage('问题');

      expect(chatStore.messages[0]).toHaveProperty('timestamp');
      expect(typeof chatStore.messages[0].timestamp).toBe('number');
    });

    it('应调用正确的 API', async () => {
      mockApiClient.post.mockResolvedValueOnce({ answer: 'OK' });

      await chatStore.sendMessage('测试');

      expect(mockApiClient.post).toHaveBeenCalledWith('/api/chat', { query: '测试' });
    });

    it('返回结果应包含 API 响应数据', async () => {
      const mockData = { answer: 'OK', sources: [] };
      mockApiClient.post.mockResolvedValueOnce(mockData);

      const result = await chatStore.sendMessage('test');

      expect(result).toEqual(mockData);
    });

    it('失败时应设置 error 消息', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('网络连接失败'));

      await chatStore.sendMessage('问题').catch(() => {});

      expect(chatStore.error).toBe('网络连接失败');
    });

    it('失败时应移除已添加的用户消息', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('错误'));

      await chatStore.sendMessage('失败请求').catch(() => {});

      expect(chatStore.messages).toHaveLength(0);
    });

    it('失败时应抛出原始错误', async () => {
      const err = new Error('自定义错误');
      mockApiClient.post.mockRejectedValueOnce(err);

      await expect(chatStore.sendMessage('q')).rejects.toThrow('自定义错误');
    });

    it('发送前应清除之前的 error', async () => {
      chatStore.error = '旧的错误';
      mockApiClient.post.mockResolvedValueOnce({ answer: 'OK' });

      await chatStore.sendMessage('q');
      expect(chatStore.error).toBeNull();
    });

    it('无论成功失败，loading 应恢复 false', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('fail'));

      await chatStore.sendMessage('q').catch(() => {});
      expect(chatStore.loading).toBe(false);
    });

    it('失败时 error 不包含 undefined', async () => {
      mockApiClient.post.mockRejectedValueOnce({});

      await chatStore.sendMessage('q').catch(() => {});
      // 如果 error.message 为 undefined，默认为 '消息发送失败'
      expect(chatStore.error).toBeDefined();
    });
  });

  describe('消息数量限制', () => {
    it('超过最大消息数时应裁剪', async () => {
      // 预先填充接近极限的消息
      for (let i = 0; i < 100; i++) {
        chatStore.messages.push({ role: 'user', content: `msg${i}`, timestamp: i });
        chatStore.messages.push({ role: 'assistant', content: `reply${i}`, timestamp: i });
      }

      // 此时已经有 200 条消息（超过了默认的 MAX_MESSAGES=100）
      mockApiClient.post.mockResolvedValueOnce({ answer: 'Reply' });

      // 发送一条新消息
      await chatStore.sendMessage('new');

      // 裁剪后应保留最多 MAX_MESSAGES 条（默认 100）
      expect(chatStore.messages.length).toBeLessThanOrEqual(100);
      // 最后一条消息应该是刚发送的 AI 回复
      expect(chatStore.messages[chatStore.messages.length - 1].content).toBe('Reply');
    });
  });

  describe('clearMessages', () => {
    it('应清空所有消息', async () => {
      mockApiClient.post.mockResolvedValueOnce({ answer: 'Reply' });
      await chatStore.sendMessage('Hello');

      expect(chatStore.messages.length).toBeGreaterThan(0);

      chatStore.clearMessages();

      expect(chatStore.messages).toEqual([]);
      expect(chatStore.error).toBeNull();
    });
  });
});
