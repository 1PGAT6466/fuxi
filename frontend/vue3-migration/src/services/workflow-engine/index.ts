/**
 * 伏羲 v2.1 — 工作流引擎服务入口
 *
 * 导出主页面组件、Store、API、类型和引擎
 */

// 主页面组件
export { default as WorkflowEnginePage } from './WorkflowEnginePage.vue';

// 工作流编辑器（可独立使用）
export { default as WorkflowEditor } from './WorkflowEditor.vue';

// Store
export { useWorkflowEngineStore } from './store';

// API
export * as workflowApi from './api';

// 类型
export type * from './types';

// 执行引擎
export * as workflowEngine from './engine';

// 节点模板
export * as workflowTemplates from './templates';
