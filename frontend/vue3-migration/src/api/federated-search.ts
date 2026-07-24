/**
 * 伏羲 v2.1 — 联邦搜索 API 模块
 *
 * 提供联邦搜索相关的 API 调用:
 * - POST /api/search/federated  联邦搜索
 * - GET  /api/search/sources    获取搜索源
 */

import apiClient from './index';
import type {
  FederatedSearchRequest,
  FederatedSearchResponse,
  SearchSourcesResponse,
} from '@/types/federated-search';

// ═══════════════════════════════════════════
// 联邦搜索
// ═══════════════════════════════════════════

/**
 * 执行联邦搜索
 * 并发查询多个搜索源，聚合去重后返回统一结果
 */
export async function federatedSearch(
  params: FederatedSearchRequest,
): Promise<FederatedSearchResponse> {
  const response = await apiClient.post('/api/search/federated', params) as FederatedSearchResponse;
  return response;
}

// ═══════════════════════════════════════════
// 搜索源管理
// ═══════════════════════════════════════════

/**
 * 获取所有可用的搜索源列表
 * 返回各源的在线状态、权重、权限要求等
 */
export async function getSearchSources(): Promise<SearchSourcesResponse> {
  const response = await apiClient.get('/api/search/sources') as SearchSourcesResponse;
  return response;
}

// ═══════════════════════════════════════════
// 前端降级 Mock（后端不可用时使用）
// ═══════════════════════════════════════════

/**
 * 前端模拟联邦搜索结果（用于后端 API 不可用时的降级展示）
 * 将所有搜索源的结果统一聚合，确保基础搜索可用
 */
export async function mockFederatedSearch(
  params: FederatedSearchRequest,
): Promise<FederatedSearchResponse> {
  const { query, limit = 20 } = params;

  // 模拟各源
  const startTime = Date.now();

  return {
    query,
    results: [],
    rawTotal: 0,
    total: 0,
    tookMs: Date.now() - startTime,
    sourceStats: [],
    categoryCounts: {
      document: 0,
      wiki: 0,
      chat: 0,
      tool: 0,
      file: 0,
      database: 0,
      external: 0,
    },
    truncated: false,
    suggestions: [`尝试精确关键词 "${query}"`, `在文档中搜索 "${query}"`],
  };
}

/**
 * 获取搜索源的降级 mock
 */
export async function mockSearchSources(): Promise<SearchSourcesResponse> {
  return {
    sources: [
      {
        id: 'local-kb',
        name: '本地知识库',
        type: 'local_kb',
        icon: '📚',
        description: '伏羲平台本地文档与知识库',
        enabled: true,
        status: 'online',
        weight: 10,
        timeout: 5000,
        resultLimit: 50,
        tags: ['内部', '文档'],
      },
      {
        id: 'wiki',
        name: 'Wiki 系统',
        type: 'wiki',
        icon: '📝',
        description: '伏羲 Wiki 知识条目',
        enabled: true,
        status: 'online',
        weight: 8,
        timeout: 5000,
        resultLimit: 30,
        tags: ['Wiki', '知识'],
      },
      {
        id: 'chat-history',
        name: '对话历史',
        type: 'chat',
        icon: '💬',
        description: 'AI 对话历史记录搜索',
        enabled: true,
        status: 'online',
        weight: 5,
        timeout: 3000,
        resultLimit: 20,
        tags: ['对话', '历史'],
      },
      {
        id: 'file-index',
        name: '文件索引',
        type: 'file',
        icon: '📁',
        description: '上传文件全文搜索',
        enabled: true,
        status: 'online',
        weight: 6,
        timeout: 5000,
        resultLimit: 30,
        tags: ['文件', '附件'],
      },
    ],
    activeCount: 4,
    offlineCount: 0,
  };
}
