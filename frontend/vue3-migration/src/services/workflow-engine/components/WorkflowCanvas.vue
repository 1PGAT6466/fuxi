<!--
  伏羲 v2.1 — 工作流画布
  负责渲染节点、连接线和处理交互事件
-->
<template>
  <div
    class="workflow-canvas"
    ref="canvasRef"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
    @mousedown="onCanvasMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @wheel.prevent="onWheel"
  >
    <!-- 变换层 -->
    <div
      class="canvas-transform"
      :style="transformStyle"
    >
      <!-- SVG 连接线层 -->
      <svg class="connections-layer" :width="svgWidth" :height="svgHeight">
        <!-- 已有连接线 -->
        <g
          v-for="conn in connections"
          :key="conn.id"
          class="connection-group"
          @click.stop="$emit('connection-click', conn.id)"
        >
          <path
            :d="getConnectionPath(conn)"
            class="connection-line"
            :class="{
              'has-label': !!conn.label,
            }"
            fill="none"
            stroke-width="2"
          />
          <text
            v-if="conn.label"
            :x="getConnectionMidpoint(conn).x"
            :y="getConnectionMidpoint(conn).y - 8"
            class="connection-label"
            text-anchor="middle"
          >
            {{ conn.label }}
          </text>
        </g>

        <!-- 正在连线中的临时线 -->
        <line
          v-if="activeConnectingLine"
          :x1="activeConnectingLine.x1"
          :y1="activeConnectingLine.y1"
          :x2="activeConnectingLine.x2"
          :y2="activeConnectingLine.y2"
          class="connection-line temp-line"
          stroke-dasharray="6,3"
        />
      </svg>

      <!-- 节点层 -->
      <WorkflowNode
        v-for="node in nodes"
        :key="node.id"
        :node="node"
        :selected="node.id === selectedNodeId"
        :connecting-active="connectingFrom !== null"
        @click="$emit('node-click', node.id)"
        @start-connection="$emit('start-connection', node.id, 'out')"
        @end-connection="$emit('end-connection', node.id, 'in')"
        @move="(x, y) => $emit('node-move', node.id, x, y)"
      />
    </div>

    <!-- 空画布提示 -->
    <div v-if="nodes.length === 0" class="canvas-empty">
      <div class="empty-icon">⚡</div>
      <div class="empty-title">空工作流</div>
      <div class="empty-desc">从左侧拖拽节点到画布开始编排</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { WorkflowNode, WorkflowConnection, Position } from '../types';
import WorkflowNodeComponent from './WorkflowNode.vue';

const props = defineProps<{
  nodes: WorkflowNode[];
  connections: WorkflowConnection[];
  selectedNodeId: string | null;
  zoom: number;
  activeTool: string;
  connectingFrom: { nodeId: string; port: string } | null;
}>();

// 当前无单独的连接选中状态管理，由父级通过 connection-click 事件处理

const emit = defineEmits<{
  'node-click': [nodeId: string];
  'node-move': [nodeId: string, x: number, y: number];
  'canvas-click': [];
  'drop-node': [templateType: string, position: Position];
  'start-connection': [nodeId: string, port: string];
  'end-connection': [nodeId: string, port: string];
  'connection-click': [connectionId: string];
}>();

const canvasRef = ref<HTMLDivElement>();
const svgWidth = ref(4000);
const svgHeight = ref(4000);
const panOffset = ref({ x: 0, y: 0 });
const isPanning = ref(false);
const panStart = ref({ x: 0, y: 0 });
const mousePos = ref({ x: 0, y: 0 });

// ───── 样式计算 ─────
const transformStyle = computed(() => ({
  transform: `translate(${panOffset.value.x}px, ${panOffset.value.y}px) scale(${props.zoom})`,
  transformOrigin: '0 0',
}));

// ───── 连线中临时线 ─────
const activeConnectingLine = computed(() => {
  if (!props.connectingFrom) return null;
  const sourceNode = props.nodes.find((n) => n.id === props.connectingFrom!.nodeId);
  if (!sourceNode) return null;
  const sourceCenter = getNodeCenter(sourceNode);
  const target = screenToCanvas(mousePos.value.x, mousePos.value.y);
  return {
    x1: sourceCenter.x,
    y1: sourceCenter.y,
    x2: target.x,
    y2: target.y,
  };
});

