<template>
  <!--
    伏羲 v2.1 — DXF 查看器主页面
    布局：全屏视图 + 左侧工具栏（面板切换）+ 底部状态栏
    7 个子组件：DxfCanvas, LayerPanel, MeasureTool, AnnotationPanel, FileExplorer, UploadZone, Toolbar
  -->
  <div class="dxf-viewer-page">
    <!-- 顶部工具栏 -->
    <DxfToolbar @toggle-layers="toggleLayerPanel" />

    <!-- 主体区域 -->
    <!-- 加载态 -->
    <div v-if="loading" class="dxf-viewer-body dxf-viewer-body--center">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 错误态 -->
    <div v-else-if="error" class="dxf-viewer-body dxf-viewer-body--center">
      <el-result icon="error" title="加载失败">
        <template #extra>
          <el-button type="primary" @click="loadDxfData">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="isEmpty" class="dxf-viewer-body dxf-viewer-body--center">
      <el-empty description="暂无DXF文件" />
    </div>

    <!-- 正常内容 -->
    <div v-else class="dxf-viewer-body">
      <!-- 左侧面板（可切换） -->
      <div v-if="activePanel !== 'none'" class="dxf-left-panel">
        <!-- 面板标签切换 -->
        <div class="dxf-panel-tabs">
          <button
            class="panel-tab"
            :class="{ 'panel-tab--active': activePanel === 'files' }"
            @click="activePanel = 'files'"
          >
            <el-icon :size="18"><FolderOpened /></el-icon>
            <span v-if="activePanel === 'files'" class="panel-tab-label">文件</span>
          </button>
          <button
            class="panel-tab"
            :class="{ 'panel-tab--active': activePanel === 'measure' }"
            @click="activePanel = 'measure'"
          >
            <el-icon :size="18"><Aim /></el-icon>
            <span v-if="activePanel === 'measure'" class="panel-tab-label">测量</span>
          </button>
          <button
            class="panel-tab"
            :class="{ 'panel-tab--active': activePanel === 'annotations' }"
            @click="activePanel = 'annotations'"
          >
            <el-icon :size="18"><EditPen /></el-icon>
            <span v-if="activePanel === 'annotations'" class="panel-tab-label">标注</span>
          </button>
        </div>

        <!-- 面板内容 -->
        <div class="dxf-panel-content">
          <FileExplorer v-if="activePanel === 'files'" />
          <MeasureTool v-if="activePanel === 'measure'" />
          <AnnotationPanel v-if="activePanel === 'annotations'" />
        </div>

        <!-- 上传区域（仅在文件面板显示） -->
        <div v-if="activePanel === 'files'" class="dxf-panel-upload">
          <UploadZone />
        </div>
      </div>

      <!-- 切换面板的按钮（面板关闭时） -->
      <button
        v-if="activePanel === 'none'"
        class="dxf-panel-toggle"
        title="展开面板"
        @click="activePanel = 'files'"
      >
        <el-icon :size="18"><DArrowRight /></el-icon>
      </button>

      <!-- Canvas 主视图 -->
      <div class="dxf-canvas-area">
        <DxfCanvas ref="dxfCanvasRef" />
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="dxf-statusbar">
      <div class="statusbar-left">
        <span v-if="store.currentFileName" class="statusbar-item">
          <el-icon :size="14"><Document /></el-icon>
          {{ store.currentFileName }}
        </span>
        <span class="statusbar-item">缩放 {{ Math.round(store.viewState.zoom * 100) }}%</span>
        <span v-if="store.renderData" class="statusbar-item">
          实体 {{ store.renderData.entities.length }} 个
        </span>
        <span v-if="store.renderData" class="statusbar-item">
          图层 {{ store.layers.length }} 层（可见 {{ store.visibleLayers.length }}）
        </span>
      </div>
      <div class="statusbar-right">
        <span class="statusbar-item" :class="connectionClass">
          <span class="status-dot" :class="connectionClass" />
          {{
            connectionStatus === 'connected'
              ? '已连接'
              : connectionStatus === 'mock'
                ? '离线模式'
                : '连接中...'
          }}
        </span>
        <span class="statusbar-item"> 工具：{{ toolLabelMap[store.activeTool] || '平移' }} </span>
        <span v-if="store.measurements.length > 0" class="statusbar-item statusbar-highlight">
          {{ store.measurements.length }} 条测量
        </span>
        <span v-if="store.annotations.length > 0" class="statusbar-item statusbar-highlight">
          {{ store.annotations.length }} 个标注
        </span>
      </div>
    </div>

    <!-- 图层面板（抽屉） -->
    <LayerPanel ref="layerPanelRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { FolderOpened, Aim, EditPen, Document, DArrowRight } from '@element-plus/icons-vue';
