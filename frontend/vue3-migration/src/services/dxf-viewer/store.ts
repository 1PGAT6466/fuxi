/**
 * 伏羲 v2.1 — DXF 查看器 Store
 * 管理：文件列表缓存 + 视图状态（缩放/平移/选中实体）+ 图层配置
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { listFiles, getRenderData } from './api';
import type {
  DxfFile,
  DxfRenderData,
  DxfLayer,
  DxfEntity,
  ViewState,
  Annotation,
  MeasurementData,
} from './types';

// ───── Store ─────

export const useDxfViewerStore = defineStore('dxf-viewer', () => {
  // ─── 文件列表 ───
  const files = ref<DxfFile[]>([]);
  const filesLoading = ref(false);
  const currentFileHash = ref<string | null>(null);
  const currentFileName = ref<string>('');

  // ─── 渲染数据 ───
  const renderData = ref<DxfRenderData | null>(null);
  const renderLoading = ref(false);

  // ─── 视图状态 ───
  const viewState = ref<ViewState>({
    zoom: 1,
    offsetX: 0,
    offsetY: 0,
    selectedEntityIndex: -1,
  });

  // ─── 图层配置（从渲染数据初始化） ───
  const layers = ref<DxfLayer[]>([]);

  // ─── 标注 ───
  const annotations = ref<Annotation[]>([]);

  // ─── 测量 ───
  const measurements = ref<MeasurementData[]>([]);

  // ─── 工具状态 ───
  const activeTool = ref<'pan' | 'measure' | 'annotate' | 'none'>('pan');
  const isMeasuring = ref(false);
  const measureStartPoint = ref<{ x: number; y: number } | null>(null);

  // ───── Getters ─────

  /** 当前可见的图层列表 */
  const visibleLayers = computed(() => layers.value.filter((l) => l.visible));

  /** 当前需渲染的实体（过滤不可见图层） */
  const visibleEntities = computed<DxfEntity[]>(() => {
    if (!renderData.value) return [];
    const invisibleLayerNames = new Set(layers.value.filter((l) => !l.visible).map((l) => l.name));
    return renderData.value.entities.filter((e) => !invisibleLayerNames.has(e.layer || '0'));
  });

  /** 渲染边界 */
  const bounds = computed(
    () => renderData.value?.bounds || { min_x: 0, min_y: 0, max_x: 500, max_y: 400 },
  );

  // ───── Actions ─────

  /** 加载文件列表 */
  async function loadFiles(): Promise<void> {
    filesLoading.value = true;
    try {
      files.value = await listFiles();
    } catch (err) {
      console.error('[DXF Store] 加载文件列表失败:', err);
    } finally {
      filesLoading.value = false;
    }
  }

  /** 加载并渲染文件 */
  async function loadFile(hash: string): Promise<void> {
    currentFileHash.value = hash;
    renderLoading.value = true;
    try {
      renderData.value = await getRenderData(hash);
      currentFileName.value = renderData.value.file_name;

      // 初始化图层
      layers.value = renderData.value.layers.map((l) => ({ ...l }));

      // 清空标注和测量
      annotations.value = [];
      measurements.value = [];
    } catch (err) {
      console.error('[DXF Store] 加载渲染数据失败:', err);
    } finally {
      renderLoading.value = false;
    }
  }

  // ─── 视图操作 ───

  function setZoom(zoom: number): void {
    viewState.value.zoom = Math.max(0.1, Math.min(10, zoom));
  }

  function setOffset(offsetX: number, offsetY: number): void {
    viewState.value.offsetX = offsetX;
    viewState.value.offsetY = offsetY;
  }

  function selectEntity(index: number): void {
    viewState.value.selectedEntityIndex = index;
  }

  function resetView(): void {
    viewState.value = {
      zoom: 1,
      offsetX: 0,
      offsetY: 0,
      selectedEntityIndex: -1,
    };
  }

  // ─── 图层操作 ───

  function toggleLayerVisibility(name: string): void {
    const layer = layers.value.find((l) => l.name === name);
    if (layer && !layer.locked) {
      layer.visible = !layer.visible;
    }
  }

  function toggleLayerLock(name: string): void {
    const layer = layers.value.find((l) => l.name === name);
    if (layer) {
      layer.locked = !layer.locked;
    }
  }

  function setLayerColor(name: string, color: string): void {
    const layer = layers.value.find((l) => l.name === name);
    if (layer && !layer.locked) {
      layer.color = color;
    }
  }

  // ─── 标注操作 ───

  function addAnnotation(annotation: Omit<Annotation, 'id' | 'created_at'>): void {
    const newAnnotation: Annotation = {
      ...annotation,
      id: `ann_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      created_at: Date.now(),
    };
    annotations.value.push(newAnnotation);
  }

  function updateAnnotation(id: string, content: string): void {
    const ann = annotations.value.find((a) => a.id === id);
    if (ann) {
      ann.content = content;
    }
  }

  function removeAnnotation(id: string): void {
    annotations.value = annotations.value.filter((a) => a.id !== id);
  }

  // ─── 测量操作 ───

  function addMeasurement(
    startPoint: { x: number; y: number },
    endPoint: { x: number; y: number },
  ): void {
    const dx = endPoint.x - startPoint.x;
    const dy = endPoint.y - startPoint.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    const measurement: MeasurementData = {
      id: `meas_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      startPoint,
      endPoint,
      distance: Math.round(distance * 100) / 100, // 保留两位小数
    };
    measurements.value.push(measurement);
  }

  function removeMeasurement(id: string): void {
    measurements.value = measurements.value.filter((m) => m.id !== id);
  }

  function clearMeasurements(): void {
    measurements.value = [];
  }

  // ─── 工具状态 ───

  function setActiveTool(tool: 'pan' | 'measure' | 'annotate' | 'none'): void {
    activeTool.value = tool;
    if (tool !== 'measure') {
      isMeasuring.value = false;
      measureStartPoint.value = null;
    }
  }

  return {
    // 状态
    files,
    filesLoading,
    currentFileHash,
    currentFileName,
    renderData,
    renderLoading,
    viewState,
    layers,
    annotations,
    measurements,
    activeTool,
    isMeasuring,
    measureStartPoint,
    // Getters
    visibleLayers,
    visibleEntities,
    bounds,
    // Actions
    loadFiles,
    loadFile,
    setZoom,
    setOffset,
    selectEntity,
    resetView,
    toggleLayerVisibility,
    toggleLayerLock,
    setLayerColor,
    addAnnotation,
    updateAnnotation,
    removeAnnotation,
    addMeasurement,
    removeMeasurement,
    clearMeasurements,
    setActiveTool,
  };
});
