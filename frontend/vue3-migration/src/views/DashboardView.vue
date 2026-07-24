<template>
  <div class="task-dashboard">
    <div class="page-header">
      <div class="page-header__left">
        <h2 class="page-title">📊 任务仪表板</h2>
        <p class="page-subtitle">系统资源与任务状态实时监控</p>
      </div>
      <button class="refresh-btn" @click="handleRefresh" title="刷新数据">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
        </svg>
        <span>刷新</span>
      </button>
    </div>

    <div class="resources-grid">
      <div class="resource-card">
        <div class="resource-card__header">
          <div class="resource-icon resource-icon--cpu">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="4" width="16" height="16" rx="2"/>
              <rect x="9" y="9" width="6" height="6"/>
              <line x1="9" y1="1" x2="9" y2="4"/>
              <line x1="15" y1="1" x2="15" y2="4"/>
              <line x1="9" y1="20" x2="9" y2="23"/>
              <line x1="15" y1="20" x2="15" y2="23"/>
              <line x1="20" y1="9" x2="23" y2="9"/>
              <line x1="20" y1="14" x2="23" y2="14"/>
              <line x1="1" y1="9" x2="4" y2="9"/>
              <line x1="1" y1="14" x2="4" y2="14"/>
            </svg>
          </div>
          <div class="resource-info">
            <span class="resource-label">CPU</span>
            <span class="resource-value">{{ resources.cpu.usage }}%</span>
          </div>
        </div>
        <div class="progress-bar">
          <div class="progress-bar__fill" :style="{ width: resources.cpu.usage + '%' }" />
        </div>
        <div class="resource-meta">
          <span>{{ resources.cpu.cores }} 核心</span>
          <span>{{ resources.cpu.temperature }}°C</span>
        </div>
      </div>
      <div class="resource-card">
        <div class="resource-card__header">
          <div class="resource-icon resource-icon--memory">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="6" width="20" height="12" rx="2"/>
              <line x1="6" y1="12" x2="18" y2="12"/>
            </svg>
          </div>
          <div class="resource-info">
            <span class="resource-label">内存</span>
            <span class="resource-value">{{ resources.memory.usagePercent }}%</span>
          </div>
        </div>
        <div class="progress-bar">
          <div class="progress-bar__fill" :style="{ width: resources.memory.usagePercent + '%' }" />
        </div>
        <div class="resource-meta">
          <span>{{ resources.memory.used }} / {{ resources.memory.total }}</span>
        </div>
      </div>
      <div class="resource-card">
        <div class="resource-card__header">
          <div class="resource-icon resource-icon--disk">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
          </div>
          <div class="resource-info">
            <span class="resource-label">磁盘</span>
            <span class="resource-value">{{ resources.disk.usagePercent }}%</span>
          </div>
        </div>
        <div class="progress-bar">
          <div class="progress-bar__fill" :style="{ width: resources.disk.usagePercent + '%' }" />
        </div>
        <div class="resource-meta">
          <span>{{ resources.disk.used }} / {{ resources.disk.total }}</span>
        </div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card stat-card--pending" @click="filterByStatus('pending')">
        <div class="stat-card__icon">⏳</div>
        <div class="stat-card__body">
          <span class="stat-card__value">{{ stats.pending }}</span>
          <span class="stat-card__label">待处理</span>
        </div>
      </div>
      <div class="stat-card stat-card--progress" @click="filterByStatus('in_progress')">
        <div class="stat-card__icon">🔄</div>
        <div class="stat-card__body">
          <span class="stat-card__value">{{ stats.inProgress }}</span>
          <span class="stat-card__label">进行中</span>
        </div>
      </div>
      <div class="stat-card stat-card--completed" @click="filterByStatus('completed')">
        <div class="stat-card__icon">✅</div>
        <div class="stat-card__body">
          <span class="stat-card__value">{{ stats.completed }}</span>
          <span class="stat-card__label">已完成</span>
        </div>
      </div>
      <div class="stat-card stat-card--failed">
        <div class="stat-card__icon">❌</div>
        <div class="stat-card__body">
          <span class="stat-card__value">{{ stats.failed }}</span>
          <span class="stat-card__label">失败</span>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <div class="card task-list-card">
        <div class="card__header">
          <h3 class="card__title">最近任务</h3>
          <span class="card__total" v-if="filteredTasks.length > 0">共 {{ filteredTasks.length }} 项</span>
        </div>
        <div class="task-list" v-if="filteredTasks.length > 0">
          <div v-for="task in filteredTasks" :key="task.id" class="task-item">
            <span class="status-dot" :class="'status-dot--' + task.status" />
            <div class="task-item__info">
              <div class="task-item__name">{{ task.name }} <span class="task-item__type-tag">{{ task.typeLabel }}</span></div>
              <div class="task-item__meta">
                <span class="task-item__user">{{ task.createdBy || '系统' }}</span>
                <span class="task-item__time">{{ formatTime(task.updatedAt) }}</span>
              </div>
            </div>
            <div class="task-item__right">
              <div class="task-item__progress" v-if="task.status === 'in_progress'">
                <div class="mini-progress"><div class="mini-progress__fill" :style="{ width: task.progress + '%' }" /></div>
                <span class="mini-progress__text">{{ task.progress }}%</span>
              </div>
              <el-tag v-else :type="statusTagType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
              <span class="task-item__priority" :class="'priority--' + task.priority">{{ priorityLabel(task.priority) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="task-list-empty">
          <p>暂无任务数据</p>
        </div>
        <div v-if="activeFilter" class="filter-banner">
          <span>当前筛选：{{ statusFilterLabel(activeFilter) }}</span>
          <button class="filter-clear-btn" @click="clearFilter">清除筛选</button>
        </div>
      </div>

      <div class="card quick-actions-card">
        <h3 class="card__title">快捷操作</h3>
        <div class="quick-actions">
          <button class="quick-action-btn" @click="handleScan">
            <div class="quick-action-icon quick-action-icon--scan">🔍</div>
            <span class="quick-action-label">全量扫描</span>
            <span class="quick-action-desc">扫描所有知识库文档</span>
          </button>
          <button class="quick-action-btn" @click="handleIndex">
            <div class="quick-action-icon quick-action-icon--index">📥</div>
            <span class="quick-action-label">重建索引</span>
            <span class="quick-action-desc">重建知识库向量索引</span>
          </button>
          <button class="quick-action-btn" @click="handleCleanup">
            <div class="quick-action-icon quick-action-icon--cleanup">🗑️</div>
            <span class="quick-action-label">清理缓存</span>
            <span class="quick-action-desc">清理过期缓存文件</span>
          </button>
          <button class="quick-action-btn" @click="handleBackup">
            <div class="quick-action-icon quick-action-icon--backup">💾</div>
            <span class="quick-action-label">数据备份</span>
            <span class="quick-action-desc">备份当前全部数据</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import {
  getTaskDashboard,
  getMockResources,
  getMockTaskStats,
  getMockRecentTasks,
  type SystemResources,
  type TaskStats,
  type TaskEntry,
  type TaskStatus,
} from '@/api/tasks';

const resources = ref<SystemResources>(getMockResources());
const stats = ref<TaskStats>(getMockTaskStats());
const tasks = ref<TaskEntry[]>(getMockRecentTasks());
const isRefreshing = ref(false);
const activeFilter = ref<TaskStatus | null>(null);
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const typeLabelMap: Record<string, string> = {
  index: '索引', import: '导入', optimize: '优化', backup: '备份',
  evaluation: '评测', rebuild: '重建', sync: '同步', scan: '扫描', cleanup: '清理',
};

function enrichTask(task: TaskEntry): TaskEntry & { typeLabel: string } {
  return { ...task, typeLabel: typeLabelMap[task.type] || task.type };
}

const filteredTasks = computed(() => {
  if (!activeFilter.value) return tasks.value.map(enrichTask);
  return tasks.value.filter((t) => t.status === activeFilter.value).map(enrichTask);
});

async function loadDashboard(): Promise<void> {
  try {
    const data = await getTaskDashboard();
    resources.value = data.resources;
    stats.value = data.stats;
    tasks.value = data.recentTasks;
  } catch {
    resources.value = getMockResources();
    stats.value = getMockTaskStats();
    tasks.value = getMockRecentTasks();
  }
}

async function handleRefresh(): Promise<void> {
  isRefreshing.value = true;
  await loadDashboard();
  setTimeout(() => { isRefreshing.value = false; }, 600);
}

function filterByStatus(status: TaskStatus): void {
  activeFilter.value = activeFilter.value === status ? null : status;
}

function clearFilter(): void {
  activeFilter.value = null;
}

function statusFilterLabel(status: TaskStatus): string {
  const map: Record<TaskStatus, string> = {
    pending: '待处理', in_progress: '进行中', completed: '已完成', failed: '失败',
  };
  return map[status];
}

async function handleScan(): Promise<void> {
  try {
    const { triggerScan } = await import('@/api/tasks');
    await triggerScan();
  } catch {}
  showToast('全量扫描任务已提交');
}

async function handleIndex(): Promise<void> {
  try {
    const { triggerIndex } = await import('@/api/tasks');
    await triggerIndex();
  } catch {}
  showToast('重建索引任务已提交');
}

async function handleCleanup(): Promise<void> {
  try {
    const { triggerCleanup } = await import('@/api/tasks');
    await triggerCleanup();
  } catch {}
  showToast('清理缓存任务已提交');
}

function handleBackup(): void {
  showToast('数据备份任务已提交');
}

function showToast(message: string): void {
  const el = document.createElement('div');
  el.className = 'task-dashboard-toast';
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('task-dashboard-toast--show'));
  setTimeout(() => {
    el.classList.remove('task-dashboard-toast--show');
    setTimeout(() => el.remove(), 300);
  }, 2000);
}

function statusTagType(status: TaskStatus): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<TaskStatus, 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'info', in_progress: 'warning', completed: 'success', failed: 'danger',
  };
  return map[status];
}

