/**
 * @fileoverview API 客户端 + 令牌管理
 * 提供统一的 fetch 封装，自动附加 JWT 认证
 * @module api-client
 */

const TK = '***', UK = '***';
const STORE = sessionStorage;

/**
 * @returns {string} 当前 JWT Token
 */
function getToken() { return STORE.getItem(TK) || ''; }

/**
 * @returns {{username?:string, role?:string, display_name?:string}}
 */
function getUser() {
  try { return JSON.parse(STORE.getItem(UK) || '{}'); } catch(e) { return {}; }
}

/**
 * 保存认证令牌
 * @param {string} token
 * @param {{username:string, role:string, display_name?:string}} user
 */
function setAuth(token, user) {
  STORE.setItem(TK, token);
  STORE.setItem(UK, JSON.stringify(user));
}

/** 清除认证 */
function clearAuth() {
  STORE.removeItem(TK);
  STORE.removeItem(UK);
}

/**
 * 统一 API 调用
 * @param {string} url - API 路径 (如 '/api/search')
 * @param {RequestInit} [opt] - fetch 配置
 * @returns {Promise<any>} JSON 响应
 */
async function api(url, opt) {
  const t = getToken();
  opt = opt || {};
  opt.headers = opt.headers || {};
  // Token 安全校验：只允许纯 ASCII base64url 字符
  if (t && /^[A-Za-z0-9._~+\/=]+$/.test(t)) {
    opt.headers['Authorization'] = 'Bearer ' + t;
  }
  if (opt.body && typeof opt.body === 'object' && !opt.headers['Content-Type']) {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(opt.body);
  }
  const r = await fetch(url, opt);
  if (r.status === 401) { clearAuth(); showLogin(); throw new Error('未登录'); }
  if (r.status === 403) { toast('无权限访问', 'error'); throw new Error('无权限'); }
  if (!r.ok) throw new Error('请求失败: ' + r.status);
  return r.json();
}
