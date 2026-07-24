/**
 * 伏羲 v2.1 — 工作流执行引擎
 *
 * 提供客户端侧的工作流模拟执行逻辑：
 * - DAG 拓扑排序（确保按正确顺序执行）
 * - 节点执行模拟（触发器→条件→动作→循环）
 * - 条件分支评估
 * - 循环迭代控制
 * - 执行上下文管理（变量传递）
 */

import type {
  Workflow,
  WorkflowNode,
  WorkflowConnection,
  WorkflowExecution,
  NodeExecutionResult,
  ExecutionStatus,
  ConditionConfig,
  ConditionBranch,
  ConditionRule,
  LoopConfig,
  ActionConfig,
} from './types';

// ───── 常量 ─────

const MAX_ITERATIONS = 100;
const MAX_DEPTH = 50;

// ───── 内部类型 ─────

/** 执行上下文 */
interface ExecutionContext {
  /** 变量作用域 */
  variables: Record<string, unknown>;
  /** 节点输出缓存 */
  outputs: Map<string, unknown>;
  /** 执行深度 */
  depth: number;
  /** 是否已中止 */
  aborted: boolean;
}

// ============================
// DAG 拓扑排序
// ============================

/**
 * 对工作流节点进行拓扑排序
 * 返回按执行顺序排列的节点 ID 列表
 */
export function topologicalSort(workflow: Workflow): string[] {
  const { nodes, connections } = workflow;
  const nodeIds = nodes.map((n) => n.id);

  // 构建邻接表
  const adjacency = new Map<string, string[]>();
  const inDegree = new Map<string, number>();

  for (const id of nodeIds) {
    adjacency.set(id, []);
    inDegree.set(id, 0);
  }

  for (const conn of connections) {
    const children = adjacency.get(conn.sourceNodeId);
    if (children) {
      children.push(conn.targetNodeId);
    }
    inDegree.set(conn.targetNodeId, (inDegree.get(conn.targetNodeId) ?? 0) + 1);
  }

  // Kahn 算法
  const queue: string[] = [];
  for (const [id, degree] of inDegree) {
    if (degree === 0) queue.push(id);
  }

  const sorted: string[] = [];
  while (queue.length > 0) {
    const current = queue.shift()!;
    sorted.push(current);
    const children = adjacency.get(current);
    if (children) {
      for (const child of children) {
        const newDegree = (inDegree.get(child) ?? 1) - 1;
        inDegree.set(child, newDegree);
        if (newDegree === 0) queue.push(child);
      }
    }
  }

  // 如果有环，将剩余节点追加到末尾
  if (sorted.length < nodeIds.length) {
    for (const id of nodeIds) {
      if (!sorted.includes(id)) sorted.push(id);
    }
  }

  return sorted;
}

/**
 * 获取节点的前驱节点输出值
 */
function getInputFromDependencies(
  nodeId: string,
  workflow: Workflow,
  context: ExecutionContext,
): Record<string, unknown> {
  const input: Record<string, unknown> = {};

  const incomingConnections = workflow.connections.filter(
    (c) => c.targetNodeId === nodeId,
  );

  for (const conn of incomingConnections) {
    const sourceOutput = context.outputs.get(conn.sourceNodeId);
    if (sourceOutput !== undefined) {
      const portName = conn.targetPort || 'data';
      input[portName] = sourceOutput;
    }
  }

  // 也传入当前上下文变量
  input._context = { ...context.variables };

  return input;
}

// ============================
// 条件评估
// ============================

/**
 * 评估单条条件规则
 */
function evaluateRule(rule: ConditionRule, context: ExecutionContext): boolean {
  const fieldValue = resolveValue(rule.field, context);

  switch (rule.operator) {
    case 'equals':
      return fieldValue === rule.value;
    case 'not_equals':
      return fieldValue !== rule.value;
    case 'contains': {
      const str = String(fieldValue);
      return str.includes(String(rule.value));
    }
    case 'not_contains': {
      const str = String(fieldValue);
      return !str.includes(String(rule.value));
    }
    case 'greater_than': {
      const numA = Number(fieldValue);
      const numB = Number(rule.value);
      return !isNaN(numA) && !isNaN(numB) && numA > numB;
    }
    case 'less_than': {
      const numA = Number(fieldValue);
      const numB = Number(rule.value);
      return !isNaN(numA) && !isNaN(numB) && numA < numB;
    }
    case 'regex': {
      try {
        const regex = new RegExp(String(rule.value));
        return regex.test(String(fieldValue));
      } catch {
        return false;
      }
    }
    case 'exists':
      return fieldValue !== undefined && fieldValue !== null;
    case 'not_exists':
      return fieldValue === undefined || fieldValue === null;
    default:
      return false;
  }
}