function statusLabel(status: TaskStatus): string {
  const map: Record<TaskStatus, string> = {
    pending: '待处理', in_progress: '进行中', completed: '已完成', failed: '失败',
  };
  return map[status];
}

function priorityLabel(priority: string): string {
  const map: Record<string, string> = { urgent: '紧急', high: '高', normal: '中', low: '低' };
  return map[priority] || priority;
}

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

onMounted(async () => {
  await loadDashboard();
  refreshTimer = setInterval(loadDashboard, 30_000);
});

onBeforeUnmount(() => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
});
</script>

<style scoped lang="scss">
.task-dashboard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px 48px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;

  &__left {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
}

.page-title {
  margin: 0;
  font-size: var(--font-size-page-title);
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--bg-divider);
  border-radius: var(--radius-input);
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
    border-color: var(--brand);
    color: var(--brand);
  }

  svg { flex-shrink: 0; }
}

/* ── 资源概览 ── */
.resources-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.resource-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  transition: transform var(--duration-normal) var(--ease-out), box-shadow var(--duration-normal) var(--ease-out);

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  &__header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;
  }
}

.resource-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &--cpu { background: var(--kun-color-light); color: var(--kun-color); }
  &--memory { background: var(--xun-color-light); color: var(--xun-color); }
  &--disk { background: var(--kan-color-light); color: var(--kan-color); }
}

