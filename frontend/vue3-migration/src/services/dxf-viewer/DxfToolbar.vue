<template>
  <!--
    伏羲 v2.1 — DxfToolbar：顶部工具栏
    缩放/平移/测量/标注/适应窗口/导出按钮
  -->
  <div class="dxf-toolbar">
    <!-- 左侧：工具组 -->
    <div class="toolbar-left">
      <!-- 当前文件名 -->
      <div v-if="store.currentFileName" class="toolbar-file">
        <el-icon :size="14"><Document /></el-icon>
        <span class="toolbar-file-name">{{ store.currentFileName }}</span>
      </div>

      <div class="toolbar-divider" />

      <!-- 导航工具 -->
      <el-tooltip content="平移 (P)" placement="bottom">
        <button
          class="toolbar-btn"
          :class="{ 'toolbar-btn--active': store.activeTool === 'pan' }"
          @click="store.setActiveTool('pan')"
        >
          <el-icon :size="18"><Rank /></el-icon>
        </button>
      </el-tooltip>

      <el-tooltip content="测量 (M)" placement="bottom">
        <button
          class="toolbar-btn"
          :class="{ 'toolbar-btn--active': store.activeTool === 'measure' }"
          @click="store.setActiveTool('measure')"
        >
          <el-icon :size="18"><Aim /></el-icon>
        </button>
      </el-tooltip>

      <el-tooltip content="标注 (A)" placement="bottom">
        <button
          class="toolbar-btn"
          :class="{ 'toolbar-btn--active': store.activeTool === 'annotate' }"
          @click="store.setActiveTool('annotate')"
        >
          <el-icon :size="18"><EditPen /></el-icon>
        </button>
      </el-tooltip>

      <div class="toolbar-divider" />

      <!-- 视图控制 -->
      <el-tooltip content="适应窗口" placement="bottom">
        <button class="toolbar-btn" @click="fitToWindow">
          <el-icon :size="18"><FullScreen /></el-icon>
        </button>
      </el-tooltip>

      <el-tooltip content="放大" placement="bottom">
        <button class="toolbar-btn" @click="zoomIn">
          <el-icon :size="18"><ZoomIn /></el-icon>
        </button>
      </el-tooltip>

      <el-tooltip content="缩小" placement="bottom">
        <button class="toolbar-btn" @click="zoomOut">
          <el-icon :size="18"><ZoomOut /></el-icon>
        </button>
      </el-tooltip>

      <el-tooltip content="重置视图" placement="bottom">
        <button class="toolbar-btn" @click="store.resetView()">
          <el-icon :size="18"><RefreshRight /></el-icon>
        </button>
      </el-tooltip>
    </div>

    <!-- 右侧：信息 + 操作 -->
    <div class="toolbar-right">
      <span class="toolbar-zoom-label"> {{ Math.round(store.viewState.zoom * 100) }}% </span>

      <div class="toolbar-divider toolbar-divider--desktop" />

      <el-tooltip content="图层管理" placement="bottom">
        <button class="toolbar-btn toolbar-btn--desktop" @click="$emit('toggle-layers')">
          <el-icon :size="18"><Grid /></el-icon>
        </button>
      </el-tooltip>

      <el-tooltip content="导出 PNG" placement="bottom">
        <button class="toolbar-btn toolbar-btn--desktop" @click="exportPng">
          <el-icon :size="18"><Download /></el-icon>
        </button>
      </el-tooltip>

      <!-- 移动端溢出菜单 -->
      <div class="toolbar-overflow-menu">
        <el-tooltip content="更多" placement="bottom">
          <button class="toolbar-btn" @click="overflowVisible = !overflowVisible">
            <el-icon :size="18"><MoreFilled /></el-icon>
          </button>
        </el-tooltip>
        <div v-if="overflowVisible" class="overflow-dropdown">
          <button
            class="toolbar-btn toolbar-btn--block"
            @click="
              $emit('toggle-layers');
              overflowVisible = false;
            "
          >
            <el-icon :size="16"><Grid /></el-icon>
            <span>图层管理</span>
          </button>
          <button
            class="toolbar-btn toolbar-btn--block"
            @click="
              exportPng();
              overflowVisible = false;
            "
          >
            <el-icon :size="16"><Download /></el-icon>
            <span>导出 PNG</span>
          </button>
        </div>
      </div>
      <!-- 移动端溢出菜单的遮罩 -->
      <div v-if="overflowVisible" class="overflow-mask" @click="overflowVisible = false" />
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Document,
  Aim,
  EditPen,
  FullScreen,
  ZoomIn,
  ZoomOut,
  RefreshRight,
  Grid,
  Download,
  Rank,
  MoreFilled,
} from '@element-plus/icons-vue';
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useDxfViewerStore } from './store';

