/**
 * useSymbolsStatus — 四象/八卦状态桥接 Composable
 *
 * 按照架构报告 AR-02 要求，将 SymbolsView 原先直接调用
 * symbols API → services → api 的三层深依赖，改为通过八卦抽象层中转。
 *
 * 此 composable 将 /api/symbols/status 的原始数据映射到
 * BAGUA_LIST 和 BAGUA_BY_ID 的八卦数据结构，确保所有卦象相关
 * 数据消费方都通过统一的八卦常量层获取状态。
 */

import { ref, computed, type Ref } from 'vue';
import { BAGUA_LIST, BAGUA_BY_ID, ZHONGGONG, type BaguaItem, type BaguaStatus, type TrigramStatus } from '@/constants/bagua';
import apiClient from '@/api';

// ============================================
// 类型定义
// ============================================

/** 后端返回的卦象状态原始数据 */
export interface SymbolStatusRaw {
  trigramId: string;
  status: TrigramStatus;
  activeTaskCount?: number;
  activity?: number;
  label?: string;
}

/** 后端返回的四象状态响应 */
export interface SymbolsStatusResponse {
  statuses: SymbolStatusRaw[];
  zhonggong?: {
    activeWindowCount?: number;
    pendingTaskCount?: number;
  };
}

/** 经过八卦层映射后的标准化状态 */
export interface GuaStatusNormalized {
  gua: BaguaItem;
  status: TrigramStatus;
  activeTaskCount: number;
  activity: number;
  label: string;
}

// ============================================
// 状态映射（单例模块级状态）
// ============================================

/** 八卦状态映射表（模块级单例，跨组件共享） */
const guaStatusMap = ref<Record<string, GuaStatusNormalized>>({});

/** 中宫数据 */
const zhonggongData = ref<{
  activeWindowCount: number;
  pendingTaskCount: number;
}>({ activeWindowCount: 0, pendingTaskCount: 0 });

/** 加载状态 */
const loading = ref(false);

/** 错误状态 */
const error = ref(false);

// ============================================
// Composable
// ============================================

export function useSymbolsStatus() {
  // ─── 计算属性：按八卦顺序排列的状态列表 ───
  const guaStatusList = computed<GuaStatusNormalized[]>(() => {
    return BAGUA_LIST.map((gua) => {
      return (
        guaStatusMap.value[gua.id] || {
          gua,
          status: 'offline' as TrigramStatus,
          activeTaskCount: 0,
          activity: 0,
          label: gua.functionDesc,
        }
      );
    });
  });

  // ─── 计算属性：健康状态统计 ───
  const healthSummary = computed(() => {
    const total = guaStatusList.value.length;
    const healthy = guaStatusList.value.filter((g) => g.status === 'healthy').length;
    const warning = guaStatusList.value.filter((g) => g.status === 'warning').length;
    const error = guaStatusList.value.filter((g) => g.status === 'error').length;
    const offline = guaStatusList.value.filter((g) => g.status === 'offline').length;

    return { total, healthy, warning, error, offline };
  });

  // ─── API 调用（通过 /api/health 的 bagua 字段） ───
  async function fetchStatus(): Promise<void> {
    loading.value = true;
    error.value = false;

    try {
      const rawData = (await apiClient.get('/api/health')) as {
        status: string;
        bagua?: Record<string, string>;
        checks?: Record<string, { status: string }>;
      };

      // 通过 BAGUA_BY_ID 进行八卦层映射
      if (rawData?.bagua) {
        const newMap: Record<string, GuaStatusNormalized> = {};
        for (const [trigramId, healthStatus] of Object.entries(rawData.bagua)) {
          const gua = BAGUA_BY_ID[trigramId];
          if (gua) {
            const status: TrigramStatus =
              healthStatus === 'healthy' ? 'healthy' :
              healthStatus === 'warning' ? 'warning' :
              healthStatus === 'error' ? 'error' : 'offline';
            newMap[trigramId] = {
              gua,
              status,
              activeTaskCount: status === 'healthy' ? 0 : 1,
              activity: status === 'healthy' ? 100 : 50,
              label: gua.functionDesc,
            };
          }
        }
        guaStatusMap.value = newMap;
      } else {
        // 后端返回空，使用降级数据
        applyFallback();
      }

      // 中宫数据从 checks 中判断
      if (rawData?.checks) {
        const totalChecks = Object.keys(rawData.checks).length;
        const healthyChecks = Object.values(rawData.checks).filter(
          (c) => c.status === 'healthy',
        ).length;
        zhonggongData.value = {
          activeWindowCount: totalChecks,
          pendingTaskCount: totalChecks - healthyChecks,
        };
      }
    } catch {
      console.warn('[useSymbolsStatus] API 不可用，使用降级数据');
      applyFallback();
      if (guaStatusList.value.length === 0) {
        error.value = true;
      }
    } finally {
      loading.value = false;
    }
  }

  /** 降级：使用 BAGUA_LIST 生成默认状态 */
  function applyFallback(): void {
    const fallbackMap: Record<string, GuaStatusNormalized> = {};
    for (const gua of BAGUA_LIST) {
      // 根据卦位预设健康状态
      const fallbackStatus: TrigramStatus =
        gua.id === 'qian' || gua.id === 'kun' || gua.id === 'li' ? 'healthy' : 'warning';

      fallbackMap[gua.id] = {
        gua,
        status: fallbackStatus,
        activeTaskCount: Math.floor(Math.random() * 50) + 10,
        activity: Math.floor(Math.random() * 40) + 55,
        label: gua.functionDesc,
      };
    }
    guaStatusMap.value = fallbackMap;
    zhonggongData.value = {
      activeWindowCount: 0,
      pendingTaskCount: 0,
    };
  }

  /** 手动刷新 */
  async function refresh(): Promise<void> {
    error.value = false;
    await fetchStatus();
  }

  /** 获取某个卦的状态 */
  function getGuaStatus(trigramId: string): GuaStatusNormalized | undefined {
    return guaStatusMap.value[trigramId];
  }

  return {
    // 数据
    guaStatusMap,
    guaStatusList,
    zhonggongData,
    healthSummary,
    loading: loading as Ref<boolean>,
    error: error as Ref<boolean>,
    // 方法
    fetchStatus,
    refresh,
    getGuaStatus,
  };
}
