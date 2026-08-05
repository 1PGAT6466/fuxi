<template>
  <!--
    伏羲 v2.1 — 任务中心
    任务列表、任务详情、创建任务、任务日志
  -->
  <div class="ops-page">
    <div class="ops-page__header">
      <h2 class="ops-page__title">⚡ 任务中心</h2>
      <div class="ops-page__actions">
        <el-select v-model="statusFilter" size="small" style="width: 120px" clearable placeholder="状态筛选">
          <el-option label="全部" value="" />
          <el-option label="运行中" value="running" />
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="等待中" value="pending" />
        </el-select>
        <el-button type="primary" size="small" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建任务
        </el-button>
      </div>
    </div>

    <!-- 任务统计 -->
    <div class="task-stats">
      <div class="task-stat">
        <span class="task-stat__value task-stat__value--running">{{ runningCount }}</span>
        <span class="task-stat__label">运行中</span>
      </div>
      <div class="task-stat">
        <span class="task-stat__value task-stat__value--success">{{ successCount }}</span>
        <span class="task-stat__label">今日成功</span>
      </div>
      <div class="task-stat">
        <span class="task-stat__value task-stat__value--failed">{{ failedCount }}</span>
        <span class="task-stat__label">今日失败</span>
      </div>
      <div class="task-stat">
        <span class="task-stat__value task-stat__value--pending">{{ pendingCount }}</span>
        <span class="task-stat__label">等待中</span>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="ops-table-wrapper">
      <el-table :data="filteredTasks" stripe class="ops-table">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="任务名称" min-width="200" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <span class="task-status" :class="`task-status--${row.status}`">
              {{ statusEmoji(row.status) }} {{ statusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress
              v-if="row.status === 'running'"
              :percentage="row.progress"
              :stroke-width="6"
              :color="row.progress > 80 ? '#00d4aa' : '#58a6ff'"
            />
            <span v-else class="task-progress-text">{{ row.progress }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="startTime" label="开始时间" width="160" />
        <el-table-column prop="duration" label="耗时" width="100" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="viewDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'running'"
              size="small"
              text
              type="danger"
              @click="handleCancel(row)"
            >取消</el-button>
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              text
              type="warning"
              @click="handleRetry(row)"
            >重试</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建任务" width="480px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="任务名称" required>
          <el-input v-model="createForm.name" placeholder="输入任务名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="createForm.type" style="width: 100%">
            <el-option label="知识同步" value="sync" />
            <el-option label="文档清洗" value="clean" />
            <el-option label="索引构建" value="index" />
            <el-option label="备份" value="backup" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="createForm.priority">
            <el-radio label="low">低</el-radio>
            <el-radio label="normal">普通</el-radio>
            <el-radio label="high">高</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="任务详情" width="600px">
      <div v-if="selectedTask" class="task-detail">
        <div class="task-detail__row">
          <span class="task-detail__label">ID：</span>
          <span>{{ selectedTask.id }}</span>
        </div>
        <div class="task-detail__row">
          <span class="task-detail__label">名称：</span>
          <span>{{ selectedTask.name }}</span>
        </div>
        <div class="task-detail__row">
          <span class="task-detail__label">类型：</span>
          <span>{{ selectedTask.type }}</span>
        </div>
        <div class="task-detail__row">
          <span class="task-detail__label">状态：</span>
          <span :class="`task-status--${selectedTask.status}`">
            {{ statusEmoji(selectedTask.status) }} {{ statusLabel(selectedTask.status) }}
          </span>
        </div>
        <div class="task-detail__row">
          <span class="task-detail__label">开始时间：</span>
          <span>{{ selectedTask.startTime }}</span>
        </div>
        <div class="task-detail__row">
          <span class="task-detail__label">耗时：</span>
          <span>{{ selectedTask.duration }}</span>
        </div>
        <div class="task-detail__log">
          <h4>执行日志</h4>
          <pre class="task-log">{{ selectedTask.log || '暂无日志' }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 任务中心 — TaskCenterView
 * 任务的创建、查看、取消、重试
 */
import { ref, reactive, computed } from 'vue';
import { Plus } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

// ============================
// 类型
// ============================

interface Task {
  id: string;
  name: string;
  type: string;
  status: 'running' | 'success' | 'failed' | 'pending';
  progress: number;
  startTime: string;
  duration: string;
  log?: string;
}

// ============================
// 数据
// ============================

const statusFilter = ref('');
const showCreateDialog = ref(false);
const showDetailDialog = ref(false);
const selectedTask = ref<Task | null>(null);

const tasks = ref<Task[]>([
  {
    id: 'T001',
    name: '知识库增量同步',
    type: '同步',
    status: 'running',
    progress: 67,
    startTime: '2026-07-16 16:30',
    duration: '进行中',
    log: '[16:30] 开始同步...\n[16:31] 已处理 120/180 文档\n[16:32] 正在构建索引...',
  },
  {
    id: 'T002',
    name: '文档清洗任务',
    type: '清洗',
    status: 'success',
    progress: 100,
    startTime: '2026-07-16 15:00',
    duration: '12m 34s',
    log: '[15:00] 开始清洗\n[15:12] 完成，共处理 45 个文档',
  },
  {
    id: 'T003',
    name: 'Rerank 模型更新',
    type: '模型',
    status: 'failed',
    progress: 45,
    startTime: '2026-07-16 14:00',
    duration: '失败',
    log: '[14:00] 开始下载模型\n[14:15] 下载失败：网络超时\n[错误] 连接 Ollama 服务超时',
  },
  {
    id: 'T004',
    name: 'ChromaDB 备份',
    type: '备份',
    status: 'success',
    progress: 100,
    startTime: '2026-07-16 12:00',
    duration: '5m 12s',
  },
  {
    id: 'T005',
    name: '日志归档',
    type: '维护',
    status: 'pending',
    progress: 0,
    startTime: '—',
    duration: '等待中',
  },
]);

const createForm = reactive({
  name: '',
  type: 'sync',
  priority: 'normal',
});

// ============================
// 计算属性
// ============================

const filteredTasks = computed(() => {
  if (!statusFilter.value) return tasks.value;
  return tasks.value.filter((t) => t.status === statusFilter.value);
});

const runningCount = computed(() => tasks.value.filter((t) => t.status === 'running').length);
const successCount = computed(() => tasks.value.filter((t) => t.status === 'success').length);
const failedCount = computed(() => tasks.value.filter((t) => t.status === 'failed').length);
const pendingCount = computed(() => tasks.value.filter((t) => t.status === 'pending').length);

// ============================
// 方法
// ============================

function statusEmoji(status: string): string {
  const map: Record<string, string> = { running: '🔄', success: '✅', failed: '❌', pending: '⏳' };
  return map[status] || '❓';
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { running: '运行中', success: '成功', failed: '失败', pending: '等待中' };
  return map[status] || status;
}

function viewDetail(task: Task): void {
  selectedTask.value = task;
  showDetailDialog.value = true;
}

async function handleCancel(task: Task): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定取消任务「${task.name}」？`, '确认取消');
    task.status = 'failed';
    task.duration = '已取消';
    ElMessage.success('任务已取消');
  } catch {
    // 取消
  }
}

function handleRetry(task: Task): void {
  task.status = 'running';
  task.progress = 0;
  task.duration = '进行中';
  ElMessage.info(`正在重试任务「${task.name}」`);
}

function handleCreate(): void {
  if (!createForm.name) {
    ElMessage.warning('请输入任务名称');
    return;
  }
  const newTask: Task = {
    id: `T${String(tasks.value.length + 1).padStart(3, '0')}`,
    name: createForm.name,
    type: createForm.type,
    status: 'pending',
    progress: 0,
    startTime: '—',
    duration: '等待中',
  };
  tasks.value.unshift(newTask);
  showCreateDialog.value = false;
  createForm.name = '';
  ElMessage.success('任务已创建');
}
</script>

<style scoped lang="scss">
.ops-page {
  padding: 20px;
  background: #0d1117;
  min-height: 100%;
  color: #e0e0e0;
}

.ops-page__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.ops-page__title {
  font-size: 20px;
  font-weight: 600;
  color: #e0e0e0;
  margin: 0;
}

.ops-page__actions {
  display: flex;
  gap: 8px;
}

/* ── 任务统计 ── */
.task-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.task-stat {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}

.task-stat__value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;

  &--running { color: #58a6ff; }
  &--success { color: #00d4aa; }
  &--failed { color: #f04040; }
  &--pending { color: #8b949e; }
}

.task-stat__label {
  font-size: 12px;
  color: #8b949e;
}

/* ── 表格 ── */
.ops-table-wrapper {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 16px;
}

.ops-table {
  --el-table-bg-color: #161b22;
  --el-table-tr-bg-color: #161b22;
  --el-table-header-bg-color: #1c2128;
  --el-table-row-hover-bg-color: #1c2128;
  --el-table-border-color: #30363d;
  --el-table-text-color: #c9d1d9;
  --el-table-header-text-color: #8b949e;
}

.task-status {
  font-size: 12px;
  &--running { color: #58a6ff; }
  &--success { color: #00d4aa; }
  &--failed { color: #f04040; }
  &--pending { color: #8b949e; }
}

.task-progress-text {
  font-size: 12px;
  color: #8b949e;
}

/* ── 详情 ── */
.task-detail__row {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #30363d;
  font-size: 14px;
}

.task-detail__label {
  width: 80px;
  color: #8b949e;
  flex-shrink: 0;
}

.task-detail__log {
  margin-top: 16px;

  h4 {
    font-size: 14px;
    color: #e0e0e0;
    margin: 0 0 8px;
  }
}

.task-log {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  color: #c9d1d9;
  font-family: 'SF Mono', monospace;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  margin: 0;
}
</style>
