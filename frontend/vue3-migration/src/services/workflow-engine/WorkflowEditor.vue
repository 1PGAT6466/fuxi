<template>
  <div class="workflow-editor" @keydown="handleKeydown">
    <!-- 顶部工具栏 -->
    <header class="editor-header">
      <div class="header-left">
        <button class="btn-back" @click="$emit('back')" title="返回列表">
          <span class="icon">←</span>
        </button>
        <h1 class="workflow-title">{{ store.currentWorkflow?.name ?? '未命名工作流' }}</h1>
        <span v-if="store.currentWorkflow" class="version-badge">
          v{{ store.currentWorkflow.version }}
        </span>
        <span
          v-if="store.hasUnsavedChanges"
          class="unsaved-badge"
          title="有未保存的更改"
        >
          ● 未保存
        </span>
      </div>

      <div class="header-center">
        <div class="tool-group">
          <button
            class="tool-btn"
            :class="{ active: activeTool === 'select' }"
            @click="activeTool = 'select'"
            title="选择（V）"
          >
            <span class="tool-icon">↖</span>
          </button>
          <button
            class="tool-btn"
            :class="{ active: activeTool === 'connect' }"
            @click="activeTool = 'connect'"
            title="连线（C）"
          >
            <span class="tool-icon">—</span>
          </button>
          <span class="tool-divider"></span>
          <button class="tool-btn" @click="zoomIn" title="放大（+）">
            <span class="tool-icon">⊕</span>
          </button>
          <span class="zoom-label">{{ Math.round(zoom * 100) }}%</span>
          <button class="tool-btn" @click="zoomOut" title="缩小（-）">
            <span class="tool-icon">⊖</span>
          </button>
          <button class="tool-btn" @click="fitToScreen" title="适应屏幕">
            <span class="tool-icon">⊞</span>
          </button>
        </div>
      </div>

      <div class="header-right">
        <button class="btn-action btn-execute" @click="handleExecute" :disabled="store.executing">
          <span v-if="store.executing" class="spinner"></span>
          <span v-else class="icon">▶</span>
          {{ store.executing ? '执行中...' : '执行' }}
        </button>
        <button class="btn-action btn-save" @click="handleSave" :disabled="store.loading">
          {{ store.loading ? '保存中...' : '保存' }}
        </button>
        <button class="btn-action btn-versions" @click="showVersions = true" title="版本管理">
          📋 版本
        </button>
      </div>
    </header>

    <!-- 主编辑区域 -->
    <div class="editor-body">
      <!-- 左侧节点面板 -->
      <aside class="node-palette">
        <div class="palette-title">节点面板</div>
        <div class="palette-section">
          <div class="palette-section-title">触发器</div>
          <NodePaletteItem
            v-for="tpl in triggerTemplates"
            :key="tpl.label"
            :template="tpl"
            @drag-start="onDragStart"
          />
        </div>
        <div class="palette-section">
          <div class="palette-section-title">条件</div>
          <NodePaletteItem
            v-for="tpl in conditionTemplates"
            :key="tpl.label"
            :template="tpl"
            @drag-start="onDragStart"
          />
        </div>
        <div class="palette-section">
          <div class="palette-section-title">动作</div>
          <NodePaletteItem
            v-for="tpl in actionTemplates"
            :key="tpl.label"
            :template="tpl"
            @drag-start="onDragStart"
          />
        </div>
        <div class="palette-section">
          <div class="palette-section-title">循环</div>
          <NodePaletteItem
            v-for="tpl in loopTemplates"
            :key="tpl.label"
            :template="tpl"
            @drag-start="onDragStart"
          />
        </div>
      </aside>

      <!-- 画布区域 -->
      <div class="canvas-container" ref="canvasContainer">
        <WorkflowCanvas
          :nodes="store.currentWorkflow?.nodes ?? []"
          :connections="store.currentWorkflow?.connections ?? []"
          :selected-node-id="selectedNodeId"
          :zoom="zoom"
          :active-tool="activeTool"
          :connecting-from="connectingFrom"
          @node-click="onNodeClick"
          @node-move="onNodeMove"
          @canvas-click="onCanvasClick"
          @drop-node="onDropNode"
          @start-connection="onStartConnection"
          @end-connection="onEndConnection"
          @connection-click="onConnectionClick"
        />
      </div>

      <!-- 右侧属性面板 -->
      <aside class="properties-panel" v-if="selectedNodeId && selectedNode">
        <div class="panel-header">
          <h2>节点属性</h2>
          <button class="btn-close" @click="selectedNodeId = null">✕</button>
        </div>
        <NodePropertyEditor
          :node="selectedNode"
          :workflow="store.currentWorkflow"
          @update:node="handleNodeUpdate"
          @delete="handleNodeDelete"
        />
      </aside>

      <aside class="properties-panel" v-else-if="selectedConnectionId && selectedConnection">
        <div class="panel-header">
          <h2>连接属性</h2>
          <button class="btn-close" @click="selectedConnectionId = null">✕</button>
        </div>
        <ConnectionPropertyEditor
          :connection="selectedConnection"
          @update:connection="handleConnectionUpdate"
          @delete="handleConnectionDelete"
        />
      </aside>
    </div>

    <!-- 底部状态栏 -->
    <footer class="editor-statusbar">
      <span>{{ store.currentWorkflow?.nodes.length ?? 0 }} 个节点</span>
      <span>{{ store.currentWorkflow?.connections.length ?? 0 }} 条连线</span>
      <span v-if="store.error" class="status-error">{{ store.error }}</span>
    </footer>

    <!-- 版本管理对话框 -->
    <WorkflowVersionsDialog
      v-if="showVersions"
      @close="showVersions = false"
    />

    <!-- 执行结果对话框 -->
    <ExecutionResultDialog
      v-if="executionResult"
      :result="executionResult"
      @close="executionResult = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useWorkflowEngineStore } from './store';
