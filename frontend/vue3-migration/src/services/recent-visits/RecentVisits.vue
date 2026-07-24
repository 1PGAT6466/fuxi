<template>
  <!--
    伏羲 v2.1 — 最近访问 / 历史记录页面
    P2 增强：访问追踪、类型筛选、快速跳转
    小米简约风
  -->
  <div class="recent-visits-page">
    <!-- ═══════════════════════════ 页头 ═══════════════════════════ -->
    <header class="page-header">
      <div class="header-left">
        <el-icon :size="22" color="#FF6700"><Timer /></el-icon>
        <h2 class="header-title">最近访问</h2>
        <el-tag v-if="store.localMode" type="warning" size="small" effect="plain">
          本地模式
        </el-tag>
      </div>
      <div class="header-right">
        <el-button
          v-if="store.hasVisits"
          text
          type="danger"
          size="small"
          :icon="Delete"
          @click="handleClearAll"
        >
          清除全部
        </el-button>
      </div>
    </header>

    <!-- ═══════════════════════════ 筛选栏 ═══════════════════════════ -->
    <div class="filter-bar">
      <el-radio-group
        v-model="activeFilter"
        size="small"
        @change="handleFilterChange"
      >
        <el-radio-button
          v-for="opt in TYPE_FILTER_OPTIONS"
          :key="opt.value"
          :value="opt.value"
        >
          <span class="filter-option">
            <el-icon :size="14" :color="opt.color">
              <component :is="opt.icon" />
            </el-icon>
            <span>{{ opt.label }}</span>
          </span>
        </el-radio-button>
      </el-radio-group>

      <span class="filter-count" v-if="!store.isLoading">
        共 {{ filteredVisits.length }} 条记录
      </span>
    </div>

    <!-- ═══════════════════════════ 加载中 ═══════════════════════════ -->
    <div v-if="store.isLoading" class="loading-container">
      <el-icon class="loading-icon" :size="28"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- ═══════════════════════════ 空状态 ═══════════════════════════ -->
    <div v-else-if="filteredVisits.length === 0" class="empty-state">
      <el-icon :size="56" color="#ccc"><Timer /></el-icon>
      <p class="empty-title">暂无访问记录</p>
      <p class="empty-desc">
        {{ store.error || '浏览对话、文档或知识库后，访问记录将显示在这里' }}
      </p>
      <el-button type="primary" size="small" @click="handleRefresh">
        刷新
      </el-button>
    </div>

    <!-- ═══════════════════════════ 访问列表 ═══════════════════════════ -->
    <div v-else class="visits-list">
      <TransitionGroup name="visit-list" tag="div" class="list-inner">
        <div
          v-for="record in filteredVisits"
          :key="record.id"
          class="visit-card"
          :class="{ 'visit-card--repeat': (record.visitCount || 1) > 1 }"
          role="listitem"
          tabindex="0"
          @click="handleJump(record)"
          @keydown.enter="handleJump(record)"
        >
          <!-- 类型图标 -->
          <div
            class="visit-type-icon"
            :style="{ background: getTypeColor(record.type) + '18', color: getTypeColor(record.type) }"
          >
            <el-icon :size="20">
              <component :is="getTypeIcon(record.type)" />
            </el-icon>
          </div>

          <!-- 内容区 -->
          <div class="visit-content">
            <div class="visit-title-row">
              <span class="visit-title">{{ record.title }}</span>
              <el-tag
                v-if="(record.visitCount || 1) > 1"
                size="small"
                type="info"
                effect="plain"
                class="visit-count-badge"
              >
                {{ record.visitCount }}次
              </el-tag>
            </div>
            <div class="visit-meta">
              <span
                class="visit-type-label"
                :style="{ color: getTypeColor(record.type) }"
              >
                {{ getTypeLabel(record.type) }}
              </span>
              <span class="visit-divider">·</span>
              <span class="visit-time" :title="formatFullTime(record.visitedAt)">
                {{ formatRelativeTime(record.visitedAt) }}
              </span>
              <span v-if="record.description" class="visit-description">
                {{ record.description }}
              </span>
            </div>
          </div>

          <!-- 操作区 -->
          <div class="visit-actions" @click.stop>
            <el-tooltip content="删除记录" placement="top">
              <button
                class="visit-action-btn"
                aria-label="删除记录"
                @click="handleDelete(record)"
              >
                <el-icon :size="16"><Close /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip content="跳转" placement="top">
              <button
                class="visit-action-btn visit-action-btn--primary"
                aria-label="跳转"
                @click="handleJump(record)"
              >
                <el-icon :size="16"><Right /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>
      </TransitionGroup>
    </div>

    <!-- ═══════════════════════════ 底部 ═══════════════════════════ -->
    <footer class="page-footer" v-if="store.total > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="store.total"
        layout="prev, pager, next"
        small
        background
        @current-change="handlePageChange"
      />
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Timer,
  Loading,
  Delete,
  Close,
  Right,
  ChatDotRound,
  Document,
  Collection,
  Grid,
} from '@element-plus/icons-vue';
import { useRecentVisitsStore } from './store';
import {
  TYPE_FILTER_OPTIONS,
  type VisitRecord,
  type VisitItemType,
} from './types';
import { VISIT_TYPE_LABELS, VISIT_TYPE_ICONS, VISIT_TYPE_COLORS } from './types';

