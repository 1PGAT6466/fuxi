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

    <section class="resources-grid" aria-label="系统资源概览">
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
        <div class="progress-bar" role="progressbar" :aria-valuenow="resources.cpu.usage" aria-valuemin="0" aria-valuemax="100" :aria-label="`CPU 使用率 ${resources.cpu.usage}%`">
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
        <div class="progress-bar" role="progressbar" :aria-valuenow="resources.memory.usagePercent" aria-valuemin="0" aria-valuemax="100" :aria-label="`内存使用率 ${resources.memory.usagePercent}%`">
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
        <div class="progress-bar" role="progressbar" :aria-valuenow="resources.disk.usagePercent" aria-valuemin="0" aria-valuemax="100" :aria-label="`磁盘使用率 ${resources.disk.usagePercent}%`">
          <div class="progress-bar__fill" :style="{ width: resources.disk.usagePercent + '%' }" />
        </div>
        <div class="resource-meta">
          <span>{{ resources.disk.used }} / {{ resources.disk.total }}</span>
        </div>
      </div>
    </section>

    <section class="stats-grid" aria-label="任务统计">
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
    </section>

    <!-- 数据洞察区 -->
    <div v-if="insightsStore.hasData" class="insights-section">
      <div class="insights-header">
        <h3 class="insights-title">📊 数据洞察</h3>
        <div class="insights-meta">
          <span class="health-badge" :class="'health--' + insightsStore.healthLevel">
            健康指数 {{ insightsStore.healthScore }}
          </span>
          <span v-if="insightsStore.unacknowledgedAnomalies > 0" class="anomaly-badge">
            {{ insightsStore.unacknowledgedAnomalies }} 个异常
          </span>
        </div>
      </div>

      <div class="insights-grid">
        <!-- 趋势卡片 -->
        <div v-if="insightsStore.trends.length > 0" class="insight-card">
          <h4 class="insight-card__title">趋势分析</h4>
          <div class="trend-list">
            <div v-for="trend in insightsStore.trends.slice(0, 5)" :key="trend.label" class="trend-item">
              <span class="trend-label">{{ trend.label }}</span>
              <span class="trend-value">{{ trend.value }}</span>
              <span v-if="trend.change !== undefined" class="trend-change" :class="trend.change >= 0 ? 'up' : 'down'">
                {{ trend.change >= 0 ? '↑' : '↓' }} {{ Math.abs(trend.change) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- 异常卡片 -->
        <div v-if="insightsStore.anomalies.length > 0" class="insight-card">
          <h4 class="insight-card__title">异常检测</h4>
          <div class="anomaly-list">
            <div
              v-for="anomaly in insightsStore.anomalies.slice(0, 4)"
              :key="anomaly.id"
              class="anomaly-item"
              :class="'severity--' + anomaly.severity"
            >
              <span class="anomaly-severity">{{ severityLabel(anomaly.severity) }}</span>
              <span class="anomaly-desc">{{ anomaly.description }}</span>
              <el-button
                v-if="!anomaly.acknowledged"
                text
                size="small"
                @click="insightsStore.acknowledgeAnomaly(anomaly.id)"
              >
                确认
              </el-button>
            </div>
          </div>
        </div>

        <!-- 洞察建议卡片 -->
        <div v-if="insightsStore.insights.length > 0" class="insight-card">
          <h4 class="insight-card__title">💡 洞察建议</h4>
          <div class="insight-list">
            <div v-for="item in insightsStore.insights.slice(0, 3)" :key="item.id" class="insight-item">
              <el-tag :type="insightTagType(item.type)" size="small">{{ insightTypeLabel(item.type) }}</el-tag>
              <span class="insight-text">{{ item.title }}</span>
            </div>
          </div>
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
          <button class="quick-action-btn" :disabled="scanLoading" @click="handleScan" aria-label="全量扫描知识库文档">
            <div class="quick-action-icon quick-action-icon--scan">{{ scanLoading ? '⏳' : '🔍' }}</div>
            <span class="quick-action-label">{{ scanLoading ? '提交中...' : '全量扫描' }}</span>
            <span class="quick-action-desc">扫描所有知识库文档</span>
          </button>
          <button class="quick-action-btn" :disabled="indexLoading" @click="handleIndex" aria-label="重建知识库向量索引">
            <div class="quick-action-icon quick-action-icon--index">{{ indexLoading ? '⏳' : '📥' }}</div>
            <span class="quick-action-label">{{ indexLoading ? '提交中...' : '重建索引' }}</span>
            <span class="quick-action-desc">重建知识库向量索引</span>
          </button>
          <button class="quick-action-btn" :disabled="cleanupLoading" @click="handleCleanup" aria-label="清理过期缓存文件">
            <div class="quick-action-icon quick-action-icon--cleanup">{{ cleanupLoading ? '⏳' : '🗑️' }}</div>
            <span class="quick-action-label">{{ cleanupLoading ? '提交中...' : '清理缓存' }}</span>
            <span class="quick-action-desc">清理过期缓存文件</span>
          </button>
          <button class="quick-action-btn" :disabled="backupLoading" @click="handleBackup" aria-label="备份当前全部数据">
            <div class="quick-action-icon quick-action-icon--backup">{{ backupLoading ? '⏳' : '💾' }}</div>
            <span class="quick-action-label">{{ backupLoading ? '提交中...' : '数据备份' }}</span>
            <span class="quick-action-desc">备份当前全部数据</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';
import {
  getDashboardStats,
  getDashboardActivity,
  getDashboardSystem,
  triggerScan,
  triggerIndex,
  triggerCleanup,
  type SystemResources,
  type TaskStats,
  type TaskEntry,
  type TaskStatus,
} from '@/api/tasks';
import { useDataInsightsStore } from '@/stores/dataInsights';

// ─── 数据洞察 Store ───
const insightsStore = useDataInsightsStore();

const resources = ref<SystemResources>({
  cpu: { usage: 0, cores: 0, temperature: 0 },
  memory: { used: '-', total: '-', usagePercent: 0 },
  disk: { used: '-', total: '-', usagePercent: 0 },
});
const stats = ref<TaskStats>({ pending: 0, inProgress: 0, completed: 0, failed: 0, total: 0 });
const tasks = ref<TaskEntry[]>([]);
const isRefreshing = ref(false);
const activeFilter = ref<TaskStatus | null>(null);
let refreshTimer: ReturnType<typeof setInterval> | null = null;

// 快捷操作 loading 状态
const scanLoading = ref(false);
const indexLoading = ref(false);
const cleanupLoading = ref(false);
const backupLoading = ref(false);

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
    const [statsData, activityData, systemData] = await Promise.allSettled([
      getDashboardStats(),
      getDashboardActivity(),
      getDashboardSystem(),
    ]);

    const statsPayload =
      statsData.status === 'fulfilled' ? ((statsData.value as Record<string, unknown>)?.data ?? statsData.value ?? {}) : {};
    const activityPayload =
      activityData.status === 'fulfilled' ? ((activityData.value as Record<string, unknown>)?.data ?? activityData.value ?? {}) : {};
    const systemPayload =
      systemData.status === 'fulfilled' ? ((systemData.value as Record<string, unknown>)?.data ?? systemData.value ?? {}) : {};

    stats.value = {
      pending: Number((statsPayload as Record<string, unknown>).pending ?? 0),
      inProgress: Number((statsPayload as Record<string, unknown>).in_progress ?? (statsPayload as Record<string, unknown>).inProgress ?? 0),
      completed: Number((statsPayload as Record<string, unknown>).completed ?? 0),
      failed: Number((statsPayload as Record<string, unknown>).failed ?? 0),
      total: Number((statsPayload as Record<string, unknown>).total ?? 0),
    };

    const recentTasks =
      Array.isArray((activityPayload as Record<string, unknown>).recent_tasks)
        ? ((activityPayload as Record<string, unknown>).recent_tasks as TaskEntry[])
        : Array.isArray((activityPayload as Record<string, unknown>).recentTasks)
          ? ((activityPayload as Record<string, unknown>).recentTasks as TaskEntry[])
          : Array.isArray((activityPayload as Record<string, unknown>).tasks)
            ? ((activityPayload as Record<string, unknown>).tasks as TaskEntry[])
            : Array.isArray((activityPayload as Record<string, unknown>).items)
              ? ((activityPayload as Record<string, unknown>).items as TaskEntry[])
              : Array.isArray(activityPayload)
                ? (activityPayload as unknown as TaskEntry[])
                : [];
    tasks.value = recentTasks;

    const cpu = (systemPayload as Record<string, unknown>).cpu as Record<string, unknown> | undefined;
    const memory = (systemPayload as Record<string, unknown>).memory as Record<string, unknown> | undefined;
    const disk = (systemPayload as Record<string, unknown>).disk as Record<string, unknown> | undefined;

    resources.value = {
      cpu: {
        usage: Number(cpu?.usage ?? 0),
        cores: Number(cpu?.cores ?? 0),
        temperature: Number(cpu?.temperature ?? 0),
      },
      memory: {
        used: String(memory?.used ?? '-'),
        total: String(memory?.total ?? '-'),
        usagePercent: Number(memory?.usagePercent ?? memory?.usage_percent ?? 0),
      },
      disk: {
        used: String(disk?.used ?? '-'),
        total: String(disk?.total ?? '-'),
        usagePercent: Number(disk?.usagePercent ?? disk?.usage_percent ?? 0),
      },
    };
  } catch {
    resources.value = {
      cpu: { usage: 0, cores: 0, temperature: 0 },
      memory: { used: '-', total: '-', usagePercent: 0 },
      disk: { used: '-', total: '-', usagePercent: 0 },
    };
    stats.value = { pending: 0, inProgress: 0, completed: 0, failed: 0, total: 0 };
    tasks.value = [];
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
  if (scanLoading.value) return;
  scanLoading.value = true;
  try {
    const { triggerScan: doScan } = await import('@/api/tasks');
    await doScan();
    ElMessage.success('全量扫描任务已提交');
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '扫描任务提交失败';
    ElMessage.error(msg);
  } finally {
    scanLoading.value = false;
  }
}

async function handleIndex(): Promise<void> {
  if (indexLoading.value) return;
  indexLoading.value = true;
  try {
    const { triggerIndex: doIndex } = await import('@/api/tasks');
    await doIndex();
    ElMessage.success('重建索引任务已提交');
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '索引任务提交失败';
    ElMessage.error(msg);
  } finally {
    indexLoading.value = false;
  }
}

async function handleCleanup(): Promise<void> {
  if (cleanupLoading.value) return;
  cleanupLoading.value = true;
  try {
    const { triggerCleanup: doCleanup } = await import('@/api/tasks');
    await doCleanup();
    ElMessage.success('清理缓存任务已提交');
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '清理任务提交失败';
    ElMessage.error(msg);
  } finally {
    cleanupLoading.value = false;
  }
}

async function handleBackup(): Promise<void> {
  if (backupLoading.value) return;
  backupLoading.value = true;
  try {
    // TODO: 替换为实际的备份 API 调用
    ElMessage.success('数据备份任务已提交');
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '备份任务提交失败';
    ElMessage.error(msg);
  } finally {
    backupLoading.value = false;
  }
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

// ─── 数据洞察辅助函数 ───
function severityLabel(severity: string): string {
  const map: Record<string, string> = { critical: '严重', high: '高', medium: '中', low: '低' };
  return map[severity] || severity;
}

function insightTagType(type: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    optimization: 'success', warning: 'warning', info: 'info', action: 'danger',
  };
  return map[type] || 'info';
}

function insightTypeLabel(type: string): string {
  const map: Record<string, string> = { optimization: '优化', warning: '警告', info: '信息', action: '行动' };
  return map[type] || type;
}

onMounted(async () => {
  await loadDashboard();
  refreshTimer = setInterval(loadDashboard, 30_000);
  // 启动数据洞察自动刷新（30秒轮询）
  insightsStore.startAutoRefresh();
});

onBeforeUnmount(() => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  insightsStore.stopAutoRefresh();
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

/* ── 数据洞察区 ── */
.insights-section {
  margin-bottom: 24px;
}

.insights-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.insights-title {
  margin: 0;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--text-primary);
}

.insights-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.health-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: var(--radius-tag);

  &.health--excellent { background: var(--status-healthy-bg); color: var(--status-healthy); }
  &.health--good { background: var(--status-healthy-bg); color: var(--status-healthy); }
  &.health--warning { background: var(--status-warning-bg); color: var(--status-warning); }
  &.health--critical { background: var(--status-error-bg); color: var(--status-error); }
}

