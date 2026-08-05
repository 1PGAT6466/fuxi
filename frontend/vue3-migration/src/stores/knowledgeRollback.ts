/**
 * 伏羲 v2.1 — 知识回滚 Store
 *
 * 功能：
 * - 按来源/时间范围查询知识版本
 * - 查看版本差异
 * - 单条/批量回滚
 * - 回滚历史记录
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '@/api';
import { createLogger } from '@/utils/logger';
import { ElMessage } from 'element-plus';

const logger = createLogger('KnowledgeRollbackStore');

// ============================
// 类型定义
// ============================

/** 知识版本记录 */
export interface KnowledgeVersion {
  id: string;
  /** 知识条目 ID */
  knowledgeId: string;
  /** 版本号 */
  version: number;
  /** 内容快照 */
  content: string;
  /** 来源 */
  source: string;
  /** 来源类型 */
  sourceType: 'upload' | 'crawl' | 'api';
  /** 操作类型 */
  action: 'create' | 'update' | 'delete' | 'rollback';
  /** 操作者 */
  operatedBy: string;
  /** 操作时间 */
  operatedAt: string;
  /** 变更说明 */
  changeNote?: string;
  /** 标签 */
  tags?: string[];
}

/** 回滚查询参数 */
export interface RollbackQuery {
  page?: number;
  pageSize?: number;
  source?: string;
  sourceType?: string;
  startDate?: string;
  endDate?: string;
  keyword?: string;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

/** 版本对比 */
export interface VersionDiff {
  knowledgeId: string;
  currentVersion: KnowledgeVersion;
  targetVersion: KnowledgeVersion;
  /** 变更行列表 */
  changes: DiffLine[];
}

/** diff 行 */
export interface DiffLine {
  type: 'add' | 'remove' | 'same';
  content: string;
  lineNum: number;
}

export const useKnowledgeRollbackStore = defineStore('knowledgeRollback', () => {
  // ============================
  // 状态
  // ============================

  const versions = ref<KnowledgeVersion[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const loading = ref(false);
  const error = ref<string | null>(null);

  /** 筛选条件 */
  const filterSource = ref('');
  const filterSourceType = ref('');
  const filterStartDate = ref('');
  const filterEndDate = ref('');
  const keyword = ref('');

  /** 选中的版本 ID（用于批量回滚） */
  const selectedIds = ref<Set<string>>(new Set());

  /** 版本对比数据 */
  const diffData = ref<VersionDiff | null>(null);
  const diffLoading = ref(false);

  /** 回滚历史 */
  const rollbackHistory = ref<KnowledgeVersion[]>([]);
  const rollbackHistoryTotal = ref(0);
  const rollbackHistoryLoading = ref(false);

  // ============================
  // 计算属性
  // ============================

  const hasVersions = computed(() => versions.value.length > 0);
  const hasSelection = computed(() => selectedIds.value.size > 0);
  const selectedCount = computed(() => selectedIds.value.size);

  /** 来源选项列表 */
  const sourceOptions = computed(() => {
    const sources = new Set(versions.value.map((v) => v.source));
    return Array.from(sources).sort();
  });

  // ============================
  // 数据获取
  // ============================

  /**
   * 查询知识版本列表
   */
  async function fetchVersions(query?: Partial<RollbackQuery>): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const params: RollbackQuery = {
        page: query?.page ?? page.value,
        pageSize: query?.pageSize ?? pageSize.value,
        source: query?.source ?? (filterSource.value || undefined),
        sourceType: query?.sourceType ?? (filterSourceType.value || undefined),
        startDate: query?.startDate ?? (filterStartDate.value || undefined),
        endDate: query?.endDate ?? (filterEndDate.value || undefined),
        keyword: query?.keyword ?? (keyword.value || undefined),
      };

      const resp = await apiClient.get('/api/knowledge/versions', { params });
      const data = extractPayload<PaginatedResponse<KnowledgeVersion>>(resp);

      versions.value = data.items ?? [];
      total.value = data.total ?? 0;
      page.value = data.page ?? params.page ?? 1;
      pageSize.value = data.pageSize ?? params.pageSize ?? 20;

      logger.info('版本列表加载成功', { total: total.value });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      error.value = msg;
      logger.warn('获取版本列表失败', msg);
      ElMessage.error('获取版本列表失败：' + msg);
    } finally {
      loading.value = false;
    }
  }

  /**
   * 获取回滚历史
   */
  async function fetchRollbackHistory(query?: Partial<RollbackQuery>): Promise<void> {
    rollbackHistoryLoading.value = true;

    try {
      const params = {
        page: query?.page ?? 1,
        pageSize: query?.pageSize ?? 50,
      };

      const resp = await apiClient.get('/api/knowledge/rollback/history', { params });
      const data = extractPayload<PaginatedResponse<KnowledgeVersion>>(resp);

      rollbackHistory.value = data.items ?? [];
      rollbackHistoryTotal.value = data.total ?? 0;

      logger.info('回滚历史加载成功', { total: rollbackHistoryTotal.value });
    } catch (err) {
      logger.warn('获取回滚历史失败', err);
    } finally {
      rollbackHistoryLoading.value = false;
    }
  }

  /**
   * 获取版本对比
   */
  async function fetchDiff(knowledgeId: string, versionA: number, versionB: number): Promise<void> {
    diffLoading.value = true;

    try {
      const resp = await apiClient.get(`/api/knowledge/versions/${knowledgeId}/diff`, {
        params: { versionA, versionB },
      });
      diffData.value = extractPayload<VersionDiff>(resp);

      logger.info('版本对比加载成功', { knowledgeId, versionA, versionB });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('获取版本对比失败：' + msg);
      logger.warn('获取版本对比失败', msg);
    } finally {
      diffLoading.value = false;
    }
  }

  // ============================
  // 回滚操作
  // ============================

  /**
   * 回滚单条到指定版本
   */
  async function rollbackVersion(versionId: string, note?: string): Promise<boolean> {
    try {
      await apiClient.post(`/api/knowledge/versions/${versionId}/rollback`, { note });

      // 更新本地状态
      const version = versions.value.find((v) => v.id === versionId);
      if (version) {
        version.action = 'rollback';
        version.operatedAt = new Date().toISOString();
        version.changeNote = note ?? `回滚到版本 ${version.version}`;
      }

      ElMessage.success('回滚成功');
      logger.info('版本回滚成功', { versionId });
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('回滚失败：' + msg);
      logger.warn('版本回滚失败', { versionId, error: msg });
      return false;
    }
  }

  /**
   * 批量回滚
   */
  async function batchRollback(versionIds?: string[], note?: string): Promise<number> {
    const targetIds = versionIds ?? Array.from(selectedIds.value);
    if (targetIds.length === 0) {
      ElMessage.warning('请先选择要回滚的版本');
      return 0;
    }

    try {
      const resp = await apiClient.post('/api/knowledge/rollback/batch', {
        versionIds: targetIds,
        note: note ?? '批量回滚',
      });
      const result = extractPayload<{ success: number; failed: number }>(resp);

      // 更新本地状态
      for (const id of targetIds) {
        const version = versions.value.find((v) => v.id === id);
        if (version) {
          version.action = 'rollback';
          version.operatedAt = new Date().toISOString();
        }
      }

      selectedIds.value.clear();
      ElMessage.success(`批量回滚成功 ${result.success ?? targetIds.length} 条`);
      logger.info('批量回滚成功', { count: targetIds.length });
      return result.success ?? targetIds.length;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('批量回滚失败：' + msg);
      logger.warn('批量回滚失败', msg);
      return 0;
    }
  }

  // ============================
  // 选择管理
  // ============================

  function toggleSelect(id: string): void {
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id);
    } else {
      selectedIds.value.add(id);
    }
    selectedIds.value = new Set(selectedIds.value);
  }

  function selectAll(): void {
    selectedIds.value = new Set(versions.value.map((v) => v.id));
  }

  function clearSelection(): void {
    selectedIds.value = new Set();
  }

  function isSelected(id: string): boolean {
    return selectedIds.value.has(id);
  }

  // ============================
  // 筛选
  // ============================

  function setFilter(filters: {
    source?: string;
    sourceType?: string;
    startDate?: string;
    endDate?: string;
    keyword?: string;
  }): void {
    filterSource.value = filters.source ?? '';
    filterSourceType.value = filters.sourceType ?? '';
    filterStartDate.value = filters.startDate ?? '';
    filterEndDate.value = filters.endDate ?? '';
    keyword.value = filters.keyword ?? '';
    page.value = 1;
    fetchVersions();
  }

  function resetFilter(): void {
    filterSource.value = '';
    filterSourceType.value = '';
    filterStartDate.value = '';
    filterEndDate.value = '';
    keyword.value = '';
    page.value = 1;
    fetchVersions();
  }

  // ============================
  // 重置
  // ============================

  function reset(): void {
    versions.value = [];
    total.value = 0;
    page.value = 1;
    error.value = null;
    selectedIds.value = new Set();
    diffData.value = null;
    rollbackHistory.value = [];
    rollbackHistoryTotal.value = 0;
  }

  return {
    // 状态
    versions,
    total,
    page,
    pageSize,
    loading,
    error,
    filterSource,
    filterSourceType,
    filterStartDate,
    filterEndDate,
    keyword,
    selectedIds,
    diffData,
    diffLoading,
    rollbackHistory,
    rollbackHistoryTotal,
    rollbackHistoryLoading,
    // 计算属性
    hasVersions,
    hasSelection,
    selectedCount,
    sourceOptions,
    // 方法
    fetchVersions,
    fetchRollbackHistory,
    fetchDiff,
    rollbackVersion,
    batchRollback,
    toggleSelect,
    selectAll,
    clearSelection,
    isSelected,
    setFilter,
    resetFilter,
    reset,
  };
});

// ============================
// 工具函数
// ============================

function extractPayload<T>(value: unknown): T {
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if ('data' in record && record.data !== undefined) {
      return record.data as T;
    }
  }
  return value as T;
}
