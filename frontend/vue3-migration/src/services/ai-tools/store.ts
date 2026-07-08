/**
 * 伏羲 v2.1 — AI 工具集 Store
 * 管理工具历史记录 + 最近使用偏好
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

// ───── 类型 ─────

export interface ToolHistoryItem {
  id: string;
  tool: string; // summarize | translate | keywords | entities | classify
  input: string;
  result: unknown;
  timestamp: number;
}

export interface ToolPreference {
  tool: string;
  key: string;
  value: unknown;
}

// ───── Store ─────

export const useAiToolsStore = defineStore('ai-tools', () => {
  // 历史记录（最多保留 50 条）
  const history = ref<ToolHistoryItem[]>([]);
  const maxHistorySize = 50;

  // 最近使用偏好
  const preferences = ref<ToolPreference[]>([]);

  // ───── Getters ─────

  /** 按工具类型分组的历史记录 */
  const historyByTool = computed(() => {
    const map: Record<string, ToolHistoryItem[]> = {};
    for (const item of history.value) {
      if (!map[item.tool]) map[item.tool] = [];
      map[item.tool].push(item);
    }
    return map;
  });

  /** 最近使用的工具列表（按最后使用时间排序） */
  const recentTools = computed(() => {
    const toolLastUse: Record<string, number> = {};
    for (const item of history.value) {
      if (!toolLastUse[item.tool] || item.timestamp > toolLastUse[item.tool]) {
        toolLastUse[item.tool] = item.timestamp;
      }
    }
    return Object.entries(toolLastUse)
      .sort(([, a], [, b]) => b - a)
      .map(([tool]) => tool);
  });

  // ───── 历史记录操作 ─────

  /** 添加历史记录 */
  function addHistory(item: Omit<ToolHistoryItem, 'id' | 'timestamp'>): void {
    const record: ToolHistoryItem = {
      id: `hist_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      tool: item.tool,
      input: item.input,
      result: item.result,
      timestamp: Date.now(),
    };

    history.value.unshift(record);

    // 裁剪超出上限的记录
    if (history.value.length > maxHistorySize) {
      history.value = history.value.slice(0, maxHistorySize);
    }
  }

  /** 清除所有历史记录 */
  function clearHistory(tool?: string): void {
    if (tool) {
      history.value = history.value.filter((item) => item.tool !== tool);
    } else {
      history.value = [];
    }
  }

  /** 删除单条历史记录 */
  function removeHistoryItem(id: string): void {
    history.value = history.value.filter((item) => item.id !== id);
  }

  // ───── 偏好管理 ─────

  /** 设置偏好 */
  function setPreference(tool: string, key: string, value: unknown): void {
    const existing = preferences.value.find((p) => p.tool === tool && p.key === key);
    if (existing) {
      existing.value = value;
    } else {
      preferences.value.push({ tool, key, value });
    }
  }

  /** 获取偏好 */
  function getPreference(tool: string, key: string): unknown {
    return preferences.value.find((p) => p.tool === tool && p.key === key)?.value;
  }

  return {
    history,
    preferences,
    historyByTool,
    recentTools,
    addHistory,
    clearHistory,
    removeHistoryItem,
    setPreference,
    getPreference,
  };
});
