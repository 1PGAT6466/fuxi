/**
 * 伏羲 v2.1 — 工作流引擎类型定义
 *
 * 定义工作流引擎核心类型：节点、连接、工作流、执行记录、版本管理
 */

// ============================
// 节点类型枚举
// ============================

/** 工作流节点类型 */
export type WorkflowNodeType = 'trigger' | 'condition' | 'action' | 'loop';

/** 触发器子类型 */
export type TriggerSubType = 'manual' | 'webhook' | 'schedule' | 'event';

/** 条件运算符 */
export type ConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'contains'
  | 'not_contains'
  | 'greater_than'
  | 'less_than'
  | 'regex'
  | 'exists'
  | 'not_exists';

/** 动作子类型 */
export type ActionSubType = 'api_call' | 'notification' | 'transform' | 'script' | 'delay';

/** 循环子类型 */
export type LoopSubType = 'for_each' | 'while' | 'repeat';

// ============================
// 节点配置
// ============================

/** 触发器节点配置 */
export interface TriggerConfig {
  subType: TriggerSubType;
  /** webhook URL（仅 webhook 类型） */
  webhookUrl?: string;
  /** Cron 表达式（仅 schedule 类型） */
  cronExpression?: string;
  /** 事件名称（仅 event 类型） */
  eventName?: string;
  /** 输入 Schema */
  inputSchema?: Record<string, unknown>;
}

/** 条件节点配置 */
export interface ConditionConfig {
  /** 条件路径列表 */
  branches: ConditionBranch[];
  /** 默认路径名称 */
  defaultBranch?: string;
}

/** 单一条件分支 */
export interface ConditionBranch {
  name: string;
  conditions: ConditionRule[];
  /** 逻辑组合方式 */
  logic: 'and' | 'or';
}

/** 单一条件规则 */
export interface ConditionRule {
  field: string;
  operator: ConditionOperator;
  value: unknown;
}

/** 动作节点配置 */
export interface ActionConfig {
  subType: ActionSubType;
  /** API URL（仅 api_call 类型） */
  apiUrl?: string;
  /** HTTP 方法（仅 api_call 类型） */
  apiMethod?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  /** 请求体模板（仅 api_call 类型） */
  apiBody?: string;
  /** 通知消息（仅 notification 类型） */
  notificationMessage?: string;
  /** 数据转换脚本（仅 transform 类型） */
  transformScript?: string;
  /** 自定义脚本（仅 script 类型） */
  script?: string;
  /** 延迟毫秒（仅 delay 类型） */
  delayMs?: number;
}

/** 循环节点配置 */
export interface LoopConfig {
  subType: LoopSubType;
  /** 循环变量名（仅 for_each 类型） */
  iteratorVar?: string;
  /** 数据源引用（仅 for_each 类型） */
  collectionRef?: string;
  /** 条件表达式（仅 while 类型） */
  conditionExpression?: string;
  /** 重复次数（仅 repeat 类型） */
  repeatCount?: number;
  /** 最大迭代次数限制 */
  maxIterations?: number;
}

/** 节点配置联合类型 */
export type NodeConfig = TriggerConfig | ConditionConfig | ActionConfig | LoopConfig;

// ============================
// 节点与连接
// ============================

/** 画布位置 */
export interface Position {
  x: number;
  y: number;
}

/** 工作流节点 */
export interface WorkflowNode {
  /** 节点唯一 ID */
  id: string;
  /** 节点显示名称 */
  label: string;
  /** 节点类型 */
  type: WorkflowNodeType;
  /** 节点配置 */
  config: NodeConfig;
  /** 画布位置 */
  position: Position;
  /** 节点描述 */
  description?: string;
  /** 是否启用 */
  enabled: boolean;
}

/** 节点连接线 */
export interface WorkflowConnection {
  /** 连接线 ID */
  id: string;
  /** 源节点 ID */
  sourceNodeId: string;
  /** 源端口名称 */
  sourcePort: string;
  /** 目标节点 ID */
  targetNodeId: string;
  /** 目标端口名称 */
  targetPort: string;
  /** 连接标签 */
  label?: string;
}

// ============================
// 工作流定义
// ============================

/** 工作流状态 */
export type WorkflowStatus = 'draft' | 'active' | 'paused' | 'archived';

