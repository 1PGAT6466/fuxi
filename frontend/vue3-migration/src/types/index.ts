/**
 * 伏羲体系 - API 类型定义
 * 包含所有 API 请求/响应类型、通用类型和枚举
 */

// ============================
// API 请求类型
// ============================

/** 登录请求 */
export interface LoginRequest {
  username: string;
  password: string;
}

/** 聊天消息请求 */
export interface ChatRequest {
  query: string;
}

/** 文件上传请求 - 使用 FormData，此处仅作文档 */
export interface UploadRequest {
  file: File;
}

// ============================
// API 响应类型
// ============================

/** 通用 API 响应格式（v2 统一格式）
 * 后端 response.py 定义:
 *   成功: {"status": "success", "message": "ok", "data": {...}}
 *   错误: {"status": "error", "message": "错误描述", "detail": "..."}
 *   分页: {"status": "success", "message": "ok", "data": {"items": [...], "total": N, ...}}
 *
 * 注意: 后端默认使用 v1 兼容模式（直接返回 data 字段内容），
 *       需要请求头 X-API-Format: v2 或查询参数 ?format=v2 才返回此格式。
 *       前端 api/index.ts 的响应拦截器已自动解包 axios 的 response.data，
 *       因此此处的 T 应匹配后端 data 字段的结构。
 */
export interface ApiResponse<T = unknown> {
  /** 状态: "success" | "error" */
  status: 'success' | 'error';
  /** 提示信息 */
  message: string;
  /** 业务数据（成功时存在） */
  data?: T;
  /** 错误详情（失败时存在） */
  detail?: string;
  /** HTTP 状态码（失败时存在） */
  status_code?: number;
}

/** 登录响应 */
export interface LoginResponse {
  token: string;
  user: UserInfo;
}

/** 聊天响应 */
export interface ChatResponse {
  answer: string;
  sources?: string[];
  confidence?: number;
}

/** 文件列表响应 */
export interface FileListResponse {
  files: FileInfo[];
  total?: number;
}

/** 文件上传响应 */
export interface UploadResponse {
  fileId: string;
  filename: string;
  size: number;
  url?: string;
}

/** 知识搜索响应 */
export interface SearchResponse {
  results: SearchResult[];
  total: number;
}

/** 搜索结果项 */
export interface SearchResult {
  id: string;
  title: string;
  content: string;
  score: number;
  source: string;
  url?: string;
  // === SAG Event 粒度新增字段 ===
  /** 关联的 Event 列表 */
  events?: EventReference[];
  /** 当前选中的 Event */
  selected_event?: EventReference | null;
  /** 检索粒度 */
  granularity?: 'chunk' | 'event' | 'auto';
  /** 来源文档名（RagTestView 使用） */
  source_doc?: string;
  /** 分块 ID（兼容字段） */
  chunk_id?: string;
  /** Token 数（兼容字段） */
  token_count?: number;
}

/** Wiki 页面响应 */
export interface WikiPageResponse {
  id: string;
  title: string;
  content: string;
  updatedAt: string;
  author?: string;
}

// ============================
// 业务实体类型
// ============================

/** 用户信息 */
export interface UserInfo {
  id: number | string;
  username: string;
  display_name?: string;
  role: 'admin' | 'user';
  avatar?: string;
  email?: string;
}

/** 文件信息 */
export interface FileInfo {
  id: string;
  filename: string;
  size: number;
  uploadedAt: string;
  type?: string;
  hash?: string;
  status?: 'uploaded' | 'processing' | 'ready' | 'error';
  url?: string;
}

/** 聊天消息 */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  sources?: string[];
  confidence?: number;
  /** 引用来源详情 */
  references?: ChatReference[];
}

/** 引用来源 */
export interface ChatReference {
  id: string;
  title: string;
  url?: string;
  snippet?: string;
  /** 来源类型：文档/网页/知识库 */
  type: 'document' | 'web' | 'knowledge';
  // === SAG Event 粒度新增字段 ===
  /** 关联的 Event 列表（SAG Event 粒度检索输出） */
  events?: EventReference[];
}

