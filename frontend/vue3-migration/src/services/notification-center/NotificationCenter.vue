<!--
  伏羲 v2.1 — 通知中心页面
  P2 增强：推送通知
  功能：通知列表、已读/未读管理、推送订阅、通知设置
-->
<template>
  <div class="notif-center" role="region" aria-label="通知中心">
    <!-- ═══ 顶部标题栏 ═══ -->
    <header class="notif-header">
      <div class="notif-header-left">
        <h2 class="notif-title">
          <el-icon :size="20"><Bell /></el-icon>
          <span>通知中心</span>
        </h2>
        <el-badge
          v-if="store.unreadCount > 0"
          :value="store.unreadCount"
          :max="99"
          type="danger"
        />
      </div>
      <div class="notif-header-actions">
        <el-button
          size="small"
          text
          :disabled="!store.hasUnread"
          @click="handleMarkAllRead"
        >
          <el-icon :size="14"><Select /></el-icon>
          全部已读
        </el-button>
        <el-button size="small" text @click="showSettings = true">
          <el-icon :size="14"><Setting /></el-icon>
          设置
        </el-button>
        <el-button size="small" text @click="handleRefresh">
          <el-icon :size="14"><Refresh /></el-icon>
        </el-button>
      </div>
    </header>

    <!-- ═══ 过滤标签 ═══ -->
    <div class="notif-filters">
      <el-radio-group
        v-model="activeFilter"
        size="small"
        @change="handleFilterChange"
      >
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="unread">
          未读
          <span v-if="store.unreadCount > 0">({{ store.unreadCount }})</span>
        </el-radio-button>
      </el-radio-group>

      <el-select
        v-model="typeFilter"
        size="small"
        placeholder="按类型"
        clearable
        style="width: 120px"
        @change="handleFilterChange"
      >
        <el-option label="全部类型" value="" />
        <el-option label="信息" value="info" />
        <el-option label="警告" value="warning" />
        <el-option label="错误" value="error" />
        <el-option label="成功" value="success" />
      </el-select>
    </div>

    <!-- ═══ 加载状态 ═══ -->
    <div v-if="store.isLoading" class="notif-loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载通知...</span>
    </div>

    <!-- ═══ 空状态 ═══ -->
    <div v-else-if="filteredNotifications.length === 0" class="notif-empty">
      <el-icon :size="48"><Notification /></el-icon>
      <p>{{ activeFilter === 'unread' ? '所有通知已读' : '暂无通知' }}</p>
    </div>

    <!-- ═══ 通知列表 ═══ -->
    <div v-else class="notif-list" ref="listRef" @scroll="handleScroll">
      <template v-for="(label, dateGroup) in filteredGrouped" :key="dateGroup">
        <div class="notif-date-label">{{ label }}</div>
        <div
          v-for="item in filteredGrouped[dateGroup]"
          :key="item.id"
          class="notif-item"
          :class="{
            'notif-item--unread': !item.read,
            [`notif-item--${item.type}`]: true,
          }"
          role="listitem"
          tabindex="0"
          @click="handleItemClick(item)"
          @keydown.enter="handleItemClick(item)"
        >
          <div class="notif-item-dot">
            <span
              v-if="!item.read"
              class="notif-item-unread-dot"
              aria-label="未读"
            />
            <el-icon v-else :size="8"><Select /></el-icon>
          </div>
          <div class="notif-item-icon">
            <el-icon :size="18">
              <InfoFilled v-if="item.type === 'info'" />
              <WarningFilled v-if="item.type === 'warning'" />
              <CircleCloseFilled v-if="item.type === 'error'" />
              <CircleCheckFilled v-if="item.type === 'success'" />
            </el-icon>
          </div>
          <div class="notif-item-content">
            <div class="notif-item-title">{{ item.title }}</div>
            <div class="notif-item-body">{{ item.body }}</div>
            <div class="notif-item-time">{{ formatTime(item.created_at) }}</div>
          </div>
          <div class="notif-item-actions">
            <el-button
              v-if="!item.read"
              size="small"
              text
              circle
              @click.stop="handleMarkRead(item.id)"
              title="标记已读"
            >
              <el-icon :size="14"><Select /></el-icon>
            </el-button>
            <el-button
              size="small"
              text
              circle
              type="danger"
              @click.stop="handleDelete(item.id)"
              title="删除"
            >
              <el-icon :size="14"><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </template>
    </div>

    <!-- ═══ 底部分页 ═══ -->
    <div v-if="store.total > store.pageSize" class="notif-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="store.pageSize"
        :total="store.total"
        size="small"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- ═══ 设置抽屉 ═══ -->
    <NotificationSettings
      :visible="showSettings"
      @close="showSettings = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Bell,
  Select,
  Setting,
  Refresh,
  Loading,
  Notification,
  InfoFilled,
  WarningFilled,
  CircleCloseFilled,
  CircleCheckFilled,
  Delete,
} from '@element-plus/icons-vue';
import { useNotificationStore } from './store';
import NotificationSettings from './NotificationSettings.vue';

