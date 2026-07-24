<!--
  伏羲 v2.1 — 画布节点组件
  可拖拽交互的工作流节点卡片
-->
<template>
  <div
    class="workflow-node"
    :class="{
      selected: selected,
      disabled: !node.enabled,
    }"
    :style="nodeStyle"
    @mousedown.stop="onMouseDown"
    @click.stop="$emit('click')"
  >
    <!-- 节点头部 -->
    <div class="node-header" :style="{ borderTopColor: nodeColor }">
      <span class="node-icon">{{ nodeIcon }}</span>
      <span class="node-label">{{ node.label }}</span>
      <span class="node-type-badge" :style="{ background: nodeColor }">
        {{ typeLabel }}
      </span>
    </div>

    <!-- 节点摘要 -->
    <div class="node-body">
      <span class="node-summary">{{ summary }}</span>
    </div>

    <!-- 输入端口（左侧） -->
    <div
      v-if="node.type !== 'trigger'"
      class="port port-in"
      title="输入端口"
      @mousedown.stop="onPortMouseDown('in', $event)"
    >
      <div class="port-dot"></div>
    </div>

    <!-- 输出端口（右侧） -->
    <div
      class="port port-out"
      title="输出端口"
      @mousedown.stop="onPortMouseDown('out', $event)"
    >
      <div class="port-dot"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { WorkflowNode as WfNode } from '../types';
import { getNodeColor, getNodeIcon } from '../templates';

const props = defineProps<{
  node: WfNode;
  selected: boolean;
  connectingActive: boolean;
}>();

const emit = defineEmits<{
  click: [];
  'start-connection': [];
  'end-connection': [];
  move: [x: number, y: number];
}>();

// ───── 样式计算 ─────
const nodeColor = computed(() => getNodeColor(props.node.type));
const nodeIcon = computed(() => getNodeIcon(props.node.type));

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    trigger: '触发器',
    condition: '条件',
    action: '动作',
    loop: '循环',
  };
  return labels[props.node.type] ?? props.node.type;
});

const nodeStyle = computed(() => ({
  left: `${props.node.position.x}px`,
  top: `${props.node.position.y}px`,
}));

const summary = computed(() => {
  const config = props.node.config as Record<string, unknown>;
  switch (props.node.type) {
    case 'trigger':
      return config.subType ? String(config.subType) : '手动';
    case 'condition':
      return `${(config.branches as unknown[])?.length ?? 0} 个分支`;
    case 'action':
      return config.subType ? String(config.subType) : '动作';
    case 'loop':
      return config.subType ? String(config.subType) : '循环';
    default:
      return '';
  }
});

// ───── 拖拽逻辑 ─────
let isDragging = false;
let dragStart = { x: 0, y: 0 };
let nodeStart = { x: 0, y: 0 };

function onMouseDown(e: MouseEvent) {
  // 忽略端口点击
  if ((e.target as HTMLElement).closest('.port')) return;

  isDragging = true;
  dragStart = { x: e.clientX, y: e.clientY };
  nodeStart = { x: props.node.position.x, y: props.node.position.y };

  const onMove = (ev: MouseEvent) => {
    if (!isDragging) return;
    const dx = ev.clientX - dragStart.x;
    const dy = ev.clientY - dragStart.y;
    const newX = nodeStart.x + dx;
    const newY = nodeStart.y + dy;
    // 限制在画布内
    emit('move', Math.max(0, newX), Math.max(0, newY));
  };

  const onUp = () => {
    isDragging = false;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  };

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function onPortMouseDown(port: string, e: MouseEvent) {
  e.stopPropagation();
  e.preventDefault();
  if (port === 'out') {
    emit('start-connection');
  } else {
    emit('end-connection');
  }
}
</script>

<style scoped>
.workflow-node {
  position: absolute;
  width: 180px;
  min-height: 70px;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s;
  user-select: none;
}

.workflow-node:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.workflow-node.selected {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.workflow-node.disabled {
  opacity: 0.5;
}

/* ───── 头部 ───── */
.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-top: 3px solid #409eff;
  border-radius: 8px 8px 0 0;
  background: var(--el-fill-color-light, #f5f7fa);
}

.node-icon {
  font-size: 14px;
}

.node-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary, #303133);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-type-badge {
  font-size: 9px;
  color: #fff;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
  font-weight: 500;
}

/* ───── 正文 ───── */
.node-body {
  padding: 6px 10px 10px;
}

.node-summary {
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
}

/* ───── 端口 ───── */
.port {
  position: absolute;
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  top: 50%;
  transform: translateY(-50%);
  cursor: crosshair;
  z-index: 2;
}

.port-in {
  left: -7px;
}

.port-out {
  right: -7px;
}

.port-dot {
  width: 10px;
  height: 10px;
  background: var(--el-bg-color, #fff);
  border: 2px solid var(--el-text-color-placeholder, #c0c4cc);
  border-radius: 50%;
  transition: all 0.15s;
}

.port:hover .port-dot {
  border-color: var(--el-color-primary, #409eff);
  background: var(--el-color-primary-light-9, #ecf5ff);
  transform: scale(1.2);
}
</style>