import type {
  WorkflowNode,
  WorkflowConnection,
  NodeTemplate,
  Position,
  WorkflowExecution,
} from './types';
import { nodeTemplates } from './templates';
import { executeWorkflow as runWorkflow } from './engine';
import NodePaletteItem from './components/NodePaletteItem.vue';
import WorkflowCanvas from './components/WorkflowCanvas.vue';
import NodePropertyEditor from './components/NodePropertyEditor.vue';
import ConnectionPropertyEditor from './components/ConnectionPropertyEditor.vue';
import WorkflowVersionsDialog from './components/WorkflowVersionsDialog.vue';
import ExecutionResultDialog from './components/ExecutionResultDialog.vue';

// ───── Emits ─────
const emit = defineEmits<{
  back: [];
}>();

// ───── Store ─────
const store = useWorkflowEngineStore();

// ───── 编辑器状态 ─────
const activeTool = ref<'select' | 'connect'>('select');
const zoom = ref(1);
const canvasContainer = ref<HTMLDivElement>();
const selectedNodeId = ref<string | null>(null);
const selectedConnectionId = ref<string | null>(null);
const showVersions = ref(false);
const executionResult = ref<WorkflowExecution | null>(null);
const connectingFrom = ref<{ nodeId: string; port: string } | null>(null);

// ───── 节点模板 ─────
const triggerTemplates = nodeTemplates.filter((t) => t.type === 'trigger');
const conditionTemplates = nodeTemplates.filter((t) => t.type === 'condition');
const actionTemplates = nodeTemplates.filter((t) => t.type === 'action');
const loopTemplates = nodeTemplates.filter((t) => t.type === 'loop');

// ───── 计算属性 ─────
const selectedNode = computed(() => {
  if (!selectedNodeId.value || !store.currentWorkflow) return null;
  return store.currentWorkflow.nodes.find((n) => n.id === selectedNodeId.value) ?? null;
});

const selectedConnection = computed(() => {
  if (!selectedConnectionId.value || !store.currentWorkflow) return null;
  return (
    store.currentWorkflow.connections.find(
      (c) => c.id === selectedConnectionId.value,
    ) ?? null
  );
});

// ───── 拖拽处理 ─────
function onDragStart(template: NodeTemplate) {
  // 拖拽数据通过 dataTransfer 传递，在 WorkflowCanvas 中处理
}