// ══════════════════════════════════════
// Store & Router
// ══════════════════════════════════════

const store = useRecentVisitsStore();
const router = useRouter();

// ══════════════════════════════════════
// 筛选状态
// ══════════════════════════════════════

const activeFilter = ref<VisitItemType | 'all'>('all');
const currentPage = ref(1);
const pageSize = ref(20);

// ══════════════════════════════════════
// 计算属性
// ══════════════════════════════════════

const filteredVisits = computed(() => {
  let list = store.visits;
  if (activeFilter.value !== 'all') {
    list = list.filter((v) => v.type === activeFilter.value);
  }
  return list;
});

// ══════════════════════════════════════
// 工具函数
// ══════════════════════════════════════

function getTypeLabel(type: VisitItemType): string {
  return VISIT_TYPE_LABELS[type];
}

function getTypeIcon(type: VisitItemType): unknown {
  const iconName = VISIT_TYPE_ICONS[type];
  const iconMap: Record<string, unknown> = {
    ChatDotRound,
    Document,
    Collection,
  };
  return iconMap[iconName] || Document;
}

function getTypeColor(type: VisitItemType): string {
  return VISIT_TYPE_COLORS[type];
}

function formatRelativeTime(isoStr: string): string {
  const now = Date.now();
  const then = new Date(isoStr).getTime();
  const diff = now - then;

  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}小时前`;
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}天前`;

  const d = new Date(isoStr);
  const month = d.getMonth() + 1;
  const day = d.getDate();
  return `${month}月${day}日`;
}

