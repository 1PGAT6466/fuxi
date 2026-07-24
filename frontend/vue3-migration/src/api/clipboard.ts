/**
 * 伏羲 v2.1 — 跨窗口剪贴板 API 封装
 *
 * 封装与剪贴板后端的通信：
 * - 剪贴板内容同步
 * - 历史记录查询
 * - 批量删除/清空
 * - 收藏管理
 */

import apiClient from './index';
import { createLogger } from '@/utils/logger';
import type {
  ClipboardSyncRequest,
  ClipboardSyncResponse,
  ClipboardHistoryQuery,
  ClipboardHistoryResponse,
  ClipboardBatchRequest,
  ClipboardBatchResponse,
} from '@/services/clipboard/types';

const logger = createLogger('ClipboardAPI');

// ═══════════════════════════════════════════
// 剪贴板同步
// ═══════════════════════════════════════════

/**
 * 同步剪贴板内容到服务端
 *
 * POST /api/clipboard/sync
 *
 * @param data - 剪贴板同步请求数据
 * @returns 同步结果
 */
export async function syncClipboard(
  data: ClipboardSyncRequest,
): Promise<ClipboardSyncResponse> {
  try {
    const res = (await apiClient.post('/api/clipboard/sync', data)) as ClipboardSyncResponse;
    logger.debug('剪贴板同步成功', { entryId: res.entryId });
    return res;
  } catch (err) {
    logger.error('剪贴板同步失败', err);
    throw err;
  }
}

// ═══════════════════════════════════════════
// 剪贴板历史查询
// ═══════════════════════════════════════════

/**
 * 获取剪贴板历史记录
 *
 * GET /api/clipboard/history
 *
 * @param query - 查询参数
 * @returns 剪贴板历史列表
 */
export async function getClipboardHistory(
  query?: ClipboardHistoryQuery,
): Promise<ClipboardHistoryResponse> {
  try {
    const res = (await apiClient.get('/api/clipboard/history', {
      params: query,
    })) as ClipboardHistoryResponse;
    logger.debug(`获取剪贴板历史: ${res.total} 条`);
    return res;
  } catch (err) {
    logger.error('获取剪贴板历史失败', err);
    throw err;
  }
}

// ═══════════════════════════════════════════
// 剪贴板条目操作
// ═══════════════════════════════════════════

/**
 * 切换条目收藏状态
 *
 * PATCH /api/clipboard/:entryId/favorite
 *
 * @param entryId - 条目 ID
 * @param isFavorite - 是否收藏
 */
export async function toggleClipboardFavorite(
  entryId: string,
  isFavorite: boolean,
): Promise<ClipboardSyncResponse> {
  try {
    const res = (await apiClient.patch(
      `/api/clipboard/${encodeURIComponent(entryId)}/favorite`,
      { isFavorite },
    )) as ClipboardSyncResponse;
    return res;
  } catch (err) {
    logger.error('切换收藏状态失败', err);
    throw err;
  }
}

/**
 * 删除单条剪贴板条目
 *
 * DELETE /api/clipboard/:entryId
 *
 * @param entryId - 条目 ID
 */
export async function deleteClipboardEntry(
  entryId: string,
): Promise<ClipboardSyncResponse> {
  try {
    const res = (await apiClient.delete(
      `/api/clipboard/${encodeURIComponent(entryId)}`,
    )) as ClipboardSyncResponse;
    return res;
  } catch (err) {
    logger.error('删除剪贴板条目失败', err);
    throw err;
  }
}

/**
 * 批量删除剪贴板条目
 *
 * POST /api/clipboard/batch-delete
 *
 * @param data - 批量删除请求
 */
export async function batchDeleteClipboardEntries(
  data: ClipboardBatchRequest,
): Promise<ClipboardBatchResponse> {
  try {
    const res = (await apiClient.post(
      '/api/clipboard/batch-delete',
      data,
    )) as ClipboardBatchResponse;
    logger.debug(`批量删除剪贴板条目: ${res.affectedCount} 条`);
    return res;
  } catch (err) {
    logger.error('批量删除剪贴板条目失败', err);
    throw err;
  }
}

/**
 * 清空所有剪贴板历史
 *
 * DELETE /api/clipboard/history
 */
export async function clearClipboardHistory(): Promise<ClipboardSyncResponse> {
  try {
    const res = (await apiClient.delete(
      '/api/clipboard/history',
    )) as ClipboardSyncResponse;
    logger.info('剪贴板历史已清空');
    return res;
  } catch (err) {
    logger.error('清空剪贴板历史失败', err);
    throw err;
  }
}