/**
 * 评估条件分支
 */
function evaluateBranch(branch: ConditionBranch, context: ExecutionContext): boolean {
  if (branch.conditions.length === 0) return true;

  const results = branch.conditions.map((rule) => evaluateRule(rule, context));

  if (branch.logic === 'and') {
    return results.every(Boolean);
  }
  return results.some(Boolean);
}

/**
 * 评估条件配置，返回激活的分支名称
 */
export function evaluateCondition(
  config: ConditionConfig,
  context: ExecutionContext,
): string {
  for (const branch of config.branches) {
    if (evaluateBranch(branch, context)) {
      return branch.name;
    }
  }
  return config.defaultBranch ?? '';
}

// ============================
// 变量解析
// ============================

/**
 * 解析变量引用（支持 {{var.path}} 语法）
 */
function resolveValue(expr: string, context: ExecutionContext): unknown {
  // 尝试解析模板变量 {{var.path.to.value}}
  const templateMatch = /^\{\{(.+)\}\}$/g.exec(expr.trim());
  if (templateMatch) {
    const path = templateMatch[1].trim();
    return getNestedValue(context.variables, path);
  }
  return expr;
}

/**
 * 从嵌套对象中获取值（支持点号路径）
 */
function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    if (typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

/**
 * 解析模板字符串，替换 {{var}} 为实际值
 */
function resolveTemplate(template: string, context: ExecutionContext): string {
  return template.replace(/\{\{([^}]+)\}\}/g, (_, path: string) => {
    const value = getNestedValue(context.variables, path.trim());
    return value !== undefined ? String(value) : '';
  });
}

// ============================
// 节点执行
// ============================

/**
 * 执行单个触发器节点
 */
async function executeTriggerNode(
  node: WorkflowNode,
  _workflow: Workflow,
  context: ExecutionContext,
): Promise<unknown> {
  const config = node.config as import('./types').TriggerConfig;

  switch (config.subType) {
    case 'manual':
      return { triggeredBy: 'manual', timestamp: Date.now() };
    case 'webhook':
      return { triggeredBy: 'webhook', url: config.webhookUrl, payload: context.variables };
    case 'schedule':
      return { triggeredBy: 'schedule', cron: config.cronExpression, timestamp: Date.now() };
    case 'event':
      return {
        triggeredBy: 'event',
        eventName: config.eventName,
        data: context.variables,
      };
    default:
      return { triggeredBy: 'unknown' };
  }
}

/**
 * 执行单个条件节点
 */
async function executeConditionNode(
  node: WorkflowNode,
  workflow: Workflow,
  context: ExecutionContext,
): Promise<unknown> {
  const config = node.config as ConditionConfig;
  const chosenBranch = evaluateCondition(config, context);

  if (chosenBranch && context.depth < MAX_DEPTH) {
    // 查找该分支对应的目标连接
    const branchConnections = workflow.connections.filter(
      (c) => c.sourceNodeId === node.id && c.sourcePort === chosenBranch,
    );

    for (const conn of branchConnections) {
      const targetNode = workflow.nodes.find((n) => n.id === conn.targetNodeId);
      if (targetNode) {
        const result = await executeNode(targetNode, workflow, context);
        if (context.aborted) break;
        context.outputs.set(targetNode.id, result);
      }
    }
  }

  return {
    conditionResult: chosenBranch,
    branches: config.branches.map((b) => b.name),
    chosen: chosenBranch,
  };
}

/**
 * 执行单个动作节点
 */