// ============================
// SAG 检索增强类型
// ============================

/** SAG Event 引用 — 从 chunk 中抽取的原子语义事件 */
export interface EventReference {
  /** SAG 事件唯一标识 */
  event_id: string;
  /** 所属 chunk（向后兼容） */
  chunk_id: string;
  /** Event 的完整语义描述 */
  content: string;
  /** 关联实体列表 */
  entities?: EntityTag[];
  /** 检索相关度分数 */
  score: number;
  /** 检索来源路径 */
  retrieval_path?: RetrievalPath;
  /** 原文中的精确 span 位置 */
  text_span?: TextSpan;
}

/** 实体标签 */
export interface EntityTag {
  /** 实体名称 */
  name: string;
  /** 实体类型 */
  type: string;
  /** 显示颜色（十六进制或 CSS 颜色名） */
  color: string;
}

/** 原文精确 span 位置 */
export interface TextSpan {
  /** 文档标识 */
  doc_id: string;
  /** 文档名称 */
  doc_name: string;
  /** 原文起始偏移 */
  start_offset: number;
  /** 原文结束偏移 */
  end_offset: number;
  /** span 上下文预览（前后各 50 字） */
  snippet: string;
}

/** 检索来源路径信息 */
export interface RetrievalPath {
  /** 来源类型 */
  source: 'entity_guided' | 'vector_direct' | 'query_time_expansion';
  /** SAG 阶段 */
  stage: 1 | 2 | 3;
  /** 多跳扩展跳数 */
  hop_count?: number;
  /** 触发实体名 */
  trigger_entity?: string;
  /** 实体向量相似度 */
  entity_similarity?: number;
}

/** 会话 */
export interface ChatSession {
  id: string;
  title: string;
  lastMessage?: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

/** 会话列表响应 */
export interface ChatSessionListResponse {
  sessions: ChatSession[];
  total: number;
}

/** 创建会话请求 */
export interface CreateSessionRequest {
  title?: string;
}

/** 发送消息请求（SSE） */
export interface ChatSendRequest {
  sessionId: string;
  query: string;
}

/** SSE 流式消息块 */
export interface ChatStreamChunk {
  type: 'content' | 'references' | 'done' | 'error' | 'sag_trace';
  content?: string;
  references?: ChatReference[];
  error?: string;
  /** SAG 检索追踪数据 */
  sag_trace?: SAGRetrievalTrace;
}

// ============================
// SAG 检索追踪类型
// ============================

/** SAG 检索追踪 — 三阶段流水线可视化数据 */
export interface SAGRetrievalTrace {
  /** 种子实体 */
  seed_entities: { name: string; type: string; score?: number }[];
  /** 种子事件 */
  seed_events: EventReference[];
  /** 扩展实体 */
  expanded_entities: { name: string; type: string; similarity: number; hop: number }[];
  /** 扩展事件 */
  expanded_events: EventReference[];
  /** Rerank 后的事件 */
  reranked_events: EventReference[];
  /** 实体超图信息 */
  entity_hypergraph: EntityHypergraph;
  /** 总候选数 */
  total_candidates?: number;
  /** 最终输出数 */
  final_output_count?: number;
  /** 耗时 ms */
  latency_ms?: number;
}

/** 实体超图数据结构 */
export interface EntityHypergraph {
  /** 节点 */
  nodes: HypergraphNode[];
  /** 边（超边） */
  edges: HypergraphEdge[];
}

/** 超图节点 */
export interface HypergraphNode {
  id: string;
  name: string;
  type: 'entity' | 'event';
  entity_type?: string;
  seed?: boolean;
  hop?: number;
}

/** 超图边 */
export interface HypergraphEdge {
  source: string;
  target: string;
  type: 'sql_join' | 'vector_match' | 'rerank';
  weight?: number;
}

// ============================
// 路由类型
// ============================
// 路由元信息类型扩展已迁移至 types/router.d.ts