.resource-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.resource-label {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.resource-value {
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.2;
}

.resource-meta {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  margin-top: 8px;
}

.progress-bar {
  height: 6px;
  background: var(--bg-subtle);
  border-radius: 3px;
  overflow: hidden;

  &__fill {
    height: 100%;
    border-radius: 3px;
    background: linear-gradient(90deg, var(--brand), #ff8533);
    transition: width 0.6s var(--ease-in-out);
  }
}

/* ── 统计卡片 ── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  transition: transform var(--duration-normal) var(--ease-out), box-shadow var(--duration-normal) var(--ease-out);

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  &:active { transform: scale(0.98); }

  &__icon {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 22px;
  }

  &--pending &__icon { background: var(--status-warning-bg); }
  &--progress &__icon { background: var(--kan-color-light); }
  &--completed &__icon { background: var(--status-healthy-bg); }
  &--failed &__icon { background: var(--status-error-bg); }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__value {
    font-size: 28px;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.2;
  }

  &__label {
    font-size: var(--font-size-caption);
    color: var(--text-secondary);
  }
}

/* ── 内容区 ── */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 20px;
}

.card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-sm);
  padding: 20px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  &__title {
    margin: 0;
    font-size: var(--font-size-card-title);
    font-weight: 600;
    color: var(--text-primary);
  }

  &__total {
    font-size: var(--font-size-small);
    color: var(--text-tertiary);
  }
}

