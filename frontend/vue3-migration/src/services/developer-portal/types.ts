/**
 * 伏羲 v2.1 — 开发者门户 类型定义
 */

// ═══════════════════════════════════════════
// API 文档
// ═══════════════════════════════════════════

/** API 文档版本 */
export interface ApiDocVersion {
  version: string;
  title: string;
  description: string;
  publishedAt: string;
  deprecated: boolean;
}

/** API 端点分组 */
export interface ApiEndpointGroup {
  tag: string;
  name: string;
  description: string;
  endpoints: ApiEndpointDef[];
}

/** API 端点定义（文档用） */
export interface ApiEndpointDef {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  summary: string;
  description: string;
  parameters: ApiParameter[];
  requestBody?: ApiRequestBody;
  responses: Record<string, ApiResponseDef>;
  deprecated: boolean;
}

/** API 参数 */
export interface ApiParameter {
  name: string;
  in: 'path' | 'query' | 'header' | 'cookie';
  required: boolean;
  description: string;
  schema: ApiSchema;
  example?: unknown;
}

/** API 请求体 */
export interface ApiRequestBody {
  required: boolean;
  content: Record<string, { schema: ApiSchema }>;
  description: string;
}

/** API 响应 */
export interface ApiResponseDef {
  description: string;
  content?: Record<string, { schema: ApiSchema }>;
}

/** JSON Schema 简化 */
export interface ApiSchema {
  type: string;
  properties?: Record<string, ApiSchema>;
  items?: ApiSchema;
  required?: string[];
  enum?: string[];
  description?: string;
  example?: unknown;
  format?: string;
  nullable?: boolean;
}

/** OpenAPI 完整文档 */
export interface OpenApiDoc {
  openapi: string;
  info: {
    title: string;
    version: string;
    description: string;
    contact?: { name: string; email: string; url: string };
  };
  servers: Array<{ url: string; description: string }>;
  tags: Array<{ name: string; description: string }>;
  paths: Record<string, Record<string, unknown>>;
  components?: {
    schemas?: Record<string, unknown>;
    securitySchemes?: Record<string, unknown>;
  };
}

// ═══════════════════════════════════════════
// SDK
// ═══════════════════════════════════════════

/** SDK 语言 */
export type SdkLanguage = 'python' | 'javascript' | 'java' | 'typescript' | 'go' | 'csharp';

/** SDK 信息 */
export interface SdkInfo {
  id: string;
  language: SdkLanguage;
  name: string;
  version: string;
  description: string;
  releaseDate: string;
  downloadUrl: string;
  npmPackage?: string;
  pipPackage?: string;
  mavenCoordinate?: string;
  repositoryUrl: string;
  documentationUrl: string;
  changelog: string;
  size: string;
  license: string;
  minPlatformVersion: string;
  features: string[];
}

/** SDK 语言标签 */
export const SDK_LANGUAGE_LABELS: Record<SdkLanguage, string> = {
  python: 'Python',
  javascript: 'JavaScript',
  java: 'Java',
  typescript: 'TypeScript',
  go: 'Go',
  csharp: 'C#',
};

/** SDK 语言图标 */
export const SDK_LANGUAGE_ICONS: Record<SdkLanguage, string> = {
  python: '🐍',
  javascript: '🟨',
  java: '☕',
  typescript: '🔷',
  go: '🔵',
  csharp: '🟣',
};

// ═══════════════════════════════════════════
// OAuth 2.0
// ═══════════════════════════════════════════

/** OAuth 授权类型 */
export type OAuthGrantType = 'authorization_code' | 'client_credentials' | 'implicit' | 'password' | 'refresh_token';

/** OAuth 应用 */
export interface OAuthApp {
  id: string;
  name: string;
  description: string;
  clientId: string;
  clientSecret?: string;
  redirectUris: string[];
  grantTypes: OAuthGrantType[];
  scopes: string[];
  homepageUrl: string;
  logoUrl: string;
  createdAt: string;
  updatedAt: string;
  status: 'active' | 'revoked' | 'pending';
}

/** OAuth 注册请求 */
export interface CreateOAuthAppRequest {
  name: string;
  description: string;
  redirectUris: string[];
  grantTypes: OAuthGrantType[];
  scopes: string[];
  homepageUrl: string;
}

/** OAuth 授权类型标签 */
export const OAUTH_GRANT_LABELS: Record<OAuthGrantType, string> = {
  authorization_code: '授权码模式 (Authorization Code)',
  client_credentials: '客户端凭证模式 (Client Credentials)',
  implicit: '隐式模式 (Implicit)',
  password: '密码模式 (Resource Owner Password)',
  refresh_token: '刷新令牌 (Refresh Token)',
};

/** OAuth 可用权限范围 */
export const OAUTH_SCOPES = [
  { value: 'read:documents', label: '读取文档', description: '读取知识库中的文档内容' },
  { value: 'write:documents', label: '写入文档', description: '创建和更新文档' },
  { value: 'read:knowledge', label: '读取知识库', description: '搜索和检索知识库内容' },
  { value: 'write:knowledge', label: '写入知识库', description: '创建和更新知识库条目' },
  { value: 'chat:send', label: '发送对话', description: '发起 AI 对话' },
  { value: 'chat:read', label: '读取对话', description: '查看历史对话记录' },
  { value: 'rag:query', label: 'RAG 查询', description: '使用 RAG 检索引擎进行查询' },
  { value: 'admin:users', label: '用户管理', description: '管理平台用户' },
  { value: 'workflow:execute', label: '执行工作流', description: '触发和执行工作流' },
  { value: 'files:read', label: '读取文件', description: '下载和查看文件' },
  { value: 'files:write', label: '上传文件', description: '上传和管理文件' },
];

// ═══════════════════════════════════════════
// 开发者社区
// ═══════════════════════════════════════════

/** 社区帖子 */
export interface CommunityPost {
  id: string;
  title: string;
  content: string;
  author: { name: string; avatar: string };
  category: CommunityCategory;
  tags: string[];
  likes: number;
  comments: number;
  views: number;
  createdAt: string;
  updatedAt: string;
  pinned: boolean;
}

/** 社区分类 */
export type CommunityCategory = 'announcement' | 'tutorial' | 'discussion' | 'showcase' | 'question' | 'changelog';

/** 社区分类标签 */
export const COMMUNITY_CATEGORY_LABELS: Record<CommunityCategory, string> = {
  announcement: '公告',
  tutorial: '教程',
  discussion: '讨论',
  showcase: '案例展示',
  question: '问答',
  changelog: '更新日志',
};

/** 社区分类图标 */
export const COMMUNITY_CATEGORY_ICONS: Record<CommunityCategory, string> = {
  announcement: 'Notification',
  tutorial: 'Reading',
  discussion: 'ChatDotRound',
  showcase: 'Star',
  question: 'QuestionFilled',
  changelog: 'Tickets',
};

// ═══════════════════════════════════════════
// API 响应
// ═══════════════════════════════════════════

/** API 文档列表响应 */
export interface ApiDocListResponse {
  versions: ApiDocVersion[];
  currentVersion: string;
}

/** SDK 列表响应 */
export interface SdkListResponse {
  sdks: SdkInfo[];
  total: number;
}

/** OAuth 应用列表响应 */
export interface OAuthAppListResponse {
  apps: OAuthApp[];
  total: number;
}

/** 社区帖子列表响应 */
export interface CommunityPostListResponse {
  posts: CommunityPost[];
  total: number;
  page: number;
  pageSize: number;
}
