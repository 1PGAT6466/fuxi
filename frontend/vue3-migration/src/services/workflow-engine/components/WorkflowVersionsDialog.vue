<!--
  伏羲 v2.1 — 工作流版本管理对话框
-->
<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog-panel">
      <div class="dialog-header">
        <h2>版本历史</h2>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <div class="dialog-body">
        <!-- 加载中 -->
        <div v-if="store.loading" class="dialog-loading">
          加载中...
        </div>

        <!-- 无版本 -->
        <div v-else-if="store.versions.length === 0" class="dialog-empty">
          <p>尚无版本记录</p>
          <p class="help-text">保存工作流后，每次更新的快照将显示在这里</p>
        </div>

        <!-- 版本列表 -->
        <div v-else class="versions-list">
          <div
            v-for="version in store.versions"
            :key="version.id"
            class="version-item"
            :class="{ current: version.version === store.currentWorkflow?.version }"
          >
            <div class="version-info">
              <div class="version-header">
                <span class="version-number">v{{ version.version }}</span>
                <span
                  v-if="version.version === store.currentWorkflow?.version"
                  class="current-badge"
                >
                  当前
                </span>
              </div>
              <div class="version-meta">
                <span class="version-changelog">{{ version.changelog || '无变更描述' }}</span>
                <span class="version-date">{{ formatDate(version.createdAt) }}</span>
                <span v-if="version.createdBy" class="version-author">
                  {{ version.createdBy }}
                </span>
              </div>
            </div>
            <button
              v-if="version.version !== store.currentWorkflow?.version"
              class="btn-rollback"
              :disabled="store.loading"
              @click="handleRollback(version.id)"
            >
              回滚
            </button>
          </div>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="btn-cancel" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useWorkflowEngineStore } from '../store';

const emit = defineEmits<{
  close: [];
}>();

const store = useWorkflowEngineStore();

onMounted(() => {
  store.loadVersions();
});

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

async function handleRollback(versionId: string) {
  const confirmed = window.confirm('确定要回滚到此版本吗？当前未保存的更改将丢失。');
  if (!confirmed) return;

  const success = await store.rollbackToVersion(versionId);
  if (success) {
    emit('close');
  }
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-panel {
  width: 520px;
  max-height: 70vh;
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-light, #e4e7ed);
}

.dialog-header h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--el-text-color-secondary, #909399);
  padding: 4px 8px;
  border-radius: 4px;
}
.btn-close:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.dialog-loading,
.dialog-empty {
  text-align: center;
  padding: 32px 0;
  color: var(--el-text-color-secondary, #909399);
}

.help-text {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
  margin-top: 8px;
}

.dialog-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--el-border-color-light, #e4e7ed);
  display: flex;
  justify-content: flex-end;
}

.btn-cancel {
  padding: 8px 20px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  background: var(--el-bg-color, #fff);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  color: var(--el-text-color-regular, #606266);
}
.btn-cancel:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}

/* ───── 版本列表 ───── */
.versions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 8px;
  transition: border-color 0.15s;
}

.version-item:hover {
  border-color: var(--el-color-primary-light-5, #a0cfff);
}

.version-item.current {
  background: var(--el-color-primary-light-9, #ecf5ff);
  border-color: var(--el-color-primary-light-5, #a0cfff);
}

.version-info {
  flex: 1;
  min-width: 0;
}

.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.version-number {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary, #303133);
}

.current-badge {
  font-size: 11px;
  background: var(--el-color-primary, #409eff);
  color: #fff;
  padding: 1px 8px;
  border-radius: 10px;
}

.version-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.version-changelog {
  font-size: 12px;
  color: var(--el-text-color-regular, #606266);
}

.version-date {
  font-size: 11px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.version-author {
  font-size: 11px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.btn-rollback {
  padding: 6px 14px;
  border: 1px solid var(--el-color-warning-light-3, #eebe77);
  background: var(--el-color-warning-light-9, #fdf6ec);
  color: var(--el-color-warning, #e6a23c);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.btn-rollback:hover:not(:disabled) {
  background: var(--el-color-warning, #e6a23c);
  color: #fff;
}
.btn-rollback:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
