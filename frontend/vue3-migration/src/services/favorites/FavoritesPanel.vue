<!--
  伏羲 v2.1 — 收藏夹面板
  P2 增强：收藏夹/置顶功能
  功能：收藏列表展示、置顶标记、快速访问
-->
<template>
  <div class="favorites-panel" role="region" aria-label="收藏夹">
    <!-- ═══ 顶部标题栏 ═══ -->
    <header class="panel-header">
      <div class="panel-header-left">
        <h2 class="panel-title">
          <el-icon :size="20"><StarFilled /></el-icon>
          <span>收藏夹</span>
        </h2>
        <el-badge
          v-if="store.totalCount > 0"
          :value="store.totalCount"
          type="warning"
        />
      </div>
      <div class="panel-header-actions">
        <el-button size="small" text @click="handleRefresh">
          <el-icon :size="14"><Refresh /></el-icon>
        </el-button>
      </div>
    </header>

    <!-- ═══ 搜索框 ═══ -->
    <div class="panel-search">
      <el-input
        v-model="searchText"
        placeholder="搜索收藏..."
        size="small"
        clearable
        @input="handleSearch"
      >
        <template #prefix>
          <el-icon :size="14"><Search /></el-icon>
        </template>
      </el-input>
    </div>

    <!-- ═══ 类型过滤器 ═══ -->
    <div class="panel-filters">
      <el-radio-group
        v-model="activeType"
        size="small"
        @change="handleTypeChange"
      >
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="conversation">对话</el-radio-button>
        <el-radio-button value="document">文档</el-radio-button>
        <el-radio-button value="knowledge_base">知识库</el-radio-button>
      </el-radio-group>
    </div>

    <!-- ═══ 加载状态 ═══ -->
    <div v-if="store.isLoading" class="panel-loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载收藏...</span>
    </div>

    <!-- ═══ 错误状态 ═══ -->
    <div v-else-if="store.errorMessage" class="panel-error">
      <el-icon :size="32"><WarningFilled /></el-icon>
      <p>{{ store.errorMessage }}</p>
      <el-button size="small" type="primary" @click="handleRefresh">重试</el-button>
    </div>

    <!-- ═══ 空状态 ═══ -->
    <div v-else-if="store.filteredFavorites.length === 0 && store.pinned.length === 0" class="panel-empty">
      <el-icon :size="48"><Star /></el-icon>
      <p v-if="activeType">该类型暂无收藏</p>
      <p v-else>还没有收藏，去收藏一些内容吧</p>
      <p class="panel-empty-hint">点击对话/文档/知识库右上角的星标即可收藏</p>
    </div>

    <!-- ═══ 收藏列表 ═══ -->
    <div v-else class="panel-list" ref="listRef">
      <!-- ─── 置顶区域 ─── -->
      <template v-if="pinnedFiltered.length > 0">
        <div class="section-header">
          <el-icon :size="14"><Top /></el-icon>
          <span>置顶</span>
          <span class="section-count">{{ pinnedFiltered.length }}</span>
        </div>
        <div
          v-for="item in pinnedFiltered"
          :key="item.id"
          class="favorite-item favorite-item--pinned"
          role="listitem"
          tabindex="0"
          @click="handleItemClick(item)"
          @keydown.enter="handleItemClick(item)"
        >
          <div class="favorite-item-icon">
            <el-icon :size="18">
              <ChatDotRound v-if="item.type === 'conversation'" />
              <Document v-if="item.type === 'document'" />
              <Collection v-if="item.type === 'knowledge_base'" />
            </el-icon>
          </div>
          <div class="favorite-item-content">
            <div class="favorite-item-title">
              {{ item.title }}
              <el-tag size="small" type="warning" effect="plain" class="pinned-tag">
                <el-icon :size="10"><Top /></el-icon>
                置顶
              </el-tag>
            </div>
            <div v-if="item.summary" class="favorite-item-summary">
              {{ item.summary }}
            </div>
            <div class="favorite-item-meta">
              <span class="favorite-item-type">
                {{ TYPE_LABELS[item.type] || item.type }}
              </span>
              <span class="favorite-item-time">{{ formatRelativeTime(item.createdAt) }}</span>
            </div>
          </div>
          <div class="favorite-item-actions">
            <el-tooltip content="取消置顶" placement="top">
              <el-button
                size="small"
                text
                circle
                @click.stop="handleTogglePin(item)"
              >
                <el-icon :size="14"><Top /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="取消收藏" placement="top">
              <el-button
                size="small"
                text
                circle
                type="danger"
                @click.stop="handleRemoveFavorite(item)"
              >
                <el-icon :size="14"><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <!-- ─── 普通收藏区域 ─── -->
      <template v-if="unpinnedFiltered.length > 0">
        <div class="section-header" v-if="pinnedFiltered.length > 0">
          <el-icon :size="14"><Star /></el-icon>
          <span>收藏列表</span>
          <span class="section-count">{{ unpinnedFiltered.length }}</span>
        </div>
        <div
          v-for="item in unpinnedFiltered"
          :key="item.id"
          class="favorite-item"
          role="listitem"
          tabindex="0"
          @click="handleItemClick(item)"
          @keydown.enter="handleItemClick(item)"
        >
          <div class="favorite-item-icon">
            <el-icon :size="18">
              <ChatDotRound v-if="item.type === 'conversation'" />
              <Document v-if="item.type === 'document'" />
              <Collection v-if="item.type === 'knowledge_base'" />
            </el-icon>
          </div>
          <div class="favorite-item-content">
            <div class="favorite-item-title">{{ item.title }}</div>
            <div v-if="item.summary" class="favorite-item-summary">
              {{ item.summary }}
            </div>
            <div class="favorite-item-meta">
              <span class="favorite-item-type">
                {{ TYPE_LABELS[item.type] || item.type }}
              </span>
              <span class="favorite-item-time">{{ formatRelativeTime(item.createdAt) }}</span>
            </div>
          </div>
          <div class="favorite-item-actions">
            <el-tooltip content="置顶" placement="top">
              <el-button
                size="small"
                text
                circle
                @click.stop="handleTogglePin(item)"
              >
                <el-icon :size="14"><Top /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="取消收藏" placement="top">
              <el-button
                size="small"
                text
                circle
                type="danger"
                @click.stop="handleRemoveFavorite(item)"
              >
                <el-icon :size="14"><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  StarFilled,
  Star,
  Top,
  Refresh,
  Loading,
  WarningFilled,
  Search,
  ChatDotRound,
  Document,
  Collection,
  Delete,
} from '@element-plus/icons-vue';
import { useFavoritesStore } from './store';
import type { FavoriteItem, FavoriteType } from './types';
import { FAVORITE_TYPE_LABELS } from './types';

