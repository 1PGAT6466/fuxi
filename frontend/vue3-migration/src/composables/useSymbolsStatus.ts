/**
 * useSymbolsStatus — 四象/八卦状态桥接 Composable
 *
 * 按照架构报告 AR-02 要求，将 SymbolsView 原先直接调用
 * symbols API → services → api 的三层深依赖，改为通过八卦抽象层中转。
 *
 * 此 composable 将 /api/health 的 bagua 字段映射到
 * BAGUA_LIST 和 BAGUA_BY_ID 的八卦数据结构，确保所有卦象相关
 * 数据消费方都通过统一的八卦常量层获取状态。
 *
 * @deprecated 当前未被直接使用。保留供未来 SymbolsView 迁移时参考。
 */

import { ref, computed, type Ref } from 'vue';
import { BAGUA_LIST, BAGUA_BY_ID, type BaguaItem, type BaguaStatus, type TrigramStatus } from '@/constants/bagua';
import apiClient from '@/api';
import { createLogger } from '@/utils/logger';

const logger = createLogger('useSymbolsStatus');

// ============================================
// 类型定义
// ============================================

export interface GuaStatusNormalized {
  gua: BaguaItem;
  status: TrigramStatus;
  activeTaskCount: number;
  activity: number;
  label: string;
}

// ============================================
// Composable
// ============================================

export function useSymbolsStatus() {
  const guaStatusMap = ref<Record<string, GuaStatusNormalized>>({});
  const zhonggongData = ref({ activeWindowCount: 0, pendingTaskCount: 0 });
  const loading = ref(false);
  const error = ref(false);

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

  const healthSummary = computed(() => {
    const total = guaStatusList.value.length;
    const healthy = guaStatusList.value.filter((g) => g.status === 'healthy').length;
    const warning = guaStatusList.value.filter((g) => g.status === 'warning').length;
    const errCount = guaStatusList.value.filter((g) => g.status === 'error').length;
    const offline = guaStatusList.value.filter((g) => g.status === 'offline').length;
    return { total, healthy, warning, error: errCount, offline };
  });

  async function fetchStatus(): Promise<void> {
    loading.value = true;
    error.value = false;

    try {
      const rawData = (await apiClient.get('/api/health')) as {
        status: string;
        bagua?: Record<string, string>;
        checks?: Record<string, { status: string }>;
      };

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
        logger.info('健康检查接口未返回 bagua 字段，使用降级数据');
        applyFallback();
      }

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
    } catch (err) {
      logger.warn('健康检查接口不可用，使用降级数据', err);
      applyFallback();
      error.value = true;
    } finally {
      loading.value = false;
    }
  }

  function applyFallback(): void {
    const fallbackMap: Record<string, GuaStatusNormalized> = {};
    for (const gua of BAGUA_LIST) {
      const fallbackStatus: TrigramStatus =
        gua.id === 'qian' || gua.id === 'kun' || gua.id === 'li' ? 'healthy' : 'warning';
      fallbackMap[gua.id] = {
        gua,
        status: fallbackStatus,
        activeTaskCount: 0,
        activity: 0,
        label: gua.functionDesc,
      };
    }
    guaStatusMap.value = fallbackMap;
    zhonggongData.value = { activeWindowCount: 0, pendingTaskCount: 0 };
  }

  async function refresh(): Promise<void> {
    error.value = false;
    await fetchStatus();
  }

  function getGuaStatus(trigramId: string): GuaStatusNormalized | undefined {
    return guaStatusMap.value[trigramId];
  }

  return {
    guaStatusMap,
    guaStatusList,
    zhonggongData,
    healthSummary,
    loading: loading as Ref<boolean>,
    error: error as Ref<boolean>,
    fetchStatus,
    refresh,
    getGuaStatus,
  };
}
