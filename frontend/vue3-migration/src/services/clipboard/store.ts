/**
 * 伏羲 v2.1 — 剪贴板 Pinia Store
 *
 * 为 Vue3 组件提供响应式剪贴板状态管理。
 * 封装 ClipboardService 实例，提供 computed 属性和 actions。
 */

import { defineStore } from 'pinia';
import { ref, computed, onMounted, onUnmounted, shallowRef } from 'vue';
import { getClipboardService, type ClipboardService } from './service';
import type {
  ClipboardEntry,
  ClipboardContentFormat,
  ClipboardChangedEvent,
  ClipboardPanelConfig,
} from './types';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ClipboardStore');

export const useClipboardStore = defineStore('clipboard', () => {
  // ═══════════════════════════════════════════
  // 核心服务（非响应式引用）
  // ═══════════════════════════════════════════

  let service: ClipboardService | null = null;

  // ═══════════════════════════════════════════
  // 响应式状态
  // ═══════════════════════════════════════════

  /** 剪贴板历史（P0-4: 大数组用 shallowRef 优化） */
  const history = shallowRef<ClipboardEntry[]>([]);

  /** 收藏条目 */
  const favorites = ref<ClipboardEntry[]>([]);

  /** 面板是否可见 */
  const panelVisible = ref(false);

  /** 搜索关键词 */
  const searchQuery = ref('');

  /** 当前过滤的格式 */
  const filterFormat = ref<ClipboardContentFormat | null>(null);

  /** 是否仅显示收藏 */
  const favoritesOnly = ref(false);

  /** 是否正在加载 */
  const isLoading = ref(false);

  /** 错误信息 */
  const errorMessage = ref<string | null>(null);

  /** 服务是否已初始化 */
  const isInitialized = ref(false);

  // 清理函数引用
  let unsubscribe: (() => void) | null = null;

  // ═══════════════════════════════════════════
  // 计算属性
  // ═══════════════════════════════════════════

  /** 历史总数 */
  const totalCount = computed(() => history.value.length);

  /** 收藏总数 */
  const favoritesCount = computed(() => favorites.value.length);

  /** 过滤后的历史列表 */
  const filteredHistory = computed(() => {
    let list = [...history.value];

    // 仅收藏项
    if (favoritesOnly.value) {
      list = list.filter((e) => e.isFavorite);
    }

    // 格式过滤
    if (filterFormat.value) {
      list = list.filter((e) => e.format === filterFormat.value);
    }

    // 关键词搜索
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase();
      list = list.filter(
        (e) =>
          e.plainText.toLowerCase().includes(q) ||
          e.formattedContent?.toLowerCase().includes(q),
      );
    }

    return list;
  });

  /** 最近 5 条历史（用于快速粘贴） */
  const recentHistory = computed(() => {
    return history.value.slice(0, 5);
  });

  /** 按格式分组 */
  const groupedByFormat = computed(() => {
    const groups: Record<string, ClipboardEntry[]> = {};
    for (const entry of history.value) {
      const label = entry.format.toUpperCase();
      if (!groups[label]) groups[label] = [];
      groups[label].push(entry);
    }
    return groups;
  });

  // ═══════════════════════════════════════════
  // 初始化
  // ═══════════════════════════════════════════

  /**
   * 初始化剪贴板 store
   *
   * @param windowId - 窗口 ID
   * @param config - 可选配置
   */
  async function init(
    windowId: string,
    config?: Partial<ClipboardPanelConfig>,
  ): Promise<void> {
    if (service) {
      logger.warn('剪贴板 store 已初始化，跳过重复初始化');
      return;
    }

    isLoading.value = true;
    errorMessage.value = null;

    try {
      service = getClipboardService(windowId, config);
      await service.initialize();

      // 同步初始数据
      syncFromService();

      // 订阅服务变更事件
      unsubscribe = service.on('change', (event: ClipboardChangedEvent) => {
        handleServiceEvent(event);
      });

      isInitialized.value = true;
      logger.info('剪贴板 store 初始化完成');
    } catch (err) {
      const msg = err instanceof Error ? err.message : '剪贴板服务初始化失败';
      errorMessage.value = msg;
      logger.error(msg, err);
    } finally {
      isLoading.value = false;
    }
  }

  /** 从服务同步数据 */
  function syncFromService(): void {
    if (!service) return;
    history.value = service.getHistory();
    favorites.value = service.getFavorites();
  }

  /** 处理服务事件 */
  function handleServiceEvent(event: ClipboardChangedEvent): void {
    switch (event.action) {
      case 'copied':
      case 'synced':
      case 'pasted':
      case 'removed':
      case 'cleared':
      case 'favorited':
      case 'unfavorited':
        syncFromService();
        break;
    }
  }

  // ═══════════════════════════════════════════
  // 操作
  // ═══════════════════════════════════════════

  /**
   * 复制内容
   */
  async function copy(
    content: string,
    format?: ClipboardContentFormat,
    metadata?: Record<string, unknown>,
  ): Promise<ClipboardEntry | null> {
    if (!service) return null;

    try {
      const entry = await service.copy(content, format, metadata);
      if (entry) {
        syncFromService();
      }
      return entry;
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '复制失败';
      return null;
    }
  }

  /**
   * 粘贴内容
   */
  async function paste(entryId?: string): Promise<string | null> {
    if (!service) return null;

    try {
      const content = await service.paste(entryId);
      return content;
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '粘贴失败';
      return null;
    }
  }

  /**
   * 删除条目
   */
  function deleteEntry(entryId: string): boolean {
    if (!service) return false;
    const result = service.deleteEntry(entryId);
    if (result) syncFromService();
    return result;
  }

  /**
   * 批量删除
   */
  function deleteEntries(entryIds: string[]): number {
    if (!service) return 0;
    const count = service.deleteEntries(entryIds);
    if (count > 0) syncFromService();
    return count;
  }

  /**
   * 清空历史
   */
  function clearHistory(): void {
    if (!service) return;
    service.clearHistory();
    syncFromService();
  }

  /**
   * 切换收藏
   */
  function toggleFavorite(entryId: string): boolean {
    if (!service) return false;
    const result = service.toggleFavorite(entryId);
    if (result) syncFromService();
    return result;
  }

  /**
   * 切换面板显示
   */
  function togglePanel(): void {
    panelVisible.value = !panelVisible.value;
  }

  /**
   * 打开面板
   */
  function openPanel(): void {
    panelVisible.value = true;
  }

  /**
   * 关闭面板
   */
  function closePanel(): void {
    panelVisible.value = false;
  }

  /**
   * 搜索
   */
  function search(query: string): void {
    searchQuery.value = query;
  }

  /**
   * 设置格式过滤
   */
  function setFilter(format: ClipboardContentFormat | null): void {
    filterFormat.value = format;
  }

  /**
   * 切换仅显示收藏
   */
  function toggleFavoritesOnly(): void {
    favoritesOnly.value = !favoritesOnly.value;
  }

  /**
   * 快速粘贴最新项
   */
  async function quickPasteLast(): Promise<string | null> {
    return paste();
  }

  // ═══════════════════════════════════════════
  // 清理
  // ═══════════════════════════════════════════

  function destroy(): void {
    unsubscribe?.();
    unsubscribe = null;
    service = null;
    isInitialized.value = false;
    logger.info('剪贴板 store 已销毁');
  }

  return {
    // state
    history,
    favorites,
    panelVisible,
    searchQuery,
    filterFormat,
    favoritesOnly,
    isLoading,
    errorMessage,
    isInitialized,

    // computed
    totalCount,
    favoritesCount,
    filteredHistory,
    recentHistory,
    groupedByFormat,

    // actions
    init,
    copy,
    paste,
    deleteEntry,
    deleteEntries,
    clearHistory,
    toggleFavorite,
    togglePanel,
    openPanel,
    closePanel,
    search,
    setFilter,
    toggleFavoritesOnly,
    quickPasteLast,
    destroy,
    syncFromService,
  };
});
