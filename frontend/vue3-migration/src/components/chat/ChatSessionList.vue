<!--
  伏羲 v2.1 — 会话列表组件
  显示最近会话，支持新建/切换/删除
-->
<template>
  <div class="session-list" :class="{ collapsed }">
    <!-- 新建会话按钮 -->
    <button class="new-session-btn" @click="$emit('newSession')">
      <el-icon :size="16"><Plus /></el-icon>
      <span v-if="!collapsed">新建会话</span>
    </button>

    <!-- 会话列表 -->
    <div v-if="!collapsed" class="session-items">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === activeSessionId }"
        @click="$emit('select', session.id)"
      >
        <div class="session-item-content">
          <div class="session-title">{{ session.title || '新对话' }}</div>
          <div class="session-preview">{{ session.lastMessage || '暂无消息' }}</div>
          <div class="session-meta">
            <span class="session-time">{{ formatDate(session.updatedAt) }}</span>
            <span class="session-count">{{ session.messageCount }} 条</span>
          </div>
        </div>
        <el-popconfirm
          title="确定删除此会话？"
          confirm-button-text="确定"
          cancel-button-text="取消"
          @confirm="$emit('delete', session.id)"
        >
          <template #reference>
            <button class="session-delete-btn" @click.stop>
              <el-icon :size="14"><Delete /></el-icon>
            </button>
          </template>
        </el-popconfirm>
      </div>

      <el-empty v-if="sessions.length === 0" description="暂无会话" :image-size="60" />
    </div>

    <!-- 折叠态：仅显示图标 -->
    <div v-else class="session-collapsed-icons">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-icon-dot"
        :class="{ active: session.id === activeSessionId }"
        :title="session.title"
        @click="$emit('select', session.id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, Delete } from '@element-plus/icons-vue';
import type { ChatSession } from '@/types';
import { formatDate } from '@/utils/helpers';

defineProps<{
  sessions: ChatSession[];
  activeSessionId: string | null;
  collapsed?: boolean;
}>();

defineEmits<{
  newSession: [];
  select: [sessionId: string];
  delete: [sessionId: string];
}>();
</script>

<style scoped lang="scss">
.session-list {
  display: flex;
  flex-direction: column;
  width: 240px;
  height: 100%;
  background: var(--fuxi-bg-card);
  border-right: 1px solid var(--fuxi-border);
  transition: width 0.25s var(--ease-in-out);
  overflow: hidden;

  &.collapsed {
    width: 56px;
  }
}

.new-session-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px;
  padding: 10px 16px;
  border: 2px dashed var(--fuxi-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--fuxi-primary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  white-space: nowrap;

  &:hover {
    background: var(--fuxi-primary-light);
    border-color: var(--fuxi-primary);
  }

  .collapsed & {
    justify-content: center;
    padding: 10px;
    border-style: solid;
  }
}

.session-items {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border);
    border-radius: 2px;
  }
}

.session-item {
  display: flex;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.2s var(--ease-out);
  margin-bottom: 4px;
  position: relative;

  &:hover {
    background: var(--fuxi-bg-hover);

    .session-delete-btn {
      opacity: 1;
    }
  }

  &.active {
    background: var(--fuxi-primary-light);
  }
}

.session-item-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--fuxi-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-preview {
  font-size: 12px;
  color: var(--fuxi-text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
}

.session-delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--fuxi-text-tertiary);
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
  flex-shrink: 0;
  margin-left: 4px;
  margin-top: 2px;

  &:hover {
    background: var(--fuxi-error-bg);
    color: var(--fuxi-error);
  }
}

.session-collapsed-icons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  overflow-y: auto;
}

.session-icon-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--fuxi-border);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: var(--fuxi-primary);
  }

  &.active {
    background: var(--fuxi-primary);
    box-shadow: 0 0 6px var(--fuxi-primary);
  }
}
</style>
