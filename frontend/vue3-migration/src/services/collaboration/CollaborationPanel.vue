<!--
  伏羲 v2.1 — 实时协作面板
  功能：协作用户列表、光标位置显示、编辑历史、连接状态
-->
<template>
  <div class="collaboration-panel" role="complementary" aria-label="实时协作面板">
    <!-- ═══ 连接状态栏 ═══ -->
    <div class="connection-bar" :class="statusClass">
      <span class="connection-dot" />
      <span class="connection-text">{{ statusLabel }}</span>
      <span v-if="store.onlineCount > 0" class="online-badge">
        {{ store.onlineCount }} 人在线
      </span>
      <el-button
        v-if="connectionStatus === 'disconnected' || connectionStatus === 'error'"
        size="small"
        type="primary"
        text
        @click="handleReconnect"
      >
        重新连接
      </el-button>
    </div>

    <!-- ═══ 通知提示 ═══ -->
    <transition name="fade">
      <div v-if="store.notification" class="notification-bar" :class="`notification--${store.notification.type}`">
        {{ store.notification.message }}
      </div>
    </transition>

    <!-- ═══ Tab 切换 ═══ -->
    <div class="panel-tabs">
      <button
        class="panel-tab"
        :class="{ active: activeTab === 'users' }"
        @click="activeTab = 'users'"
      >
        <el-icon :size="14"><User /></el-icon>
        <span>协作者</span>
        <span v-if="store.participants.length > 0" class="tab-count">{{ store.participants.length }}</span>
      </button>
      <button
        class="panel-tab"
        :class="{ active: activeTab === 'history' }"
        @click="activeTab = 'history'"
      >
        <el-icon :size="14"><Clock /></el-icon>
        <span>历史</span>
        <span v-if="store.editHistory.length > 0" class="tab-count">{{ store.editHistory.length }}</span>
      </button>
    </div>

    <!-- ═══ 加载中 ═══ -->
    <div v-if="store.isConnecting" class="panel-loading">
      <el-icon class="is-loading" :size="20"><Loading /></el-icon>
      <span>正在连接协作服务器...</span>
    </div>

    <!-- ═══ 错误状态 ═══ -->
    <div v-else-if="store.errorMessage" class="panel-error">
      <el-icon :size="28"><WarningFilled /></el-icon>
      <p>{{ store.errorMessage }}</p>
      <el-button size="small" type="primary" @click="handleReconnect">重试</el-button>
    </div>

    <!-- ═══ 空状态 ═══ -->
    <div v-else-if="store.participants.length === 0 && connectionStatus !== 'connecting'" class="panel-empty">
      <el-icon :size="40"><Connection /></el-icon>
      <p>暂无协作者</p>
      <p class="panel-empty-hint">分享此文档链接，邀请他人协作编辑</p>
    </div>

    <!-- ═══ 内容区 ═══ -->
    <div v-else class="panel-content">
      <!-- ─── 协作者列表 ─── -->
      <div v-if="activeTab === 'users'" class="users-tab">
        <!-- 当前用户 -->
        <div class="section-label">我</div>
        <div class="user-item user-item--me">
          <div class="user-avatar" :style="{ background: myColor }">
            {{ avatarText(store.currentUserName) }}
          </div>
          <div class="user-info">
            <div class="user-name">
              {{ store.currentUserName || '我' }}
              <el-tag size="small" type="info" effect="plain" class="you-tag">你</el-tag>
            </div>
            <div class="user-cursor" v-if="myCursor">
              L{{ myCursor.line }}:C{{ myCursor.column }}
            </div>
          </div>
          <div class="user-status online" />
        </div>

        <!-- 其他用户 -->
        <template v-if="otherUsers.length > 0">
          <div class="section-label">
            协作者
            <span class="section-count">{{ otherUsers.length }}</span>
          </div>
          <div
            v-for="user in otherUsers"
            :key="user.userId"
            class="user-item"
          >
            <div class="user-avatar" :style="{ background: user.avatarColor }">
              {{ avatarText(user.userName) }}
            </div>
            <div class="user-info">
              <div class="user-name">{{ user.userName }}</div>
              <div class="user-cursor" v-if="getRemoteCursor(user.userId)">
                L{{ getRemoteCursor(user.userId)!.line }}:C{{ getRemoteCursor(user.userId)!.column }}
                <span v-if="getRemoteCursor(user.userId)!.selectionEnd" class="cursor-selection">
                  (已选择)
                </span>
              </div>
              <div v-else class="user-cursor idle">空闲</div>
            </div>
            <div
              class="user-status"
              :class="{ online: user.online }"
            />
          </div>
        </template>

        <!-- 光标覆盖层（在父组件编辑器区域显示） -->
        <div class="cursor-note">
          <el-icon :size="14"><Connection /></el-icon>
          光标将显示在编辑器中
        </div>
      </div>

      <!-- ─── 编辑历史 ─── -->
      <div v-if="activeTab === 'history'" class="history-tab">
        <div v-if="store.editHistory.length === 0" class="history-empty">
          <el-icon :size="32"><Clock /></el-icon>
          <p>暂无编辑记录</p>
        </div>
        <div
          v-for="op in store.editHistory"
          :key="op.id"
          class="history-item"
        >
          <div class="history-avatar" :style="{ background: getOpColor(op.userName) }">
            {{ avatarText(op.userName) }}
          </div>
          <div class="history-content">
            <div class="history-user">{{ op.userName }}</div>
            <div class="history-action">
              <el-tag
                :type="operationTagType(op.type)"
                size="small"
                effect="plain"
              >
                {{ operationLabel(op.type) }}
              </el-tag>
              <span v-if="op.summary" class="history-summary">{{ op.summary }}</span>
            </div>
            <div class="history-time">{{ formatTime(op.timestamp) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 底部操作 ═══ -->
    <div class="panel-footer">
      <el-button size="small" text @click="handleShare">
        <el-icon :size="14"><Share /></el-icon>
        分享链接
      </el-button>
      <el-button size="small" text type="danger" @click="handleLeave">
        <el-icon :size="14"><CloseBold /></el-icon>
        退出协作
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  User,
  Clock,
  Loading,
  WarningFilled,
  Connection,
  Share,
  CloseBold,
} from '@element-plus/icons-vue';
import { useCollaborationStore } from './store';
import type { ConnectionStatus, CursorPosition, EditOperationType } from './types';
import { COLLABORATOR_COLORS } from './types';

const store = useCollaborationStore();

// ════════════════════════════════
// Props & Emits
// ════════════════════════════════

const props = defineProps<{
  /** 文档 ID */
  documentId: string;
  /** 用户 ID */
  userId: string;
  /** 用户名 */
  userName: string;
  /** 房间 ID（可选，默认与 documentId 相同） */
  roomId?: string;
}>();

const emit = defineEmits<{
  /** 退出协作 */
  'leave': [];
  /** 分享 */
  'share': [url: string];
  /** 连接状态变化 */
  'connection-change': [status: ConnectionStatus];
}>();

// ════════════════════════════════
// 本地状态
// ════════════════════════════════

const activeTab = ref<'users' | 'history'>('users');
const myCursor = ref<CursorPosition | null>(null);

// ════════════════════════════════
// 计算属性
// ════════════════════════════════

const connectionStatus = computed(() => store.connectionStatus);

const statusClass = computed(() => {
  const map: Record<string, string> = {
    connected: 'status-connected',
    connecting: 'status-connecting',
    reconnecting: 'status-reconnecting',
    disconnected: 'status-disconnected',
    error: 'status-error',
  };
  return map[connectionStatus.value] || 'status-disconnected';
});

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    connected: '已连接',
    connecting: '连接中...',
    reconnecting: '重连中...',
    disconnected: '未连接',
    error: '连接失败',
  };
  return map[connectionStatus.value] || '未知';
});