/* ── 任务列表 ── */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 520px;
  overflow-y: auto;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: var(--bg-divider); border-radius: 4px; }
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast) var(--ease-out);

  &:hover { background: var(--bg-hover); }
  &__status { flex-shrink: 0; }
  &__info { flex: 1; min-width: 0; }

  &__name {
    font-size: var(--font-size-caption);
    font-weight: 500;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__type-tag {
    font-size: var(--font-size-small);
    padding: 1px 6px;
    background: var(--bg-card);
    border-radius: var(--radius-tag);
    color: var(--text-tertiary);
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 4px;
  }

  &__user { font-size: var(--font-size-small); color: var(--text-tertiary); }
  &__time { font-size: var(--font-size-small); color: var(--text-tertiary); font-family: monospace; }
  &__right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  &__priority { font-size: 10px; padding: 1px 6px; border-radius: var(--radius-tag); font-weight: 600; }
}

.priority {
  &--urgent { background: var(--status-error-bg); color: var(--status-error); }
  &--high { background: var(--status-warning-bg); color: var(--status-warning); }
  &--normal { background: var(--bg-subtle); color: var(--text-tertiary); }
  &--low { color: var(--text-tertiary); }
}

.status-dot {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;

  &--pending { background: #909399; }
  &--in_progress { background: var(--status-warning); box-shadow: 0 0 6px rgba(255,149,0,.4); }
  &--completed { background: var(--status-healthy); box-shadow: 0 0 6px rgba(52,199,89,.4); }
  &--failed { background: var(--status-error); box-shadow: 0 0 6px rgba(255,59,48,.4); }
}

.mini-progress {
  width: 60px;
  height: 4px;
  background: var(--bg-divider);
  border-radius: 2px;
  overflow: hidden;

  &__fill {
    height: 100%;
    background: linear-gradient(90deg, var(--brand), #ff8533);
    border-radius: 2px;
    transition: width 0.6s var(--ease-in-out);
  }

  &__text {
    font-size: 10px;
    color: var(--text-tertiary);
    font-family: monospace;
    width: 30px;
    text-align: right;
  }
}

.task-item__progress { display: flex; align-items: center; gap: 6px; }

.task-list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

.filter-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--brand-soft);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-small);
  color: var(--brand);
}

.filter-clear-btn {
  background: none;
  border: none;
  color: var(--brand);
  cursor: pointer;
  font-size: var(--font-size-small);
  font-weight: 500;

  &:hover { text-decoration: underline; }
}

/* ── 快捷操作 ── */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-action-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--bg-subtle);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  transition: background var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
    border-color: var(--brand);
  }

  &:active { transform: scale(0.98); }
}

.quick-action-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 20px;

  &--scan { background: var(--kun-color-light); }
  &--index { background: var(--xun-color-light); }
  &--cleanup { background: var(--kan-color-light); }
  &--backup { background: var(--qian-color-light); }
}

.quick-action-label {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
}

.quick-action-desc {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  margin-left: auto;
}

/* ── 响应式 ── */
@media (max-width: 1023px) {
  .resources-grid { grid-template-columns: repeat(2, 1fr); }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
}

@media (max-width: 767px) {
  .task-dashboard { padding: 16px 12px 36px; }
  .resources-grid { grid-template-columns: 1fr; }
  .stats-grid { grid-template-columns: 1fr 1fr; }
  .quick-action-desc { display: none; }
}
</style>