const TYPE_LABELS = FAVORITE_TYPE_LABELS;

const store = useFavoritesStore();

// ════════════════════════════════
// 本地状态
// ════════════════════════════════

const searchText = ref('');
const activeType = ref<string>('');
const listRef = ref<HTMLElement | null>(null);

// ════════════════════════════════
// 计算属性（面板内独立过滤置顶区域）
// ════════════════════════════════

/** 过滤后的置顶项 */
const pinnedFiltered = computed(() => {
  let list = store.pinned;
  if (activeType.value) {
    list = list.filter((f) => f.type === activeType.value);
  }
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase();
    list = list.filter(
      (f) =>
        f.title.toLowerCase().includes(q) ||
        f.summary.toLowerCase().includes(q),
    );
  }
  return list;
});

/** 过滤后的非置顶项 */
const unpinnedFiltered = computed(() => {
  return store.filteredFavorites.filter(
    (f) => !store.pinned.some((p) => p.itemId === f.itemId),
  );
});

// ════════════════════════════════
// 格式化
// ════════════════════════════════

function formatRelativeTime(dateStr: string): string {
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
  });
}

// ════════════════════════════════
// 事件处理
// ════════════════════════════════

function handleSearch(): void {
  store.setSearchQuery(searchText.value);
}

function handleTypeChange(val: string): void {
  store.setTypeFilter((val || null) as FavoriteType | null);
}

async function handleRefresh(): Promise<void> {
  await store.loadFavorites(store.activeTypeFilter || undefined);
  ElMessage.success('已刷新');
}

function handleItemClick(item: FavoriteItem): void {
  // 如果有跳转链接，打开
  if (item.url) {
    window.open(item.url, '_self');
    return;
  }

  // 否则发送导航事件（可由父组件或事件总线处理）
  if (item.type === 'conversation' && item.itemId) {
    ElMessage.info(`导航到对话: ${item.title}`);
  } else if (item.type === 'document' && item.itemId) {
    ElMessage.info(`导航到文档: ${item.title}`);
  } else if (item.type === 'knowledge_base' && item.itemId) {
    ElMessage.info(`导航到知识库: ${item.title}`);
  }
}