// ───── 坐标转换 ─────
function screenToCanvas(screenX: number, screenY: number): Position {
  const rect = canvasRef.value?.getBoundingClientRect();
  if (!rect) return { x: screenX, y: screenY };
  return {
    x: (screenX - rect.left - panOffset.value.x) / props.zoom,
    y: (screenY - rect.top - panOffset.value.y) / props.zoom,
  };
}

function getNodeCenter(node: WorkflowNode): Position {
  const NODE_WIDTH = 180;
  const NODE_HEIGHT = 80;
  return {
    x: node.position.x + NODE_WIDTH / 2,
    y: node.position.y + NODE_HEIGHT / 2,
  };
}

function getNodeOutPort(node: WorkflowNode): Position {
  const center = getNodeCenter(node);
  return { x: center.x + 90, y: center.y };
}

function getNodeInPort(node: WorkflowNode): Position {
  const center = getNodeCenter(node);
  return { x: center.x - 90, y: center.y };
}

// ───── SVG 连接线路径 ─────
function getConnectionPath(conn: WorkflowConnection): string {
  const sourceNode = props.nodes.find((n) => n.id === conn.sourceNodeId);
  const targetNode = props.nodes.find((n) => n.id === conn.targetNodeId);
  if (!sourceNode || !targetNode) return '';

  const start = getNodeOutPort(sourceNode);
  const end = getNodeInPort(targetNode);
  const dx = end.x - start.x;
  const controlOffset = Math.max(Math.abs(dx) * 0.5, 50);

  // 贝塞尔曲线
  return `M ${start.x} ${start.y} C ${start.x + controlOffset} ${start.y}, ${end.x - controlOffset} ${end.y}, ${end.x} ${end.y}`;
}

function getConnectionMidpoint(conn: WorkflowConnection): Position {
  const sourceNode = props.nodes.find((n) => n.id === conn.sourceNodeId);
  const targetNode = props.nodes.find((n) => n.id === conn.targetNodeId);
  if (!sourceNode || !targetNode) return { x: 0, y: 0 };
  const start = getNodeOutPort(sourceNode);
  const end = getNodeInPort(targetNode);
  return {
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2,
  };
}

// ───── 鼠标事件 ─────
function onCanvasMouseDown(e: MouseEvent) {
  if (e.target === canvasRef.value || (e.target as HTMLElement).classList.contains('canvas-transform')) {
    isPanning.value = true;
    panStart.value = { x: e.clientX - panOffset.value.x, y: e.clientY - panOffset.value.y };
    emit('canvas-click');
  }
}

function onMouseMove(e: MouseEvent) {
  mousePos.value = { x: e.clientX, y: e.clientY };
  if (isPanning.value) {
    panOffset.value = {
      x: e.clientX - panStart.value.x,
      y: e.clientY - panStart.value.y,
    };
  }
}

function onMouseUp() {
  isPanning.value = false;
}

// ───── 缩放 ─────
function onWheel(e: WheelEvent) {
  const newZoom = props.zoom - e.deltaY * 0.001;
  // 通过父组件更新 zoom
  // zoom 是 prop，这里只在 canvas 内部参考
}

// ───── 拖放节点 ─────
function onDragOver(e: DragEvent) {
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'copy';
  }
}

function onDragLeave(_e: DragEvent) {
  // handle if needed
}

function onDrop(e: DragEvent) {
  const templateType = e.dataTransfer?.getData('application/workflow-template-type');
  if (!templateType) return;

  const position = screenToCanvas(e.clientX, e.clientY);
  emit('drop-node', templateType, position);
}
</script>

<style scoped>
.workflow-canvas {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  cursor: grab;
}

.workflow-canvas:active {
  cursor: grabbing;
}

.canvas-transform {
  position: absolute;
  top: 0;
  left: 0;
}

.connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  overflow: visible;
}

.connection-group {
  pointer-events: stroke;
  cursor: pointer;
}

.connection-line {
  stroke: var(--el-text-color-placeholder, #c0c4cc);
  stroke-width: 2;
  transition: stroke 0.15s;
}

.connection-line.selected {
  stroke: var(--el-color-primary, #409eff);
  stroke-width: 3;
}

.connection-line.temp-line {
  stroke: var(--el-color-primary, #409eff);
  opacity: 0.5;
}

.connection-group:hover .connection-line {
  stroke: var(--el-color-primary, #409eff);
  stroke-width: 2.5;
}

.connection-label {
  font-size: 11px;
  fill: var(--el-text-color-secondary, #909399);
  pointer-events: none;
}

/* ───── 空状态 ───── */
.canvas-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.3;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-placeholder, #c0c4cc);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}
</style>