function onDropNode(templateType: string, position: Position) {
  const template = nodeTemplates.find((t) => t.type === templateType);
  if (!template) return;

  const nodeId = `node_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const newNode: WorkflowNode = {
    id: nodeId,
    label: `${template.label} ${store.nodeCount + 1}`,
    type: template.type,
    config: JSON.parse(JSON.stringify(template.defaultConfig)),
    position,
    enabled: true,
  };

  store.addNode(newNode);
  selectedNodeId.value = nodeId;
}

// ───── 节点操作 ─────
function onNodeClick(nodeId: string) {
  if (activeTool.value === 'connect') {
    // 连线工具状态：处理连线
    handleConnectClick(nodeId);
    return;
  }
  selectedNodeId.value = nodeId;
  selectedConnectionId.value = null;
}

function onNodeMove(nodeId: string, x: number, y: number) {
  store.moveNode(nodeId, x, y);
}

function onCanvasClick() {
  selectedNodeId.value = null;
  selectedConnectionId.value = null;
  connectingFrom.value = null;
}

// ───── 连线处理 ─────
function onStartConnection(nodeId: string, port: string) {
  connectingFrom.value = { nodeId, port };
}

function onEndConnection(nodeId: string, port: string) {
  if (!connectingFrom.value) return;
  if (connectingFrom.value.nodeId === nodeId) return;

  const connId = `conn_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const newConn: WorkflowConnection = {
    id: connId,
    sourceNodeId: connectingFrom.value.nodeId,
    sourcePort: connectingFrom.value.port,
    targetNodeId: nodeId,
    targetPort: port,
  };

  store.addConnection(newConn);
  connectingFrom.value = null;
}

function handleConnectClick(nodeId: string) {
  if (!connectingFrom.value) {
    // 开始连线
    connectingFrom.value = { nodeId, port: 'out' };
  } else {
    // 结束连线
    onEndConnection(nodeId, 'in');
  }
}

function onConnectionClick(connectionId: string) {
  selectedConnectionId.value = connectionId;
  selectedNodeId.value = null;
}

// ───── 属性更新 ─────
function handleNodeUpdate(nodeId: string, updates: Partial<WorkflowNode>) {
  store.updateNode(nodeId, updates);
}

function handleNodeDelete(nodeId: string) {
  store.removeNode(nodeId);
  selectedNodeId.value = null;
}

function handleConnectionUpdate(connectionId: string, updates: Partial<WorkflowConnection>) {
  // 通过 store 更新
  const conn = store.currentWorkflow?.connections.find((c) => c.id === connectionId);
  if (conn) {
    Object.assign(conn, updates);
    store.hasUnsavedChanges; // 触发响应式
  }
}

function handleConnectionDelete(connectionId: string) {
  store.removeConnection(connectionId);
  selectedConnectionId.value = null;
}

// ───── 缩放控制 ─────
function zoomIn() {
  zoom.value = Math.min(2, zoom.value + 0.1);
}

function zoomOut() {
  zoom.value = Math.max(0.3, zoom.value - 0.1);
}

function fitToScreen() {
  zoom.value = 1;
}

// ───── 工具栏操作 ─────
async function handleSave() {
  if (!store.currentWorkflow) {
    // 提示用户创建工作流
    const name = prompt('请输入工作流名称:');
    if (!name) return;
    store.createDraft(name);
  }

  const wf = store.currentWorkflow;
  if (!wf) return;

  if (wf.id.startsWith('wf_')) {
    // 新工作流，执行创建
    await store.createWorkflow({
      name: wf.name,
      description: wf.description,
      nodes: wf.nodes,
      connections: wf.connections,
      variables: wf.variables,
      tags: wf.tags,
    });
  } else {
    // 更新已有的
    await store.updateWorkflow({
      name: wf.name,
      description: wf.description,
      nodes: wf.nodes,
      connections: wf.connections,
      variables: wf.variables,
      tags: wf.tags,
    });
  }
}

async function handleExecute() {
  if (!store.currentWorkflow) return;
  const result = await runWorkflow(store.currentWorkflow);
  if (result) {
    executionResult.value = result;
  }
}