async function handleTogglePin(item: FavoriteItem): Promise<void> {
  const success = await store.togglePin(item.itemId);
  if (success) {
    const action = item.pinned ? '已取消置顶' : '已置顶';
    ElMessage.success(action);
  } else {
    ElMessage.error('操作失败');
  }
}

async function handleRemoveFavorite(item: FavoriteItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定取消收藏「${item.title}」？`,
      '取消收藏',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
    const success = await store.removeFavorite(item.itemId);
    if (success) {
      ElMessage.success('已取消收藏');
    } else {
      ElMessage.error('取消收藏失败');
    }
  } catch {
    // 用户取消操作
  }
}

// ════════════════════════════════
// props & emits
// ════════════════════════════════

const props = defineProps<{
  /** 用户 ID（可选，不传则从 store 获取） */
  userId?: string;
  /** 初始筛选类型 */
  initialType?: FavoriteType;
}>();

const emit = defineEmits<{
  /** 点击收藏项时触发 */
  'item-click': [item: FavoriteItem];
  /** 收藏变更时触发 */
  'favorite-changed': [event: { action: string; item: FavoriteItem }];
}>();

// ════════════════════════════════
// 初始化
// ════════════════════════════════

onMounted(async () => {
  if (props.userId) {
    store.setUser(props.userId);
  }
  if (props.initialType) {
    activeType.value = props.initialType;
    store.setTypeFilter(props.initialType);
  }
  await store.init(props.userId);
});

// 监听外部 userId 变化
watch(
  () => props.userId,
  (newId) => {
    if (newId) {
      store.setUser(newId);
      store.loadFavorites();
    }
  },
);

// 暴露搜索文本，供内部使用
defineExpose({
  searchText,
  refresh: handleRefresh,
});
</script>

<style scoped lang="scss">
.favorites-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fuxi-bg-card, #ffffff);
  color: var(--fuxi-text, #333333);
  overflow: hidden;
}

/* ── 顶部 ── */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

.panel-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--fuxi-text, #333333);
}

.panel-header-actions {
  display: flex;
  gap: 4px;
}

/* ── 搜索 ── */
.panel-search {
  padding: 8px 16px;
  flex-shrink: 0;
}

/* ── 过滤器 ── */
.panel-filters {
  padding: 6px 16px 8px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
}

/* ── 加载/空状态/错误 ── */
.panel-loading,
.panel-empty,
.panel-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-align: center;
  padding: 24px;

  p {
    margin: 0;
    font-size: 14px;
  }
}

.panel-empty-hint {
  font-size: 12px !important;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin-top: 4px;
}

.panel-error {
  color: var(--fuxi-error, #f56c6c);

  p {
    color: var(--fuxi-text-secondary, #999999);
  }
}

/* ── 列表 ── */
.panel-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 8px;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 2px;
  }
  &::-webkit-scrollbar-track { background: transparent; }
}

/* ── 区域标题 ── */
.section-header {
  display: flex;
  align-items: center;
  gap: 6px;
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

.section-count {
  font-weight: 400;
  color: var(--fuxi-text-tertiary, #cccccc);

  &::before {
    content: '(';
  }
  &::after {
    content: ')';
  }
}

/* ── 收藏项 ── */
.favorite-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
  margin-bottom: 2px;

  &:hover {
    background: var(--fuxi-bg-subtle, #f0ede5);

    .favorite-item-actions {
      opacity: 1;
    }
  }

  &:focus-visible {
    outline: 2px solid var(--fuxi-primary, #ff6700);
    outline-offset: -2px;
  }

  &.favorite-item--pinned {
    background: var(--fuxi-bg-hover, #fff9f5);
    border-left: 3px solid var(--fuxi-primary, #ff6700);
  }
}

.favorite-item-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--fuxi-primary, #ff6700);
}

.favorite-item-content {
  flex: 1;
  min-width: 0;
}

.favorite-item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--fuxi-text, #333333);
  line-height: 1.4;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pinned-tag {
  flex-shrink: 0;
  font-size: 11px;
}

.favorite-item-summary {
  font-size: 12px;
  color: var(--fuxi-text-secondary, #999999);
  line-height: 1.5;
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.favorite-item-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
}

.favorite-item-type {
  color: var(--fuxi-primary, #ff6700);
  background: var(--fuxi-primary-bg, #fef0e6);
  padding: 1px 6px;
  border-radius: 4px;
}

.favorite-item-time {
  color: var(--fuxi-text-tertiary, #cccccc);
}

.favorite-item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s ease;
}
</style>
