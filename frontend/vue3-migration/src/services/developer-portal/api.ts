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

// ═══════════════════════════════════════════
// API 文档
// ═══════════════════════════════════════════

/** 获取 API 文档版本列表 */
export async function getApiDocVersions(): Promise<ApiDocListResponse> {
  return apiClient.get(`${API_BASE}/docs`) as Promise<ApiDocListResponse>;
}

/** 获取指定版本的 OpenAPI 文档 */
export async function getApiDoc(version?: string): Promise<OpenApiDoc> {
  const path = version ? `${API_BASE}/docs/${version}` : `${API_BASE}/docs`;
  return apiClient.get(path) as Promise<OpenApiDoc>;
}

// ═══════════════════════════════════════════
// SDK 下载
// ═══════════════════════════════════════════

/** 获取 SDK 列表 */
export async function getSdkList(): Promise<SdkListResponse> {
  return apiClient.get(`${API_BASE}/sdk`) as Promise<SdkListResponse>;
}

/** 获取指定语言 SDK 详情 */
export async function getSdkDetail(language: string): Promise<SdkInfo> {
  return apiClient.get(`${API_BASE}/sdk/${language}`) as Promise<SdkInfo>;
}

// ═══════════════════════════════════════════
// OAuth 2.0 应用管理
// ═══════════════════════════════════════════

/** 注册 OAuth 应用 */
export async function registerOAuthApp(data: CreateOAuthAppRequest): Promise<OAuthApp> {
  return apiClient.post(`${API_BASE}/oauth/register-app`, data) as Promise<OAuthApp>;
}

/** 获取已注册的 OAuth 应用列表 */
export async function getOAuthApps(): Promise<OAuthAppListResponse> {
  return apiClient.get(`${API_BASE}/oauth/apps`) as Promise<OAuthAppListResponse>;
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
  return apiClient.get(`${API_BASE}/community/posts`, {
    params: { page, pageSize, category },
  }) as Promise<CommunityPostListResponse>;
}