import DxfToolbar from './DxfToolbar.vue';
import DxfCanvas from './DxfCanvas.vue';
import LayerPanel from './LayerPanel.vue';
import MeasureTool from './MeasureTool.vue';
import AnnotationPanel from './AnnotationPanel.vue';
import FileExplorer from './FileExplorer.vue';
import UploadZone from './UploadZone.vue';
import { useDxfViewerStore } from './store';
import { healthCheck } from './api';

const store = useDxfViewerStore();

// ─── 加载/空/错误状态 ───
const loading = ref(true);
const error = ref(false);
const isEmpty = ref(false);

async function loadDxfData(): Promise<void> {
  loading.value = true;
  error.value = false;
  isEmpty.value = false;
  try {
    // 健康检查 + 数据加载
    await healthCheck();
    connectionStatus.value = 'connected';
    connectionClass.value = 'statusbar-ok';

    // 检查是否有 DXF 文件数据
    if (!store.renderData || store.renderData.entities.length === 0) {
      isEmpty.value = true;
    }
  } catch {
    connectionStatus.value = 'mock';
    connectionClass.value = 'statusbar-mock';
    // 仅当没有任何渲染数据时才判定为空
    if (!store.renderData || store.renderData.entities.length === 0) {
      isEmpty.value = true;
    }
  } finally {
    loading.value = false;
  }
}

// ─── 面板引用 ───
const dxfCanvasRef = ref<InstanceType<typeof DxfCanvas> | null>(null);
const layerPanelRef = ref<InstanceType<typeof LayerPanel> | null>(null);

// ─── 左侧面板状态 ───
type PanelType = 'files' | 'measure' | 'annotations' | 'none';
const activePanel = ref<PanelType>('files');

// ─── 连接状态 ───
const connectionStatus = ref<'connected' | 'mock' | 'checking'>('checking');

const toolLabelMap: Record<string, string> = {
  pan: '平移',
  measure: '测量',
  annotate: '标注',
  none: '无',
};

const connectionClass = ref('statusbar-ok');

// ─── 图层面板 ───
function toggleLayerPanel(): void {
  layerPanelRef.value?.toggle();
}

// ─── 适应窗口 ───
function handleFitToWindow(): void {
  dxfCanvasRef.value?.fitToWindow();
}

onMounted(() => {
  loadDxfData();
  window.addEventListener('dxf-fit-to-window', handleFitToWindow);
});

onUnmounted(() => {
  window.removeEventListener('dxf-fit-to-window', handleFitToWindow);
});
</script>

<style scoped lang="scss">
.dxf-viewer-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--fuxi-bg);
  color: var(--text-primary);
}

/* ─── 主体 ─── */
.dxf-viewer-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;

  &--center {
    align-items: center;
    justify-content: center;
  }
}

/* ─── 左侧面板 ─── */
.dxf-left-panel {
  width: 240px;
  min-width: 240px;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-right: 1px solid var(--bg-divider);
  overflow: hidden;
}

.dxf-panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--bg-divider);
}

.panel-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 10px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-tertiary);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;

  &:hover {
    color: var(--text-secondary);
    background: var(--bg-hover);
  }

  &--active {
    color: var(--brand);

    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 25%;
      right: 25%;
      height: 2px;
      background: var(--brand);
      border-radius: 1px;
    }
  }
}

.panel-tab-label {
  font-size: 10px;
  font-weight: 500;
}

.dxf-panel-content {
  flex: 1;
  overflow: hidden;
}

.dxf-panel-upload {
  border-top: 1px solid var(--bg-divider);
  padding: 12px;
}

/* ─── 面板切换按钮（折叠态） ─── */
.dxf-panel-toggle {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
  width: 28px;
  height: 48px;
  border: 1px solid var(--bg-divider);
  border-left: none;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--bg-card);
  cursor: pointer;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-out);

  &:hover {
    color: var(--brand);
    background: var(--brand-soft);
  }
}

/* ─── Canvas 区域 ─── */
.dxf-canvas-area {
  flex: 1;
  min-width: 0;
  position: relative;
}

/* ─── 底部状态栏 ─── */
.dxf-statusbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 16px;
  background: var(--bg-card);
  border-top: 1px solid var(--bg-divider);
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.statusbar-left,
.statusbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.statusbar-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.statusbar-highlight {
  color: var(--brand);
  font-weight: 600;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.statusbar-ok {
  color: var(--status-healthy);

  .status-dot {
    background: var(--status-healthy);
  }
}

.statusbar-mock {
  color: var(--status-warning);

  .status-dot {
    background: var(--status-warning);
  }
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .dxf-left-panel {
    width: 200px;
    min-width: 200px;
  }

  .dxf-statusbar {
    padding: 4px 8px;
  }

  .statusbar-left,
  .statusbar-right {
    gap: 8px;
  }
}
</style>
