<template>
  <!--
    伏羲 v2.1 — DxfCanvas：Canvas 2D 渲染核心
    支持缩放（滚轮）、平移（拖拽）、适应窗口
  -->
  <div
    ref="containerRef"
    class="dxf-canvas-container"
    @wheel.prevent="handleWheel"
    @mousedown="handleMouseDown"
    @mousemove="handleMouseMove"
    @mouseup="handleMouseUp"
    @mouseleave="handleMouseUp"
    @touchstart.prevent="handleTouchStart"
    @touchmove.prevent="handleTouchMove"
    @touchend.prevent="handleTouchEnd"
  >
    <canvas ref="canvasRef" class="dxf-canvas" :width="canvasWidth" :height="canvasHeight" />
    <!-- 加载状态 -->
    <div v-if="store.renderLoading" class="dxf-canvas-loading">
      <el-skeleton :rows="5" animated class="canvas-skeleton" />
    </div>
    <!-- 错误状态 -->
    <div v-else-if="renderError" class="dxf-canvas-error">
      <el-result icon="error" title="渲染失败" sub-title="无法加载 DXF 渲染数据，请重试">
        <template #extra>
          <el-button type="primary" size="small" @click="retryRender">重试</el-button>
        </template>
      </el-result>
    </div>
    <!-- 空状态 -->
    <div v-else-if="!store.renderData" class="dxf-canvas-empty">
      <el-empty description="选择一个 DXF 文件开始浏览" :image-size="80" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useDxfViewerStore } from './store';
import type { DxfEntity, DxfPoint } from './types';

const store = useDxfViewerStore();
const renderError = ref(false);

// 监听渲染数据变化来清除错误状态
watch(
  () => store.currentFileHash,
  () => {
    renderError.value = false;
  },
);

watch(
  () => store.renderLoading,
  (loading) => {
    if (!loading && !store.renderData && store.currentFileHash) {
      // 加载完成但没有数据 → 错误状态
      renderError.value = true;
    }
  },
);

function retryRender() {
  if (store.currentFileHash) {
    renderError.value = false;
    store.loadFile(store.currentFileHash);
  }
}

// ─── Canvas 引用 ───
const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
const canvasWidth = ref(1200);
const canvasHeight = ref(800);

// ─── 交互状态 ───
const isPanning = ref(false);
const panStart = ref<DxfPoint>({ x: 0, y: 0 });
const panOffsetStart = ref<DxfPoint>({ x: 0, y: 0 });

// ─── 初始化 ───
onMounted(() => {
  updateCanvasSize();
  window.addEventListener('resize', updateCanvasSize);
  render();
});

onUnmounted(() => {
  window.removeEventListener('resize', updateCanvasSize);
});

// ─── 监听数据变化重新渲染 ───
watch(
  () => [
    store.visibleEntities,
    store.viewState.zoom,
    store.viewState.offsetX,
    store.viewState.offsetY,
    store.annotations,
    store.measurements,
    store.viewState.selectedEntityIndex,
  ],
  () => {
    nextTick(render);
  },
  { deep: true },
);

// ─── Canvas 尺寸 ───
function updateCanvasSize(): void {
  if (containerRef.value) {
    canvasWidth.value = containerRef.value.clientWidth;
    canvasHeight.value = containerRef.value.clientHeight;
    nextTick(render);
  }
}

// ─── 渲染核心 ───
function render(): void {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 背景（阳模式米白色）
  ctx.fillStyle = '#FAFAF5';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const { zoom, offsetX, offsetY } = store.viewState;

  // 应用变换
  ctx.save();
  ctx.translate(offsetX, offsetY);
  ctx.scale(zoom, zoom);

  // 渲染网格（轻量背景网格）
  drawGrid(ctx);

  // 渲染实体
  const entities = store.visibleEntities;
  for (let i = 0; i < entities.length; i++) {
    const entity = entities[i];
    const isSelected = i === store.viewState.selectedEntityIndex;
    drawEntity(ctx, entity, isSelected);
  }

  ctx.restore();

  // 渲染标注（屏幕坐标 — 在当前变换外面）
  drawAnnotations(ctx);

  // 渲染测量（屏幕坐标）
  drawMeasurements(ctx);
}

