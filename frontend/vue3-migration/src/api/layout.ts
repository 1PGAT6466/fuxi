/**
 * 伏羲 v2.1 — 窗口布局持久化 API
 *
 * 提供布局方案的后端 CRUD 操作：
 * - POST /api/layouts     创建/保存布局
 * - GET  /api/layouts     获取布局列表
 * - GET  /api/layouts/:id 获取单个布局
 * - PUT  /api/layouts/:id 更新布局
 * - DELETE /api/layouts/:id 删除布局
 * - POST /api/layouts/:id/activate 激活布局
 * - POST /api/layouts/import  导入布局
 * - GET  /api/layouts/export  导出布局
 */
import apiClient from './index';
import { createLogger } from '@/utils/logger';
import type {
  SaveLayoutRequest,
  UpdateLayoutRequest,
  ImportLayoutRequest,
  LayoutListResponse,
  LayoutPlan,
  LayoutActionResult,
  LayoutExport,
} from '@/types/layout';

const logger = createLogger('LayoutAPI');

// ═══════════════════════════════════════════
// 布局 CRUD
// ═══════════════════════════════════════════

/**
 * 创建新布局方案
 *
 * @param data - 布局数据
 */
export async function saveLayout(
  data: SaveLayoutRequest,
): Promise<LayoutActionResult> {
  try {
    const res = (await apiClient.post('/api/layouts', data)) as LayoutActionResult;
    logger.info('布局保存成功:', data.name);
    return res;
  } catch (err) {
    logger.error('布局保存失败', err);
    return { success: false, message: '布局保存失败' };
  }
}

/**
 * 获取布局列表
 */
export async function listLayouts(): Promise<LayoutListResponse> {
  try {
    const res = (await apiClient.get('/api/layouts')) as LayoutListResponse;
    logger.info(`获取布局列表: ${res.total} 个方案`);
    return res;
  } catch (err) {
    logger.error('获取布局列表失败', err);
    return { layouts: [], total: 0, activeLayoutId: null };
  }
}

/**
 * 获取单个布局
 *
 * @param layoutId - 布局 ID
 */
export async function getLayout(
  layoutId: string,
): Promise<LayoutActionResult> {
  try {
    const res = (await apiClient.get(`/api/layouts/${encodeURIComponent(layoutId)}`)) as LayoutActionResult;
    return res;
  } catch (err) {
    logger.error('获取布局失败', err);
    return { success: false, message: '获取布局失败' };
  }
}

/**
 * 更新布局
 *
 * @param layoutId - 布局 ID
 * @param updates - 要更新的字段
 */
export async function updateLayout(
  layoutId: string,
  updates: UpdateLayoutRequest,
): Promise<LayoutActionResult> {
  try {
    const res = (await apiClient.put(
      `/api/layouts/${encodeURIComponent(layoutId)}`,
      updates,
    )) as LayoutActionResult;
    logger.info('布局更新成功:', layoutId);
    return res;
  } catch (err) {
    logger.error('布局更新失败', err);
    return { success: false, message: '布局更新失败' };
  }
}

/**
 * 删除布局
 *
 * @param layoutId - 布局 ID
 */
export async function deleteLayout(
  layoutId: string,
): Promise<LayoutActionResult> {
  try {
    const res = (await apiClient.delete(
      `/api/layouts/${encodeURIComponent(layoutId)}`,
    )) as LayoutActionResult;
    logger.info('布局已删除:', layoutId);
    return res;
  } catch (err) {
    logger.error('删除布局失败', err);
    return { success: false, message: '删除布局失败' };
  }
}

/**
 * 激活布局方案
 *
 * @param layoutId - 布局 ID
 */
export async function activateLayout(
  layoutId: string,
): Promise<LayoutActionResult> {
  try {
    const res = (await apiClient.post(
      `/api/layouts/${encodeURIComponent(layoutId)}/activate`,
    )) as LayoutActionResult;
    logger.info('布局已激活:', layoutId);
    return res;
  } catch (err) {
    logger.error('激活布局失败', err);
    return { success: false, message: '激活布局失败' };
  }
}

// ═══════════════════════════════════════════
// 布局导入/导出
// ═══════════════════════════════════════════

/**
 * 导出布局数据
 */
export async function exportLayouts(): Promise<LayoutExport | null> {
  try {
    const res = (await apiClient.get('/api/layouts/export')) as LayoutExport;
    return res;
  } catch (err) {
    logger.error('导出布局失败', err);
    return null;
  }
}

/**
 * 导入布局数据
 *
 * @param data - 导入数据
 */
export async function importLayouts(
  data: ImportLayoutRequest,
): Promise<LayoutActionResult> {
  try {
    const res = (await apiClient.post('/api/layouts/import', data)) as LayoutActionResult;
    logger.info('布局导入成功');
    return res;
  } catch (err) {
    logger.error('导入布局失败', err);
    return { success: false, message: '导入布局失败' };
  }
}
