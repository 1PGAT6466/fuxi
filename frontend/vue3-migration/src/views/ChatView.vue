<!--
  伏羲 v2.1 — 对话工作台 ChatView
  左侧会话列表（可折叠 240px） + 右侧消息区域
  支持 SSE 流式输出、Markdown 渲染、引用溯源
  适配小米简约风
-->
<template>
  <div class="chat-view">
    <!-- 会话列表（左侧） -->
    <div class="chat-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <ChatSessionList
        :sessions="chatStore.sessions"
        :active-session-id="chatStore.activeSessionId"
        :collapsed="sidebarCollapsed"
        @new-session="handleNewSession"
        @select="chatStore.switchSession"
        @delete="handleDeleteSession"
      />
    </div>

    <!-- 折叠切换按钮 -->
    <button
      class="sidebar-toggle"
      :title="sidebarCollapsed ? '展开会话列表' : '折叠会话列表'"
      @click="sidebarCollapsed = !sidebarCollapsed"
    >
      <el-icon :size="16">
        <ArrowLeft v-if="!sidebarCollapsed" />
        <ArrowRight v-else />
      </el-icon>
    </button>

    <!-- 消息区域（右侧） -->
    <div class="chat-main">
      <!-- 无会话空状态 -->
      <div v-if="!chatStore.activeSessionId" class="chat-empty">
        <div class="empty-icon">
          <div class="bagua-ring">
            <span class="bagua-core">☰</span>
          </div>
        </div>
        <h2 class="empty-title">伏羲 · 智能对话</h2>
        <p class="empty-desc">选择已有会话或新建对话，开始提问</p>
        <el-button type="primary" size="large" :icon="Plus" @click="handleNewSession">
          新建会话
        </el-button>
      </div>

      <!-- 有会话 -->
      <template v-else>
        <!-- 顶部标题栏 -->
        <div class="chat-header">
          <div class="chat-header-info">
            <h3 class="chat-session-title">
              {{ chatStore.activeSession?.title || '新对话' }}
            </h3>
            <span v-if="chatStore.activeSession" class="chat-session-meta">
              {{ chatStore.activeSession.messageCount }} 条消息
            </span>
          </div>
          <div class="chat-header-actions">
            <el-button text :icon="Delete" @click="handleDeleteSession(chatStore.activeSessionId!)">
              清空会话
            </el-button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div ref="messagesContainer" class="chat-messages" @scroll="handleScroll">
          <ChatMessageBubble
            v-for="(msg, idx) in chatStore.messages"
            :key="`${msg.timestamp}-${idx}`"
            :message="msg"
          />

          <!-- 流式指示器 -->
          <StreamingIndicator v-if="chatStore.streaming" />

          <!-- 错误信息 -->
          <div v-if="chatStore.error" class="chat-error" role="alert">
            <div class="error-content">
              <el-icon :size="16"><WarningFilled /></el-icon>
              <span>{{ chatStore.error }}</span>
            </div>
            <el-button size="small" type="primary" @click="chatStore.retryLastMessage()">
              重试
            </el-button>
          </div>

          <!-- 底部占位确保滚动 -->
          <div ref="scrollAnchor" class="scroll-anchor" />
        </div>

        <!-- 输入框 -->
        <ChatInput :disabled="chatStore.streaming" @send="handleSend" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { createLogger } from '@/utils/logger';
const logger = createLogger('ChatView');
import { Plus, Delete, ArrowLeft, ArrowRight, WarningFilled } from '@element-plus/icons-vue';
import { useChatStore } from '@/stores/chat';
import ChatSessionList from '@/components/chat/ChatSessionList.vue';
import ChatMessageBubble from '@/components/chat/ChatMessageBubble.vue';
import ChatInput from '@/components/chat/ChatInput.vue';
import StreamingIndicator from '@/components/chat/StreamingIndicator.vue';

const chatStore = useChatStore();
const sidebarCollapsed = ref(false);
const messagesContainer = ref<HTMLElement | null>(null);
const scrollAnchor = ref<HTMLElement | null>(null);
const isNearBottom = ref(true);

// ============================
// 会话操作
// ============================

async function handleNewSession(): Promise<void> {
  try {
    await chatStore.addSession();
  } catch (error) {
    logger.error('创建会话失败', error);
    ElMessage.error('创建会话失败，请稍后重试');
  }
}

async function handleDeleteSession(sessionId: string): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要删除此会话吗？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await chatStore.removeSession(sessionId);
  } catch {
    // 用户取消
  }
}

// ============================
// 消息发送
// ============================