function drawGrid(ctx: CanvasRenderingContext2D): void {
  const step = 50;
  const { zoom, offsetX, offsetY } = store.viewState;
  const invZoom = 1 / zoom;

  // 计算可见范围（世界坐标）
  const worldLeft = -offsetX * invZoom - step;
  const worldTop = -offsetY * invZoom - step;
  const worldRight = (-offsetX + canvasWidth.value) * invZoom + step;
  const worldBottom = (-offsetY + canvasHeight.value) * invZoom + step;

  const startX = Math.floor(worldLeft / step) * step;
  const startY = Math.floor(worldTop / step) * step;

  ctx.strokeStyle = '#E8E4D9'; // 网格线色（米白配套）
  ctx.lineWidth = 1 * invZoom;

  ctx.beginPath();
  for (let x = startX; x <= worldRight; x += step) {
    ctx.moveTo(x, worldTop);
    ctx.lineTo(x, worldBottom);
  }
  for (let y = startY; y <= worldBottom; y += step) {
    ctx.moveTo(worldLeft, y);
    ctx.lineTo(worldRight, y);
  }
  ctx.stroke();
}

function drawEntity(ctx: CanvasRenderingContext2D, entity: DxfEntity, isSelected: boolean): void {
  const color = entity.color || '#333333'; // 默认文字色（阳模式主文字）

  ctx.strokeStyle = isSelected ? '#FF6700' : color; // 选中态暖橙点缀
  ctx.fillStyle = color;
  ctx.lineWidth = isSelected ? 3 : 1.5;

  switch (entity.type) {
    case 'LINE':
      ctx.beginPath();
      ctx.moveTo(entity.start.x, entity.start.y);
      ctx.lineTo(entity.end.x, entity.end.y);
      ctx.stroke();
      break;

    case 'CIRCLE':
      ctx.beginPath();
      ctx.arc(entity.center.x, entity.center.y, entity.radius, 0, Math.PI * 2);
      if (isSelected) {
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fillStyle = 'rgba(255, 103, 0, 0.08)';
        ctx.fill();
      } else {
        ctx.stroke();
      }
      break;

    case 'RECT': {
      const w = entity.max.x - entity.min.x;
      const h = entity.max.y - entity.min.y;
      ctx.strokeRect(entity.min.x, entity.min.y, w, h);
      if (isSelected) {
        ctx.fillStyle = 'rgba(255, 103, 0, 0.08)';
        ctx.fillRect(entity.min.x, entity.min.y, w, h);
      }
      break;
    }

    case 'TEXT': {
      const fontSize = entity.height || 14;
        ctx.font = `${isSelected ? 'bold ' : ''}${fontSize}px "MiSans", "Inter", sans-serif`;
      ctx.fillStyle = color;
      ctx.fillText(entity.content, entity.position.x, entity.position.y);
      break;
    }

    default:
      break;
  }

  // 选中高亮边框
if (isSelected) {
ctx.strokeStyle = '#FF6700'; // 暖橙点缀色
ctx.lineWidth = 3;
}
}

// ─── 标注渲染（屏幕坐标） ───
function drawAnnotations(ctx: CanvasRenderingContext2D): void {
  const { zoom, offsetX, offsetY } = store.viewState;

  for (const ann of store.annotations) {
    const sx = ann.x * zoom + offsetX;
    const sy = ann.y * zoom + offsetY;

    // 标注图标（小圆点）
    ctx.fillStyle = '#FF6700';
    ctx.beginPath();
    ctx.arc(sx, sy, 6, 0, Math.PI * 2);
    ctx.fill();

    // 标注文本气泡
    ctx.fillStyle = '#FFFFFF';
    ctx.strokeStyle = '#FF6700';
    ctx.lineWidth = 1;
    const textWidth = ctx.measureText(ann.content).width + 16;
    const bubbleX = sx + 10;
    const bubbleY = sy - 20;
    const bubbleH = 24;

    // 圆角矩形
    roundRect(ctx, bubbleX, bubbleY, textWidth, bubbleH, 6);
    ctx.fill();
    ctx.stroke();

    // 文本（阳模式主文字色）
    ctx.fillStyle = '#333333';
    ctx.font = '12px "MiSans", "Inter", sans-serif';
    ctx.fillText(ann.content, bubbleX + 8, bubbleY + 17);
  }
}

