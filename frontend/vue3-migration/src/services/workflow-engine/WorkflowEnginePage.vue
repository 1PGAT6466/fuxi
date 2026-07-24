<!--
  伏羲 v2.1 — 工作流引擎主页面
  工作流列表 + 入口到 WorkflowEditor
-->
<template>
  <div class="workflow-engine-page">
    <!-- 工作流列表视图 -->
    <div v-if="!editingWorkflowId && !store.currentWorkflow" class="workflow-list-view">
      <header class="page-header">
        <div class="header-info">
          <h1 class="page-title">⚡ 工作流引擎</h1>
          <p class="page-subtitle">可视化编排自动化流程</p>
        </div>
        <button class="btn-create" @click="handleCreateNew">
          + 新建工作流
        </button>
      </header>

      <!-- 加载中 -->
      <div v-if="store.loading && store.workflows.length === 0" class="loading-state">
        加载中...
      </div>

      <!-- 空状态 -->
      <div v-else-if="store.workflows.length === 0" class="empty-state">
        <div class="empty-icon">⚡</div>
        <h2>尚无工作流</h2>
        <p>创建您的第一个工作流，开始自动化之旅</p>
        <button class="btn-create" @click="handleCreateNew">+ 新建工作流</button>
      </div>

      <!-- 工作流列表 -->
      <div v-else class="workflow-grid">
        <div
          v-for="wf in store.workflows"
          :key="wf.id"
          class="workflow-card"
          @click="openWorkflow(wf.id)"
        >
          <div class="card-header">
            <span class="card-status" :class="wf.status"></span>
            <h3 class="card-title">{{ wf.name }}</h3>
            <span class="card-version">v{{ wf.version }}</span>
          </div>
          <p class="card-desc">{{ wf.description || '无描述' }}</p>
          <div class="card-meta">
            <span class="meta-item">
              📦 {{ wf.nodes.length }} 节点
            </span>
            <span class="meta-item">
              🔗 {{ wf.connections.length }} 连线
            </span>
            <span class="meta-item">
              🕐 {{ formatDate(wf.updatedAt) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 工作流编辑器 -->
    <WorkflowEditor
      v-else
      @back="handleBackToList"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useWorkflowEngineStore } from './store';
import WorkflowEditor from './WorkflowEditor.vue';

const store = useWorkflowEngineStore();
const editingWorkflowId = ref<string | null>(null);

onMounted(() => {
  store.loadWorkflows();
});

async function handleCreateNew() {
  store.clearEditor();
  const name = prompt('请输入工作流名称:');
  if (!name) return;
  store.createDraft(name);
}

async function openWorkflow(id: string) {
  editingWorkflowId.value = id;
  await store.loadWorkflow(id);
}

function handleBackToList() {
  store.clearEditor();
  editingWorkflowId.value = null;
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}
</script>

<style scoped>
.workflow-engine-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color-page, #f5f7fa);
}

/* ───── 列表视图 ───── */
.workflow-list-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: var(--el-text-color-primary, #303133);
}

.page-subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
  margin: 0;
}

.btn-create {
  padding: 10px 24px;
  background: var(--el-color-primary, #409eff);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.btn-create:hover {
  background: #3a8ee6;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

/* ───── 加载/空状态 ───── */
.loading-state {
  text-align: center;
  padding: 64px 0;
  color: var(--el-text-color-secondary, #909399);
}

.empty-state {
  text-align: center;
  padding: 64px 0;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state h2 {
  font-size: 18px;
  color: var(--el-text-color-primary, #303133);
  margin: 0 0 8px;
}

.empty-state p {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
  margin: 0 0 20px;
}

/* ───── 工作流卡片 ───── */
.workflow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.workflow-card {
  padding: 16px;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.workflow-card:hover {
  border-color: var(--el-color-primary-light-5, #a0cfff);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.card-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.card-status.draft {
  background: var(--el-text-color-placeholder, #c0c4cc);
}
.card-status.active {
  background: var(--el-color-success, #67c23a);
}
.card-status.paused {
  background: var(--el-color-warning, #e6a23c);
}
.card-status.archived {
  background: var(--el-text-color-disabled, #c0c4cc);
}

.card-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: var(--el-text-color-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-version {
  font-size: 11px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.card-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin: 0 0 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  font-size: 11px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}
</style>
