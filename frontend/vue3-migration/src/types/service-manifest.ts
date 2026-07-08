/**
 * 伏羲 v2.1 — 服务清单类型定义
 *
 * 定义 ServiceManifest 协议、窗口管理类型、事件总线类型等核心接口。
 * 所有服务相关的类型集中管理于此文件。
 */

// ============================
// 枚举类型
// ============================

/** 窗口模式 */
export type WindowMode = 'tab' | 'modal' | 'drawer' | 'fullscreen';

/** 服务分类（对齐业务领域） */
export type ServiceCategory = 'workspace' | 'analytics' | 'engineering' | 'admin' | 'personal';

/** 八卦符号 */
export type GuaSymbol = 'qian' | 'kun' | 'zhen' | 'xun' | 'kan' | 'li' | 'gen' | 'dui';

/** 窗口状态 */
export type WindowState = 'maximized' | 'normal' | 'minimized' | 'closing' | 'closed';

/** 布局模式 */
export type LayoutMode = 'free' | 'tiled' | 'split';

// ============================
// API 端点
// ============================

/** 单个 API 端点定义 */
export interface EndpointDef {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  description: string;
  requestSchema?: string;
  responseSchema?: string;
}

// ============================
// 服务清单协议
// ============================

/** 卦组合 = 服务归属 */
export interface GuaCombination {
  primary: GuaSymbol;
  secondary: GuaSymbol;
}

/** 窗口默认尺寸 */
export interface WindowDefaultSize {
  width: number;
  height: number;
}

/** 窗口默认位置 */
export interface WindowDefaultPosition {
  x: 'center' | number;
  y: 'center' | number;
}

/** 服务清单 = manifest.json 的核心协议 */
export interface ServiceManifest {
  // ── 标识 ──
  id: string;
  name: string;
  icon: string;
  description: string;
  version: string;

  // ── 分类与归属 ──
  category: ServiceCategory;
  guaAffinity?: GuaCombination;

  // ── 路由与 API ──
  route: string;
  apiBase: string;
  endpoints: EndpointDef[];

  // ── 访问控制 ──
  requiredRole: 'user' | 'admin';
  featureFlag?: string;

  // ── 窗口行为 ──
  windowMode: WindowMode;
  defaultSize?: WindowDefaultSize;
  defaultPosition?: WindowDefaultPosition;
  resizable?: boolean;
  minimizable?: boolean;
  singleton?: boolean;

  // ── 元数据 ──
  tags?: string[];
  dependencies?: string[];
  author?: string;
  changelog?: string;
}

// ============================
// 窗口实例
// ============================

/** 服务窗口实例（运行时） */
export interface ServiceWindow {
  id: string;
  serviceId: string;
  title: string;
  icon: string;
  state: WindowState;
  zIndex: number;
  size: { width: number | string; height: number | string };
  position: { x: number; y: number };
  minimizedPosition?: { x: number; y: number };
  openedAt: number;
  data?: Record<string, any>;
}

// ============================
// 窗口布局
// ============================

/** 窗口布局配置 */
export interface WindowLayout {
  mode: LayoutMode;
  /** 分栏比例（仅 split 模式有效） */
  ratios?: number[];
  /** 每行/列最大窗口数（仅 tiled 模式有效） */
  maxPerRow?: number;
}

// ============================
// 事件总线
// ============================

/** 事件处理器类型 */
export type EventHandler = (...args: any[]) => void;

// ============================
// 服务窗口协议
// ============================

/** 服务窗口组件暴露接口 */
export interface ServiceWindowExposed {
  isDirty: () => boolean;
  beforeClose: () => Promise<boolean> | boolean;
  onActivated: () => void;
  onDeactivated: () => void;
  serialize: () => Record<string, any>;
  deserialize: (data: Record<string, any>) => void;
}
