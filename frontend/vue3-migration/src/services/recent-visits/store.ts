/**
 * 伏羲 v2.1 — 最近访问 Store
 * P2 增强：访问记录 Pinia Store（支持本地优先降级）
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';
import { useAuthStore } from '@/stores/auth';
import type { VisitRecord, VisitItemType, RecordVisitRequest } from './types';
import * as historyApi from './api';

const logger = createLogger('RecentVisitsStore');

/** localStorage 存储键 */
const LOCAL_STORAGE_KEY = 'fuxi-recent-visits';
const MAX_LOCAL_RECORDS = 50;

// ═══════════════════════════════════════════
// 本地存储工具
// ═══════════════════════════════════════════

function loadFromLocal(userId: string | number): VisitRecord[] {
  try {
    const raw = localStorage.getItem(`${LOCAL_STORAGE_KEY}-${userId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    return [];
  } catch {
    return [];
  }
}

function saveToLocal(userId: string | number, records: VisitRecord[]): void {
  try {
    const toSave = records.slice(0, MAX_LOCAL_RECORDS);
    localStorage.setItem(`${LOCAL_STORAGE_KEY}-${userId}`, JSON.stringify(toSave));
  } catch {
    logger.warn('本地存储历史记录失败');
  }
}

function clearLocal(userId: string | number): void {
  try {
    localStorage.removeItem(`${LOCAL_STORAGE_KEY}-${userId}`);
  } catch {
    // ignore
  }
}

function generateLocalId(): string {
  return `local_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// ═══════════════════════════════════════════

export const useRecentVisitsStore = defineStore('recent-visits', () => {
  // ── State ──
  const visits = ref<VisitRecord[]>([]);
  const total = ref(0);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  /** 是否使用本地存储模式（后端不可用时自动降级） */
  const localMode = ref(false);

  // ── Computed ──

  const hasVisits = computed(() => visits.value.length > 0);

  /** 按类型分组 */
  const groupedByType = computed(() => {
    const groups: Record<string, VisitRecord[]> = {
      chat: [],
      document: [],
      knowledge_base: [],
    };
    for (const v of visits.value) {
      if (groups[v.type]) {
        groups[v.type].push(v);
      }
    }
    return groups;
  });

  /** 按日期分组（今天/昨天/更早） */
  const groupedByDate = computed(() => {
    const groups: Record<string, VisitRecord[]> = {};
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const todayStr = today.toLocaleDateString('zh-CN');
    const yesterdayStr = yesterday.toLocaleDateString('zh-CN');

    for (const item of visits.value) {
      const date = new Date(item.visitedAt).toLocaleDateString('zh-CN');
      let label: string;
      if (date === todayStr) {
        label = '今天';
      } else if (date === yesterdayStr) {
        label = '昨天';
      } else {
        label = date;
      }
      if (!groups[label]) groups[label] = [];
      groups[label].push(item);
    }
    return groups;
  });

  // ── 获取当前用户 ID ──

  function getUserId(): string | number {
    const authStore = useAuthStore();
    return authStore.user?.id || 'anonymous';
  }

  // ── Actions ──

  /**
   * 记录一次访问
   * - 优先调用后端 API
   * - 失败时降级到 localStorage
   * - 同一 item 重复访问会去重 + 更新访问时间
   */
  async function recordVisit(
    itemId: string,
    type: VisitItemType,
    title: string,
    description?: string,
    route?: string,
  ): Promise<void> {
    const userId = getUserId();
    const now = new Date().toISOString();

    try {
      const params: RecordVisitRequest = {
        userId,
        itemId,
        type,
        title,
        description,
        route,
      };

      const record = await historyApi.recordVisit(params);
      // 后端成功后，更新本地状态
      const existingIdx = visits.value.findIndex(
        (v) => v.itemId === itemId && v.type === type,
      );
      if (existingIdx >= 0) {
        visits.value.splice(existingIdx, 1);
      }
      visits.value.unshift(record);
      total.value = visits.value.length;
      localMode.value = false;
    } catch (err) {
      // 降级到本地存储
      logger.warn('后端记录访问失败，使用本地存储', err);
      localMode.value = true;

      const existing = visits.value.find(
        (v) => v.itemId === itemId && v.type === type,
      );
      if (existing) {
        existing.visitedAt = now;
        existing.visitCount = (existing.visitCount || 1) + 1;
        // 提到最前面
        visits.value = visits.value.filter((v) => v !== existing);
        visits.value.unshift(existing);
      } else {
        const record: VisitRecord = {
          id: generateLocalId(),
          userId,
          itemId,
          type,
          title,
          description,
          route,
          visitedAt: now,
          visitCount: 1,
        };
        visits.value.unshift(record);
      }

      // 限制最大条数
      if (visits.value.length > MAX_LOCAL_RECORDS) {
        visits.value = visits.value.slice(0, MAX_LOCAL_RECORDS);
      }
      total.value = visits.value.length;

      saveToLocal(userId, visits.value);
    }
  }

  /**
   * 获取最近访问列表
   * - 优先调用后端 API
   * - 失败时从 localStorage 读取
   */
  async function loadRecentVisits(
    limit = 20,
    type?: VisitItemType,
  ): Promise<void> {
    const userId = getUserId();
    isLoading.value = true;
    error.value = null;

    try {
      const data = await historyApi.getRecentVisits({ userId, limit, type });
      visits.value = data.visits;
      total.value = data.total;
      localMode.value = false;
    } catch (err) {
      // 从本地加载
      logger.warn('后端获取历史失败，从本地加载', err);
      let localData = loadFromLocal(userId);

      if (type) {
        localData = localData.filter((v) => v.type === type);
      }
      localData = localData.slice(0, limit);

      visits.value = localData;
      total.value = localData.length;
      localMode.value = true;
      error.value = '无法连接服务器，显示本地记录';
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 清除所有历史
   */
  async function clearAllHistory(): Promise<void> {
    const userId = getUserId();

    try {
      await historyApi.clearHistory(userId);
      visits.value = [];
      total.value = 0;
    } catch (err) {
      logger.warn('后端清除历史失败，清除本地数据', err);
      visits.value = [];
      total.value = 0;
    }
    clearLocal(userId);
  }

  /**
   * 删除单条历史
   */
  async function deleteVisit(id: string): Promise<void> {
    const userId = getUserId();

    try {
      if (!localMode.value) {
        await historyApi.deleteHistoryItem(userId, id);
      }
    } catch (err) {
      logger.warn('后端删除记录失败', err);
    }

    visits.value = visits.value.filter((v) => v.id !== id);
    total.value = visits.value.length;

    if (localMode.value) {
      saveToLocal(userId, visits.value);
    }
  }

  /**
   * 初始化：从本地加载数据（用于快速首屏渲染）
   */
  function initFromLocal(): void {
    const userId = getUserId();
    const localData = loadFromLocal(userId);
    if (localData.length > 0) {
      visits.value = localData;
      total.value = localData.length;
      localMode.value = true;
    }
  }

  return {
    // state
    visits,
    total,
    isLoading,
    error,
    localMode,
    // computed
    hasVisits,
    groupedByType,
    groupedByDate,
    // actions
    recordVisit,
    loadRecentVisits,
    clearAllHistory,
    deleteVisit,
    initFromLocal,
  };
});
