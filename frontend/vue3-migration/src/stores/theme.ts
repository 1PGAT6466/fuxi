/**
 * 伏羲 v2.1 — 阴阳主题系统 Pinia Store
 *
 * 功能：
 * - 阴阳双模式切换 (yang / yin)
 * - 主题偏好 localStorage 持久化
 * - 太极旋转过渡动画
 * - CSS 变量实时同步
 * - 主色调自定义
 */

import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';

/** 主题模式 */
export type ThemeMode = 'yang' | 'yin';

/** CSS 变量对象 */
export interface ThemeCssVars {
  '--fuxi-bg': string;
  '--fuxi-bg-card': string;
  '--fuxi-bg-hover': string;
  '--fuxi-bg-subtle': string;
  '--fuxi-text': string;
  '--fuxi-text-secondary': string;
  '--fuxi-text-tertiary': string;
  '--fuxi-border': string;
  '--fuxi-primary': string;
  '--fuxi-primary-light': string;
  '--fuxi-primary-gradient': string;
  '--fuxi-shadow': string;
  '--fuxi-shadow-sm': string;
  '--fuxi-shadow-lg': string;
  '--fuxi-radius': string;
  '--fuxi-input-bg': string;
  '--fuxi-input-border': string;
  '--fuxi-input-focus': string;
  '--fuxi-success': string;
  '--fuxi-error': string;
  '--fuxi-error-bg': string;
}

const THEME_STORAGE_KEY = 'fuxi-v2-theme';
const PRIMARY_COLOR_KEY = 'fuxi-primary-color';

/** 从 localStorage 加载主题偏好 */
function loadThemeMode(): ThemeMode {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'yang' || saved === 'yin') return saved;
  } catch {
    // localStorage 不可用
  }
  return 'yang';
}

/** 从 localStorage 加载主色调 */
function loadPrimaryColor(): string {
  try {
    const saved = localStorage.getItem(PRIMARY_COLOR_KEY);
    if (saved && /^#[0-9A-Fa-f]{6}$/.test(saved)) return saved;
  } catch {
    // localStorage 不可用
  }
  return '#FF6700';
}

export const useThemeStore = defineStore('theme', () => {
  // ============================================
  // State
  // ============================================
  const mode = ref<ThemeMode>(loadThemeMode());
  const primaryColor = ref<string>(loadPrimaryColor());

  // ============================================
  // Getters
  // ============================================
  const isYang = computed(() => mode.value === 'yang');
  const isYin = computed(() => mode.value === 'yin');

  /** 根据模式计算背景色 */
  const bgColor = computed(() => (isYang.value ? '#FAFAF5' : '#1A1A2E'));

  /** 根据模式计算文字色 */
  const textColor = computed(() => (isYang.value ? '#333333' : '#E0E0E0'));

  /** 返回完整的 CSS 变量对象 */
  const currentTheme = computed<ThemeCssVars>(() => {
    if (isYang.value) {
      return {
        '--fuxi-bg': '#FAFAF5',
        '--fuxi-bg-card': '#FFFFFF',
        '--fuxi-bg-hover': '#FFFCF9',
        '--fuxi-bg-subtle': '#F0EDE5',
        '--fuxi-text': '#333333',
        '--fuxi-text-secondary': '#999999',
        '--fuxi-text-tertiary': '#CCCCCC',
        '--fuxi-border': '#EEEEEE',
        '--fuxi-primary': primaryColor.value,
        '--fuxi-primary-light': '#FFF3E8',
        '--fuxi-primary-gradient': `linear-gradient(135deg, ${primaryColor.value}, #E55A2B)`,
        '--fuxi-shadow': '0 2px 16px rgba(255, 103, 0, 0.06)',
        '--fuxi-shadow-sm': '0 1px 6px rgba(0, 0, 0, 0.04)',
        '--fuxi-shadow-lg': '0 8px 32px rgba(0, 0, 0, 0.06)',
        '--fuxi-radius': '16px',
        '--fuxi-input-bg': '#FFFFFF',
        '--fuxi-input-border': '#E0E0E0',
        '--fuxi-input-focus': primaryColor.value,
        '--fuxi-success': '#34C759',
        '--fuxi-error': '#FF3B30',
        '--fuxi-error-bg': 'rgba(255, 59, 48, 0.08)',
      };
    } else {
      return {
        '--fuxi-bg': '#1A1A2E',
        '--fuxi-bg-card': '#252542',
        '--fuxi-bg-hover': '#2A2A4A',
        '--fuxi-bg-subtle': '#1E1E36',
        '--fuxi-text': '#E0E0E0',
        '--fuxi-text-secondary': '#888888',
        '--fuxi-text-tertiary': '#555555',
        '--fuxi-border': '#333355',
        '--fuxi-primary': primaryColor.value,
        '--fuxi-primary-light': 'rgba(255, 103, 0, 0.12)',
        '--fuxi-primary-gradient': `linear-gradient(135deg, ${primaryColor.value}, #E55A2B)`,
        '--fuxi-shadow': '0 2px 16px rgba(255, 103, 0, 0.12)',
        '--fuxi-shadow-sm': '0 1px 6px rgba(0, 0, 0, 0.16)',
        '--fuxi-shadow-lg': '0 8px 32px rgba(0, 0, 0, 0.22)',
        '--fuxi-radius': '16px',
        '--fuxi-input-bg': '#1E1E36',
        '--fuxi-input-border': '#333355',
        '--fuxi-input-focus': primaryColor.value,
        '--fuxi-success': '#34C759',
        '--fuxi-error': '#FF453A',
        '--fuxi-error-bg': 'rgba(255, 69, 58, 0.12)',
      };
    }
  });

  // ============================================
  // Actions
  // ============================================

  /** 切换阴阳模式（太极旋转切换动画） */
  function toggleMode(): void {
    const nextMode: ThemeMode = isYang.value ? 'yin' : 'yang';

    // 添加过渡类触发旋转动画
    const root = document.documentElement;
    root.classList.add('theme-transitioning');

    // 延迟切换以等待动画
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        mode.value = nextMode;
      });
    });

    // 移除过渡类
    setTimeout(() => {
      root.classList.remove('theme-transitioning');
    }, 600);
  }

  /** 设置主色调 */
  function setPrimaryColor(color: string): void {
    if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
      primaryColor.value = color;
      localStorage.setItem(PRIMARY_COLOR_KEY, color);
    } else {
      console.warn(`[themeStore] 无效的颜色值: ${color}，应使用 #RRGGBB 格式`);
    }
  }

  // ============================================
  // 持久化与同步
  // ============================================

  /** 监听 mode 变化，持久化到 localStorage 并同步到 DOM */
  watch(mode, (newMode) => {
    localStorage.setItem(THEME_STORAGE_KEY, newMode);
  });

  /** 监听 currentTheme 变化，实时同步 CSS 变量到 <html> */
  watch(
    currentTheme,
    (vars) => {
      const root = document.documentElement;
      for (const [key, value] of Object.entries(vars)) {
        root.style.setProperty(key, value);
      }
      // 设置 data-theme 属性
      root.setAttribute('data-theme', mode.value);
    },
    { immediate: true },
  );

  return {
    // State
    mode,
    primaryColor,
    // Getters
    isYang,
    isYin,
    bgColor,
    textColor,
    currentTheme,
    // Actions
    toggleMode,
    setPrimaryColor,
  };
});
