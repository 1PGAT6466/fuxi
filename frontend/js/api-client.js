/**
 * API Client + Token Manager + Cache + Timeout/Retry
 * 小米风格 · 性能优化版 · v1.50 统一封装
 *
 * 合并自 api-client.js + fetch-utils.js
 * - Token 管理 + sessionStorage 持久化
 * - GET 请求 30 秒缓存
 * - 超时控制（默认 15s）+ 自动重试（默认 2 次，仅 5xx）
 */

var __TK = 'fuxi_token', __UK = 'fuxi_user';
var __STORE = sessionStorage;

// API 缓存（GET 请求 30 秒有效）
var __apiCache = new Map();
var __CACHE_TTL = 30000;

// 超时与重试配置
var __DEFAULT_TIMEOUT = 15000; // 15 秒
var __DEFAULT_RETRIES = 2;

function getToken() {
  var v = __STORE.getItem(__TK);
  if (!v) return '';
  if (!/^[A-Za-z0-9._~+\/=-]+$/.test(v)) {
    __STORE.removeItem(__TK);
    return '';
  }
  return v;
}

function getUser() {
  try { return JSON.parse(__STORE.getItem(__UK) || '{}'); } catch(e) { return {}; }
}

function setAuth(token, user) {
  __STORE.setItem(__TK, token);
  __STORE.setItem(__UK, JSON.stringify(user));
}

function clearAuth() {
  __STORE.removeItem(__TK);
  __STORE.removeItem(__UK);
  __apiCache.clear();
}

function __getCacheKey(url, opt) {
  return url + (opt && opt.method ? ':' + opt.method : '');
}

/**
 * 带超时的 fetch（内部辅助函数）
 * @param {string} url
 * @param {object} options - fetch options
 * @param {number} timeoutMs - 超时毫秒
 * @returns {Promise<Response>}
 */
async function __fetchWithTimeout(url, options, timeoutMs) {
  var controller = new AbortController();
  var timer = setTimeout(function() { controller.abort(); }, timeoutMs);
  var fetchOpts = Object.assign({}, options || {}, { signal: controller.signal });
  try {
    var resp = await fetch(url, fetchOpts);
    clearTimeout(timer);
    return resp;
  } catch (e) {
    clearTimeout(timer);
    if (e.name === 'AbortError') {
      throw new Error('请求超时 (' + timeoutMs + 'ms): ' + url);
    }
    throw e;
  }
}

/**
 * 统一 API 请求
 * @param {string} url
 * @param {object} opt - { method, body, headers, timeout, retries, useCache, cacheTime }
 * @returns {Promise<any>}
 */
async function api(url, opt) {
  var t = getToken();
  if (!opt) opt = {};
  if (!opt.headers) opt.headers = {};
  if (t) opt.headers['Authorization'] = 'Bearer ' + t;

  var timeoutMs = opt.timeout || __DEFAULT_TIMEOUT;
  var retries = opt.retries !== undefined ? opt.retries : __DEFAULT_RETRIES;

  // GET 请求缓存
  var isGet = !opt.method || opt.method === 'GET';
  if (isGet) {
    var cacheKey = __getCacheKey(url, opt);
    var cached = __apiCache.get(cacheKey);
    if (cached && Date.now() - cached.time < (opt.cacheTime || __CACHE_TTL)) {
      return cached.data;
    }
  }

  if (opt.body && typeof opt.body === 'object' && !(opt.body instanceof FormData) && !opt.headers['Content-Type']) {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(opt.body);
  }

  // 带重试的请求
  var lastErr = null;
  for (var attempt = 0; attempt <= retries; attempt++) {
    try {
      var r = await __fetchWithTimeout(url, opt, timeoutMs);

      // 服务器错误可重试
      if (r.status >= 500 && attempt < retries) {
        await new Promise(function(resolve) { setTimeout(resolve, 1000 * (attempt + 1)); });
        continue;
      }

      if (r.status === 401) {
        clearAuth();
        // P1-10: 确保登录页可见，主应用隐藏（防御性写法）
        try { showLogin(); } catch(e) {
          document.getElementById('loginPage').style.display = 'flex';
          document.getElementById('mainApp').style.display = 'none';
        }
        throw new Error('Not logged in');
      }
      if (r.status === 403) { toast('没有权限', 'error'); throw new Error('Forbidden'); }
      if (!r.ok) throw new Error('请求失败: ' + r.status);

      var data = await r.json();

      // P2-7 fix + v1.50 unified: 处理后端 {status: 'success'|'error', data: {...}} 统一格式
      if (data && data.status === 'error' && data.message) {
        throw new Error(data.message);
      }

      // v1.50: 统一格式自动解包 data 字段，同时保留顶层字段用于兼容
      // 前端代码可以继续用 data.answer / data.files / data.results 等旧路径
      // 也可以开始迁移到 data.data.xxx 新路径
      if (data && data.status === 'success' && data.data && typeof data.data === 'object') {
        // 将 data.data 中的字段展开到顶层，保持向后兼容
        // 但也保留 data.data 让新代码可以逐步迁移
        for (var key in data.data) {
          if (data.data.hasOwnProperty(key) && !(key in data)) {
            data[key] = data.data[key];
          }
        }
        // 分页兼容: {data: {items: [...]}} → data.files = data.items
        if (data.items && !data.files) {
          data.files = data.items;
        }
      }

      // 缓存 GET 响应
      if (isGet) {
        __apiCache.set(__getCacheKey(url, opt), { data: data, time: Date.now() });
      }

      return data;
    } catch (e) {
      lastErr = e;
      // 超时或网络错误可重试
      if (attempt < retries && (e.message.indexOf('超时') >= 0 || e.name === 'TypeError')) {
        await new Promise(function(resolve) { setTimeout(resolve, 1000 * (attempt + 1)); });
        continue;
      }
      throw e;
    }
  }
  throw lastErr || new Error('请求失败');
}

// 清除指定 URL 缓存
function invalidateCache(urlPattern) {
  if (!urlPattern) {
    __apiCache.clear();
    return;
  }
  for (var key of __apiCache.keys()) {
    if (key.indexOf(urlPattern) >= 0) __apiCache.delete(key);
  }
}