async function handleSend(query: string): Promise<void> {
  try {
    // 如果没有活跃会话，先创建
    if (!chatStore.activeSessionId) {
      await chatStore.addSession(query.slice(0, 20));
    }
    await chatStore.sendMessage(query);
  } catch (error) {
    logger.error('发送消息失败', error);
    ElMessage.error('发送消息失败，请稍后重试');
  }
}

// ============================
// 自动滚动
// ============================

function scrollToBottom(): void {
  nextTick(() => {
    if (scrollAnchor.value) {
      scrollAnchor.value.scrollIntoView({ behavior: 'smooth' });
    }
  });
}

function handleScroll(): void {
  if (!messagesContainer.value) return;
  const el = messagesContainer.value;
  const threshold = 80;
  isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

// 消息变化时自动滚动（用户消息或新 AI 回复）
watch(
  () => chatStore.messages.length,
  () => {
    if (isNearBottom.value) {
      scrollToBottom();
    }
  },
);

// 流式内容更新时持续滚动
watch(
  () => {
    const msgs = chatStore.messages;
    if (msgs.length === 0) return '';
    const last = msgs[msgs.length - 1];
    return last.content;
  },
  () => {
    if (isNearBottom.value && chatStore.streaming) {
      nextTick(() => {
        if (scrollAnchor.value) {
          scrollAnchor.value.scrollIntoView({ behavior: 'auto' });
        }
      });
    }
  },
);

// ============================
// 生命周期
// ============================

onMounted(() => {
  chatStore.loadSessions();
});

onUnmounted(() => {
  chatStore.cancelStream();
});
</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  height: 100%;
  background: var(--fuxi-bg);
  position: relative;
  overflow: hidden;
}

/* ───── 侧边栏 ───── */

.chat-sidebar {
  height: 100%;
  flex-shrink: 0;
  transition: width 0.25s var(--ease-in-out);
  overflow: hidden;
  z-index: 2;

  &.collapsed {
    width: 56px;
  }
}

/* ───── 折叠切换按钮 ───── */

.sidebar-toggle {
  position: absolute;
  left: 240px;
  bottom: 32px;
  width: 24px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--fuxi-border);
  border-left: none;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--fuxi-bg-card);
  color: var(--fuxi-text-secondary);
  cursor: pointer;
  transition: all 0.25s var(--ease-in-out);
  z-index: 3;
  padding: 0;

  &:hover {
    color: var(--fuxi-primary);
    background: var(--fuxi-primary-light);
  }
}

.chat-sidebar.collapsed ~ .sidebar-toggle {
  left: 56px;
}

/* ───── 主区域 ───── */

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
}

/* ───── 空状态 ───── */

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 64px;
}

.empty-icon {
  margin-bottom: 8px;
}

.bagua-ring {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--fuxi-primary-light), var(--qian-color-light));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--fuxi-shadow);

  .bagua-core {
    font-size: 32px;
    color: var(--fuxi-primary);
  }
}

.empty-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--fuxi-text);
  margin: 0;
}

.empty-desc {
  font-size: 14px;
  color: var(--fuxi-text-secondary);
  margin: 0;
}

/* ───── 顶部标题栏 ───── */

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--fuxi-bg-card);
  border-bottom: 1px solid var(--fuxi-border);
  flex-shrink: 0;
}

.chat-header-info {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.chat-session-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--fuxi-text);
  margin: 0;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-session-meta {
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
}

/* ───── 消息列表 ───── */

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  scroll-behavior: smooth;

  &::-webkit-scrollbar {
    width: 5px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border);
    border-radius: 3px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

.scroll-anchor {
  height: 1px;
}

/* ───── 错误状态 ───── */

.chat-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin: 8px 0;
  background: var(--fuxi-error-bg);
  border: 1px solid rgba(255, 59, 48, 0.2);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.error-content {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--fuxi-error);
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .chat-view {
    flex-direction: column;
  }

  .chat-sidebar {
    width: 100% !important;
    height: auto;
    max-height: 50vh;

    &.collapsed {
      width: 100% !important;
      height: 0;
    }
  }

  .chat-main {
    flex: 1;
    min-width: 0;
  }

  .sidebar-toggle {
    left: auto !important;
    right: 16px;
    top: 4px;
    bottom: auto;
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--fuxi-border);
  }

  .chat-empty {
    padding: 32px 16px;
  }

  .chat-header {
    padding: 10px 16px;
  }

  .chat-session-title {
    max-width: 180px;
  }

  .chat-messages {
    padding: 16px;
  }
}
</style>