// ───── 键盘快捷键 ─────
function handleKeydown(e: KeyboardEvent) {
  // 只在编辑器区域内响应
  if (e.ctrlKey || e.metaKey) {
    switch (e.key.toLowerCase()) {
      case 's':
        e.preventDefault();
        handleSave();
        break;
      case 'z':
        e.preventDefault();
        // TODO: 撤销
        break;
      case 'a':
        e.preventDefault();
        // 全选
        break;
    }
    return;
  }

  switch (e.key.toLowerCase()) {
    case 'v':
      activeTool.value = 'select';
      break;
    case 'c':
      activeTool.value = 'connect';
      break;
    case 'delete':
    case 'backspace':
      if (selectedNodeId.value) {
        e.preventDefault();
        handleNodeDelete(selectedNodeId.value);
      } else if (selectedConnectionId.value) {
        e.preventDefault();
        handleConnectionDelete(selectedConnectionId.value);
      }
      break;
  }
}

// ───── 生命周期 ─────
onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped>
.workflow-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color-page, #f5f7fa);
  color: var(--el-text-color-primary, #303133);
}

/* ───── 顶部工具栏 ───── */
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--el-bg-color, #fff);
  border-bottom: 1px solid var(--el-border-color-light, #e4e7ed);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-back {
  background: none;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 16px;
  color: var(--el-text-color-regular, #606266);
}
.btn-back:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}

.workflow-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.version-badge {
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.unsaved-badge {
  color: var(--el-color-warning, #e6a23c);
  font-size: 11px;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.header-center {
  display: flex;
  align-items: center;
}

.tool-group {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 6px;
  padding: 4px;
}

.tool-btn {
  background: none;
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  color: var(--el-text-color-regular, #606266);
  font-size: 14px;
}
.tool-btn:hover {
  background: var(--el-color-primary-light-9, #ecf5ff);
}
.tool-btn.active {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.tool-divider {
  width: 1px;
  height: 20px;
  background: var(--el-border-color, #dcdfe6);
  margin: 0 4px;
}

.zoom-label {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  min-width: 36px;
  text-align: center;
}

.tool-icon {
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-action {
  padding: 6px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}
.btn-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-execute {
  background: var(--el-color-success, #67c23a);
  color: #fff;
}
.btn-execute:hover:not(:disabled) {
  background: #5daf34;
}

.btn-save {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}
.btn-save:hover:not(:disabled) {
  background: #3a8ee6;
}

.btn-versions {
  background: var(--el-fill-color, #f0f2f5);
  color: var(--el-text-color-regular, #606266);
  border: 1px solid var(--el-border-color, #dcdfe6);
}
.btn-versions:hover {
  background: var(--el-border-color-extra-light, #e4e7ed);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ───── 编辑主体 ───── */
.editor-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ───── 左侧节点面板 ───── */
.node-palette {
  width: 200px;
  min-width: 200px;
  background: var(--el-bg-color, #fff);
  border-right: 1px solid var(--el-border-color-light, #e4e7ed);
  overflow-y: auto;
  padding: 12px;
}

.palette-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular, #606266);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light, #f2f6fc);
}

.palette-section {
  margin-bottom: 16px;
}

.palette-section-title {
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  padding-left: 4px;
}

/* ───── 画布区域 ───── */
.canvas-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: var(--el-bg-color-page, #f0f2f5);
  background-image:
    radial-gradient(circle, var(--el-border-color-extra-light, #e4e7ed) 1px, transparent 1px);
  background-size: 20px 20px;
}

/* ───── 右侧属性面板 ───── */
.properties-panel {
  width: 320px;
  min-width: 320px;
  background: var(--el-bg-color, #fff);
  border-left: 1px solid var(--el-border-color-light, #e4e7ed);
  overflow-y: auto;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-light, #e4e7ed);
  position: sticky;
  top: 0;
  background: var(--el-bg-color, #fff);
  z-index: 5;
}

.panel-header h2 {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--el-text-color-secondary, #909399);
  padding: 4px;
  border-radius: 4px;
}
.btn-close:hover {
  background: var(--el-fill-color-light, #f5f7fa);
  color: var(--el-text-color-primary, #303133);
}

/* ───── 底部状态栏 ───── */
.editor-statusbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 4px 16px;
  background: var(--el-bg-color, #fff);
  border-top: 1px solid var(--el-border-color-light, #e4e7ed);
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
}

.status-error {
  color: var(--el-color-danger, #f56c6c);
  flex: 1;
}
</style>