const myColor = computed(() => {
  // 基于 userId 获取一致的颜色
  let hash = 0;
  const uid = props.userId || '';
  for (let i = 0; i < uid.length; i++) {
    hash = (hash * 31 + uid.charCodeAt(i)) & 0xffffffff;
  }
  return COLLABORATOR_COLORS[Math.abs(hash) % COLLABORATOR_COLORS.length];
});

const otherUsers = computed(() => store.otherParticipants);

// ════════════════════════════════
// 方法
// ════════════════════════════════

function avatarText(name: string): string {
  if (!name) return '?';
  // 取第一个字符（中文）或首字母大写（英文）
  const trimmed = name.trim();
  if (/[\u4e00-\u9fff]/.test(trimmed[0])) {
    return trimmed[0]; // 中文 → 取第一个字
  }
  return trimmed[0]?.toUpperCase() || '?';
}

function getRemoteCursor(userId: string): CursorPosition | undefined {
  return store.getCursor(userId);
}

function getOpColor(userName: string): string {
  let hash = 0;
  for (let i = 0; i < userName.length; i++) {
    hash = (hash * 31 + userName.charCodeAt(i)) & 0xffffffff;
  }
  return COLLABORATOR_COLORS[Math.abs(hash) % COLLABORATOR_COLORS.length];
}

