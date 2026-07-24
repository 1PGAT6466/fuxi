/**
 * 伏羲 v2.1 — 全局快捷键系统
 *
 * 注册全局键盘快捷键：
 * - Cmd/Ctrl+K：打开伏羲令
 * - Cmd/Ctrl+/：打开快捷键帮助面板
 * - Cmd/Ctrl+Shift+V：打开剪贴板面板（跨窗口剪贴板）
 * - Cmd/Ctrl+1~9：切换九宫格宫位
 *
 * 使用 useEventListener 模式，组件卸载时自动清理
 */

import { onMounted, onUnmounted, type Ref, ref } from 'vue';
import { useRouter } from 'vue-router';
import { BAGUA_GRID } from '@/constants/bagua';

/** 快捷键动作类型 */
export interface ShortcutAction {
  key: string;
  /** 修饰键 */
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  /** 动作描述（用于帮助面板） */
  description: string;
  /** 动作执行 */
  handler: () => void;
}

/** 宫位路由映射（1-9 → route） */
function getGuaRoute(shortcutNum: number): string | null {
  const item = BAGUA_GRID[shortcutNum];
  if (!item) return null;
  return item.route;
}

export function useShortcuts(options?: {
  /** 打开伏羲令的回调 */
  onOpenFuxiLing?: () => void;
  /** 打开快捷键帮助面板的回调 */
  onOpenHelp?: () => void;
  /** 打开剪贴板面板的回调 */
  onOpenClipboard?: () => void;
}) {
  const router = useRouter();

  /** 快捷键帮助面板是否可见 */
  const showHelp = ref(false);

  // 键盘事件处理
  function handleKeydown(e: KeyboardEvent): void {
    // 不拦截输入框中的按键
    const target = e.target as HTMLElement;
    const tag = target.tagName.toLowerCase();
    const isInput = tag === 'input' || tag === 'textarea' || target.isContentEditable;
    if (isInput) return;

    const isCtrl = e.ctrlKey || e.metaKey;

    // Cmd/Ctrl+K — 伏羲令
    if (isCtrl && e.key === 'k') {
      e.preventDefault();
      options?.onOpenFuxiLing?.();
      return;
    }

    // Cmd/Ctrl+/ — 快捷键帮助
    if (isCtrl && e.key === '/') {
      e.preventDefault();
      showHelp.value = !showHelp.value;
      options?.onOpenHelp?.();
      return;
    }

    // Cmd/Ctrl+Shift+V — 剪贴板面板
    if (isCtrl && e.shiftKey && e.key === 'V') {
      e.preventDefault();
      options?.onOpenClipboard?.();
      return;
    }

    // Cmd/Ctrl+1~9 — 切换宫位
    if (isCtrl && /^[1-9]$/.test(e.key)) {
      e.preventDefault();
      const num = parseInt(e.key, 10);
      const route = getGuaRoute(num);
      if (route) {
        router.push(route);
      }
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
  });

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
  });

  return {
    showHelp,
  };
}

/** 快捷键列表（用于帮助面板展示） */
export const SHORTCUT_LIST: { keys: string; description: string }[] = [
  { keys: '⌘/Ctrl + K', description: '打开伏羲令全局搜索' },
  { keys: '⌘/Ctrl + /', description: '打开/关闭快捷键帮助' },
  { keys: '⌘/Ctrl + Shift + V', description: '打开剪贴板面板（历史/收藏/同步）' },
  { keys: '⌘/Ctrl + 1~9', description: '切换九宫格宫位' },
  { keys: 'Esc', description: '关闭弹窗/面板' },
  { keys: '↑↓', description: '伏羲令结果选择' },
  { keys: 'Enter', description: '确认跳转' },
];
