/**
 * 伏羲 v2.1 — 工作流引擎 API 封装
 *
 * 封装工作流 CRUD、执行、版本管理等 REST API
 * 数据来源：后端 API，失败时抛出错误
 */

import apiClient from '@/api';
import type {
  Workflow,
  WorkflowExecution,
  WorkflowVersion,
  CreateWorkflowRequest,
  UpdateWorkflowRequest,
  ExecuteWorkflowRequest,
  WorkflowListResponse,
  ExecutionHistoryResponse,
  VersionListResponse,
} from './types';

// ───── 常量 ─────

const API_BASE = '/api/workflows';

// ───── 错误类型 ─────

export class WorkflowApiError extends Error {
  constructor(endpoint: string, originalError?: unknown) {
    super(`工作流 API ${endpoint} 请求失败`);
    this.name = 'WorkflowApiError';
    if (originalError instanceof Error) {
      this.message = `${originalError.message}`;
      this.stack = originalError.stack;
    }
  }
}

// ───── 通用请求封装 ─────

async function apiRequest<T>(
  endpoint: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
  body?: unknown,
): Promise<T> {
  try {
    if (method === 'GET') {
      return (await apiClient.get(`${API_BASE}${endpoint}`)) as T;
    }
    if (method === 'DELETE') {
      return (await apiClient.delete(`${API_BASE}${endpoint}`)) as T;
    }
    if (method === 'PUT') {
      return (await apiClient.put(`${API_BASE}${endpoint}`, body)) as T;
    }
    return (await apiClient.post(`${API_BASE}${endpoint}`, body)) as T;
  } catch (error) {
    throw new WorkflowApiError(endpoint, error);
  }
}

// ============================
// 工作流 CRUD
// ============================

/** 获取工作流列表 */
export async function getWorkflows(): Promise<WorkflowListResponse> {
  return apiRequest<WorkflowListResponse>('/');
}

/** 获取工作流详情 */
export async function getWorkflow(id: string): Promise<Workflow> {
  return apiRequest<Workflow>(`/${id}`);
}

/** 创建工作流 */
export async function createWorkflow(data: CreateWorkflowRequest): Promise<Workflow> {
  return apiRequest<Workflow>('/', 'POST', data);
}

/** 更新工作流 */
export async function updateWorkflow(id: string, data: UpdateWorkflowRequest): Promise<Workflow> {
  return apiRequest<Workflow>(`/${id}`, 'PUT', data);
}

/** 删除工作流 */
export async function deleteWorkflow(id: string): Promise<void> {
  return apiRequest<void>(`/${id}`, 'DELETE');
}

// ============================
// 工作流执行
// ============================

/** 执行工作流 */
export async function executeWorkflow(
  id: string,
  data?: ExecuteWorkflowRequest,
): Promise<WorkflowExecution> {
  return apiRequest<WorkflowExecution>(`/${id}/execute`, 'POST', data ?? {});
}

/** 获取执行历史 */
export async function getExecutionHistory(id: string): Promise<ExecutionHistoryResponse> {
  return apiRequest<ExecutionHistoryResponse>(`/${id}/executions`);
}

// ============================
// 版本管理
// ============================

/** 获取工作流版本列表 */
export async function getWorkflowVersions(id: string): Promise<VersionListResponse> {
  return apiRequest<VersionListResponse>(`/${id}/versions`);
}

/** 回滚到指定版本 */
export async function rollbackWorkflow(
  id: string,
  versionId: string,
): Promise<Workflow> {
  return apiRequest<Workflow>(`/${id}/versions/${versionId}/rollback`, 'POST');
}
