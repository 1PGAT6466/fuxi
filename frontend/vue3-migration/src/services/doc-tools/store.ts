/**
 * 伏羲 v2.1 — 文档工具 Store
 * 管理上传队列 + 最近转换记录
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { RecentRecord, ProgressInfo } from './types';

// ───── Store ─────

export const useDocToolsStore = defineStore('doc-tools', () => {
  // 上传/处理队列
  const queue = ref<ProgressInfo[]>([]);

  // 最近转换记录（最多 50 条）
  const recentRecords = ref<RecentRecord[]>([]);
  const maxRecords = 50;

  // 当前活跃工具
  const activeTool = ref<string>('convert');

  // ───── Getters ─────

  /** 队列中正在进行的任务数 */
  const activeQueueCount = computed(() => {
    return queue.value.filter((q) => q.status === 'uploading' || q.status === 'processing').length;
  });

  /** 最近转换记录按工具分组 */
  const recordsByTool = computed(() => {
    const map: Record<string, RecentRecord[]> = {};
    for (const r of recentRecords.value) {
      if (!map[r.tool]) map[r.tool] = [];
      map[r.tool].push(r);
    }
    return map;
  });

  // ───── 队列管理 ─────

  /** 添加上传任务 */
  function addToQueue(task: Omit<ProgressInfo, 'progress' | 'status'>): string {
    const item: ProgressInfo = {
      ...task,
      progress: 0,
      status: 'uploading',
    };
    queue.value.push(item);
    return item.id;
  }

  /** 更新任务进度 */
  function updateProgress(id: string, progress: number, status: ProgressInfo['status']): void {
    const item = queue.value.find((q) => q.id === id);
    if (item) {
      item.progress = progress;
      item.status = status;
    }
  }

  /** 移除已完成的队列任务 */
  function removeFromQueue(id: string): void {
    queue.value = queue.value.filter((q) => q.id !== id);
  }

  /** 清理已完成/失败的任务 */
  function clearCompletedQueue(): void {
    queue.value = queue.value.filter((q) => q.status === 'uploading' || q.status === 'processing');
  }

  // ───── 最近记录 ─────

  /** 添加转换记录 */
  function addRecord(record: Omit<RecentRecord, 'id' | 'timestamp'>): void {
    const item: RecentRecord = {
      id: `rec_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      timestamp: Date.now(),
      ...record,
    };
    recentRecords.value.unshift(item);

    if (recentRecords.value.length > maxRecords) {
      recentRecords.value = recentRecords.value.slice(0, maxRecords);
    }
  }

  /** 清空记录 */
  function clearRecords(): void {
    recentRecords.value = [];
  }

  // ───── 工具切换 ─────

  function setActiveTool(tool: string): void {
    activeTool.value = tool;
  }

  return {
    queue,
    recentRecords,
    activeTool,
    activeQueueCount,
    recordsByTool,
    addToQueue,
    updateProgress,
    removeFromQueue,
    clearCompletedQueue,
    addRecord,
    clearRecords,
    setActiveTool,
  };
});
