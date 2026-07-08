/**
 * 伏羲 v2.1 — Feature Flags API
 * 路径对齐：后端 /api/feature-flags 统一返回 {flags, defaults}
 */

import apiClient from './index';

export interface FeatureFlagsResponse {
  flags: Record<string, boolean>;
  defaults: Record<string, boolean>;
}

/** 获取所有 Feature Flag 状态 */
export function getFeatureFlags(): Promise<FeatureFlagsResponse> {
  return apiClient.get('/api/feature-flags') as Promise<FeatureFlagsResponse>;
}

/** 更新 Feature Flag。后端接收 {value: boolean}，本函数兼容传入 enabled */
export function updateFeatureFlag(key: string, value: boolean) {
  // 后端 PUT /api/feature-flags/{name} 期望 {value: true/false}
  return apiClient.put(`/api/feature-flags/${key}`, { value });
}
