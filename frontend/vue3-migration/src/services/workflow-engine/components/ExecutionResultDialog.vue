<!--
  伏羲 v2.1 — 执行结果对话框
  展示工作流执行后的详细结果
-->
<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog-panel">
      <div class="dialog-header">
        <h2>
          执行结果
          <span
            class="exec-status"
            :class="statusClass"
          >
            {{ statusLabel }}
          </span>
        </h2>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <div class="dialog-body">
        <!-- 执行摘要 -->
        <div class="exec-summary">
          <div class="summary-item">
            <span class="summary-label">执行 ID</span>
            <span class="summary-value mono">{{ result.id }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">耗时</span>
            <span class="summary-value">{{ formatDuration(result.durationMs) }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">节点总数</span>
            <span class="summary-value">{{ result.nodeResults.length }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">成功</span>
            <span class="summary-value success">
              {{ result.nodeResults.filter((n) => n.status === 'completed').length }}
            </span>
          </div>
          <div v-if="result.error" class="summary-item">
            <span class="summary-label">错误</span>
            <span class="summary-value error">{{ result.error }}</span>
          </div>
        </div>

        <!-- 节点执行详情 -->
        <div class="node-results">
          <h3 class="results-title">节点执行详情</h3>
          <div
            v-for="nodeResult in result.nodeResults"
            :key="nodeResult.nodeId"
            class="node-result-item"
            :class="nodeResult.status"
          >
            <div class="node-result-header" @click="toggleExpand(nodeResult.nodeId)">
              <span class="node-result-icon">
                {{ nodeResult.status === 'completed' ? '✅' : nodeResult.status === 'failed' ? '❌' : '⏳' }}
              </span>
              <span class="node-result-label">{{ nodeResult.nodeLabel }}</span>
              <span class="node-result-duration">{{ nodeResult.durationMs }}ms</span>
              <span class="node-result-arrow">{{ expandedSet.has(nodeResult.nodeId) ? '▾' : '▸' }}</span>
            </div>
            <div v-if="expandedSet.has(nodeResult.nodeId)" class="node-result-detail">
              <div v-if="nodeResult.error" class="detail-section error">
                <div class="detail-label">错误</div>
                <pre class="detail-value">{{ nodeResult.error }}</pre>
              </div>
              <div v-if="nodeResult.input" class="detail-section">
                <div class="detail-label">输入</div>
                <pre class="detail-value">{{ JSON.stringify(nodeResult.input, null, 2) }}</pre>
              </div>
              <div v-if="nodeResult.output" class="detail-section">
                <div class="detail-label">输出</div>
                <pre class="detail-value">{{ JSON.stringify(nodeResult.output, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>

        <!-- 执行上下文 -->
        <div v-if="result.context && Object.keys(result.context).length" class="context-section">
          <h3 class="results-title">执行上下文</h3>
          <pre class="context-value">{{ JSON.stringify(result.context, null, 2) }}</pre>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="btn-close-dialog" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { WorkflowExecution } from '../types';

const props = defineProps<{
  result: WorkflowExecution;
}>();

defineEmits<{
  close: [];
}>();

const expandedSet = ref(new Set<string>());

function toggleExpand(nodeId: string) {
  if (expandedSet.value.has(nodeId)) {
    expandedSet.value.delete(nodeId);
  } else {
    expandedSet.value.add(nodeId);
  }
}

const statusClass = computed(() => ({
  completed: props.result.status === 'completed',
  failed: props.result.status === 'failed',
  running: props.result.status === 'running',
}));

const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    completed: '成功',
    failed: '失败',
    running: '运行中',
    pending: '等待中',
    cancelled: '已取消',
  };
  return labels[props.result.status] ?? props.result.status;
});

function formatDuration(ms?: number): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
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
  width: 640px;
  max-height: 80vh;
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
  display: flex;
  align-items: center;
  gap: 10px;
}

.exec-status {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
}
.exec-status.completed {
  background: #e8f5e9;
  color: #2e7d32;
}
.exec-status.failed {
  background: #ffebee;
  color: #c62828;
}
.exec-status.running {
  background: #fff3e0;
  color: #ef6c00;
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

.dialog-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--el-border-color-light, #e4e7ed);
  display: flex;
  justify-content: flex-end;
}

.btn-close-dialog {
  padding: 8px 20px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  background: var(--el-bg-color, #fff);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  color: var(--el-text-color-regular, #606266);
}
.btn-close-dialog:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}

/* ───── 执行摘要 ───── */
.exec-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 8px;
  margin-bottom: 16px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.summary-label {
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
}

.summary-value {
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
}
.summary-value.mono {
  font-family: monospace;
  font-size: 12px;
}
.summary-value.success {
  color: var(--el-color-success, #67c23a);
}
.summary-value.error {
  color: var(--el-color-danger, #f56c6c);
  word-break: break-all;
}

/* ───── 节点结果 ───── */
.results-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular, #606266);
  margin: 0 0 8px 0;
}

.node-results {
  margin-bottom: 16px;
}

.node-result-item {
  border: 1px solid var(--el-border-color-extra-light, #f2f6fc);
  border-radius: 6px;
  margin-bottom: 4px;
  overflow: hidden;
}
.node-result-item.completed {
  border-left: 3px solid var(--el-color-success, #67c23a);
}
.node-result-item.failed {
  border-left: 3px solid var(--el-color-danger, #f56c6c);
}

.node-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.node-result-header:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}

.node-result-icon {
  font-size: 14px;
}

.node-result-label {
  flex: 1;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
}

.node-result-duration {
  font-size: 11px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.node-result-arrow {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.node-result-detail {
  padding: 8px 12px 12px;
  border-top: 1px solid var(--el-border-color-extra-light, #f2f6fc);
}

.detail-section {
  margin-bottom: 8px;
}
.detail-section:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
  margin-bottom: 4px;
}

.detail-value {
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  background: var(--el-fill-color, #f0f2f5);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.detail-section.error .detail-value {
  background: #fef0f0;
  color: var(--el-color-danger, #f56c6c);
}

/* ───── 上下文 ───── */
.context-section {
  margin-top: 16px;
}

.context-value {
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  background: var(--el-fill-color, #f0f2f5);
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
