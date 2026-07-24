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
  return (await apiClient.get(url)) as MarketServiceListResponse;
}

// ───── 获取服务详情 ─────

/** 获取单个服务的详细信息 */
export async function getMarketServiceById(id: string): Promise<MarketService> {
  return (await apiClient.get(`${API_BASE}/services/${id}`)) as MarketService;
}

// ───── 安装服务 ─────

/** 安装服务 */
export async function installService(
  data: InstallServiceRequest,
): Promise<InstallServiceResponse> {
  return (await apiClient.post(`${API_BASE}/install`, data)) as InstallServiceResponse;
}

// ───── 卸载服务 ─────

/** 卸载服务 */
export async function uninstallService(
  data: UninstallServiceRequest,
): Promise<UninstallServiceResponse> {
  return (await apiClient.post(`${API_BASE}/uninstall`, data)) as UninstallServiceResponse;
}

// ───── 已安装服务 ─────

/** 获取当前用户已安装的服务列表 */
export async function getInstalledServices(): Promise<InstalledService[]> {
  return (await apiClient.get(`${API_BASE}/installed`)) as InstalledService[];
}

// ───── 版本管理 ─────

/** 获取某服务的所有可用版本 */
export async function getServiceVersions(id: string): Promise<ServiceVersionsResponse> {
  return (await apiClient.get(`${API_BASE}/versions/${id}`)) as ServiceVersionsResponse;
}
