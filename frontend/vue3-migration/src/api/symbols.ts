/**
 * 伏羲 v2.1 — 卦象状态 API
 * 读取后端 /api/symbols/status 获取器官实时状态
 * 同时提供统一搜索接口 /api/unified-search
 */

import apiClient from './index';
import type { OrganStatus, TrigramStatus } from '@/constants/bagua';

// ============================
// 类型定义
// ============================

export interface SymbolStatusResponse {
  data: {
    statuses: OrganStatus[];
    /** 服务管理中心（中宫）摘要 */
    zhonggong: {
      activeWindowCount: number;
      pendingTaskCount: number;
      evolutionLevel: number;
      evolutionProgress: number;
    };
  };
}

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

// ============================
// API 方法
// ============================

/** 获取卦象器官实时状态 */
export async function fetchSymbolStatus(): Promise<SymbolStatusResponse> {
  return apiClient.get('/api/symbols/status') as Promise<SymbolStatusResponse>;
}

/** 伏羲令统一搜索 */
export async function unifiedSearch(query: string): Promise<UnifiedSearchResponse> {
  return apiClient.get('/api/unified-search', {
    params: { q: query },
  }) as Promise<UnifiedSearchResponse>;
}

// ============================
// Mock 数据（后端未就绪时使用）
// ============================

/** Mock 器官状态数据 */
export function getMockSymbolStatus(): SymbolStatusResponse {
  return {
    data: {
      statuses: [
        { trigramId: 'qian', status: 'healthy', activeTaskCount: 1, label: '乾·大脑' },
        { trigramId: 'kun', status: 'healthy', activeTaskCount: 3, label: '坤·脾' },
        { trigramId: 'zhen', status: 'warning', activeTaskCount: 2, label: '震·肝' },
        { trigramId: 'xun', status: 'healthy', activeTaskCount: 1, label: '巽·肺' },
        { trigramId: 'kan', status: 'healthy', activeTaskCount: 0, label: '坎·肾' },
        { trigramId: 'li', status: 'warning', activeTaskCount: 2, label: '离·心' },
        { trigramId: 'gen', status: 'healthy', activeTaskCount: 0, label: '艮·皮肤' },
        { trigramId: 'dui', status: 'healthy', activeTaskCount: 1, label: '兑·鼻' },
        { trigramId: 'zhonggong', status: 'healthy', activeTaskCount: 0, label: '中宫·胃' },
      ],
      zhonggong: {
        activeWindowCount: 4,
        pendingTaskCount: 5,
        evolutionLevel: 2,
        evolutionProgress: 65,
      },
    },
  };
}

/** Mock 统一搜索数据 */
export function getMockUnifiedSearch(query: string): UnifiedSearchResponse {
  const allMatches: UnifiedSearchResult[] = [
    {
      type: 'service',
      title: 'AI 对话助手',
      url: '/workspace/chat',
      description: '多模态大模型对话，支持流式输出',
      icon: '🧠',
    },
    {
      type: 'service',
      title: '知识库管理',
      url: '/knowledge',
      description: '企业知识文档管理，向量检索',
      icon: '📚',
    },
    {
      type: 'service',
      title: '文档工具集',
      url: '/workspace/doc-tools',
      description: '格式转换、PDF合并/拆分',
      icon: '🛠️',
    },
    {
      type: 'service',
      title: '数据分析看板',
      url: '/workspace/analytics',
      description: '数据趋势分析与可视化报表',
      icon: '📊',
    },
    {
      type: 'service',
      title: 'DXF 工程浏览器',
      url: '/dxf-viewer',
      description: 'CAD图纸在线查看，图层与测量',
      icon: '📐',
    },
    {
      type: 'service',
      title: '评测管理中心',
      url: '/admin/evaluation',
      description: 'LLM 评测数据集与任务管理',
      icon: '📋',
    },
    {
      type: 'service',
      title: '系统监控',
      url: '/admin',
      description: 'API 调用、存储、用户健康仪表板',
      icon: '🛡️',
    },
    {
      type: 'document',
      title: '伏羲 v2.1 架构方案',
      url: '/workspace/wiki',
      description: '六层架构模型与八卦宇宙映射',
      icon: '📄',
    },
    {
      type: 'document',
      title: 'API 接口文档',
      url: '/workspace/wiki',
      description: '48 端点完整接口规范',
      icon: '📄',
    },
    {
      type: 'wiki',
      title: '开发指南',
      url: '/workspace/wiki',
      description: '服务注册规范与开发流程',
      icon: '📝',
    },
    // 卦象命令：输入"乾宫"等直接跳转
    {
      type: 'gua',
      title: '乾宫 → AI 对话',
      url: '/workspace/chat',
      description: '☰ 乾·大脑·AI 智能对话',
      icon: '☰',
    },
    {
      type: 'gua',
      title: '坤宫 → 知识库',
      url: '/knowledge',
      description: '☷ 坤·脾·知识管理',
      icon: '☷',
    },
    {
      type: 'gua',
      title: '震宫 → 文档中心',
      url: '/workspace/documents',
      description: '☳ 震·肝·文档消化',
      icon: '☳',
    },
    {
      type: 'gua',
      title: '巽宫 → Wiki 文档',
      url: '/workspace/wiki',
      description: '☴ 巽·肺·知识检索',
      icon: '☴',
    },
    {
      type: 'gua',
      title: '坎宫 → 数据精炼',
      url: '/workspace/worldtree',
      description: '☵ 坎·肾·数据精炼',
      icon: '☵',
    },
    {
      type: 'gua',
      title: '离宫 → 评测中心',
      url: '/admin/evaluation',
      description: '☲ 离·心·决策判断',
      icon: '☲',
    },
    {
      type: 'gua',
      title: '艮宫 → 系统管理',
      url: '/admin',
      description: '☶ 艮·皮肤·系统守卫',
      icon: '☶',
    },
    {
      type: 'gua',
      title: '兑宫 → AI 对话',
      url: '/workspace/chat',
      description: '☱ 兑·鼻·智能对话',
      icon: '☱',
    },
  ];

  // 过滤匹配
  const q = query.toLowerCase();
  const matches = allMatches.filter(
    (m) =>
      m.title.toLowerCase().includes(q) ||
      (m.description && m.description.toLowerCase().includes(q)),
  );

  return {
    data: {
      query,
      matches: matches.slice(0, 8),
    },
  };
}
