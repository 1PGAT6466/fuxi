/**
 * 伏羲 v2.1 — 开发者门户 API 封装
 *
 * 封装端点：
 * - GET  /api/developer/docs            — 获取 API 文档版本列表
 * - GET  /api/developer/docs/:version    — 获取指定版本 OpenAPI 文档
 * - GET  /api/developer/sdk              — 获取 SDK 列表
 * - GET  /api/developer/sdk/:language    — 获取指定语言 SDK 详情
 * - POST /api/developer/oauth/register-app — 注册 OAuth2.0 应用
 * - GET  /api/developer/oauth/apps       — 获取已注册 OAuth2.0 应用列表
 * - GET  /api/developer/community/posts  — 获取开发者社区帖子
 */

import apiClient from '@/api';
import type {
  ApiDocListResponse,
  OpenApiDoc,
  SdkListResponse,
  SdkInfo,
  OAuthApp,
  OAuthAppListResponse,
  CreateOAuthAppRequest,
  CommunityPostListResponse,
} from './types';

const API_BASE = '/api/developer';

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

// ═══════════════════════════════════════════
// API 文档
// ═══════════════════════════════════════════

/** 获取 API 文档版本列表 */
export async function getApiDocVersions(): Promise<ApiDocListResponse> {
  try {
    const resp = await apiClient.get(`${API_BASE}/docs`);
    return extractData<ApiDocListResponse>(resp);
  } catch (e) {
    console.error('[developer-api] getApiDocVersions 失败:', e);
    return { versions: [], currentVersion: '' };
  }
}

/** 获取指定版本的 OpenAPI 文档 */
export async function getApiDoc(version?: string): Promise<OpenApiDoc> {
  const path = version ? `${API_BASE}/docs/${version}` : `${API_BASE}/docs`;
  const resp = await apiClient.get(path);
  return extractData<OpenApiDoc>(resp);
}

// ═══════════════════════════════════════════
// SDK 下载
// ═══════════════════════════════════════════

/** 获取 SDK 列表 */
export async function getSdkList(): Promise<SdkListResponse> {
  try {
    const resp = await apiClient.get(`${API_BASE}/sdk`);
    return extractData<SdkListResponse>(resp);
  } catch (e) {
    console.error('[developer-api] getSdkList 失败:', e);
    return { sdks: [], total: 0 };
  }
}

/** 获取指定语言 SDK 详情 */
export async function getSdkDetail(language: string): Promise<SdkInfo> {
  const resp = await apiClient.get(`${API_BASE}/sdk/${language}`);
  return extractData<SdkInfo>(resp);
}

// ═══════════════════════════════════════════
// OAuth 2.0 应用管理
// ═══════════════════════════════════════════

/** 注册 OAuth 应用 */
export async function registerOAuthApp(data: CreateOAuthAppRequest): Promise<OAuthApp> {
  const resp = await apiClient.post(`${API_BASE}/oauth/register-app`, data);
  return extractData<OAuthApp>(resp);
}

/** 获取已注册的 OAuth 应用列表 */
export async function getOAuthApps(): Promise<OAuthAppListResponse> {
  try {
    const resp = await apiClient.get(`${API_BASE}/oauth/apps`);
    return extractData<OAuthAppListResponse>(resp);
  } catch (e) {
    console.error('[developer-api] getOAuthApps 失败:', e);
    return { apps: [], total: 0 };
  }
}

// ═══════════════════════════════════════════
// 开发者社区
// ═══════════════════════════════════════════

/** 获取社区帖子列表 */
export async function getCommunityPosts(
  page?: number,
  pageSize?: number,
  category?: string,
): Promise<CommunityPostListResponse> {
  try {
    const resp = await apiClient.get(`${API_BASE}/community/posts`, {
      params: { page, pageSize, category },
    });
    return extractData<CommunityPostListResponse>(resp);
  } catch (e) {
    console.error('[developer-api] getCommunityPosts 失败:', e);
    return { posts: [], total: 0, page: 1, pageSize: 10 };
  }
}
