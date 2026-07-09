/**
 * useGuaServices — 卦位-服务映射 Composable
 *
 * 从 ServiceRegistry 获取所有服务，按 guaAffinity 分组
 * 返回 Record<GuaSymbol, ServiceManifest[]>
 * 用于 BaguaCell 的下拉菜单
 *
 * @deprecated 当前未被使用。服务数据改为从 ServiceRegistry 动态加载。
 * 保留此模块供未来 BaguaCell 集成时参考。
 */

import { computed } from 'vue';
import apiClient from '@/api';
import { createLogger } from '@/utils/logger';

const logger = createLogger('useGuaServices');

// ============================================
// 类型定义
// ============================================

/** 八卦符号枚举 */
export type GuaSymbol = 'qian' | 'kun' | 'zhen' | 'xun' | 'kan' | 'li' | 'gen' | 'dui';

/** 服务清单 */
export interface ServiceManifest {
  id: string;
  name: string;
  description: string;
  icon?: string;
  /** 归属卦位 */
  guaAffinity: GuaSymbol;
  /** 服务路由或窗口 ID */
  route: string;
  /** 是否为活动服务 */
  isActive?: boolean;
  /** 活跃任务数 */
  activeTaskCount?: number;
  /** 服务状态 */
  status?: 'online' | 'degraded' | 'offline';
}

/** 按卦位分组的服务映射 */
export type GuaServiceMap = Record<GuaSymbol, ServiceManifest[]>;

// ============================================
// Composable
// ============================================

/** 服务注册表（模块级单例，可被外部更新） */
let serviceRegistry: ServiceManifest[] = [];

export function useGuaServices() {
  /** 按卦位分组的服务映射 */
  const guaServiceMap = computed<GuaServiceMap>(() => {
    const map: GuaServiceMap = {
      qian: [], kun: [], zhen: [], xun: [],
      kan: [], li: [], gen: [], dui: [],
    };
    for (const service of serviceRegistry) {
      map[service.guaAffinity].push(service);
    }
    return map;
  });

  /** 获取特定卦位的服务列表 */
  function getServicesForGua(gua: GuaSymbol): ServiceManifest[] {
    return serviceRegistry.filter((s) => s.guaAffinity === gua);
  }

  /** 获取特定卦位的活跃任务总数 */
  function getActiveTaskCountForGua(gua: GuaSymbol): number {
    return serviceRegistry
      .filter((s) => s.guaAffinity === gua)
      .reduce((sum, s) => sum + (s.activeTaskCount || 0), 0);
  }

  /** 从 API 获取服务清单并更新注册表 */
  async function fetchServiceManifest(): Promise<void> {
    try {
      const data = (await apiClient.get('/api/services')) as unknown as {
        data?: ServiceManifest[];
        services?: ServiceManifest[];
        items?: ServiceManifest[];
      };
      const list = data?.data ?? data?.services ?? data?.items;
      if (list && Array.isArray(list)) {
        serviceRegistry = list;
        logger.info(`从 API 加载了 ${list.length} 个服务`);
      }
    } catch (err) {
      logger.warn('服务清单 API 不可用', err);
    }
  }

  /** 更新服务注册表 */
  function updateServiceRegistry(services: ServiceManifest[]): void {
    serviceRegistry = services;
  }

  /** 所有服务总数 */
  const totalServices = computed(() => serviceRegistry.length);

  /** 平台总活跃任务数 */
  const totalActiveTasks = computed(() =>
    serviceRegistry.reduce((sum, s) => sum + (s.activeTaskCount || 0), 0),
  );

  /** 平台总在线服务数 */
  const totalOnlineServices = computed(
    () => serviceRegistry.filter((s) => s.status === 'online').length,
  );

  return {
    services: serviceRegistry,
    guaServiceMap,
    getServicesForGua,
    getActiveTaskCountForGua,
    fetchServiceManifest,
    updateServiceRegistry,
    totalServices,
    totalActiveTasks,
    totalOnlineServices,
  };
}
