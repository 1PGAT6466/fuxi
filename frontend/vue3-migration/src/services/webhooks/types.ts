/**
 * 伏羲 v2.1 — Webhook 配置管理 类型定义
 */

// ═══════════════════════════════════════════
// 事件类型枚举
// ═══════════════════════════════════════════

/** Webhook 事件类型 */
export type WebhookEventType =
  | 'document.uploaded'
  | 'document.processed'
  | 'document.deleted'
  | 'conversation.created'
  | 'conversation.completed'
  | 'conversation.message_received'
  | 'knowledge.updated'
  | 'knowledge.indexed'
  | 'knowledge.deleted'
  | 'user.registered'
  | 'user.login'
  | 'rag.query_executed'
  | 'evaluation.completed'
  | 'workflow.executed';

/** 事件类型分组 */
export interface WebhookEventGroup {
  label: string;
  icon: string;
  events: WebhookEventType[];
}

/** Webhook 事件分组定义 */
export const WEBHOOK_EVENT_GROUPS: WebhookEventGroup[] = [
  {
    label: '文档事件',
    icon: 'Document',
    events: ['document.uploaded', 'document.processed', 'document.deleted'],
  },
  {
    label: '对话事件',
    icon: 'ChatDotRound',
    events: ['conversation.created', 'conversation.completed', 'conversation.message_received'],
  },
  {
    label: '知识库事件',
    icon: 'Collection',
    events: ['knowledge.updated', 'knowledge.indexed', 'knowledge.deleted'],
  },
  {
    label: '用户事件',
    icon: 'User',
    events: ['user.registered', 'user.login'],
  },
  {
    label: '系统事件',
    icon: 'Monitor',
    events: ['rag.query_executed', 'evaluation.completed', 'workflow.executed'],
  },
];

/** 事件类型标签映射 */
export const WEBHOOK_EVENT_LABELS: Record<WebhookEventType, string> = {
  'document.uploaded': '文档上传',
  'document.processed': '文档处理完成',
  'document.deleted': '文档删除',
  'conversation.created': '对话创建',
  'conversation.completed': '对话完成',
  'conversation.message_received': '消息接收',
  'knowledge.updated': '知识库更新',
  'knowledge.indexed': '知识库索引完成',
  'knowledge.deleted': '知识库删除',
  'user.registered': '用户注册',
  'user.login': '用户登录',
  'rag.query_executed': 'RAG 查询执行',
  'evaluation.completed': '评测完成',
  'workflow.executed': '工作流执行',
};

// ═══════════════════════════════════════════
// Webhook 状态
// ═══════════════════════════════════════════

/** Webhook 状态 */
export type WebhookStatus = 'active' | 'paused' | 'failed';

/** 状态标签映射 */
export const WEBHOOK_STATUS_LABELS: Record<WebhookStatus, string> = {
  active: '启用',
  paused: '暂停',
  failed: '失败',
};

/** 状态 Tag 类型 */
export const WEBHOOK_STATUS_TAG_TYPES: Record<WebhookStatus, string> = {
  active: 'success',
  paused: 'warning',
  failed: 'danger',
};

// ═══════════════════════════════════════════
// Webhook 实体
// ═══════════════════════════════════════════

/** Webhook 实体 */
export interface Webhook {
  /** 唯一 ID */
  id: string;
  /** Webhook 名称 */
  name: string;
  /** 回调 URL */
  url: string;
  /** 订阅的事件列表 */
  events: WebhookEventType[];
  /** 状态 */
  status: WebhookStatus;
  /** 密钥（用于签名验证，仅在创建时返回一次） */
  secret?: string;
  /** 是否启用签名验证 */
  signatureEnabled: boolean;
  /** 签名算法 */
  signatureAlgorithm: string;
  /** 重试配置 */
  retryConfig: WebhookRetryConfig;
  /** 最后一次发送时间（ISO 字符串） */
  lastSentAt: string | null;
  /** 最后一次发送状态 */
  lastSentStatus: 'success' | 'failed' | null;
  /** 总发送次数 */
  totalSent: number;
  /** 总失败次数 */
  totalFailed: number;
  /** 创建时间（ISO 字符串） */
  createdAt: string;
  /** 更新时间（ISO 字符串） */
  updatedAt: string;
  /** 描述 */
  description?: string;
}

/** 重试配置 */
export interface WebhookRetryConfig {
  /** 最大重试次数 */
  maxRetries: number;
  /** 重试间隔（毫秒） */
  retryDelayMs: number;
  /** 是否启用指数退避 */
  exponentialBackoff: boolean;
}

/** 默认重试配置 */
export const DEFAULT_RETRY_CONFIG: WebhookRetryConfig = {
  maxRetries: 3,
  retryDelayMs: 1000,
  exponentialBackoff: true,
};

// ═══════════════════════════════════════════
// API 请求/响应
// ═══════════════════════════════════════════

/** 创建 Webhook 请求 */
export interface CreateWebhookRequest {
  name: string;
  url: string;
  events: WebhookEventType[];
  signatureEnabled?: boolean;
  signatureAlgorithm?: string;
  retryConfig?: WebhookRetryConfig;
  description?: string;
}

/** 更新 Webhook 请求 */
export interface UpdateWebhookRequest {
  name?: string;
  url?: string;
  events?: WebhookEventType[];
  status?: WebhookStatus;
  signatureEnabled?: boolean;
  retryConfig?: WebhookRetryConfig;
  description?: string;
}

/** Webhook 列表响应 */
export interface WebhookListResponse {
  webhooks: Webhook[];
  total: number;
}

/** 测试发送请求 */
export interface TestWebhookRequest {
  /** 测试事件类型 */
  eventType?: WebhookEventType;
  /** 自定义测试 payload */
  customPayload?: Record<string, unknown>;
}

/** 测试发送响应 */
export interface TestWebhookResponse {
  success: boolean;
  statusCode: number;
  responseBody: string;
  responseTimeMs: number;
  error?: string;
}

/** 操作结果 */
export interface WebhookActionResult {
  success: boolean;
  webhook?: Webhook;
  message?: string;
}

/** 最近投递记录 */
export interface WebhookDelivery {
  id: string;
  webhookId: string;
  eventType: WebhookEventType;
  status: 'pending' | 'success' | 'failed';
  statusCode: number;
  responseTimeMs: number;
  attempt: number;
  error?: string;
  sentAt: string;
}

/** 投递列表响应 */
export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[];
  total: number;
}
