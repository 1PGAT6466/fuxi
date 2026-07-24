/**
 * 伏羲 v2.1 — 最近访问服务模块
 *
 * 统一导出：
 * - HistoryService（编程式 API，无 Vue 依赖）
 * - useRecentVisitsStore（Pinia Store，Vue 组件使用）
 * - RecentVisits 组件
 * - 类型定义
 */

export { historyService } from './HistoryService';
export { useRecentVisitsStore } from './store';
export { default as RecentVisits } from './RecentVisits.vue';
export * from './types';
export * from './api';
