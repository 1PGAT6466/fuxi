<template>
  <div class="chat-container">
    <div ref="messagesContainer" class="chat-messages">
      <ChatMessage v-for="msg in chatStore.messages" :key="msg.timestamp" :message="msg" />

      <div v-if="chatStore.loading" class="typing-indicator">
        <span />
        <span />
        <span />
      </div>

      <div v-if="chatStore.error" class="chat-error" role="alert">
        <el-icon><WarningFilled /></el-icon>
        {{ chatStore.error }}
        <el-button size="small" type="primary" @click="retryLastMessage">
          {{ $t('chat.retry') }}
        </el-button>
      </div>
    </div>

    <ChatInput :disabled="chatStore.loading" @send="handleSend" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { useChatStore } from '@/stores/chat';
import { WarningFilled } from '@element-plus/icons-vue';
import ChatMessage from '@/components/chat/ChatMessage.vue';
import ChatInput from '@/components/chat/ChatInput.vue';
import { logger } from '@/utils/logger';

const chatStore = useChatStore();
const messagesContainer = ref<HTMLElement | null>(null);

// 【修复】仅 watch messages 的 length 变化，避免 deep: true 的大对象遍历
watch(
  () => chatStore.messages.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
      }
    });
  },
);

async function handleSend(query: string) {
  try {
    await chatStore.sendMessage(query);
  } catch (error) {
    logger.error('发送消息失败', error);
    ElMessage.error('发送消息失败，请稍后重试');
  }
}

// 重试最后一条消息
async function retryLastMessage() {
  const messages = chatStore.messages;
  if (messages.length >= 2) {
    // 首先获取最后一条用户消息（在弹出 AI 回复之前）
    const lastUserMsg = messages[messages.length - 2];
    // 移除最后一条 AI 回复
    messages.pop();
    if (lastUserMsg?.role === 'user') {
      try {
        await chatStore.sendMessage(lastUserMsg.content);
      } catch {
        // 错误已在 store 中处理
      }
    }
  }
}

// 暴露给测试的内部状态和方法
defineExpose({
  chatStore,
  handleSend,
  retryLastMessage,
});
</script>

<style scoped lang="scss">
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px;

  span {
    width: 8px;
    height: 8px;
    background: var(--text-tertiary);
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out;

    &:nth-child(1) {
      animation-delay: -0.32s;
    }
    &:nth-child(2) {
      animation-delay: -0.16s;
    }
  }
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.chat-error {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-error);
  border: 1px solid var(--border-error);
  border-radius: 8px;
  color: var(--color-danger);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
