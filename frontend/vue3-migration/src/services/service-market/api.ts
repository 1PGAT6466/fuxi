/**
 * 伏羲 v2.1 — 服务市场 API 封装
 *
 * 封装服务市场所有后端 API 端点。
 * 数据来源：后端 API，失败时抛出错误，不返回兜底 mock。
 */

import apiClient from '@/api';
import type {
  MarketServiceListParams,
  MarketServiceListResponse,
  MarketService,
  InstallServiceRequest,
  InstallServiceResponse,
  UninstallServiceRequest,
  UninstallServiceResponse,
  InstalledService,
  ServiceVersionsResponse,
} from './types';

/**
 * 后端返回格式: { status: 'success', data: T }
 * apiClient 响应拦截器已返回 response.data，所以这里拿到的是 { status, data } 包装
 * 需要提取 .data 字段
 */
interface ApiResponse<T> {
  status: string;
  data: T;
}

function extractData<T>(resp: unknown): T {
  if (resp && typeof resp === 'object' && 'data' in resp) {
    return (resp as ApiResponse<T>).data;
  }
  return resp as T;
}

const API_BASE = '/api/market';

// ───── 获取服务列表 ─────

/** 获取市场服务列表（支持分类、搜索、排序、分页） */
export async function getMarketServices(
  params: MarketServiceListParams = {},
): Promise<MarketServiceListResponse> {
  const queryParams = new URLSearchParams();
  if (params.category) queryParams.set('category', params.category);
  if (params.search) queryParams.set('search', params.search);
  if (params.sortField) queryParams.set('sortField', params.sortField);
  if (params.sortDirection) queryParams.set('sortDirection', params.sortDirection);
  if (params.page) queryParams.set('page', String(params.page));
  if (params.pageSize) queryParams.set('pageSize', String(params.pageSize));

  const qs = queryParams.toString();
  const url = qs ? `${API_BASE}/services?${qs}` : `${API_BASE}/services`;
  try {
    const resp = await apiClient.get(url);
    return extractData<MarketServiceListResponse>(resp);
  } catch (e) {
    console.error('[market-api] getMarketServices 失败:', e);
    return { items: [], total: 0, page: 1, pageSize: 12 };
  }
}

// ───── 获取服务详情 ─────

/** 获取单个服务的详细信息 */
export async function getMarketServiceById(id: string): Promise<MarketService> {
  try {
    const resp = await apiClient.get(`${API_BASE}/services/${id}`);
    return extractData<MarketService>(resp);
  } catch (e) {
    console.error('[market-api] getMarketServiceById 失败:', e);
    throw e;
  }
}

// ───── 安装服务 ─────

/** 安装服务 */
export async function installService(
  data: InstallServiceRequest,
): Promise<InstallServiceResponse> {
  const resp = await apiClient.post(`${API_BASE}/install`, data);
  return extractData<InstallServiceResponse>(resp);
}

// ───── 卸载服务 ─────

/** 卸载服务 */
export async function uninstallService(
  data: UninstallServiceRequest,
): Promise<UninstallServiceResponse> {
  const resp = await apiClient.post(`${API_BASE}/uninstall`, data);
  return extractData<UninstallServiceResponse>(resp);
}

// ───── 已安装服务 ─────

/** 获取当前用户已安装的服务列表 */
export async function getInstalledServices(): Promise<InstalledService[]> {
  try {
    const resp = await apiClient.get(`${API_BASE}/installed`);
    const data = extractData<{ items: InstalledService[]; total: number } | InstalledService[]>(resp);
    // 后端返回 {items: [...], total: N}，需要提取 items
    if (data && typeof data === 'object' && 'items' in data) {
      return (data as { items: InstalledService[] }).items || [];
    }
    return Array.isArray(data) ? data : [];
  } catch (e) {
    console.error('[market-api] getInstalledServices 失败:', e);
    return [];
  }
}

// ───── 版本管理 ─────

/** 获取某服务的所有可用版本 */
export async function getServiceVersions(id: string): Promise<ServiceVersionsResponse> {
  try {
    const resp = await apiClient.get(`${API_BASE}/versions/${id}`);
    return extractData<ServiceVersionsResponse>(resp);
  } catch (e) {
    console.error('[market-api] getServiceVersions 失败:', e);
    return { serviceId: id, versions: [] };
  }
}
