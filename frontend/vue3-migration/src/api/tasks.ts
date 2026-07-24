/**
 * 伏羲 v2.1 — 任务仪表板 API
 *
 * 后端路由（规划中）：
 *   GET  /api/tasks/stats       → { pending, inProgress, completed, total }
 *   GET  /api/tasks             → 任务列表（分页）
 *   GET  /api/system/resources  → { cpu, memory, disk }
 *   POST /api/tasks/scan        → 触发扫描任务
 *   POST /api/tasks/index       → 触发索引任务
 *   POST /api/tasks/cleanup     → 触发清理任务
 */

import apiClient from './index';

// ─── 类型定义 ───

/** 系统资源状态 */
export interface SystemResources {
  cpu: {
    usage: number; // 0-100
    cores: number;
    temperature: number; // °C
  };
  memory: {
    used: string; // e.g. "12.4 GB"
    total: string; // e.g. "32.0 GB"
    usagePercent: number; // 0-100
  };
  disk: {
    used: string;
    total: string;
    usagePercent: number;
  };
}

/** 任务统计 */
export interface TaskStats {
  pending: number;
  inProgress: number;
  completed: number;
  failed: number;
  total: number;
}

/** 任务状态 */
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

/** 单一任务条目 */
export interface TaskEntry {
  id: string;
  name: string;
  type: string;
  status: TaskStatus;
  progress: number; // 0-100
  createdAt: string;
  updatedAt: string;
  createdBy?: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
}

/** 任务列表响应 */
export interface TaskListResponse {
  tasks: TaskEntry[];
  total: number;
  page: number;
  pageSize: number;
}

/** 仪表板概览（聚合） */
export interface TaskDashboardOverview {
  resources: SystemResources;
  stats: TaskStats;
  recentTasks: TaskEntry[];
  searchIndexCount: number;
  lastIndexTime: string;
}

// ─── API 方法 ───

/** 获取系统资源状态 → /api/system/resources */
export function getSystemResources(): Promise<SystemResources> {
  return apiClient.get('/api/system/resources') as Promise<SystemResources>;
}

/** 获取任务统计 → /api/tasks/stats */
export function getTaskStats(): Promise<TaskStats> {
  return apiClient.get('/api/tasks/stats') as Promise<TaskStats>;
}

/** 获取任务列表 → /api/tasks */
export function getTasks(params?: {
  page?: number;
  pageSize?: number;
  status?: TaskStatus;
}): Promise<TaskListResponse> {
  return apiClient.get('/api/tasks', { params }) as Promise<TaskListResponse>;
}

/** 获取仪表板聚合概览 → /api/tasks/dashboard */
export function getTaskDashboard(): Promise<TaskDashboardOverview> {
  return apiClient.get('/api/tasks/dashboard') as Promise<TaskDashboardOverview>;
}

/** 触发扫描任务 */
export function triggerScan(): Promise<{ ok: boolean; taskId: string }> {
  return apiClient.post('/api/tasks/scan') as Promise<{ ok: boolean; taskId: string }>;
}

/** 触发索引任务 */
export function triggerIndex(): Promise<{ ok: boolean; taskId: string }> {
  return apiClient.post('/api/tasks/index') as Promise<{ ok: boolean; taskId: string }>;
}

/** 触发清理任务 */
export function triggerCleanup(): Promise<{ ok: boolean; taskId: string }> {
  return apiClient.post('/api/tasks/cleanup') as Promise<{ ok: boolean; taskId: string }>;
}

// ─── Mock 数据（后端不可用时降级使用） ───

export function getMockResources(): SystemResources {
  return {
    cpu: {
      usage: Math.floor(Math.random() * 30) + 15,
      cores: 8,
      temperature: Math.floor(Math.random() * 20) + 45,
    },
    memory: {
      used: '18.7 GB',
      total: '32.0 GB',
      usagePercent: Math.floor(Math.random() * 20) + 50,
    },
    disk: {
      used: '156 GB',
      total: '500 GB',
      usagePercent: Math.floor(Math.random() * 15) + 25,
    },
  };
}

export function getMockTaskStats(): TaskStats {
  return {
    pending: 12,
    inProgress: 5,
    completed: 342,
    failed: 3,
    total: 362,
  };
}

export function getMockRecentTasks(): TaskEntry[] {
  const now = Date.now();
  return [
    {
      id: 'task-001',
      name: '知识库索引更新',
      type: 'index',
      status: 'completed',
      progress: 100,
      createdAt: new Date(now - 1200000).toISOString(),
      updatedAt: new Date(now - 1100000).toISOString(),
      createdBy: 'system',
      priority: 'normal',
    },
    {
      id: 'task-002',
      name: '文档批量导入',
      type: 'import',
      status: 'in_progress',
      progress: 67,
      createdAt: new Date(now - 3600000).toISOString(),
      updatedAt: new Date(now - 600000).toISOString(),
      createdBy: 'admin',
      priority: 'high',
    },
    {
      id: 'task-003',
      name: 'RAG 管道优化',
      type: 'optimize',
      status: 'pending',
      progress: 0,
      createdAt: new Date(now - 7200000).toISOString(),
      updatedAt: new Date(now - 7200000).toISOString(),
      createdBy: 'zhangsan',
      priority: 'normal',
    },
    {
      id: 'task-004',
      name: '数据库定时备份',
      type: 'backup',
      status: 'completed',
      progress: 100,
      createdAt: new Date(now - 10800000).toISOString(),
      updatedAt: new Date(now - 10700000).toISOString(),
      createdBy: 'system',
      priority: 'low',
    },
    {
      id: 'task-005',
      name: '评测任务 Eval-042',
      type: 'evaluation',
      status: 'failed',
      progress: 45,
      createdAt: new Date(now - 14400000).toISOString(),
      updatedAt: new Date(now - 13000000).toISOString(),
      createdBy: 'lisi',
      priority: 'urgent',
    },
    {
      id: 'task-006',
      name: '向量库重建',
      type: 'rebuild',
      status: 'in_progress',
      progress: 34,
      createdAt: new Date(now - 18000000).toISOString(),
      updatedAt: new Date(now - 1200000).toISOString(),
      createdBy: 'admin',
      priority: 'high',
    },
    {
      id: 'task-007',
      name: '功能开关配置同步',
      type: 'sync',
      status: 'completed',
      progress: 100,
      createdAt: new Date(now - 21600000).toISOString(),
      updatedAt: new Date(now - 21500000).toISOString(),
      createdBy: 'system',
      priority: 'low',
    },
  ];
}

export function getMockTaskDashboard(): TaskDashboardOverview {
  return {
    resources: getMockResources(),
    stats: getMockTaskStats(),
    recentTasks: getMockRecentTasks(),
    searchIndexCount: 12800,
    lastIndexTime: '10 分钟前',
  };
}
