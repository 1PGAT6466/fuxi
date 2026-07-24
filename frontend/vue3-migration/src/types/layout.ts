/**
 * 伏羲 v2.1 — 窗口布局持久化类型定义
 *
 * 定义布局方案、窗口快照、显示器信息等核心类型。
 * 支持多显示器适配和布局方案导入/导出。
 */

import type { WindowState } from './service-manifest';

// ============================
// 显示器信息
// ============================

/** 物理显示器信息 */
export interface DisplayInfo {
  /** 显示器唯一标识（浏览器 screen 信息组合） */
  id: string;
  /** 显示器名称 */
  name: string;
  /** 可用宽度 */
  availWidth: number;
  /** 可用高度 */
  availHeight: number;
  /** 总宽度 */
  width: number;
  /** 总高度 */
  height: number;
  /** 距主屏幕左侧偏移 */
  left: number;
  /** 距主屏幕顶部偏移 */
  top: number;
  /** 是否为主显示器 */
  isPrimary: boolean;
  /** 设备像素比 */
  devicePixelRatio: number;
}

/** 检测到的显示器配置摘要 */
export interface DisplayConfiguration {
  /** 显示器数量 */
  count: number;
  /** 各显示器详情 */
  displays: DisplayInfo[];
  /** 总可用区域 */
  totalBounds: {
    left: number;
    top: number;
    right: number;
    bottom: number;
  };
  /** 配置指纹（用于判断显示器是否变化） */
  fingerprint: string;
}

// ============================
// 窗口快照
// ============================

/** 单个窗口快照 */
export interface WindowSnapshot {
  /** 原始窗口 ID */
  windowId: string;
  /** 服务 ID */
  serviceId: string;
  /** 窗口标题 */
  title: string;
  /** 窗口状态 */
  state: Exclude<WindowState, 'closed' | 'closing'>;
  /** 窗口位置 */
  position: { x: number; y: number };
  /** 窗口尺寸 */
  size: { width: number; height: number };
  /** z 轴顺序（用于恢复层级） */
  zIndex: number;
  /** 所在显示器 ID */
  displayId: string;
  /** 额外数据（服务特定） */
  data?: Record<string, unknown>;
}

// ============================
// 布局方案
// ============================

/** 布局方案（可保存/恢复的完整布局状态） */
export interface LayoutPlan {
  /** 方案唯一 ID */
  id: string;
  /** 方案名称 */
  name: string;
  /** 方案描述 */
  description?: string;
  /** 创建时间（ISO 字符串） */
  createdAt: string;
  /** 更新时间（ISO 字符串） */
  updatedAt: string;
  /** 显示器配置指纹（用于验证兼容性） */
  displayFingerprint: string;
  /** 显示器信息快照 */
  displayConfiguration: DisplayConfiguration;
  /** 窗口快照列表 */
  windows: WindowSnapshot[];
  /** 是否激活的布局 */
  isActive: boolean;
  /** 是否为系统默认布局 */
  isDefault: boolean;
  /** 标签 */
  tags?: string[];
  /** 版本号（用于迁移） */
  version: number;
}

// ============================
// 布局导出/导入格式
// ============================

/** 布局导出文件格式 */
export interface LayoutExport {
  /** 格式版本 */
  formatVersion: number;
  /** 导出时间 */
  exportedAt: string;
  /** 应用版本 */
  appVersion: string;
  /** 布局方案数组 */
  layouts: LayoutPlan[];
}

// ============================
// API 请求/响应类型
// ============================

/** 保存布局请求 */
export interface SaveLayoutRequest {
  /** 布局名称 */
  name: string;
  /** 布局描述 */
  description?: string;
  /** 窗口快照列表 */
  windows: Omit<WindowSnapshot, 'displayId'>[];
  /** 显示器配置 */
  displayConfiguration: DisplayConfiguration;
  /** 标签 */
  tags?: string[];
}

/** 更新布局请求 */
export interface UpdateLayoutRequest {
  name?: string;
  description?: string;
  isActive?: boolean;
  windows?: Omit<WindowSnapshot, 'displayId'>[];
  displayConfiguration?: DisplayConfiguration;
  tags?: string[];
}

/** 导入布局请求 */
export interface ImportLayoutRequest {
  /** Base64 编码的 JSON 数据 */
  data: string;
  /** 是否覆盖同名布局 */
  overwrite?: boolean;
}

/** 布局列表响应 */
export interface LayoutListResponse {
  layouts: LayoutPlan[];
  total: number;
  activeLayoutId: string | null;
}

/** 布局操作结果 */
export interface LayoutActionResult {
  success: boolean;
  layout?: LayoutPlan;
  message?: string;
}
