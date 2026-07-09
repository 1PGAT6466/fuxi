/**
 * 伏羲 v2.1 — TokenManager 统一令牌管理
 *
 * 集中管理 JWT token 的存储、解析、过期检测和刷新逻辑。
 * 将散落在 router 和 store 中的重复代码统一到一个入口。
 *
 * 职责：
 * - 读写 localStorage token（KEY 由 constants/storage-keys.ts 统一导出）
 * - 解析 JWT exp
 * - 过期检测（5 分钟余量）
 * - 带并发锁的 token 刷新
 *
 * 注意：refreshToken() 是全局唯一的 token 刷新入口。
 * auth.ts 中的 refreshToken() 和 router/index.ts 中的刷新逻辑均委托给此方法。
 */

import { TOKEN_KEY, TOKEN_EXPIRY_KEY } from '@/constants/storage-keys';

// ============================
// 常量
// ============================

/** 过期前多少毫秒视作"即将过期" */
const REFRESH_MARGIN_MS = 5 * 60 * 1000;

// ============================
// 并发刷新锁
// ============================

let refreshPromise: Promise<string | null> | null = null;

// ============================
// TokenManager 类
// ============================

class TokenManager {
  // ────────── 读写 token ──────────

  /** 统一读取 token */
  static getToken(): string {
    return localStorage.getItem(TOKEN_KEY) || '';
  }

  /** 统一写入 token 及到期时间 */
  static setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
    const expiry = TokenManager.parseExpiry(token);
    if (expiry) {
      localStorage.setItem(TOKEN_EXPIRY_KEY, String(expiry));
    }
  }

  /** 统一清除 token 数据 */
  static clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    // 兼容旧 key
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
  }

  // ────────── 解析 ──────────

  /** 解析 JWT token 中的 exp 字段，返回毫秒时间戳 */
  static parseExpiry(token: string): number | null {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(base64));
      return payload.exp ? payload.exp * 1000 : null;
    } catch (err) {
      console.warn('[TokenManager] 解析 token 过期时间失败', err);
      return null;
    }
  }

  // ────────── 过期检测 ──────────

  /** token 是否已过期 */
  static isExpired(token: string): boolean {
    const expiry = TokenManager.parseExpiry(token);
    if (!expiry) return false;
    return Date.now() >= expiry;
  }

  /** token 是否即将在 5 分钟内过期（支持空参数：从 localStorage 读） */
  static isExpiringSoon(optionalToken?: string): boolean {
    const token = optionalToken ?? TokenManager.getToken();
    const expiry = TokenManager.parseExpiry(token);
    if (!expiry) return false;
    return Date.now() + REFRESH_MARGIN_MS >= expiry;
  }

  // ────────── 刷新（带并发锁） ──────────

  /**
   * 安全刷新 token
   * - 使用 Promise 锁防止多个调用者同时刷新
   * - 返回新 token 或 null
   */
  static async refreshToken(): Promise<string | null> {
    // 如果已有刷新任务进行中，返回同一个 promise
    if (refreshPromise) {
      return refreshPromise;
    }

    refreshPromise = (async () => {
      try {
        // R5 蓝队修复：使用原生 fetch 保留（因为 apiClient 拦截器依赖 TokenManager.refreshToken()，
        // 直接用 apiClient 会导致循环调用）。但统一错误处理格式。
        const currentToken = TokenManager.getToken();
        const response = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: currentToken ? `Bearer ${currentToken}` : '',
          },
        });

        if (!response.ok) {
          throw new Error(`刷新失败 (${response.status})`);
        }

        const data = await response.json();
        // R5: 统一处理 {status, data, message} 和 {code, data, message} 两种格式
        if (data.status === 'error') {
          throw new Error(data.message || 'Token 刷新失败');
        }
        if (data.code !== undefined && data.code !== 0 && data.code !== 200) {
          throw new Error(data.message || 'Token 刷新失败');
        }

        const newToken = data.data?.token || data.token;
        if (!newToken) {
          throw new Error('刷新响应不含 token');
        }

        // 持久化
        TokenManager.setToken(newToken);

        return newToken;
      } catch (error) {
        console.warn('[TokenManager] Token 刷新失败:', error);
        return null;
      } finally {
        refreshPromise = null;
      }
    })();

    return refreshPromise;
  }

  // ────────── 刷新锁状态（仅调试用） ──────────

  /** 检查刷新锁是否正在被持有 */
  static get isRefreshing(): boolean {
    return refreshPromise !== null;
  }
}

// ============================
// 单例导出
// ============================

export default TokenManager;
