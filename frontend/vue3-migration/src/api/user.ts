/**
 * 伏羲 v2.1 — 用户偏好 API
 * 对接方案规划的后端 /api/user/preferences（当前后端为占位实现）
 *
 * 方案要求：用户偏好 CRUD，支持主题、语言、通知设置
 * 当前状态：后端尚未实现完整用户偏好 API，前端 API 层预备对接
 */

import apiClient from './index';

export interface UserPreferences {
  theme?: 'light' | 'dark' | 'system';
  language?: string;
  notifications_enabled?: boolean;
  sidebar_collapsed?: boolean;
  default_engine?: 'v1' | 'v2';
  [key: string]: unknown;
}

export interface PreferencesResponse {
  data: {
    preferences: UserPreferences;
  };
}

/** 获取用户偏好 */
export async function fetchPreferences(): Promise<PreferencesResponse> {
  return apiClient.get('/api/user/preferences') as Promise<PreferencesResponse>;
}

/** 更新用户偏好 */
export async function updatePreferences(prefs: Partial<UserPreferences>): Promise<PreferencesResponse> {
  return apiClient.put('/api/user/preferences', prefs) as Promise<PreferencesResponse>;
}