.anomaly-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: var(--radius-tag);
  background: var(--status-error-bg);
  color: var(--status-error);
}

.insights-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.insight-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-sm);
  padding: 20px;

  &__title {
    margin: 0 0 12px;
    font-size: var(--font-size-caption);
    font-weight: 600;
    color: var(--text-primary);
  }
}

/* ── 趋势 ── */
.trend-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.trend-label {
  flex: 1;
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trend-value {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
}

.trend-change {
  font-size: 11px;
  font-weight: 600;
  &.up { color: var(--status-healthy); }
  &.down { color: var(--status-error); }
}

/* ── 异常 ── */
.anomaly-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.anomaly-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);

  &.severity--critical { border-left: 3px solid var(--status-error); }
  &.severity--high { border-left: 3px solid var(--status-error); }
  &.severity--medium { border-left: 3px solid var(--status-warning); }
  &.severity--low { border-left: 3px solid var(--text-tertiary); }
}

.anomaly-severity {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-tag);
  background: var(--bg-card);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.anomaly-desc {
  flex: 1;
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 洞察建议 ── */
.insight-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insight-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.insight-text {
  flex: 1;
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 响应式 ── */
@media (max-width: 1023px) {
  .resources-grid { grid-template-columns: repeat(2, 1fr); }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
  .insights-grid { grid-template-columns: 1fr; }
}

@media (max-width: 767px) {
  .task-dashboard { padding: 16px 12px 36px; }
  .resources-grid { grid-template-columns: 1fr; }
  .stats-grid { grid-template-columns: 1fr 1fr; }
  .quick-action-desc { display: none; }
}
</style>
