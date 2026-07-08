/**
 * 伏羲 v2.1 — DXF 查看器类型定义
 */

// ───── 健康检查 ─────

export interface DxfHealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  storage_used_mb: number;
}

// ───── 文件信息 ─────

export interface DxfFile {
  id: string;
  hash: string;
  name: string;
  size: number;
  uploaded_at: string;
  layers_count: number;
}

// ───── DXF 几何数据 ─────

export interface DxfPoint {
  x: number;
  y: number;
}

export interface DxfLine {
  type: 'LINE';
  start: DxfPoint;
  end: DxfPoint;
  color?: string;
  layer?: string;
}

export interface DxfCircle {
  type: 'CIRCLE';
  center: DxfPoint;
  radius: number;
  color?: string;
  layer?: string;
}

export interface DxfRectangle {
  type: 'RECT';
  min: DxfPoint;
  max: DxfPoint;
  color?: string;
  layer?: string;
}

export interface DxfText {
  type: 'TEXT';
  position: DxfPoint;
  content: string;
  height: number;
  color?: string;
  layer?: string;
}

export type DxfEntity = DxfLine | DxfCircle | DxfRectangle | DxfText;

// ───── 图层 ─────

export interface DxfLayer {
  name: string;
  color: string;
  visible: boolean;
  locked: boolean;
  entityCount: number;
}

// ───── 渲染数据 ─────

export interface DxfRenderData {
  file_id: string;
  file_name: string;
  entities: DxfEntity[];
  layers: DxfLayer[];
  bounds: {
    min_x: number;
    min_y: number;
    max_x: number;
    max_y: number;
  };
}

// ───── 标注 ─────

export interface Annotation {
  id: string;
  x: number;
  y: number;
  content: string;
  color: string;
  created_at: number;
}

// ───── 测量 ─────

export interface MeasurementData {
  id: string;
  startPoint: DxfPoint;
  endPoint: DxfPoint;
  distance: number;
}

// ───── 视图状态 ─────

export interface ViewState {
  zoom: number;
  offsetX: number;
  offsetY: number;
  selectedEntityIndex: number;
}
