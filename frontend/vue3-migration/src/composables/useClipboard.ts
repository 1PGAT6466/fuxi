/**
 * 伏羲 v2.1 — 剪贴板 Composable (useClipboard)
 *
 * 提供在任意组件中集成剪贴板能力的便捷 Hook。
 * 封装 ClipboardService + ClipboardStore，提供简化的 API。
 *
 * 用法：
 * ```vue
 * <script setup>
 * const { copy, paste, panelVisible, togglePanel } = useClipboard({ windowId: 'my-window' });
 * </script>
 * ```
 *
 * @module useClipboard
 */

import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useClipboardStore } from '@/services/clipboard/store';
import type {
  ClipboardEntry,
  ClipboardContentFormat,
  ClipboardPanelConfig,
} from '@/services/clipboard/types';

/**
 * 剪贴板组合函数
 *
 * @param options.windowId - 当前窗口 ID（必需，用于跨窗口同步标识）
 * @param options.config - 剪贴板配置（可选）
 */
export function useClipboard(options: {
  windowId: string;
  config?: Partial<ClipboardPanelConfig>;
}) {
  const store = useClipboardStore();
  const isReady = ref(false);

  // ══════════════════════════════════════
  // 初始化
  // ══════════════════════════════════════

  onMounted(async () => {
    if (!store.isInitialized) {
      await store.init(options.windowId, options.config);
    }
    isReady.value = true;
  });

  onUnmounted(() => {
    // 不销毁全局 store，因为它是单例
  });

  // ══════════════════════════════════════
  // 基础操作
  // ══════════════════════════════════════

  /**
   * 复制文本到剪贴板
   *
   * @param content - 要复制的内容
   * @param format - 内容格式（默认 text）
   * @returns 创建的剪贴板条目
   */
  async function copy(
    content: string,
    format?: ClipboardContentFormat,
  ): Promise<ClipboardEntry | null> {
    return store.copy(content, format);
  }

  /**
   * 粘贴剪贴板内容
   *
   * @param entryId - 可选：指定条目 ID
   * @returns 粘贴的文本内容
   */
  async function paste(entryId?: string): Promise<string | null> {
    return store.paste(entryId);
  }

  /**
   * 复制并写入系统剪贴板
   * 等同于 Ctrl+C 的快捷键效果
   */
  async function copyToSystem(
    content: string,
    format?: ClipboardContentFormat,
  ): Promise<ClipboardEntry | null> {
    return store.copy(content, format);
  }

  /**
   * 从系统剪贴板读取并添加到历史
   */
  async function readFromSystem(): Promise<string | null> {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        await store.copy(text, 'text');
        return text;
      }
      return null;
    } catch {
      return null;
    }
  }

  // ══════════════════════════════════════
  // 面板操作
  // ══════════════════════════════════════

  /** 面板可见性 */
  const panelVisible = computed({
    get: () => store.panelVisible,
    set: (val: boolean) => {
      if (val) store.openPanel();
      else store.closePanel();
    },
  });

  /** 切换面板显示 */
  function togglePanel(): void {
    store.togglePanel();
  }

  /** 打开面板 */
  function openPanel(): void {
    store.openPanel();
  }

  /** 关闭面板 */
  function closePanel(): void {
    store.closePanel();
  }

  // ══════════════════════════════════════
  // 历史 & 收藏
  // ══════════════════════════════════════

  /** 全部历史 */
  const history = computed(() => store.filteredHistory);

  /** 最近 5 条 */
  const recentEntries = computed(() => store.recentHistory);

  /** 收藏条目 */
  const favorites = computed(() => store.favorites);

  /** 历史总数 */
  const totalCount = computed(() => store.totalCount);

  /** 搜索历史 */
  function search(query: string): void {
    store.search(query);
  }

  /** 删除条目 */
  function removeEntry(entryId: string): void {
    store.deleteEntry(entryId);
  }

  /** 清空历史 */
  function clearAll(): void {
    store.clearHistory();
  }

  /** 切换收藏 */
  function toggleFavorite(entryId: string): boolean {
    return store.toggleFavorite(entryId);
  }

  // ══════════════════════════════════════
  // 快捷方法
  // ══════════════════════════════════════

  /**
   * 快速粘贴最新条目
   */
  async function quickPaste(): Promise<string | null> {
    return store.quickPasteLast();
  }

  /**
   * 粘贴指定条目
   */
  async function pasteEntry(entryId: string): Promise<string | null> {
    return store.paste(entryId);
  }

  return {
    // state
    store,
    isReady,
    panelVisible,

    // computed
    history,
    recentEntries,
    favorites,
    totalCount,

    // copy/paste
    copy,
    paste,
    copyToSystem,
    readFromSystem,

    // panel
    togglePanel,
    openPanel,
    closePanel,

    // history
    search,
    removeEntry,
    clearAll,
    toggleFavorite,

    // quick
    quickPaste,
    pasteEntry,
  };
}
