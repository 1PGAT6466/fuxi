<!--
  伏羲 v2.1 — 聊天输入框（增强版）
  支持 Enter 发送、Shift+Enter 换行、中英输入法兼容
-->
<template>
  <div class="chat-input-v2">
    <div class="input-wrapper">
      <el-input
        v-model="query"
        type="textarea"
        :rows="1"
        :autosize="{ minRows: 1, maxRows: 5 }"
        placeholder="输入消息... (Shift+Enter 换行)"
        :disabled="disabled"
        resize="none"
        @keydown="handleKeydown"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
      />

      <button
        class="send-btn"
        :disabled="!query.trim() || disabled"
        :class="{ loading: disabled }"
        title="发送消息"
        @click="handleSend"
      >
        <el-icon v-if="!disabled" :size="18"><Promotion /></el-icon>
        <div v-else class="send-spinner" />
      </button>
    </div>

    <div class="input-hint">
      <span>Enter 发送 · Shift+Enter 换行</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Promotion } from '@element-plus/icons-vue';

const props = defineProps<{
  disabled?: boolean;
}>();

const emit = defineEmits<{
  send: [query: string];
}>();

const query = ref('');
const isComposing = ref(false);

function handleKeydown(event: KeyboardEvent): void {
  // 输入法组合中不触发
  if (isComposing.value) return;

  // Enter（非 Shift）发送消息
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

function handleSend(): void {
  const text = query.value.trim();
  if (!text || props.disabled) return;

  emit('send', text);
  query.value = '';
}

defineExpose({ query });
</script>

<style scoped lang="scss">
.chat-input-v2 {
  padding: 12px 16px 16px;
  background: var(--fuxi-bg-card);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--fuxi-bg-subtle);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-md);
  padding: 6px 8px;
  transition: border-color 0.2s var(--ease-out);

  &:focus-within {
    border-color: var(--fuxi-primary);
    box-shadow: 0 0 0 3px var(--fuxi-primary-light);
  }

  :deep(.el-textarea) {
    flex: 1;

    .el-textarea__inner {
      background: transparent;
      border: none;
      box-shadow: none;
      font-size: 14px;
      line-height: 1.5;
      padding: 4px 8px;
      resize: none;
      color: var(--fuxi-text);

      &::placeholder {
        color: var(--fuxi-text-tertiary);
      }
    }
  }
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--fuxi-primary-gradient);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  flex-shrink: 0;

  &:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 2px 12px rgba(255, 103, 0, 0.3);
  }

  &:disabled {
    background: var(--fuxi-bg-subtle);
    color: var(--fuxi-text-tertiary);
    cursor: not-allowed;
  }

  &.loading {
    background: var(--fuxi-primary-light);
  }
}

.send-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--fuxi-border);
  border-top-color: var(--fuxi-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.input-hint {
  margin-top: 6px;
  text-align: center;

  span {
    font-size: 11px;
    color: var(--fuxi-text-tertiary);
  }
}
</style>