function formatFullTime(isoStr: string): string {
  const d = new Date(isoStr);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hour = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${min}`;
}

function getJumpRoute(record: VisitRecord): string {
  if (record.route) return record.route;
  // 默认回退路由
  const fallback: Record<string, string> = {
    chat: '/chat',
    document: '/workspace/documents',
    knowledge_base: '/knowledge',
  };
  return fallback[record.type] || '/';
}

// ══════════════════════════════════════
// 事件处理
// ══════════════════════════════════════

function handleJump(record: VisitRecord): void {
  const route = getJumpRoute(record);
  router.push(route);
}

async function handleDelete(record: VisitRecord): Promise<void> {
  await store.deleteVisit(record.id);
}

async function handleClearAll(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '确定要清除所有访问记录吗？此操作不可恢复。',
      '确认清除',
      {
        confirmButtonText: '清除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
    await store.clearAllHistory();
    ElMessage.success('已清除所有访问记录');
  } catch {
    // 用户取消
  }
}

function handleFilterChange(): void {
  currentPage.value = 1;
}

function handlePageChange(page: number): void {
  currentPage.value = page;
}

async function handleRefresh(): Promise<void> {
  await store.loadRecentVisits(pageSize.value);
}

// ══════════════════════════════════════
// 生命周期
// ══════════════════════════════════════

onMounted(async () => {
  // 先秒开本地数据
  store.initFromLocal();
  // 再从后端加载
  await store.loadRecentVisits(pageSize.value);
});
</script>

<style scoped lang="scss">
/* ═══════════════════════════════════════
   RecentVisits — 最近访问页面
   小米简约风
   ═══════════════════════════════════════ */

.recent-visits-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 860px;
  margin: 0 auto;
  padding: var(--space-lg, 24px) var(--space-md, 16px);
}

/* ─── 页头 ─── */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md, 16px);
  padding-bottom: var(--space-sm, 8px);
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
  margin: 0;
}

.header-right {
  display: flex;
  gap: 8px;
}

/* ─── 筛选栏 ─── */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md, 16px);
  flex-wrap: wrap;
  gap: 12px;
}

.filter-option {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
}

.filter-count {
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

/* ─── 加载状态 ─── */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--fuxi-text-tertiary, #cccccc);
  gap: 12px;

  .loading-icon {
    animation: spin 1s linear infinite;
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ─── 空状态 ─── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  text-align: center;
  gap: 8px;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--fuxi-text-secondary, #999999);
  margin: 0;
}

.empty-desc {
  font-size: 13px;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin: 0 0 12px;
  max-width: 360px;
}

/* ─── 访问列表 ─── */
.visits-list {
  flex: 1;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 5px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 3px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

.list-inner {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ─── 访问卡片 ─── */
.visit-card {
  display: flex;
  align-items: center;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--fuxi-bg-card, #ffffff);
  border: 1px solid var(--fuxi-border, #eeeeee);
  cursor: pointer;
  transition: all 0.2s ease;
  gap: 12px;

  &:hover {
    border-color: var(--fuxi-primary, #FF6700);
    box-shadow: var(--fuxi-shadow-sm, 0 1px 6px rgba(0, 0, 0, 0.04));
    transform: translateX(2px);
  }

  &:focus-visible {
    outline: 2px solid var(--fuxi-primary, #FF6700);
    outline-offset: 2px;
  }

  &--repeat {
    border-left: 3px solid var(--fuxi-primary, #FF6700);
  }
}

/* 类型图标 */
.visit-type-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 内容区 */
.visit-content {
  flex: 1;
  min-width: 0;
}

.visit-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.visit-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--fuxi-text, #333333);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.visit-count-badge {
  flex-shrink: 0;
}

.visit-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  overflow: hidden;
}

.visit-type-label {
  font-weight: 500;
  flex-shrink: 0;
}

.visit-divider {
  color: var(--fuxi-text-tertiary, #cccccc);
}

.visit-time {
  color: var(--fuxi-text-tertiary, #cccccc);
  flex-shrink: 0;
}

.visit-description {
  color: var(--fuxi-text-secondary, #999999);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 操作区 */
.visit-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s ease;

  .visit-card:hover & {
    opacity: 1;
  }
}

.visit-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--fuxi-text-tertiary, #cccccc);
  transition: all 0.15s ease;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
    color: var(--fuxi-text, #333333);
  }

  &--primary:hover {
    background: var(--fuxi-primary-light, rgba(255, 103, 0, 0.08));
    color: var(--fuxi-primary, #FF6700);
  }
}

/* ─── 列表动画 ─── */
.visit-list-enter-active {
  transition: all 0.3s ease;
}
.visit-list-leave-active {
  transition: all 0.2s ease;
}
.visit-list-enter-from {
  opacity: 0;
  transform: translateX(-12px);
}
.visit-list-leave-to {
  opacity: 0;
  transform: translateX(12px);
}
.visit-list-move {
  transition: transform 0.3s ease;
}

/* ─── 页面底部 ─── */
.page-footer {
  display: flex;
  justify-content: center;
  padding: var(--space-md, 16px) 0 0;
  border-top: 1px solid var(--fuxi-border, #eeeeee);
  margin-top: var(--space-md, 16px);
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .recent-visits-page {
    padding: 16px 12px;
  }

  .header-title {
    font-size: 17px;
  }

  .visit-actions {
    opacity: 1;
  }

  .visit-meta {
    flex-wrap: wrap;
  }
}
</style>
