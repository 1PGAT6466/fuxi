/**
 * 伏羲 v2.1 — 数据洞察 Store
 *
 * 功能：
 * - 从 /api/dashboard/insights 获取数据洞察数据
 * - 趋势分析、异常检测、洞察建议
 * - 自动刷新（30秒轮询）
 * - 历史数据缓存（最近 50 条）
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getDashboardInsights } from '@/api/dashboard';
import { createLogger } from '@/utils/logger';

const logger = createLogger('DataInsightsStore');

/** 缓存有效期 5 分钟 */
const CACHE_TTL = 5 * 60 * 1000;
/** 最大缓存条数 */
const MAX_HISTORY = 50;
/** 自动刷新间隔 30 秒 */
const POLL_INTERVAL = 30_000;

/** 趋势数据点 */
export interface TrendPoint {
  /** 时间标签 */
  label: string;
  /** 数值 */
  value: number;
  /** 变化率（百分比） */
  change?: number;
}

/** 异常检测项 */
export interface AnomalyItem {
  /** 异常 ID */
  id: string;
  /** 异常类型 */
  type: 'spike' | 'drop' | 'pattern' | 'threshold';
  /** 异常描述 */
  description: string;
  /** 严重程度 */
  severity: 'low' | 'medium' | 'high' | 'critical';
  /** 相关指标 */
  metric: string;
  /** 发生时间 */
  timestamp: string;
  /** 是否已确认 */
  acknowledged?: boolean;
}

/** 洞察建议 */
export interface InsightItem {
  /** 建议 ID */
  id: string;
  /** 建议类型 */
  type: 'optimization' | 'warning' | 'info' | 'action';
  /** 建议标题 */
  title: string;
  /** 详细描述 */
  description: string;
  /** 影响范围 */
  impact?: string;
  /** 优先级 1-10 */
  priority: number;
  /** 建议的操作 */
  actionLabel?: string;
}

/** 数据洞察完整数据 */
export interface DataInsights {
  /** 趋势数据 */
  trends: TrendPoint[];
  /** 异常列表 */
  anomalies: AnomalyItem[];
  /** 洞察建议 */
  insights: InsightItem[];
  /** 系统健康分数 0-100 */
  healthScore: number;
  /** 数据更新时间 */
  updatedAt: string;
}

/** 缓存条目 */
interface CacheEntry {
  data: DataInsights;
  timestamp: number;
}

