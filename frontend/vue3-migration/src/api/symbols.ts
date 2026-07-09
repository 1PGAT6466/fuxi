/**
 * 伏羲 v2.1 — 卦象状态 API
 * 从 /api/health 获取八卦器官状态（bagua 字段）
 * 同时提供统一搜索接口
 */

import apiClient from './index';
import type { OrganStatus } from '@/constants/bagua';

// ============================
// 类型定义
// ============================

export interface HealthResponse {
  status: string;
  checks: Record<string, { status: string; timestamp: number }>;
  bagua: Record<string, string>;
  engine: string;
  intent_mode: string;
  timestamp: number;
}

export interface SymbolStatusResponse {
  data: {
    statuses: OrganStatus[];
    zhonggong: {
      activeWindowCount: number;
      pendingTaskCount: number;
      evolutionLevel: number;
      evolutionProgress: number;
    };
  };
}

// ============================
// API 方法
// ============================

/** 获取卦象器官实时状态 → 从 /api/health 的 bagua 字段获取 */
export async function fetchSymbolStatus(): Promise<SymbolStatusResponse> {
  const data = (await apiClient.get('/api/health')) as HealthResponse;

  // 将 bagua 映射为 OrganStatus[]
  const baguaMap: Record<string, string> = {
    qian: '乾·大脑', kun: '坤·脾', zhen: '震·肝', xun: '巽·肺',
    kan: '坎·肾', li: '离·心', gen: '艮·皮肤', dui: '兑·鼻',
  };
  const statuses: OrganStatus[] = [];
  if (data.bagua) {
    for (const [key, status] of Object.entries(data.bagua)) {
      statuses.push({
        trigramId: key as OrganStatus['trigramId'],
        status: status === 'healthy' ? 'healthy' : status === 'warning' ? 'warning' : 'offline',
        activeTaskCount: status === 'healthy' ? 0 : 1,
        label: baguaMap[key] || key,
      });
    }
  }

  // 补充中宫
  if (!statuses.find((s) => s.trigramId === 'zhonggong')) {
    statuses.push({
      trigramId: 'zhonggong',
      status: 'healthy',
      activeTaskCount: 0,
      label: '中宫·胃',
    });
  }

  return {
    data: {
      statuses,
      zhonggong: {
        activeWindowCount: 4,
        pendingTaskCount: 0,
        evolutionLevel: 1,
        evolutionProgress: 50,
      },
    },
  };
}

/** 伏羲令统一搜索 */
export interface UnifiedSearchResult {
  type: 'document' | 'wiki' | 'tool' | 'service' | 'gua';
  title: string;
  url: string;
  description?: string;
  icon?: string;
}

export interface UnifiedSearchResponse {
  data: {
    query: string;
    matches: UnifiedSearchResult[];
  };
}

export async function unifiedSearch(query: string): Promise<UnifiedSearchResponse> {
  return apiClient.get('/api/unified-search', {
    params: { q: query },
  }) as Promise<UnifiedSearchResponse>;
}

/** 后端不可用时的 mock 数据（供 HomeView 降级使用） */
export function getMockSymbolStatus(): SymbolStatusResponse {
  const guaIds = ['qian', 'kun', 'zhen', 'xun', 'kan', 'li', 'gen', 'dui'];
  const guaLabels: Record<string, string> = {
    qian: '乾·大脑', kun: '坤·脾', zhen: '震·肝', xun: '巽·肺',
    kan: '坎·肾', li: '离·心', gen: '艮·皮肤', dui: '兑·鼻',
  };
  return {
    data: {
      statuses: guaIds.map((id) => ({
        trigramId: id,
        status: 'healthy' as const,
        activeTaskCount: 0,
        label: guaLabels[id] || id,
      })),
      zhonggong: {
        activeWindowCount: 0,
        pendingTaskCount: 0,
        evolutionLevel: 1,
        evolutionProgress: 0,
      },
    },
  };
}

