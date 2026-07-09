/**
 * 伏羲 v2.1 — 认证 API 封装
 *
 * 提供 login / refreshToken / logout 三个核心接口
 */

import TokenManager from '@/utils/TokenManager';

// ============================================
// 类型定义
// ============================================

export interface LoginParams {
  username: string;
  password: string;
  role: 'admin' | 'user';
}

export interface LoginResult {
  token: string;
  user: {
    id: number | string;
    username: string;
    display_name?: string;
    role: 'admin' | 'user';
    avatar?: string;
    email?: string;
  };
}

// ============================================
// API 函数
// ============================================

/**
 * 用户登录
 * @param username 用户名
 * @param password 密码
 * @param role 角色选择
 * @returns 登录结果（含 token 和用户信息）
 */
export async function login(
  username: string,
  password: string,
  role: 'admin' | 'user',
): Promise<LoginResult> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password, role }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || errorData.detail || `登录失败 (${response.status})`);
  }

  const data = await response.json();

  // 后端返回 {token, username, role, display_name}
  if (!data.token) {
    throw new Error(data.detail || data.message || '登录失败：服务器未返回 token');
  }

  const userRole = data.role || 'user';
  if (userRole !== role) {
    throw new Error(
      role === 'admin'
        ? '该账号不是管理员账号，请切换到普通用户登录'
        : '该账号是管理员账号，请切换到管理员登录',
    );
  }

  return {
    token: data.token,
    user: {
      id: 0,
      username: data.username,
      display_name: data.display_name || data.username,
      role: userRole,
    },
  };
}

/**
 * 刷新 token（统一入口 — 委托给 TokenManager）
 * @returns 新的 token 字符串
 */
export async function refreshToken(): Promise<string> {
  const newToken = await TokenManager.refreshToken();
  if (!newToken) {
    throw new Error('Token 刷新失败，请重新登录');
  }
  return newToken;
}

/**
 * 退出登录
 */
export async function logout(): Promise<void> {
  const token = TokenManager.getToken();

  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
    });
  } catch (err) {
    console.error('[Auth API] 退出登录请求失败', err);
    // 即使后端请求失败，仍执行本地清除
  }
}