function operationLabel(type: EditOperationType): string {
  const map: Record<string, string> = {
    insert: '插入',
    delete: '删除',
    replace: '替换',
  };
  return map[type] || type;
}

function operationTagType(type: EditOperationType): 'success' | 'danger' | 'warning' | 'info' {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    insert: 'success',
    delete: 'danger',
    replace: 'warning',
  };
  return map[type] || 'info';
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;

  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ════════════════════════════════
// 事件处理
// ════════════════════════════════

async function handleReconnect(): Promise<void> {
  await store.leaveRoom();
  await store.joinRoom(
    props.documentId,
    props.userId,
    props.userName,
    props.roomId,
  );
}

function handleShare(): void {
  const url = `${window.location.origin}/workspace/documents?collab=${props.documentId}`;
  emit('share', url);

  // 尝试复制到剪贴板
  navigator.clipboard.writeText(url).then(() => {
    ElMessage.success('协作链接已复制到剪贴板');
  }).catch(() => {
    ElMessage.info(`协作链接: ${url}`);
  });
}

function handleLeave(): void {
  store.leaveRoom();
  emit('leave');
}

// ════════════════════════════════
// 监听连接状态
// ════════════════════════════════

watch(connectionStatus, (newStatus) => {
  emit('connection-change', newStatus);
});

// ════════════════════════════════
// 生命周期
// ════════════════════════════════

onMounted(async () => {
  if (props.documentId && props.userId) {
    await store.joinRoom(
      props.documentId,
      props.userId,
      props.userName,
      props.roomId,
    );
  }
});

onUnmounted(() => {
  store.leaveRoom();
});

// 暴露给父组件的方法
defineExpose({
  activeTab,
  myCursor,
  refresh: handleReconnect,
});
</script>

<style scoped lang="scss">
.collaboration-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fuxi-bg-card, #ffffff);
  color: var(--fuxi-text, #333333);
  overflow: hidden;
  font-size: 13px;
}