/** 工作流定义 */
export interface Workflow {
  /** 工作流 ID */
  id: string;
  /** 工作流名称 */
  name: string;
  /** 工作流描述 */
  description: string;
  /** 当前版本号 */
  version: number;
  /** 工作流状态 */
  status: WorkflowStatus;
  /** 节点列表 */
  nodes: WorkflowNode[];
  /** 连接线列表 */
  connections: WorkflowConnection[];
  /** 变量定义 */
  variables?: WorkflowVariable[];
  /** 创建时间 */
  createdAt: string;
  /** 更新时间 */
  updatedAt: string;
  /** 创建者 */
  createdBy?: string;
  /** 标签 */
  tags?: string[];
}

/** 工作流变量 */
export interface WorkflowVariable {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  defaultValue?: unknown;
  required?: boolean;
  description?: string;
}

// ============================
// 工作流版本
// ============================

/** 工作流快照版本 */
export interface WorkflowVersion {
  /** 版本 ID */
  id: string;
  /** 关联工作流 ID */
  workflowId: string;
  /** 版本号 */
  version: number;
  /** 工作流完整快照 */
  snapshot: Omit<Workflow, 'version' | 'id'>;
  /** 变更描述 */
  changelog: string;
  /** 创建时间 */
  createdAt: string;
  /** 创建者 */
  createdBy?: string;
}

// ============================
// 执行记录
// ============================

/** 执行状态 */
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

/** 节点执行状态 */
export interface NodeExecutionResult {
  /** 节点 ID */
  nodeId: string;
  /** 节点标签 */
  nodeLabel: string;
  /** 执行状态 */
  status: ExecutionStatus;
  /** 输入数据 */
  input?: unknown;
  /** 输出数据 */
  output?: unknown;
  /** 错误信息 */
  error?: string;
  /** 开始时间 */
  startedAt: string;
  /** 结束时间 */
  endedAt?: string;
  /** 耗时（毫秒） */
  durationMs?: number;
}

/** 工作流执行记录 */
export interface WorkflowExecution {
  /** 执行 ID */
  id: string;
  /** 关联工作流 ID */
  workflowId: string;
  /** 工作流版本号 */
  workflowVersion: number;
  /** 执行状态 */
  status: ExecutionStatus;
  /** 触发方式 */
  triggerType: TriggerSubType;
  /** 输入数据 */
  input?: unknown;
  /** 输出数据 */
  output?: unknown;
  /** 各节点执行结果 */
  nodeResults: NodeExecutionResult[];
  /** 执行上下文（变量值） */
  context?: Record<string, unknown>;
  /** 开始时间 */
  startedAt: string;
  /** 结束时间 */
  endedAt?: string;
  /** 总耗时（毫秒） */
  durationMs?: number;
  /** 错误信息 */
  error?: string;
}

// ============================
// API 请求/响应类型
// ============================

/** 创建工作流请求 */
export interface CreateWorkflowRequest {
  name: string;
  description?: string;
  nodes?: WorkflowNode[];
  connections?: WorkflowConnection[];
  variables?: WorkflowVariable[];
  tags?: string[];
}

/** 更新工作流请求 */
export interface UpdateWorkflowRequest {
  name?: string;
  description?: string;
  nodes?: WorkflowNode[];
  connections?: WorkflowConnection[];
  variables?: WorkflowVariable[];
  status?: WorkflowStatus;
  tags?: string[];
}

/** 执行工作流请求 */
export interface ExecuteWorkflowRequest {
  input?: Record<string, unknown>;
  /** 异步执行（不等待完成） */
  async?: boolean;
}

/** 工作流列表响应 */
export interface WorkflowListResponse {
  workflows: Workflow[];
  total: number;
}

/** 执行历史响应 */
export interface ExecutionHistoryResponse {
  executions: WorkflowExecution[];
  total: number;
}

/** 版本列表响应 */
export interface VersionListResponse {
  versions: WorkflowVersion[];
  total: number;
}

// ============================
// 编辑器拖拽类型
// ============================

/** 节点模板（拖拽源） */
export interface NodeTemplate {
  type: WorkflowNodeType;
  label: string;
  icon: string;
  category: string;
  defaultConfig: NodeConfig;
}

/** 拖拽状态 */
export interface DragState {
  isDragging: boolean;
  template: NodeTemplate | null;
  dropPosition: Position | null;
}

/** 选中状态 */
export interface SelectionState {
  selectedNodeId: string | null;
  selectedConnectionId: string | null;
}
