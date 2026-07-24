/**
 * 伏羲 v2.1 — 工作流引擎 Store
 *
 * 管理工作流状态：工作流列表、当前编辑的工作流、执行结果、版本历史
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';
import type {
  Workflow,
  WorkflowExecution,
  WorkflowVersion,
  WorkflowNode,
  WorkflowConnection,
  CreateWorkflowRequest,
  UpdateWorkflowRequest,
  ExecuteWorkflowRequest,
  WorkflowVariable,
} from './types';
import * as workflowApi from './api';

const logger = createLogger('WorkflowEngineStore');

// ───── ID 生成器 ─────

function generateId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// ============================
// Store
// ============================

export const useWorkflowEngineStore = defineStore('workflow-engine', () => {
  // ───── 状态 ─────

  /** 工作流列表 */
  const workflows = ref<Workflow[]>([]);
  /** 列表总数 */
  const total = ref(0);
  /** 当前编辑的工作流 */
  const currentWorkflow = ref<Workflow | null>(null);
  /** 执行记录列表 */
  const executions = ref<WorkflowExecution[]>([]);
  /** 版本列表 */
  const versions = ref<WorkflowVersion[]>([]);
  /** 加载状态 */
  const loading = ref(false);
  /** 执行中状态 */
  const executing = ref(false);
  /** 错误信息 */
  const error = ref<string | null>(null);
  /** 脏标记（未保存的更改） */
  const hasUnsavedChanges = ref(false);

  // ───── 计算属性 ─────

  /** 当前工作流是否为空 */
  const isEmpty = computed(() => !currentWorkflow.value || currentWorkflow.value.nodes.length === 0);

  /** 当前工作流节点数 */
  const nodeCount = computed(() => currentWorkflow.value?.nodes.length ?? 0);

  /** 当前工作流连接线数 */
  const connectionCount = computed(() => currentWorkflow.value?.connections.length ?? 0);

  /** 当前选中的节点（通过 selection state 外部管理） */

  // ───── 工作流列表操作 ─────

  /** 加载工作流列表 */
  async function loadWorkflows(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const result = await workflowApi.getWorkflows();
      workflows.value = result.workflows;
      total.value = result.total;
      logger.info(`加载了 ${total.value} 个工作流`);
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载工作流列表失败';
      logger.error('加载工作流列表失败', e);
    } finally {
      loading.value = false;
    }
  }

  /** 创建工作流 */
  async function createWorkflow(data: CreateWorkflowRequest): Promise<Workflow | null> {
    loading.value = true;
    error.value = null;
    try {
      const workflow = await workflowApi.createWorkflow(data);
      workflows.value.unshift(workflow);
      total.value++;
      logger.info(`创建工作流: ${workflow.name}`);
      return workflow;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '创建工作流失败';
      logger.error('创建工作流失败', e);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /** 加载工作流详情到编辑器 */
  async function loadWorkflow(id: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const workflow = await workflowApi.getWorkflow(id);
      currentWorkflow.value = workflow;
      hasUnsavedChanges.value = false;
      logger.info(`加载工作流: ${workflow.name} (v${workflow.version})`);
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载工作流失败';
      logger.error('加载工作流失败', e);
    } finally {
      loading.value = false;
    }
  }

  /** 更新工作流 */
  async function updateWorkflow(data: UpdateWorkflowRequest): Promise<boolean> {
    if (!currentWorkflow.value) return false;
    loading.value = true;
    error.value = null;
    try {
      const updated = await workflowApi.updateWorkflow(currentWorkflow.value.id, data);
      currentWorkflow.value = updated;
      hasUnsavedChanges.value = false;
      // 同步更新列表中的项
      const idx = workflows.value.findIndex((w) => w.id === updated.id);
      if (idx !== -1) workflows.value[idx] = updated;
      logger.info(`更新工作流: ${updated.name} (v${updated.version})`);
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '更新工作流失败';
      logger.error('更新工作流失败', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  /** 删除工作流 */
  async function removeWorkflow(id: string): Promise<boolean> {
    loading.value = true;
    error.value = null;
    try {
      await workflowApi.deleteWorkflow(id);
      workflows.value = workflows.value.filter((w) => w.id !== id);
      total.value--;
      if (currentWorkflow.value?.id === id) {
        currentWorkflow.value = null;
        hasUnsavedChanges.value = false;
      }
      logger.info(`删除工作流: ${id}`);
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '删除工作流失败';
      logger.error('删除工作流失败', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  // ───── 编辑器操作 ─────

  /** 创建新工作流草稿（仅在客户端） */
  function createDraft(name: string, description?: string): void {
    currentWorkflow.value = {
      id: generateId('wf'),
      name,
      description: description ?? '',
      version: 1,
      status: 'draft',
      nodes: [],
      connections: [],
      variables: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      tags: [],
    };
    hasUnsavedChanges.value = true;
  }

  /** 添加节点 */
  function addNode(node: WorkflowNode): void {
    if (!currentWorkflow.value) return;
    currentWorkflow.value.nodes.push(node);
    hasUnsavedChanges.value = true;
  }

  /** 更新节点 */
  function updateNode(nodeId: string, updates: Partial<WorkflowNode>): void {
    if (!currentWorkflow.value) return;
    const idx = currentWorkflow.value.nodes.findIndex((n) => n.id === nodeId);
    if (idx === -1) return;
    currentWorkflow.value.nodes[idx] = { ...currentWorkflow.value.nodes[idx], ...updates };
    hasUnsavedChanges.value = true;
  }

  /** 移除节点 */
  function removeNode(nodeId: string): void {
    if (!currentWorkflow.value) return;
    // 移除节点
    currentWorkflow.value.nodes = currentWorkflow.value.nodes.filter((n) => n.id !== nodeId);
    // 移除相关连接线
    currentWorkflow.value.connections = currentWorkflow.value.connections.filter(
      (c) => c.sourceNodeId !== nodeId && c.targetNodeId !== nodeId,
    );
    hasUnsavedChanges.value = true;
  }

  /** 添加连接线 */
  function addConnection(connection: WorkflowConnection): void {
    if (!currentWorkflow.value) return;
    // 检查是否已存在相同连接
    const exists = currentWorkflow.value.connections.some(
      (c) =>
        c.sourceNodeId === connection.sourceNodeId &&
        c.sourcePort === connection.sourcePort &&
        c.targetNodeId === connection.targetNodeId &&
        c.targetPort === connection.targetPort,
    );
    if (exists) return;
    currentWorkflow.value.connections.push(connection);
    hasUnsavedChanges.value = true;
  }

  /** 移除连接线 */
  function removeConnection(connectionId: string): void {
    if (!currentWorkflow.value) return;
    currentWorkflow.value.connections = currentWorkflow.value.connections.filter(
      (c) => c.id !== connectionId,
    );
    hasUnsavedChanges.value = true;
  }

  /** 移动节点 */
  function moveNode(nodeId: string, x: number, y: number): void {
    if (!currentWorkflow.value) return;
    const node = currentWorkflow.value.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    node.position = { x, y };
    hasUnsavedChanges.value = true;
  }

  /** 添加变量 */
  function addVariable(variable: WorkflowVariable): void {
    if (!currentWorkflow.value) return;
    if (!currentWorkflow.value.variables) {
      currentWorkflow.value.variables = [];
    }
    currentWorkflow.value.variables.push(variable);
    hasUnsavedChanges.value = true;
  }

  /** 移除变量 */
  function removeVariable(name: string): void {
    if (!currentWorkflow.value?.variables) return;
    currentWorkflow.value.variables = currentWorkflow.value.variables.filter(
      (v) => v.name !== name,
    );
    hasUnsavedChanges.value = true;
  }

  // ───── 执行操作 ─────

  /** 执行当前工作流 */
  async function executeCurrentWorkflow(
    input?: Record<string, unknown>,
    asyncExec = false,
  ): Promise<WorkflowExecution | null> {
    if (!currentWorkflow.value) return null;
    executing.value = true;
    error.value = null;
    try {
      const execution = await workflowApi.executeWorkflow(currentWorkflow.value.id, {
        input,
        async: asyncExec,
      });
      logger.info(`工作流执行: ${execution.id} — ${execution.status}`);
      return execution;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '工作流执行失败';
      logger.error('工作流执行失败', e);
      return null;
    } finally {
      executing.value = false;
    }
  }

  /** 加载执行历史 */
  async function loadExecutions(workflowId?: string): Promise<void> {
    const id = workflowId ?? currentWorkflow.value?.id;
    if (!id) return;
    loading.value = true;
    error.value = null;
    try {
      const result = await workflowApi.getExecutionHistory(id);
      executions.value = result.executions;
      logger.info(`加载了 ${result.total} 条执行历史`);
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载执行历史失败';
      logger.error('加载执行历史失败', e);
    } finally {
      loading.value = false;
    }
  }

  // ───── 版本管理操作 ─────

  /** 加载版本历史 */
  async function loadVersions(workflowId?: string): Promise<void> {
    const id = workflowId ?? currentWorkflow.value?.id;
    if (!id) return;
    loading.value = true;
    error.value = null;
    try {
      const result = await workflowApi.getWorkflowVersions(id);
      versions.value = result.versions;
      logger.info(`加载了 ${result.total} 个版本`);
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载版本历史失败';
      logger.error('加载版本历史失败', e);
    } finally {
      loading.value = false;
    }
  }

  /** 回滚到指定版本 */
  async function rollbackToVersion(versionId: string): Promise<boolean> {
    if (!currentWorkflow.value) return false;
    loading.value = true;
    error.value = null;
    try {
      const workflow = await workflowApi.rollbackWorkflow(currentWorkflow.value.id, versionId);
      currentWorkflow.value = workflow;
      hasUnsavedChanges.value = false;
      logger.info(`回滚到版本: ${versionId}`);
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '版本回滚失败';
      logger.error('版本回滚失败', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  // ───── 工具方法 ─────

  /** 清除编辑器状态 */
  function clearEditor(): void {
    currentWorkflow.value = null;
    hasUnsavedChanges.value = false;
    error.value = null;
  }

  /** 清除错误 */
  function clearError(): void {
    error.value = null;
  }

  return {
    // 状态
    workflows,
    total,
    currentWorkflow,
    executions,
    versions,
    loading,
    executing,
    error,
    hasUnsavedChanges,
    // 计算属性
    isEmpty,
    nodeCount,
    connectionCount,
    // 操作
    loadWorkflows,
    createWorkflow,
    loadWorkflow,
    updateWorkflow,
    removeWorkflow,
    createDraft,
    addNode,
    updateNode,
    removeNode,
    addConnection,
    removeConnection,
    moveNode,
    addVariable,
    removeVariable,
    executeCurrentWorkflow,
    loadExecutions,
    loadVersions,
    rollbackToVersion,
    clearEditor,
    clearError,
  };
});
