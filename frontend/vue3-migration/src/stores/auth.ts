/**
 * 伏羲 v2.1 — 认证 Store (Pinia)
 *
 * 功能：
 * - 状态：user, token, isAuthenticated, role
 * - 动作：login(), logout(), refreshToken()
 * - 持久化 token 到 localStorage
 * - token 过期自动刷新
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import * as authApi from '@/api/auth';
import TokenManager from '@/utils/TokenManager';
import { createLogger } from '@/utils/logger';
import type { UserInfo } from '@/types';
import type { LoginResult } from '@/api/auth';

const logger = createLogger('AuthStore');

// ────────────────────────────────────────────
// 模块级：自动刷新定时器
// ────────────────────────────────────────────
let refreshTimer: ReturnType<typeof setInterval> | null = null;

function startAutoRefresh(refreshFn: () => Promise<void>): void {
  stopAutoRefresh();
  refreshTimer = setInterval(
    async () => {
      const token = TokenManager.getToken();
      if (!token) {
        stopAutoRefresh();
        return;
      }
      if (TokenManager.isExpiringSoon(token)) {
        try {
          await refreshFn();
        } catch {
          stopAutoRefresh();
        }
      }
    },
    2 * 60 * 1000,
  );
}

function stopAutoRefresh(): void {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

// ============================================
// Pinia Store
// ============================================

export const useAuthStore = defineStore('auth', () => {
  // ─── State ───
  const token = ref<string>(TokenManager.getToken());
  const user = ref<UserInfo | null>(null);
  const loading = ref<boolean>(false);

  // ─── Getters ───
  const isAuthenticated = computed(() => !!token.value);
  const role = computed(() => user.value?.role ?? null);
  const isAdmin = computed(() => user.value?.role === 'admin');

  // ─── Actions ───

  /**
   * 登录
   */
  async function login(
    username: string,
    password: string,
    loginRole: 'admin' | 'user' = 'user',
  ): Promise<LoginResult> {
    loading.value = true;
    try {
      const result = await authApi.login(username, password, loginRole);
      token.value = result.token;
      user.value = result.user;
      TokenManager.setToken(result.token);
      startAutoRefresh(doRefreshToken);
      return result;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 内部：执行 token 刷新
   */
  async function doRefreshToken(): Promise<string> {
    try {
      const newToken = await authApi.refreshToken();
      token.value = newToken;
      TokenManager.setToken(newToken);
      return newToken;
    } catch {
      logout();
      throw new Error('Token 刷新失败，已退出登录');
    }
  }

  /**
   * 刷新 token（公开方法）
   */
  async function refreshToken(): Promise<string> {
    return doRefreshToken();
  }

  /**
   * 退出登录
   */
  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } catch (err) {
      logger.error('退出登录失败', err);
    } finally {
      token.value = '';
      user.value = null;
      TokenManager.clearToken();
      stopAutoRefresh();
    }
  }

  /**
   * 获取当前用户信息
   */
  async function fetchUser(): Promise<UserInfo> {
    loading.value = true;
    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          Authorization: `Bearer ${token.value}`,
        },
      });
      if (!response.ok) {
        throw new Error('获取用户信息失败');
      }
      const data = await response.json();
      if (data.code !== 0 && data.code !== 200) {
        throw new Error(data.message || '获取用户信息失败');
      }
      user.value = data.data;
      return data.data;
    } catch {
      await logout();
      throw new Error('获取用户信息失败');
    } finally {
      loading.value = false;
    }
  }

  /**
   * 初始化：从 localStorage 恢复 token 后加载用户信息
   */
  async function initAuth(): Promise<void> {
    if (!token.value) return;
    loading.value = true;
    try {
      // 如果 token 已过期，直接清除
      if (TokenManager.isExpiringSoon(token.value)) {
        try {
          await doRefreshToken();
        } catch {
          await logout();
          return;
        }
      }
      await fetchUser();
      startAutoRefresh(doRefreshToken);
    } finally {
      loading.value = false;
    }
  }

  return {
    // State
    token,
    user,
    loading,
    // Getters
    isAuthenticated,
    role,
    isAdmin,
    // Actions
    login,
    logout,
    refreshToken: doRefreshToken,
    isTokenExpiringSoon: () => TokenManager.isExpiringSoon(token.value),
    fetchUser,
    initAuth,
  };
});
