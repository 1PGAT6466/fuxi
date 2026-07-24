/**
 * 伏羲 v2.1 — API Key 管理 类型定义
 */

// ═══════════════════════════════════════════
// 权限范围枚举
// ═══════════════════════════════════════════

/** 权限范围 */
export type ApiKeyPermission =
  | 'read:documents'
  | 'write:documents'
  | 'read:chat'
  | 'write:chat'
  | 'read:knowledge'
  | 'write:knowledge'
  | 'read:analytics'
  | 'read:users'
  | 'write:users'
  | 'admin';

/** 权限范围标签映射 */
export const API_KEY_PERMISSION_LABELS: Record<ApiKeyPermission, string> = {
  'read:documents': '读取文档',
  'write:documents': '写入文档',
  'read:chat': '读取对话',
  'write:chat': '发起对话',
  'read:knowledge': '读取知识库',
  'write:knowledge': '写入知识库',
  'read:analytics': '读取分析',
  'read:users': '读取用户',
  'write:users': '管理用户',
  'admin': '管理员',
};

/** 权限范围分组 */
export interface PermissionGroup {
  label: string;
  permissions: ApiKeyPermission[];
}

/** 权限范围分组定义 */
export const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    label: '文档',
    permissions: ['read:documents', 'write:documents'],
  },
  {
    label: '对话',
    permissions: ['read:chat', 'write:chat'],
  },
  {
    label: '知识库',
    permissions: ['read:knowledge', 'write:knowledge'],
  },
  {
    label: '分析',
    permissions: ['read:analytics'],
  },
  {
    label: '用户管理',
    permissions: ['read:users', 'write:users'],
  },
  {
    label: '系统管理',
    permissions: ['admin'],
  },
];

// ═══════════════════════════════════════════
// API Key 状态
// ═══════════════════════════════════════════

/** API Key 状态 */
export type ApiKeyStatus = 'active' | 'expired' | 'revoked';

/** 状态标签映射 */
export const API_KEY_STATUS_LABELS: Record<ApiKeyStatus, string> = {
  active: '使用中',
  expired: '已过期',
  revoked: '已撤销',
};

/** 状态颜色映射 */
export const API_KEY_STATUS_COLORS: Record<ApiKeyStatus, string> = {
  active: '#34C759',
  expired: '#FF9500',
  revoked: '#FF3B30',
};

// ═══════════════════════════════════════════
// API Key 实体
// ═══════════════════════════════════════════

/** API Key 实体 */
export interface ApiKey {
  /** 唯一 ID */
  id: string;
  /** Key 名称（便于识别） */
  name: string;
  /** 完整 API Key（仅创建时返回一次） */
  key?: string;
  /** Key 前缀（用于列表展示，如 fuxi_sk_***） */
  keyPrefix: string;
  /** 权限范围列表 */
  permissions: ApiKeyPermission[];
  /** 状态 */
  status: ApiKeyStatus;
  /** 创建者 ID */
  createdBy: string;
  /** 过期时间（ISO 字符串），null 表示永不过期 */
  expiresAt: string | null;
  /** 最后使用时间（ISO 字符串） */
  lastUsedAt: string | null;
  /** 创建时间（ISO 字符串） */
  createdAt: string;
  /** 更新时间（ISO 字符串） */
  updatedAt: string;
  /** 总请求次数 */
  totalRequests: number;
  /** 描述 */
  description?: string;
}

// ═══════════════════════════════════════════
// API 请求/响应
// ═══════════════════════════════════════════

/** 创建 API Key 请求 */
export interface CreateApiKeyRequest {
  name: string;
  permissions: ApiKeyPermission[];
  expiresAt?: string | null;
  description?: string;
}

/** 更新 API Key 请求 */
export interface UpdateApiKeyRequest {
  name?: string;
  permissions?: ApiKeyPermission[];
  status?: ApiKeyStatus;
  expiresAt?: string | null;
  description?: string;
}

/** API Key 列表响应 */
export interface ApiKeyListResponse {
  keys: ApiKey[];
  total: number;
}

/** 使用量数据点 */
export interface UsageDataPoint {
  date: string;
  requests: number;
  tokens: number;
}

/** 使用量统计响应 */
export interface ApiKeyUsageResponse {
  keyId: string;
  keyName: string;
  period: UsagePeriod;
  totalRequests: number;
  totalTokens: number;
  dailyUsage: UsageDataPoint[];
}

/** 使用量统计周期 */
export type UsagePeriod = 'day' | 'week' | 'month';

/** 操作结果 */
export interface ApiKeyActionResult {
  success: boolean;
  key?: ApiKey;
  message?: string;
}
