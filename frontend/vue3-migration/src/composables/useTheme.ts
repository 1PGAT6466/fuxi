/**
 * useTheme — 主题管理 composable
 *
 * 功能：
 * - 桥接到 theme.ts Pinia Store 的 yang/yin 双模式
 * - 对外提供 light/dark/actualTheme 兼容 API
 * - yang → light, yin → dark 映射
 * - 注入 Element Plus 暗色模式 CSS 变量
 * - 保持与 MainLayout.vue 等现有组件的 API 兼容
 */

import { computed, watchEffect } from 'vue';
import { useThemeStore } from '@/stores/theme';

// ============================================
// Element Plus 暗色模式 CSS 变量模板
// ============================================
// 参考 Element Plus 官方 dark/css-vars.css，
// 手动注入到 document.documentElement.style 以同步暗色模式

/** Element Plus 暗色模式覆盖变量组 */
interface ElThemeOverrides {
  '--el-bg-color'?: string;
  '--el-bg-color-page'?: string;
  '--el-bg-color-overlay'?: string;
  '--el-text-color-primary'?: string;
  '--el-text-color-regular'?: string;
  '--el-text-color-secondary'?: string;
  '--el-text-color-placeholder'?: string;
  '--el-border-color'?: string;
  '--el-border-color-light'?: string;
  '--el-border-color-lighter'?: string;
  '--el-border-color-extra-light'?: string;
  '--el-border-color-dark'?: string;
  '--el-fill-color'?: string;
  '--el-fill-color-light'?: string;
  '--el-fill-color-lighter'?: string;
  '--el-fill-color-blank'?: string;
  '--el-color-primary-light-3'?: string;
  '--el-color-primary-light-5'?: string;
  '--el-color-primary-light-7'?: string;
  '--el-color-primary-light-8'?: string;
  '--el-color-primary-light-9'?: string;
  '--el-color-primary-dark-2'?: string;
  '--el-mask-color'?: string;
  '--el-box-shadow'?: string;
  '--el-box-shadow-light'?: string;
  '--el-box-shadow-lighter'?: string;
  '--el-box-shadow-dark'?: string;
  '--el-color-white'?: string;
  '--el-color-black'?: string;
  [key: string]: string | undefined;
}

const EL_DARK_VARS: ElThemeOverrides = {
  '--el-bg-color': '#141414',
  '--el-bg-color-page': '#0a0a0a',
  '--el-bg-color-overlay': '#1d1e1f',
  '--el-text-color-primary': '#E5EAF3',
  '--el-text-color-regular': '#CFD3DC',
  '--el-text-color-secondary': '#A3A6AD',
  '--el-text-color-placeholder': '#8D9095',
  '--el-border-color': '#363637',
  '--el-border-color-light': '#2B2B2C',
  '--el-border-color-lighter': '#242525',
  '--el-border-color-extra-light': '#1E1F20',
  '--el-border-color-dark': '#424243',
  '--el-fill-color': '#303030',
  '--el-fill-color-light': '#262727',
  '--el-fill-color-lighter': '#2B2B2C',
  '--el-fill-color-blank': '#141414',
  '--el-mask-color': 'rgba(0, 0, 0, 0.8)',
  '--el-box-shadow': '0px 12px 32px 4px rgba(0, 0, 0, .36), 0px 8px 20px 3px rgba(0, 0, 0, .26)',
  '--el-box-shadow-light': '0px 0px 12px rgba(0, 0, 0, .12)',
  '--el-box-shadow-lighter': '0px 0px 6px rgba(0, 0, 0, .12)',
  '--el-box-shadow-dark':
    '0px 16px 48px 4px rgba(0, 0, 0, .36), 0px 12px 24px 5px rgba(0, 0, 0, .3), 0px 0px 8px 1px rgba(0, 0, 0, .24)',
  '--el-color-white': '#141414',
  '--el-color-black': '#141414',
};

// 基础 Element Plus CSS 变量键值对 — 暗色模式下需要反转的变量
// 使用 Element Plus 2.x 标准暗色模式变量集合
const EL_VAR_KEYS = Object.freeze([
  '--el-bg-color',
  '--el-bg-color-page',
  '--el-bg-color-overlay',
  '--el-text-color-primary',
  '--el-text-color-regular',
  '--el-text-color-secondary',
  '--el-text-color-placeholder',
  '--el-border-color',
  '--el-border-color-light',
  '--el-border-color-lighter',
  '--el-border-color-extra-light',
  '--el-border-color-dark',
  '--el-fill-color',
  '--el-fill-color-light',
  '--el-fill-color-lighter',
  '--el-fill-color-blank',
  '--el-mask-color',
  '--el-box-shadow',
  '--el-box-shadow-light',
  '--el-box-shadow-lighter',
  '--el-box-shadow-dark',
  '--el-color-white',
  '--el-color-black',
] as const);

/**
 * 应用 / 移除 Element Plus 暗色模式 CSS 变量
 * @param isDark 是否启用暗色模式
 */
function applyElDarkMode(isDark: boolean): void {
  const root = document.documentElement;
  if (isDark) {
    // Element Plus 原生暗色模式 class
    root.classList.add('dark');
    // 注入暗色模式 CSS 变量覆盖
    for (const [key, value] of Object.entries(EL_DARK_VARS)) {
      if (value !== undefined) {
        root.style.setProperty(key, value);
      }
    }
    // 设置 color-scheme 告知浏览器
    root.style.setProperty('color-scheme', 'dark');
  } else {
    // 移除 Element Plus 暗色模式 class
    root.classList.remove('dark');
    // 移除暗色模式变量 — 恢复 Element Plus 默认浅色值
    for (const key of EL_VAR_KEYS) {
      root.style.removeProperty(key);
    }
    root.style.removeProperty('color-scheme');
  }
}

// ============================================
// 模块级初始化标志 — 确保只在首次注入
// ============================================
let elDarkModeInitialized = false;

type Theme = 'light' | 'dark';
type ThemePreference = Theme | 'system';

/** 获取系统偏好主题 */
export function getSystemTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function useTheme() {
  const themeStore = useThemeStore();

  /** 当前实际主题：yang→light, yin→dark */
  const actualTheme = computed<Theme>(() => (themeStore.isYang ? 'light' : 'dark'));

  /** 用户偏好：统一为 ThemePreference（系统跟随暂不支持，固定为手动） */
  const preference = computed<ThemePreference>(() =>
    themeStore.mode === 'yang' ? 'light' : 'dark',
  );

  /** 是否为暗色 */
  const isDark = computed(() => themeStore.isYin);

  // 首次初始化：监听 isDark 变化并同步 Element Plus 变量
  if (!elDarkModeInitialized) {
    elDarkModeInitialized = true;
    // 使用 watchEffect 自动响应主题变化
    watchEffect(() => {
      applyElDarkMode(isDark.value);
    });
  }

  /** 设置主题偏好 (兼容旧 API) */
  function setTheme(value: ThemePreference): void {
    if (value === 'light') {
      if (themeStore.isYin) themeStore.toggleMode();
    } else if (value === 'dark') {
      if (themeStore.isYang) themeStore.toggleMode();
    }
    // 'system' 不处理（暂不支持）
  }

  /** 切换 light/dark（兼容旧 API） */
  function toggleTheme(): void {
    themeStore.toggleMode();
  }

  return {
    preference,
    actualTheme,
    systemIsDark: computed(() => getSystemTheme() === 'dark'),
    isDark,
    setTheme,
    toggleTheme,
  };
}
