/**
 * 伏羲 v2.1 — 知识审批 Store
 *
 * 功能：
 * - 获取待审批知识条目列表
 * - 单条审批（通过/拒绝）
 * - 批量审批操作
 * - 审批历史查询
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '@/api';
import { createLogger } from '@/utils/logger';
import { ElMessage } from 'element-plus';

const logger = createLogger('KnowledgeApprovalStore');

// ============================
// 类型定义
// ============================

/** 审批状态 */
export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

/** 知识条目 */
export interface KnowledgeItem {
  id: string;
  /** 知识内容/摘要 */
  content: string;
  /** 来源文档 */
  source: string;
  /** 来源类型：上传/爬取/API导入 */
  sourceType: 'upload' | 'crawl' | 'api';
  /** 知识类型：文档/问答/实体 */
  knowledgeType: 'document' | 'qa' | 'entity';
  /** 提交者 */
  submittedBy: string;
  /** 提交时间 */
  submittedAt: string;
  /** 审批状态 */
  status: ApprovalStatus;
  /** 审批人 */
  reviewedBy?: string;
  /** 审批时间 */
  reviewedAt?: string;
  /** 审批备注 */
  reviewNote?: string;
  /** 标签 */
  tags?: string[];
}

/** 审批请求参数 */
export interface ApprovalQuery {
  page?: number;
  pageSize?: number;
  status?: ApprovalStatus;
  sourceType?: string;
  keyword?: string;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export const useKnowledgeApprovalStore = defineStore('knowledgeApproval', () => {
  // ============================
  // 状态
  // ============================

  const items = ref<KnowledgeItem[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const loading = ref(false);
  const error = ref<string | null>(null);

  /** 当前筛选状态 */
  const filterStatus = ref<ApprovalStatus | ''>('');
  const filterSourceType = ref('');
  const keyword = ref('');

  /** 选中的条目 ID（用于批量操作） */
  const selectedIds = ref<Set<string>>(new Set());

  /** 审批历史 */
  const history = ref<KnowledgeItem[]>([]);
  const historyTotal = ref(0);
  const historyLoading = ref(false);

  // ============================
  // 计算属性
  // ============================

  const hasItems = computed(() => items.value.length > 0);
  const hasSelection = computed(() => selectedIds.value.size > 0);
  const selectedCount = computed(() => selectedIds.value.size);
  const pendingCount = computed(() => items.value.filter((i) => i.status === 'pending').length);

  // ============================
  // 数据获取
  // ============================

  /**
   * 获取待审批列表
   */
  async function fetchPendingList(query?: Partial<ApprovalQuery>): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const params: ApprovalQuery = {
        page: query?.page ?? page.value,
        pageSize: query?.pageSize ?? pageSize.value,
        status: query?.status ?? (filterStatus.value || undefined),
        sourceType: query?.sourceType ?? (filterSourceType.value || undefined),
        keyword: query?.keyword ?? (keyword.value || undefined),
      };

      const resp = await apiClient.get('/api/knowledge/approval/pending', { params });
      const data = extractPayload<PaginatedResponse<KnowledgeItem>>(resp);

      items.value = data.items ?? [];
      total.value = data.total ?? 0;
      page.value = data.page ?? params.page ?? 1;
      pageSize.value = data.pageSize ?? params.pageSize ?? 20;

      logger.info('待审批列表加载成功', { total: total.value });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      error.value = msg;
      logger.warn('获取待审批列表失败', msg);
      ElMessage.error('获取待审批列表失败：' + msg);
    } finally {
      loading.value = false;
    }
  }

  /**
   * 获取审批历史
   */
  async function fetchHistory(query?: Partial<ApprovalQuery>): Promise<void> {
    historyLoading.value = true;

    try {
      const params = {
        page: query?.page ?? 1,
        pageSize: query?.pageSize ?? 50,
        status: query?.status,
      };

      const resp = await apiClient.get('/api/knowledge/approval/history', { params });
      const data = extractPayload<PaginatedResponse<KnowledgeItem>>(resp);

      history.value = data.items ?? [];
      historyTotal.value = data.total ?? 0;

      logger.info('审批历史加载成功', { total: historyTotal.value });
    } catch (err) {
      logger.warn('获取审批历史失败', err);
    } finally {
      historyLoading.value = false;
    }
  }

  // ============================
  // 审批操作
  // ============================

  /**
   * 审批通过单条
   */
  async function approveItem(id: string, note?: string): Promise<boolean> {
    try {
      await apiClient.post(`/api/knowledge/approval/${id}/approve`, { note });

      // 更新本地状态
      const item = items.value.find((i) => i.id === id);
      if (item) {
        item.status = 'approved';
        item.reviewedAt = new Date().toISOString();
        item.reviewNote = note;
      }

      ElMessage.success('已通过');
      logger.info('审批通过', { id });
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('审批失败：' + msg);
      logger.warn('审批通过失败', { id, error: msg });
      return false;
    }
  }

  /**
   * 审批拒绝单条
   */
  async function rejectItem(id: string, reason: string): Promise<boolean> {
    try {
      await apiClient.post(`/api/knowledge/approval/${id}/reject`, { reason });

      const item = items.value.find((i) => i.id === id);
      if (item) {
        item.status = 'rejected';
        item.reviewedAt = new Date().toISOString();
        item.reviewNote = reason;
      }

      ElMessage.success('已拒绝');
      logger.info('审批拒绝', { id });
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('操作失败：' + msg);
      logger.warn('审批拒绝失败', { id, error: msg });
      return false;
    }
  }

  /**
   * 批量审批通过
   */
  async function batchApprove(ids?: string[]): Promise<number> {
    const targetIds = ids ?? Array.from(selectedIds.value);
    if (targetIds.length === 0) {
      ElMessage.warning('请先选择要操作的条目');
      return 0;
    }

    try {
      const resp = await apiClient.post('/api/knowledge/approval/batch-approve', {
        ids: targetIds,
      });
      const result = extractPayload<{ success: number; failed: number }>(resp);

      // 更新本地状态
      for (const id of targetIds) {
        const item = items.value.find((i) => i.id === id);
        if (item) {
          item.status = 'approved';
          item.reviewedAt = new Date().toISOString();
        }
      }

      selectedIds.value.clear();
      ElMessage.success(`批量通过 ${result.success ?? targetIds.length} 条`);
      logger.info('批量审批通过', { count: targetIds.length });
      return result.success ?? targetIds.length;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('批量通过失败：' + msg);
      logger.warn('批量审批通过失败', msg);
      return 0;
    }
  }

  /**
   * 批量审批拒绝
   */
  async function batchReject(ids: string[], reason: string): Promise<number> {
    const targetIds = ids.length > 0 ? ids : Array.from(selectedIds.value);
    if (targetIds.length === 0) {
      ElMessage.warning('请先选择要操作的条目');
      return 0;
    }

    try {
      const resp = await apiClient.post('/api/knowledge/approval/batch-reject', {
        ids: targetIds,
        reason,
      });
      const result = extractPayload<{ success: number; failed: number }>(resp);

      for (const id of targetIds) {
        const item = items.value.find((i) => i.id === id);
        if (item) {
          item.status = 'rejected';
          item.reviewedAt = new Date().toISOString();
          item.reviewNote = reason;
        }
      }

      selectedIds.value.clear();
      ElMessage.success(`批量拒绝 ${result.success ?? targetIds.length} 条`);
      logger.info('批量审批拒绝', { count: targetIds.length });
      return result.success ?? targetIds.length;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ElMessage.error('批量拒绝失败：' + msg);
      logger.warn('批量审批拒绝失败', msg);
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
    // 触发响应式更新
    selectedIds.value = new Set(selectedIds.value);
  }

  function selectAll(): void {
    selectedIds.value = new Set(items.value.filter((i) => i.status === 'pending').map((i) => i.id));
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

  function setFilter(status: ApprovalStatus | '', sourceType: string, kw: string): void {
    filterStatus.value = status;
    filterSourceType.value = sourceType;
    keyword.value = kw;
    page.value = 1;
    fetchPendingList();
  }

  function resetFilter(): void {
    filterStatus.value = '';
    filterSourceType.value = '';
    keyword.value = '';
    page.value = 1;
    fetchPendingList();
  }

  // ============================
  // 重置
  // ============================

  function reset(): void {
    items.value = [];
    total.value = 0;
    page.value = 1;
    error.value = null;
    selectedIds.value = new Set();
    history.value = [];
    historyTotal.value = 0;
  }

  return {
    // 状态
    items,
    total,
    page,
    pageSize,
    loading,
    error,
    filterStatus,
    filterSourceType,
    keyword,
    selectedIds,
    history,
    historyTotal,
    historyLoading,
    // 计算属性
    hasItems,
    hasSelection,
    selectedCount,
    pendingCount,
    // 方法
    fetchPendingList,
    fetchHistory,
    approveItem,
    rejectItem,
    batchApprove,
    batchReject,
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