export const useDataInsightsStore = defineStore('dataInsights', () => {
  // ============================
  // 状态
  // ============================

  const data = ref<DataInsights | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastFetchTime = ref<number>(0);

  /** 历史数据缓存（按时间倒序） */
  const history = ref<CacheEntry[]>([]);

  /** 轮询定时器 */
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  // ============================
  // 计算属性
  // ============================

  /** 趋势数据 */
  const trends = computed(() => data.value?.trends ?? []);

  /** 异常列表（按严重程度排序） */
  const anomalies = computed(() => {
    const items = data.value?.anomalies ?? [];
    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    return [...items].sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
  });

  /** 洞察建议（按优先级排序） */
  const insights = computed(() => {
    const items = data.value?.insights ?? [];
    return [...items].sort((a, b) => b.priority - a.priority);
  });

  /** 未确认的异常数 */
  const unacknowledgedAnomalies = computed(
    () => anomalies.value.filter((a) => !a.acknowledged).length,
  );

  /** 系统健康分数 */
  const healthScore = computed(() => data.value?.healthScore ?? 0);

  /** 健康等级 */
  const healthLevel = computed(() => {
    const score = healthScore.value;
    if (score >= 80) return 'excellent';
    if (score >= 60) return 'good';
    if (score >= 40) return 'warning';
    return 'critical';
  });

  /** 是否有数据 */
  const hasData = computed(() => data.value !== null);

  /** 数据是否过期 */
  const isStale = computed(() => {
    if (!lastFetchTime.value) return true;
    return Date.now() - lastFetchTime.value > CACHE_TTL;
  });

  // ============================
  // 数据获取
  // ============================

  /**
   * 获取数据洞察
   * @param force 是否强制刷新（忽略缓存）
   */
  async function fetchInsights(force = false): Promise<void> {
    // 非强制刷新时检查缓存
    if (!force && !isStale.value && data.value) {
      logger.debug('使用缓存数据，跳过刷新');
      return;
    }

    loading.value = true;
    error.value = null;

    try {
      const raw = await getDashboardInsights();

      // 兼容多种后端返回格式
      const payload = extractPayload(raw);

      const insights: DataInsights = {
        trends: normalizeArray<TrendPoint>(payload.trends, []),
        anomalies: normalizeArray<AnomalyItem>(payload.anomalies, []),
        insights: normalizeArray<InsightItem>(payload.insights ?? payload.recommendations, []),
        healthScore: Number(payload.healthScore ?? payload.health_score ?? 0),
        updatedAt: String(payload.updatedAt ?? payload.updated_at ?? new Date().toISOString()),
      };

      data.value = insights;
      lastFetchTime.value = Date.now();

      // 添加到历史缓存
      addToHistory(insights);

      logger.info('数据洞察加载成功', { anomalies: insights.anomalies.length });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      error.value = msg;
      logger.warn('获取数据洞察失败', msg);
    } finally {
      loading.value = false;
    }
  }

  // ============================
  // 自动刷新
  // ============================

  /** 启动自动刷新（30秒轮询） */
  function startAutoRefresh(): void {
    stopAutoRefresh();
    // 立即执行一次
    fetchInsights();
    pollTimer = setInterval(() => {
      fetchInsights(true); // 强制刷新，绕过缓存
    }, POLL_INTERVAL);
    logger.info('自动刷新已启动', { interval: POLL_INTERVAL });
  }

  /** 停止自动刷新 */
  function stopAutoRefresh(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
      logger.info('自动刷新已停止');
    }
  }

  // ============================
  // 历史缓存
  // ============================

  /** 添加数据到历史缓存 */
  function addToHistory(insights: DataInsights): void {
    history.value.unshift({
      data: insights,
      timestamp: Date.now(),
    });
    // 限制缓存大小
    if (history.value.length > MAX_HISTORY) {
      history.value = history.value.slice(0, MAX_HISTORY);
    }
  }

  /** 获取历史数据 */
  function getHistory(limit = 10): CacheEntry[] {
    return history.value.slice(0, limit);
  }

  /** 清除历史缓存 */
  function clearHistory(): void {
    history.value = [];
  }

  // ============================
  // 异常操作
  // ============================

  /** 确认异常 */
  function acknowledgeAnomaly(anomalyId: string): void {
    if (!data.value) return;
    const anomaly = data.value.anomalies.find((a) => a.id === anomalyId);
    if (anomaly) {
      anomaly.acknowledged = true;
      logger.info('异常已确认', { anomalyId });
    }
  }

  /** 确认所有异常 */
  function acknowledgeAll(): void {
    if (!data.value) return;
    data.value.anomalies.forEach((a) => {
      a.acknowledged = true;
    });
  }

  // ============================
  // 重置
  // ============================

  function reset(): void {
    data.value = null;
    error.value = null;
    lastFetchTime.value = 0;
    stopAutoRefresh();
  }

  return {
    // 状态
    data,
    loading,
    error,
    lastFetchTime,
    history,
    // 计算属性
    trends,
    anomalies,
    insights,
    unacknowledgedAnomalies,
    healthScore,
    healthLevel,
    hasData,
    isStale,
    // 方法
    fetchInsights,
    startAutoRefresh,
    stopAutoRefresh,
    getHistory,
    clearHistory,
    acknowledgeAnomaly,
    acknowledgeAll,
    reset,
  };
});

// ============================
// 工具函数
// ============================

/** 从响应中提取 payload */
function extractPayload<T>(value: unknown): T {
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if ('data' in record && record.data !== undefined) {
      return record.data as T;
    }
  }
  return value as T;
}

/** 安全数组规范化 */
function normalizeArray<T>(value: unknown, fallback: T[]): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const candidates = [record.items, record.list, record.data, record.results];
    for (const candidate of candidates) {
      if (Array.isArray(candidate)) return candidate as T[];
    }
  }
  return fallback;
}