const store = useNotificationStore();

// ════════════════════════════════
// 过滤
// ════════════════════════════════

const activeFilter = ref<'all' | 'unread'>('all');
const typeFilter = ref('');
const showSettings = ref(false);
const currentPage = ref(1);
const listRef = ref<HTMLElement | null>(null);

const filteredNotifications = computed(() => {
  let list = store.notifications;

  if (activeFilter.value === 'unread') {
    list = list.filter((n) => !n.read);
  }

  if (typeFilter.value) {
    list = list.filter((n) => n.type === typeFilter.value);
  }

  return list;
});

const filteredGrouped = computed(() => {
  const groups: Record<string, typeof filteredNotifications.value> = {};
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const todayStr = today.toLocaleDateString('zh-CN');
  const yesterdayStr = yesterday.toLocaleDateString('zh-CN');

  for (const item of filteredNotifications.value) {
    const date = new Date(item.created_at).toLocaleDateString('zh-CN');
    let label: string;
    if (date === todayStr) {
      label = '今天';
    } else if (date === yesterdayStr) {
      label = '昨天';
    } else {
      label = date;
    }
    if (!groups[label]) groups[label] = [];
    groups[label].push(item);
  }
  return groups;
});

// ════════════════════════════════
// 格式化
// ════════════════════════════════

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;

  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} 天前`;

  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ════════════════════════════════
// 事件处理
// ════════════════════════════════

function handleFilterChange(): void {
  currentPage.value = 1;
}

async function handleRefresh(): Promise<void> {
  await store.loadNotifications(currentPage.value);
  ElMessage.success('已刷新');
}

async function handleItemClick(item: { id: string; read: boolean; data?: { url?: string } }): Promise<void> {
  if (!item.read) {
    await store.markRead(item.id);
  }
  // 如果有跳转链接，打开
  if (item.data?.url) {
    window.open(item.data.url, '_blank');
  }
}

async function handleMarkRead(id: string): Promise<void> {
  await store.markRead(id);
}

async function handleMarkAllRead(): Promise<void> {
  await store.markAllRead();
  ElMessage.success('已全部标为已读');
}

function handleDelete(id: string): void {
  ElMessage.info('删除功能即将上线');
}

function handlePageChange(page: number): void {
  currentPage.value = page;
  store.loadNotifications(page);
}

function handleScroll(): void {
  // 预留无限滚动位置
}

// ════════════════════════════════
// 初始化
// ════════════════════════════════

onMounted(() => {
  store.init();
});
</script>

<style scoped lang="scss">
.notif-center {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fuxi-bg-card, #ffffff);
  color: var(--fuxi-text, #333333);
  overflow: hidden;
}

/* ── 顶部 ── */
.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

.notif-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notif-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--fuxi-text, #333333);
}

.notif-header-actions {
  display: flex;
  gap: 4px;
}

/* ── 过滤器 ── */
.notif-filters {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

/* ── 加载/空状态 ── */
.notif-loading,
.notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);

  p {
    margin: 0;
    font-size: 14px;
  }
}

/* ── 通知列表 ── */
.notif-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 2px;
  }
  &::-webkit-scrollbar-track { background: transparent; }
}

.notif-date-label {
  padding: 12px 4px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: sticky;
  top: 0;
  background: var(--fuxi-bg-card, #ffffff);
  z-index: 1;
}

.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;

  &:hover {
    background: var(--fuxi-bg-subtle, #f0ede5);
  }

  &:focus-visible {
    outline: 2px solid var(--fuxi-primary, #ff6700);
    outline-offset: -2px;
  }

  &.notif-item--unread {
    background: var(--fuxi-bg-hover, #fff9f5);

    .notif-item-title {
      font-weight: 600;
    }
  }
}

.notif-item-dot {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 3px;
}

.notif-item-unread-dot {
  width: 8px;
  height: 8px;
  background: var(--fuxi-primary, #ff6700);
  border-radius: 50%;
}

.notif-item-icon {
  flex-shrink: 0;
  margin-top: 2px;

  .notif-item--info & { color: #409eff; }
  .notif-item--warning & { color: #e6a23c; }
  .notif-item--error & { color: #f56c6c; }
  .notif-item--success & { color: #67c23a; }
}

.notif-item-content {
  flex: 1;
  min-width: 0;
}

.notif-item-title {
  font-size: 14px;
  color: var(--fuxi-text, #333333);
  line-height: 1.4;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notif-item-body {
  font-size: 13px;
  color: var(--fuxi-text-secondary, #999999);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notif-item-time {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin-top: 4px;
}

.notif-item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.notif-item:hover .notif-item-actions {
  opacity: 1;
}

/* ── 分页 ── */
.notif-pagination {
  display: flex;
  justify-content: center;
  padding: 12px 0;
  border-top: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}
</style>
