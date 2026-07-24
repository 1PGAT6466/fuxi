/**
 * 伏羲 v2.1 — HistoryService
 *
 * 提供访问历史追踪的编程接口，不依赖 Vue 组件。
 *
 * 使用方式：
 *   import { historyService } from '@/services/recent-visits/HistoryService';
 *   historyService.recordVisit(userId, itemId, 'chat', 'AI 对话标题');
 *   const recents = await historyService.getRecentVisits(userId, 10);
 *   await historyService.clearHistory(userId);
 */

import * as historyApi from './api';
import type { VisitRecord, VisitItemType, RecordVisitRequest } from './types';
import { createLogger } from '@/utils/logger';

const logger = createLogger('HistoryService');

// ═══════════════════════════════════════════
// localStorage 降级
// ═══════════════════════════════════════════

const LOCAL_KEY_PREFIX = 'fuxi-history';
const MAX_LOCAL = 50;

function loadLocal(userId: string | number): VisitRecord[] {
  try {
    const raw = localStorage.getItem(`${LOCAL_KEY_PREFIX}-${userId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveLocal(userId: string | number, records: VisitRecord[]): void {
  try {
    localStorage.setItem(
      `${LOCAL_KEY_PREFIX}-${userId}`,
      JSON.stringify(records.slice(0, MAX_LOCAL)),
    );
  } catch {
    // ignore
  }
}

function clearLocal(userId: string | number): void {
  localStorage.removeItem(`${LOCAL_KEY_PREFIX}-${userId}`);
}

function generateId(): string {
  return `hist_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// ═══════════════════════════════════════════
// HistoryService 类
// ═══════════════════════════════════════════

class HistoryService {
  /**
   * 记录一次访问
   *
   * @param userId - 用户 ID
   * @param itemId - 被访问的资源 ID
   * @param type   - 资源类型 (chat/document/knowledge_base)
   * @param title  - 资源标题
   * @param description - 可选的资源描述
   * @param route  - 可选的跳转路由
   * @returns 创建的访问记录
   */
  async recordVisit(
    userId: string | number,
    itemId: string,
    type: VisitItemType,
    title: string,
    description?: string,
    route?: string,
  ): Promise<VisitRecord> {
    const params: RecordVisitRequest = {
      userId,
      itemId,
      type,
      title,
      description,
      route,
    };

    try {
      const record = await historyApi.recordVisit(params);
      return record;
    } catch (err) {
      // 降级到本地存储
      logger.warn('记录访问失败，降级到本地存储', err);

      const localRecords = loadLocal(userId);
      const existing = localRecords.find(
        (r) => r.itemId === itemId && r.type === type,
      );

      if (existing) {
        existing.visitedAt = new Date().toISOString();
        existing.visitCount = (existing.visitCount || 1) + 1;
        saveLocal(userId, localRecords);
        return existing;
      }

      const record: VisitRecord = {
        id: generateId(),
        userId,
        itemId,
        type,
        title,
        description,
        route,
        visitedAt: new Date().toISOString(),
        visitCount: 1,
      };

      localRecords.unshift(record);
      saveLocal(userId, localRecords);
      return record;
    }
  }

  /**
   * 获取最近访问列表
   *
   * @param userId - 用户 ID
   * @param limit  - 最大返回条数（默认 20）
   * @param type   - 可选类型过滤
   * @returns 访问记录数组
   */
  async getRecentVisits(
    userId: string | number,
    limit = 20,
    type?: VisitItemType,
  ): Promise<VisitRecord[]> {
    try {
      const data = await historyApi.getRecentVisits({ userId, limit, type });
      return data.visits;
    } catch (err) {
      // 降级到本地存储
      logger.warn('获取最近访问失败，从本地加载', err);

      let records = loadLocal(userId);
      if (type) {
        records = records.filter((r) => r.type === type);
      }
      return records.slice(0, limit);
    }
  }

  /**
   * 清除指定用户的所有历史记录
   *
   * @param userId - 用户 ID
   */
  async clearHistory(userId: string | number): Promise<void> {
    try {
      await historyApi.clearHistory(userId);
    } catch (err) {
      logger.warn('清除历史失败，清除本地数据', err);
    }
    clearLocal(userId);
  }

  /**
   * 删除单条历史记录
   *
   * @param userId - 用户 ID
   * @param id     - 记录 ID
   */
  async deleteHistoryItem(userId: string | number, id: string): Promise<void> {
    try {
      await historyApi.deleteHistoryItem(userId, id);
    } catch (err) {
      logger.warn('删除记录失败', err);
    }
    // 同时清除本地记录
    const localRecords = loadLocal(userId).filter((r) => r.id !== id);
    saveLocal(userId, localRecords);
  }
}

// ═══════════════════════════════════════════
// 单例导出
// ═══════════════════════════════════════════

export const historyService = new HistoryService();
export default historyService;