async function executeActionNode(
  node: WorkflowNode,
  _workflow: Workflow,
  context: ExecutionContext,
): Promise<unknown> {
  const config = node.config as ActionConfig;

  switch (config.subType) {
    case 'api_call':
      return {
        action: 'api_call',
        url: resolveTemplate(config.apiUrl ?? '', context),
        method: config.apiMethod ?? 'GET',
        body: config.apiBody ? resolveTemplate(config.apiBody, context) : undefined,
        simulated: true,
      };
    case 'notification':
      return {
        action: 'notification',
        message: resolveTemplate(config.notificationMessage ?? '', context),
        sent: true,
      };
    case 'transform':
      return {
        action: 'transform',
        script: config.transformScript,
        result: context.variables, // 简化的变换结果
      };
    case 'script':
      return {
        action: 'script',
        executed: true,
        result: { message: '脚本执行完成（客户端模拟）' },
      };
    case 'delay':
      return {
        action: 'delay',
        delayMs: config.delayMs ?? 0,
        completed: true,
      };
    default:
      return { action: 'unknown' };
  }
}

/**
 * 执行单个循环节点
 */
async function executeLoopNode(
  node: WorkflowNode,
  workflow: Workflow,
  context: ExecutionContext,
): Promise<unknown> {
  const config = node.config as LoopConfig;
  const results: unknown[] = [];
  const maxIter = config.maxIterations ?? MAX_ITERATIONS;

  // 查找循环体内的节点
  const bodyConnections = workflow.connections.filter(
    (c) => c.sourceNodeId === node.id && c.sourcePort === 'body',
  );
  const bodyNodeIds = bodyConnections.map((c) => c.targetNodeId);

  switch (config.subType) {
    case 'for_each': {
      const collection = config.collectionRef
        ? getNestedValue(context.variables, config.collectionRef)
        : [];
      const items = Array.isArray(collection) ? collection : [collection];
      let iterCount = 0;

      for (const item of items) {
        if (iterCount >= maxIter || context.aborted) break;
        // 设置迭代变量
        if (config.iteratorVar) {
          context.variables[config.iteratorVar] = item;
        }
        context.variables._index = iterCount;

        const subContext: ExecutionContext = {
          ...context,
          variables: { ...context.variables },
          depth: context.depth + 1,
        };

        for (const bodyNodeId of bodyNodeIds) {
          if (subContext.aborted) break;
          const bodyNode = workflow.nodes.find((n) => n.id === bodyNodeId);
          if (bodyNode) {
            const result = await executeNode(bodyNode, workflow, subContext);
            results.push(result);
          }
        }
        iterCount++;
      }
      break;
    }

    case 'while': {
      let iterCount = 0;
      while (
        iterCount < maxIter &&
        !context.aborted &&
        evaluateWhileCondition(config.conditionExpression ?? '', context)
      ) {
        const subContext: ExecutionContext = {
          ...context,
          variables: { ...context.variables, _index: iterCount },
          depth: context.depth + 1,
        };

        for (const bodyNodeId of bodyNodeIds) {
          if (subContext.aborted) break;
          const bodyNode = workflow.nodes.find((n) => n.id === bodyNodeId);
          if (bodyNode) {
            const result = await executeNode(bodyNode, workflow, subContext);
            results.push(result);
          }
        }
        iterCount++;
      }
      break;
    }

    case 'repeat': {
      const repeatCount = config.repeatCount ?? 1;
      for (let i = 0; i < repeatCount && i < maxIter && !context.aborted; i++) {
        const subContext: ExecutionContext = {
          ...context,
          variables: { ...context.variables, _index: i },
          depth: context.depth + 1,
        };

        for (const bodyNodeId of bodyNodeIds) {
          if (subContext.aborted) break;
          const bodyNode = workflow.nodes.find((n) => n.id === bodyNodeId);
          if (bodyNode) {
            const result = await executeNode(bodyNode, workflow, subContext);
            results.push(result);
          }
        }
      }
      break;
    }
  }

  return {
    loopType: config.subType,
    iterations: results,
    totalIterations: results.length,
  };
}

/**
 * 评估 while 循环条件（简化版：从上下文变量求值）
 */