// ─── 测量渲染（屏幕坐标） ───
function drawMeasurements(ctx: CanvasRenderingContext2D): void {
  const { zoom, offsetX, offsetY } = store.viewState;

  for (const meas of store.measurements) {
    const sx = meas.startPoint.x * zoom + offsetX;
    const sy = meas.startPoint.y * zoom + offsetY;
    const ex = meas.endPoint.x * zoom + offsetX;
    const ey = meas.endPoint.y * zoom + offsetY;

    // 测量线
    ctx.strokeStyle = '#FF3B30';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 3]);
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(ex, ey);
    ctx.stroke();
    ctx.setLineDash([]);

    // 端点标记
    ctx.fillStyle = '#FF3B30';
    ctx.beginPath();
    ctx.arc(sx, sy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(ex, ey, 5, 0, Math.PI * 2);
    ctx.fill();

    // 距离标注
    const midX = (sx + ex) / 2;
    const midY = (sy + ey) / 2;
    const label = `${meas.distance}px`;
    ctx.fillStyle = '#FF3B30';
    ctx.font = 'bold 12px "PingFang SC", sans-serif';
    const labelWidth = ctx.measureText(label).width;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(midX - labelWidth / 2 - 4, midY - 10, labelWidth + 8, 18);
    ctx.fillStyle = '#FF3B30';
    ctx.fillText(label, midX - labelWidth / 2, midY + 4);
  }
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

// ─── 交互：滚轮缩放 ───
function handleWheel(e: WheelEvent): void {
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  const newZoom = store.viewState.zoom * delta;
  store.setZoom(newZoom);

  // 以鼠标位置为中心缩放
  if (containerRef.value && canvasRef.value) {
    const rect = containerRef.value.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const worldX = (mouseX - store.viewState.offsetX) / store.viewState.zoom;
    const worldY = (mouseY - store.viewState.offsetY) / store.viewState.zoom;

    const newOffsetX = mouseX - worldX * newZoom;
    const newOffsetY = mouseY - worldY * newZoom;

    store.setOffset(newOffsetX, newOffsetY);
  }
}

// ─── 触摸事件（映射到鼠标处理） ───
const touchInfo: {
  startX: number;
  startY: number;
  offsetX: number;
  offsetY: number;
  isPinching: boolean;
  lastPinchDistance: number;
  lastPinchZoom: number;
} = {
  startX: 0,
  startY: 0,
  offsetX: 0,
  offsetY: 0,
  isPinching: false,
  lastPinchDistance: 0,
  lastPinchZoom: 0,
};

