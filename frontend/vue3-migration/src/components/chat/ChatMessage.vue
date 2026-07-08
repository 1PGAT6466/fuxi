<!--
  @deprecated 请使用 ChatMessageBubble.vue 替代
  旧版消息组件 - 保留用于向后兼容，新功能请使用 ChatMessageBubble
-->
<template>
  <div class="message" :class="[message.role]">
    <div class="message-avatar">
      <el-icon v-if="message.role === 'user'" :size="20"><User /></el-icon>
      <el-icon v-else :size="20"><Monitor /></el-icon>
    </div>

    <div class="message-content">
      <div class="message-text" v-html="safeContent" />

      <div v-if="message.sources?.length" class="message-sources">
        <span class="sources-label">{{ t('chat.source') }}</span>
        <el-tag
          v-for="(source, index) in message.sources"
          :key="index"
          size="small"
          type="info"
          class="source-tag"
          >{{ source }}</el-tag
        >
      </div>

      <!-- SAG 检索追踪面板 (代理 trace 内的 SAG 层) -->
      <SAGTracePanel
        v-if="showSAGTrace"
        :trace="sagTrace"
        :loading="streaming"
      />

      <div class="message-meta">
        <span class="message-time">{{ formattedTime }}</span>
        <span v-if="confidencePercent != null" class="message-confidence">
          {{ t('chat.confidence') }}: {{ confidencePercent }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { renderMarkdown } from '@/utils/markdown';
import { User, Monitor } from '@element-plus/icons-vue';
import { formatTime } from '@/utils/helpers';
import { useChatStore } from '@/stores/chat';
import SAGTracePanel from './SAGTracePanel.vue';
import type { ChatMessage } from '@/types';

// 【修复 HIGH-3】显式导入 i18n 以替代模板中的 $t()
const { t } = useI18n();

const props = defineProps<{
  message: ChatMessage;
}>();

const chatStore = useChatStore();

// 使用共享的安全 Markdown 渲染工具
const safeContent = computed(() => renderMarkdown(props.message?.content));

const formattedTime = computed(() => formatTime(props.message?.timestamp));

const confidencePercent = computed(() => {
  // 使用 nullish check 处理 undefined 和 null（0 是合法值）
  if (props.message?.confidence == null) return null;
  return (props.message.confidence * 100).toFixed(0);
});

// SAG 追踪（仅对 AI 消息显示，且仅最后一个消息）
const sagTrace = computed(() => chatStore.sagTrace);
const streaming = computed(() => chatStore.streaming);
// 【修复 MEDIUM-8】仅最后一条 AI 消息才显示 SAG 追踪面板
const showSAGTrace = computed(() => {
  if (props.message.role !== 'assistant') return false;
  const messages = chatStore.messages;
  if (!messages || messages.length === 0) return false;
  const lastAssistantIdx = messages.map((m, i) => ({ m, i })).filter(x => x.m.role === 'assistant').pop()?.i;
  if (lastAssistantIdx === undefined) return false;
  const isLastAssistant = messages[lastAssistantIdx].timestamp === props.message.timestamp
    && messages[lastAssistantIdx].content === props.message.content;
  if (!isLastAssistant) return false;
  const trace = chatStore.sagTrace;
  return !!trace;
});
</script>

<style scoped lang="scss">
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;

  &.user {
    flex-direction: row-reverse;

    .message-content {
      background: var(--bubble-user);
      border-radius: 12px 12px 0 12px;
    }
  }

  &.assistant {
    .message-content {
      background: var(--bubble-assistant);
      border-radius: 12px 12px 12px 0;
    }
  }
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-secondary);
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
}

.message-text {
  line-height: 1.6;
  color: var(--text-primary);

  p {
    margin: 0 0 8px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  code {
    background: rgba(128, 128, 128, 0.15);
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 0.9em;
    color: var(--color-primary);
  }

  pre {
    background: var(--fuxi-bg, #FAFAF5);
    border: 1px solid var(--fuxi-border, #E8E4D9);
    color: var(--fuxi-text-primary, #333333);
    [data-theme='dark'] & {
      background: #1A1A2E;
      border-color: #333355;
      color: #E0E0E0;
    }
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;

    code {
      background: none;
      padding: 0;
      color: inherit;
    }
  }

  a {
    color: var(--color-primary);
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}

.message-sources {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color-light);

  .sources-label {
    font-size: 12px;
    color: var(--text-secondary);
    margin-right: 8px;
  }

  .source-tag {
    margin-right: 4px;
    margin-bottom: 4px;
  }
}

.message-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);

  .message-confidence {
    margin-left: 12px;
  }
}
</style>