function evaluateWhileCondition(expr: string, context: ExecutionContext): boolean {
  // 简单实现：在上下文中查找变量值
  const trimmed = expr.trim();
  const value = getNestedValue(context.variables, trimmed);
  return Boolean(value);
}

// ============================
// 节点执行路由
// ============================

/**
 * 执行单个节点
 */
async function executeNode(
  node: WorkflowNode,
  workflow: Workflow,
  context: ExecutionContext,
): Promise<unknown> {
  if (context.aborted) return null;
  if (!node.enabled) return { skipped: true };

  const input = getInputFromDependencies(node.id, workflow, context);

  let output: unknown;
  switch (node.type) {
    case 'trigger':
      output = await executeTriggerNode(node, workflow, context);
      break;
    case 'condition':
      output = await executeConditionNode(node, workflow, context);
      break;
    case 'action':
      output = await executeActionNode(node, workflow, context);
      break;
    case 'loop':
      output = await executeLoopNode(node, workflow, context);
      break;
    default:
      output = { unknown: true };
  }

  // 将输出写入上下文变量
  if (output && typeof output === 'object') {
    Object.assign(context.variables, { [`${node.id}_output`]: output });
  }

  return output;
}

// ============================
// 流程执行
// ============================

/**
 * 执行整个工作流
 *
 * 工作流执行流程：
 * 1. 初始化执行上下文
 * 2. 拓扑排序节点
 * 3. 按顺序执行每个节点
 * 4. 收集执行结果
 * 5. 返回执行记录
 */
export async function executeWorkflow(
  workflow: Workflow,
  input?: Record<string, unknown>,
  onNodeProgress?: (result: NodeExecutionResult) => void,
): Promise<WorkflowExecution> {
  const executionId = `exec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

  // 初始化上下文
  const context: ExecutionContext = {
    variables: input ? { ...input } : {},
    outputs: new Map(),
    depth: 0,
    aborted: false,
  };

  // 设置工作流变量默认值
  for (const variable of workflow.variables ?? []) {
    if (!(variable.name in context.variables) && variable.defaultValue !== undefined) {
      context.variables[variable.name] = variable.defaultValue;
    }
  }

  const nodeResults: NodeExecutionResult[] = [];
  const startTime = Date.now();

  // 拓扑排序
  const sortedIds = topologicalSort(workflow);

  // 按顺序执行节点
  for (const nodeId of sortedIds) {
    if (context.aborted) break;

    const node = workflow.nodes.find((n) => n.id === nodeId);
    if (!node) continue;

    const nodeStartTime = Date.now();
    let result: NodeExecutionResult;

    try {
      const output = await executeNode(node, workflow, context);
      context.outputs.set(nodeId, output);

      result = {
        nodeId,
        nodeLabel: node.label,
        status: 'completed',
        input: getInputFromDependencies(nodeId, workflow, context),
        output,
        startedAt: new Date(nodeStartTime).toISOString(),
        endedAt: new Date().toISOString(),
        durationMs: Date.now() - nodeStartTime,
      };
    } catch (error) {
      result = {
        nodeId,
        nodeLabel: node.label,
        status: 'failed',
        input: getInputFromDependencies(nodeId, workflow, context),
        error: error instanceof Error ? error.message : '未知错误',
        startedAt: new Date(nodeStartTime).toISOString(),
        endedAt: new Date().toISOString(),
        durationMs: Date.now() - nodeStartTime,
      };
      context.aborted = true;
    }

    nodeResults.push(result);
    onNodeProgress?.(result);
  }

  const endedAt = new Date().toISOString();
  const overallFailed = nodeResults.some((r) => r.status === 'failed');

  return {
    id: executionId,
    workflowId: workflow.id,
    workflowVersion: workflow.version,
    status: overallFailed ? 'failed' : 'completed',
    triggerType: 'manual',
    input,
    output: Object.fromEntries(context.outputs),
    nodeResults,
    context: context.variables,
    startedAt: new Date(startTime).toISOString(),
    endedAt,
    durationMs: Date.now() - startTime,
    error: overallFailed
      ? nodeResults.find((r) => r.status === 'failed')?.error
      : undefined,
  };
}

/**
 * 中止执行上下文
 */
export function abortExecution(context: { aborted: boolean }): void {
  context.aborted = true;
}