function getTouchDistance(touches: TouchList): number {
  if (touches.length < 2) return 0;
  const dx = touches[0].clientX - touches[1].clientX;
  const dy = touches[0].clientY - touches[1].clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

function getTouchCenter(touches: TouchList): { x: number; y: number } {
  if (touches.length === 0) return { x: 0, y: 0 };
  let x = 0,
    y = 0;
  for (let i = 0; i < touches.length; i++) {
    x += touches[i].clientX;
    y += touches[i].clientY;
  }
  return { x: x / touches.length, y: y / touches.length };
}

function handleTouchStart(e: TouchEvent): void {
  const touches = e.touches;

  if (touches.length === 2) {
    // 双指缩放
    touchInfo.isPinching = true;
    touchInfo.lastPinchDistance = getTouchDistance(touches);
    touchInfo.lastPinchZoom = store.viewState.zoom;
    return;
  }

  if (touches.length === 1 && !touchInfo.isPinching) {
    // 单指 → 映射为 mousedown
    const touch = touches[0];
    touchInfo.startX = touch.clientX;
    touchInfo.startY = touch.clientY;
    touchInfo.offsetX = store.viewState.offsetX;
    touchInfo.offsetY = store.viewState.offsetY;
    touchInfo.isPinching = false;
    isPanning.value = true;
  }
}

function handleTouchMove(e: TouchEvent): void {
  const touches = e.touches;

  if (touchInfo.isPinching && touches.length === 2) {
    const newDist = getTouchDistance(touches);
    if (touchInfo.lastPinchDistance > 0) {
      const scale = newDist / touchInfo.lastPinchDistance;
      const newZoom = touchInfo.lastPinchZoom * scale;
      store.setZoom(newZoom);

      // 以双指中心为缩放中心
      const center = getTouchCenter(touches);
      if (containerRef.value) {
        const rect = containerRef.value.getBoundingClientRect();
        const cx = center.x - rect.left;
        const cy = center.y - rect.top;
        const wx = (cx - store.viewState.offsetX) / store.viewState.zoom;
        const wy = (cy - store.viewState.offsetY) / store.viewState.zoom;
        store.setOffset(cx - wx * newZoom, cy - wy * newZoom);
      }
    }
    return;
  }

  if (isPanning.value && touches.length === 1) {
    const dx = touches[0].clientX - touchInfo.startX;
    const dy = touches[0].clientY - touchInfo.startY;
    store.setOffset(touchInfo.offsetX + dx, touchInfo.offsetY + dy);
  }
}

function handleTouchEnd(): void {
  isPanning.value = false;
  touchInfo.isPinching = false;
  touchInfo.lastPinchDistance = 0;
}

// ─── 交互：鼠标（平移 + 工具） ───
function handleMouseDown(e: MouseEvent): void {
  if (!containerRef.value) return;

  const rect = containerRef.value.getBoundingClientRect();
  const clientX = e.clientX - rect.left;
  const clientY = e.clientY - rect.top;

  // 转换为世界坐标
  const worldX = (clientX - store.viewState.offsetX) / store.viewState.zoom;
  const worldY = (clientY - store.viewState.offsetY) / store.viewState.zoom;

  switch (store.activeTool) {
    case 'pan':
    case 'none':
      isPanning.value = true;
      panStart.value = { x: e.clientX, y: e.clientY };
      panOffsetStart.value = {
        x: store.viewState.offsetX,
        y: store.viewState.offsetY,
      };
      break;

    case 'measure':
      if (!store.isMeasuring) {
        store.isMeasuring = true;
        store.measureStartPoint = { x: worldX, y: worldY };
      }
      break;

    case 'annotate':
      store.addAnnotation({
        x: worldX,
        y: worldY,
        content: '点击编辑标注内容',
        color: '#FF6700',
      });
      break;

    default:
      break;
  }
}

function handleMouseMove(e: MouseEvent): void {
  if (isPanning.value) {
    const dx = e.clientX - panStart.value.x;
    const dy = e.clientY - panStart.value.y;
    store.setOffset(panOffsetStart.value.x + dx, panOffsetStart.value.y + dy);
  }
}

function handleMouseUp(e: MouseEvent): void {
  if (isPanning.value) {
    isPanning.value = false;
    return;
  }

  if (store.isMeasuring && store.measureStartPoint) {
    const rect = containerRef.value?.getBoundingClientRect();
    if (!rect) return;

    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    const worldX = (clientX - store.viewState.offsetX) / store.viewState.zoom;
    const worldY = (clientY - store.viewState.offsetY) / store.viewState.zoom;

    const dx = worldX - store.measureStartPoint.x;
    const dy = worldY - store.measureStartPoint.y;

    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      store.addMeasurement(store.measureStartPoint, { x: worldX, y: worldY });
    }

    store.isMeasuring = false;
    store.measureStartPoint = null;
  }
}

// ─── 适应窗口（暴露给父组件） ───
function fitToWindow(): void {
  const canvas = canvasRef.value;
  if (!canvas || !store.renderData) return;

  const { bounds } = store;
  const dataWidth = bounds.max_x - bounds.min_x;
  const dataHeight = bounds.max_y - bounds.min_y;

  const padding = 40;
  const scaleX = (canvas.width - padding * 2) / dataWidth;
  const scaleY = (canvas.height - padding * 2) / dataHeight;
  const zoom = Math.min(scaleX, scaleY, 3); // 最大 3 倍

  const centerX = (bounds.min_x + bounds.max_x) / 2;
  const centerY = (bounds.min_y + bounds.max_y) / 2;

  const offsetX = canvas.width / 2 - centerX * zoom;
  const offsetY = canvas.height / 2 - centerY * zoom;

  store.setZoom(zoom);
  store.setOffset(offsetX, offsetY);
}

defineExpose({ fitToWindow });
</script>

<style scoped lang="scss">
.dxf-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--fuxi-bg);
  cursor: v-bind(
    "store.activeTool === 'pan' || store.activeTool === 'none' ? 'grab' : store.activeTool === 'measure' ? 'crosshair' : 'cell'"
  );
}

.dxf-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.dxf-canvas-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 60%;
  max-width: 400px;
}

.canvas-skeleton {
  background: rgba(255, 255, 255, 0.9);
  border-radius: var(--radius-md);
  padding: 24px;
}

.dxf-canvas-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.dxf-canvas-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
