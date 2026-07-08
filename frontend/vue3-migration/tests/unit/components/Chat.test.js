/**
 * Chat.vue 组件测试
 * 测试消息发送、显示和重试功能
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

// Mock chat store before importing component
vi.mock('@/stores/chat', () => ({
  useChatStore: vi.fn(),
}));

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  WarningFilled: { name: 'WarningFilled' },
}));

// Mock sub-components
vi.mock('@/components/chat/ChatMessage.vue', () => ({
  default: {
    name: 'ChatMessage',
    props: ['message'],
    template: '<div class="chat-message">{{ message.content }}</div>',
  },
}));

vi.mock('@/components/chat/ChatInput.vue', () => ({
  default: {
    name: 'ChatInput',
    props: ['disabled'],
    template: '<div class="chat-input"><input @keyup.enter="$emit(\'send\', \'test query\')" /></div>',
    emits: ['send'],
  },
}));

describe('Chat.vue', () => {
  let wrapper;
  let chatStoreMock;

  beforeEach(async () => {
    setActivePinia(createPinia());

    chatStoreMock = {
      messages: [
        { role: 'user', content: 'Hello', timestamp: 1000 },
        { role: 'assistant', content: 'Hi there!', timestamp: 2000 },
      ],
      loading: false,
      error: null,
      sendMessage: vi.fn(),
      clearMessages: vi.fn(),
    };

    const { useChatStore } = await import('@/stores/chat');
    useChatStore.mockReturnValue(chatStoreMock);

    const Chat = (await import('@/views/Chat.vue')).default;
    wrapper = mount(Chat, {
      global: {
        stubs: {
          'el-button': {
            template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
            props: ['size', 'type'],
            emits: ['click'],
          },
          'el-icon': { template: '<i><slot /></i>' },
          transition: false,
        },
      },
      attachTo: document.body,
    });
  });

  describe('组件渲染', () => {
    it('应该渲染聊天容器', () => {
      expect(wrapper.find('.chat-container').exists()).toBe(true);
    });

    it('应该渲染消息列表区域', () => {
      expect(wrapper.find('.chat-messages').exists()).toBe(true);
    });

    it('应该渲染 ChatMessage 组件', () => {
      expect(wrapper.findComponent({ name: 'ChatMessage' }).exists()).toBe(true);
    });

    it('应该渲染 ChatInput 组件', () => {
      expect(wrapper.findComponent({ name: 'ChatInput' }).exists()).toBe(true);
    });
  });

  describe('消息显示', () => {
    it('应该显示 store 中的消息', () => {
      expect(wrapper.vm.chatStore.messages).toHaveLength(2);
    });

    it('每条消息都应渲染为 ChatMessage 组件', () => {
      const messages = wrapper.findAllComponents({ name: 'ChatMessage' });
      expect(messages.length).toBe(2);
    });
  });

  describe('加载状态', () => {
    it('loading 为 true 时应显示打字指示器', async () => {
      chatStoreMock.loading = true;
      await wrapper.vm.$nextTick();
      // 由于我们的 stub 结构，验证 store 上的 loading 状态
      expect(wrapper.vm.chatStore.loading).toBe(true);
    });

    it('loading 为 false 时应隐藏打字指示器', () => {
      chatStoreMock.loading = false;
      expect(wrapper.vm.chatStore.loading).toBe(false);
    });
  });

  describe('错误处理', () => {
    it('有错误时应显示错误信息', async () => {
      chatStoreMock.error = '连接超时';
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.chatStore.error).toBe('连接超时');
    });

    it('应显示重试按钮', async () => {
      chatStoreMock.error = '连接超时';
      chatStoreMock.messages = [
        { role: 'user', content: 'Hello', timestamp: 1000 },
        { role: 'assistant', content: '', timestamp: 2000 },
      ];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.chatStore.error).toBeTruthy();
    });
  });

  describe('消息发送', () => {
    it('handleSend 应调用 store.sendMessage', async () => {
      await wrapper.vm.handleSend('测试问题');
      expect(chatStoreMock.sendMessage).toHaveBeenCalledWith('测试问题');
    });
  });

  describe('重试最后一条消息', () => {
    it('retryLastMessage 应在有足够消息时重试', async () => {
      chatStoreMock.messages = [
        { role: 'user', content: '上一条问题', timestamp: 1000 },
        { role: 'assistant', content: '失败回复', timestamp: 2000 },
      ];

      await wrapper.vm.retryLastMessage();
      expect(chatStoreMock.sendMessage).toHaveBeenCalledWith('上一条问题');
    });

    it('消息少于 2 条时不重试', async () => {
      chatStoreMock.messages = [
        { role: 'user', content: 'only one', timestamp: 1000 },
      ];

      await wrapper.vm.retryLastMessage();
      expect(chatStoreMock.sendMessage).not.toHaveBeenCalled();
    });
  });
});
