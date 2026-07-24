/**
 * 伏羲 v2.1 — API Key 管理服务入口
 *
 * 统一导出所有公开接口
 */

// 类型
export type {
  ApiKey,
  ApiKeyPermission,
  ApiKeyStatus,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  ApiKeyListResponse,
  UsageDataPoint,
  ApiKeyUsageResponse,
  UsagePeriod,
  ApiKeyActionResult,
  PermissionGroup,
} from './types';

export {
  API_KEY_PERMISSION_LABELS,
  PERMISSION_GROUPS,
  API_KEY_STATUS_LABELS,
  API_KEY_STATUS_COLORS,
} from './types';

// API
export {
  getApiKeys,
  getApiKey,
  createApiKey,
  updateApiKey,
  deleteApiKey,
  getApiKeyUsage,
} from './api';

// Pinia Store
export { useApiKeysStore } from './store';

// 组件
export { default as ApiKeyManager } from './ApiKeyManager.vue';