/* ═══ 连接状态栏 ═══ */
.connection-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  flex-shrink: 0;
  font-size: 12px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);

  &.status-connected {
    background: var(--fuxi-success-bg, #f0f9f4);
    color: var(--fuxi-success, #52c41a);
  }

  &.status-connecting,
  &.status-reconnecting {
    background: var(--fuxi-warning-bg, #fefce8);
    color: var(--fuxi-warning, #faad14);
  }

  &.status-disconnected,
  &.status-error {
    background: var(--fuxi-danger-bg, #fff2f0);
    color: var(--fuxi-danger, #ff4d4f);
  }
}

.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;

  .status-connecting &,
  .status-reconnecting & {
    animation: pulse 1.5s ease-in-out infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.connection-text {
  flex: 1;
  font-weight: 500;
}

.online-badge {
  background: rgba(255, 255, 255, 0.5);
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

/* ═══ 通知提示 ═══ */
.notification-bar {
  padding: 6px 16px;
  font-size: 12px;
  text-align: center;
  flex-shrink: 0;

  &.notification--info { background: var(--el-color-info-light-9, #f0f5ff); color: var(--el-color-info, #909399); }
  &.notification--success { background: var(--el-color-success-light-9, #f0f9f4); color: var(--el-color-success, #52c41a); }
  &.notification--warning { background: var(--el-color-warning-light-9, #fefce8); color: var(--el-color-warning, #faad14); }
  &.notification--error { background: var(--el-color-danger-light-9, #fff2f0); color: var(--el-color-danger, #ff4d4f); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ═══ Tab 切换 ═══ */
.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

.panel-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  border: none;
  background: transparent;
  color: var(--fuxi-text-secondary, #999999);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;

  &:hover {
    color: var(--fuxi-text, #333333);
    background: var(--fuxi-bg-hover, #f5f5f5);
  }

  &.active {
    color: var(--fuxi-primary, #FF6700);
    font-weight: 600;

    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 20%;
      right: 20%;
      height: 2px;
      background: var(--fuxi-primary, #FF6700);
      border-radius: 1px;
    }
  }
}

.tab-count {
  background: var(--fuxi-bg-subtle, #f0ede5);
  color: var(--fuxi-text-secondary, #999999);
  font-size: 11px;
  padding: 0 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

/* ═══ 加载/错误/空状态 ═══ */
.panel-loading,
.panel-error,
.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 10px;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-align: center;
  padding: 24px;

  p {
    margin: 0;
    font-size: 13px;
  }
}

.panel-error {
  color: var(--fuxi-error, #f56c6c);

  p {
    color: var(--fuxi-text-secondary, #999999);
  }
}

.panel-empty-hint {
  font-size: 11px !important;
  color: var(--fuxi-text-tertiary, #cccccc);
}

/* ═══ 内容区 ═══ */
.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 2px;
  }
  &::-webkit-scrollbar-track { background: transparent; }
}

/* ═══ 区域标签 ═══ */
.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-count {
  font-weight: 400;

  &::before { content: '('; }
  &::after { content: ')'; }
}

/* ═══ 用户项 ═══ */
.user-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  transition: background 0.15s ease;

  &:hover {
    background: var(--fuxi-bg-hover, #f5f5f5);
  }

  &--me {
    background: var(--fuxi-primary-bg, #fef0e6);
  }
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--fuxi-text, #333333);
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.you-tag {
  font-size: 10px;
  padding: 0 4px;
}

.user-cursor {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin-top: 2px;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;

  &.idle {
    font-style: italic;
  }
}

.cursor-selection {
  color: var(--fuxi-primary, #FF6700);
  font-size: 10px;
}

.user-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--fuxi-border, #eeeeee);
  flex-shrink: 0;

  &.online {
    background: var(--fuxi-success, #52c41a);
  }
}

/* ═══ 光标提示 ═══ */
.cursor-note {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  margin: 8px 12px;
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  background: var(--fuxi-bg-subtle, #f0ede5);
  border-radius: 6px;
}

/* ═══ 编辑历史 ═══ */
.history-tab {
  padding: 0 12px;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--fuxi-text-tertiary, #cccccc);

  p { margin: 0; font-size: 13px; }
}

.history-item {
  display: flex;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);

  &:last-child {
    border-bottom: none;
  }
}

.history-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.history-content {
  flex: 1;
  min-width: 0;
}

.history-user {
  font-size: 12px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
  line-height: 1.4;
}

.history-action {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.history-summary {
  font-size: 11px;
  color: var(--fuxi-text-secondary, #999999);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-time {
  font-size: 10px;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin-top: 3px;
}

/* ═══ 底部操作 ═══ */
.panel-footer {
  display: flex;
  justify-content: space-between;
  padding: 10px 16px;
  border-top: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
  background: var(--fuxi-bg-card, #ffffff);
}
</style>