const store = useDxfViewerStore();
const overflowVisible = ref(false);

defineEmits<{
  (e: 'toggle-layers'): void;
}>();

// ─── 缩放操作 ───
function zoomIn(): void {
  store.setZoom(store.viewState.zoom * 1.2);
}

function zoomOut(): void {
  store.setZoom(store.viewState.zoom * 0.8);
}

function fitToWindow(): void {
  // 通过 canvas 组件的 expose 方法调用
  // 这里通过自定义事件方式，实际上父组件会处理
  window.dispatchEvent(new CustomEvent('dxf-fit-to-window'));
}

// ─── 导出 PNG ───
function exportPng(): void {
  const canvas = document.querySelector('.dxf-canvas') as HTMLCanvasElement | null;
  if (!canvas) {
    ElMessage.warning('没有可导出的画布');
    return;
  }
  try {
    const url = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = `${store.currentFileName || 'dxf-view'}_export.png`;
    link.href = url;
    link.click();
    ElMessage.success('导出成功');
  } catch {
    ElMessage.error('导出失败');
  }
}

// ─── 键盘快捷键 ───
function handleKeydown(e: KeyboardEvent): void {
  // 忽略输入框内的按键
  const tag = (e.target as HTMLElement).tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;

  switch (e.key.toLowerCase()) {
    case 'p':
      store.setActiveTool('pan');
      break;
    case 'm':
      store.setActiveTool('measure');
      break;
    case 'a':
      store.setActiveTool('annotate');
      break;
    case 'escape':
      store.setActiveTool('pan');
      store.isMeasuring = false;
      store.measureStartPoint = null;
      break;
    case 'f':
      e.preventDefault();
      fitToWindow();
      break;
    case '+':
    case '=':
      zoomIn();
      break;
    case '-':
      zoomOut();
      break;
    case '0':
      store.resetView();
      break;
    default:
      break;
  }
}

// 挂载/卸载键盘监听
import { onMounted, onUnmounted } from 'vue';
onMounted(() => window.addEventListener('keydown', handleKeydown));
onUnmounted(() => window.removeEventListener('keydown', handleKeydown));
</script>

<style scoped lang="scss">
.dxf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--bg-divider);
  user-select: none;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.toolbar-file {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: var(--font-size-small);
}

.toolbar-file-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-divider {
  width: 1px;
  height: 24px;
  background: var(--bg-divider);
  margin: 0 6px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  &--active {
    background: var(--brand-soft);
    color: var(--brand);
  }
}

.toolbar-zoom-label {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  font-family: monospace;
  min-width: 40px;
  text-align: center;
  user-select: none;
}

/* ─── 溢出菜单（移动端） ─── */
.toolbar-overflow-menu {
  display: none;
  position: relative;
}

.overflow-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 140px;
  background: var(--bg-card);
  border: 1px solid var(--bg-divider);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  padding: 4px;
  z-index: 100;
}

.toolbar-btn--block {
  width: 100%;
  justify-content: flex-start;
  padding: 0 12px;
  gap: 8px;

  span {
    font-size: var(--font-size-caption);
    color: var(--text-primary);
  }
}

.overflow-mask {
  position: fixed;
  inset: 0;
  z-index: 99;
  background: transparent;
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .dxf-toolbar {
    padding: 6px 12px;
  }

  .toolbar-file {
    max-width: 100px;
  }

  .toolbar-file-name {
    max-width: 80px;
  }

  .toolbar-divider--desktop,
  .toolbar-btn--desktop {
    display: none;
  }

  .toolbar-overflow-menu {
    display: block;
  }
}
</style>
