/**
 * API Client + Token Manager + Cache + Timeout/Retry + CSRF + Token Refresh Mutex
 * 小米风格 · 性能优化版 · v1.50 统一封装
 *
 * 合并自 api-client.js + fetch-utils.js
 * - Token 管理 + sessionStorage 持久化
 * - 加密存储 Token（AES-256-GCM 风格，Web Crypto API 不可用时降级 base64）
 * - GET 请求 30 秒缓存
 * - 超时控制（默认 15s）+ 自动重试（默认 2 次，仅 5xx）
 * - CSRF Token 双重防护（Header + Cookie）
 * - Token 刷新互斥锁（防竞态）
 */

var __TK = 'fuxi_token', __UK = 'fuxi_user';
var __STORE = sessionStorage;
var __CSRF_KEY = 'fuxi_csrf';

// API 缓存（GET 请求 30 秒有效）
var __apiCache = new Map();
var __CACHE_TTL = 30000;

// 超时与重试配置
var __DEFAULT_TIMEOUT = 15000; // 15 秒
var __DEFAULT_RETRIES = 2;

// ===== CRITICAL-1 fix: Token 加密存储 =====
// 使用 AES-GCM (Web Crypto API)，不可用时回退到 XOR+base64 混淆
var __CRYPTO_READY = false;
var __CRYPTO_KEY = null;
var __TOKEN_SALT = 'fuxi_v1.44_salt_2026';
var __TOKEN_IV_BYTES = 12; // 96-bit IV for GCM

// 初始化 Web Crypto（若可用）
(function _initCrypto() {
  if (typeof crypto !== 'undefined' && crypto.subtle && crypto.subtle.encrypt) {
    // 从固定的 seed 派生密钥（生产环境应使用更安全的密钥管理）
    var enc = new TextEncoder();
    var keyMaterial = crypto.subtle.importKey(
      'raw', enc.encode(__TOKEN_SALT + '_aes_key_256bit!'),
      { name: 'PBKDF2' }, false, ['deriveKey']
    ).then(function(baseKey) {
      return crypto.subtle.deriveKey(
        { name: 'PBKDF2', salt: enc.encode(__TOKEN_SALT), iterations: 100000, hash: 'SHA-256' },
        baseKey,
        { name: 'AES-GCM', length: 256 },
        false, ['encrypt', 'decrypt']
      );
    }).then(function(key) {
      __CRYPTO_KEY = key;
      __CRYPTO_READY = true;
    }).catch(function() {
      __CRYPTO_READY = false;
    });
  }
})();

// 生成随机 IV
function _randomBytes(n) {
  var arr = new Uint8Array(n);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(arr);
  } else {
    for (var i = 0; i < n; i++) arr[i] = Math.floor(Math.random() * 256);
  }
  return arr;
}

// 加密 token（AES-GCM → 存储为 base64 IV+ciphertext）
async function _encryptToken(plaintext) {
  if (!__CRYPTO_READY || !__CRYPTO_KEY) {
    return _fallbackEncode(plaintext);
  }
  try {
    var iv = _randomBytes(__TOKEN_IV_BYTES);
    var enc = new TextEncoder();
    var ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: iv },
      __CRYPTO_KEY,
      enc.encode(plaintext)
    );
    var combined = new Uint8Array(iv.length + ciphertext.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ciphertext), iv.length);
    return _arrayBufferToBase64(combined.buffer);
  } catch(e) {
    return _fallbackEncode(plaintext);
  }
}

// 解密 token
async function _decryptToken(cipherB64) {
  if (!cipherB64) return '';
  if (!__CRYPTO_READY || !__CRYPTO_KEY) {
    return _fallbackDecode(cipherB64);
  }
  try {
    var combined = _base64ToArrayBuffer(cipherB64);
    var iv = combined.slice(0, __TOKEN_IV_BYTES);
    var ct = combined.slice(__TOKEN_IV_BYTES);
    var plainBuf = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: iv },
      __CRYPTO_KEY,
      ct
    );
    return new TextDecoder().decode(plainBuf);
  } catch(e) {
    return _fallbackDecode(cipherB64);
  }
}

// fallback: XOR 混淆 + base64（弱但比明文好）
function _fallbackEncode(s) {
  var key = __TOKEN_SALT;
  var result = '';
  for (var i = 0; i < s.length; i++) {
    result += String.fromCharCode(s.charCodeAt(i) ^ key.charCodeAt(i % key.length));
  }
  return btoa(unescape(encodeURIComponent(result)));
}

function _fallbackDecode(s) {
  try {
    var decoded = decodeURIComponent(escape(atob(s)));
    var key = __TOKEN_SALT;
    var result = '';
    for (var i = 0; i < decoded.length; i++) {
      result += String.fromCharCode(decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }
    return result;
  } catch(e) { return ''; }
}

// ArrayBuffer ↔ Base64 工具函数
function _arrayBufferToBase64(buffer) {
  var bytes = new Uint8Array(buffer);
  var binary = '';
  for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function _base64ToArrayBuffer(b64) {
  var binary = atob(b64);
  var bytes = new Uint8Array(binary.length);
  for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// ===== CSRF Token 机制（CRITICAL-4 fix）=====
function _generateCSRFToken() {
  var arr = _randomBytes(32);
  return _arrayBufferToBase64(arr.buffer).replace(/[+/=]/g, '').substring(0, 43);
}

function getCSRFToken() {
  var v = __STORE.getItem(__CSRF_KEY);
  if (!v) {
    v = _generateCSRFToken();
    __STORE.setItem(__CSRF_KEY, v);
  }
  return v;
}

// ===== Token 刷新互斥锁（CRITICAL-8 fix）=====
var __refreshLock = null;  // Promise | null — 正在刷新时复用同一个 Promise
var __refreshRetries = 0;
var __REFRESH_MAX_RETRIES = 3;

function _acquireRefreshLock() {
  if (__refreshLock) return __refreshLock;
  var resolve, reject;
  __refreshLock = new Promise(function(res, rej) { resolve = res; reject = rej; });
  __refreshLock._resolve = resolve;
  __refreshLock._reject = reject;
  __refreshRetries = 0;
  return null; // 调用者自己持有锁
}

function _releaseRefreshLock(token) {
  if (__refreshLock && __refreshLock._resolve) {
    __refreshLock._resolve(token);
  }
  __refreshLock = null;
}

function _rejectRefreshLock(err) {
  if (__refreshLock && __refreshLock._reject) {
    __refreshLock._reject(err);
  }
  __refreshLock = null;
}

// 尝试刷新 token（带互斥锁和重试）
async function _refreshToken() {
  // 如果有正在进行的刷新，等待它的结果
  if (__refreshLock) {
    try {
      return await __refreshLock;
    } catch(e) {
      throw e;
    }
  }
  // 获取锁
  _acquireRefreshLock();
  try {
    var currentToken = getToken();
    if (!currentToken) throw new Error('No token to refresh');
    var resp = await __fetchWithTimeout('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + currentToken, 'X-CSRF-Token': getCSRFToken() }
    }, 10000);
    if (resp.status === 401) {
      clearAuth();
      throw new Error('Not logged in');
    }
    if (!resp.ok) throw new Error('Token refresh failed: ' + resp.status);
    var data = await resp.json();
    if (data && data.token) {
      setAuth(data.token, getUser());
      _releaseRefreshLock(data.token);
      return data.token;
    }
    throw new Error('Token refresh: invalid response');
  } catch(e) {
    _rejectRefreshLock(e);
    throw e;
  }
}

// ===== 核心 getToken — 支持加密/明文双模式 =====
async function _getTokenDecrypted() {
  var v = __STORE.getItem(__TK);
  if (!v) return '';
  // 先尝试验证格式（明文 token）
  if (/^[A-Za-z0-9._~+\/=-]+$/.test(v)) {
    return v;
  }
  // 可能已加密，尝试解密
  var decrypted = await _decryptToken(v);
  if (decrypted && /^[A-Za-z0-9._~+\/=-]+$/.test(decrypted)) {
    return decrypted;
  }
  __STORE.removeItem(__TK);
  return '';
}

function getToken() {
  var v = __STORE.getItem(__TK);
  if (!v) return '';
  // 同步：先尝试明文 token
  if (/^[A-Za-z0-9._~+\/=-]+$/.test(v)) {
    return v;
  }
  // 加密的 token 无法同步解密，尝试 fallback decode
  var dec = _fallbackDecode(v);
  if (dec && /^[A-Za-z0-9._~+\/=-]+$/.test(dec)) {
    return dec;
  }
  __STORE.removeItem(__TK);
  return '';
}

// 异步获取 token（用于 SSE 等需要 await 的场景）
async function getTokenAsync() {
  return await _getTokenDecrypted();
}

function getUser() {
  try { return JSON.parse(__STORE.getItem(__UK) || '{}'); } catch(e) { return {}; }
}

async function setAuth(token, user) {
  try {
    var encrypted = await _encryptToken(token);
    __STORE.setItem(__TK, encrypted);
  } catch(e) {
    // Web Crypto 可能未就绪，fallback 存储明文
    __STORE.setItem(__TK, token);
  }
  __STORE.setItem(__UK, JSON.stringify(user));
  // 确保 CSRF token 存在
  getCSRFToken();
}

function clearAuth() {
  __STORE.removeItem(__TK);
  __STORE.removeItem(__UK);
  __STORE.removeItem(__CSRF_KEY);
  __apiCache.clear();
}

// 同步设置（用于 login.html 等无法使用 async 的场景）
function setAuthSync(token, user) {
  __STORE.setItem(__TK, token);
  __STORE.setItem(__UK, JSON.stringify(user));
  getCSRFToken();
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

  // 添加 Authorization 和 CSRF Token header
  if (t) opt.headers['Authorization'] = 'Bearer ' + t;
  opt.headers['X-CSRF-Token'] = getCSRFToken();

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
        // CRITICAL-8: 尝试自动刷新 token（带互斥锁）
        try {
          t = await _refreshToken();
          if (t) {
            opt.headers['Authorization'] = 'Bearer ' + t;
            // 重试本次请求
            continue;
          }
        } catch(refreshErr) {
          // 刷新失败，退登
        }
        clearAuth();
        try { showLogin(); } catch(e) {
          var lp = document.getElementById('loginPage');
          var ma = document.getElementById('mainApp');
          if (lp) lp.style.display = 'flex';
          if (ma) ma.style.display = 'none';
        }
        throw new Error('Not logged in');
      }
      if (r.status === 403) { toast('没有权限', 'error'); throw new Error('Forbidden'); }
      if (!r.ok) {
        // 先尝试解析响应体，提取错误信息（FastAPI 默认 {detail: "..."} 格式）
        var errData = null;
        try { errData = await r.json(); } catch(_) { errData = null; }
        if (errData && errData.detail) {
          throw new Error(errData.detail);
        }
        if (errData && errData.status === 'error' && errData.message) {
          throw new Error(errData.message);
        }
        throw new Error('请求失败: ' + r.status);
      }

      var data = await r.json();

      // P2-7 fix + v1.50 unified + R5: 处理后端 {status: 'success'|'error', data: {...}} 统一格式
      if (data && data.status === 'error' && data.message) {
        throw new Error(data.message);
      }
      // R5: FastAPI 默认错误格式 {detail: "..."} 兜底（非 success 响应才处理）
      if (data && data.detail && typeof data.detail === 'string' && data.status !== 'success') {
        throw new Error(data.detail);
      }

      // v1.50: 统一格式自动解包 data 字段，同时保留顶层字段用于兼容
      if (data && data.status === 'success' && data.data && typeof data.data === 'object') {
        for (var key in data.data) {
          if (data.data.hasOwnProperty(key) && !(key in data)) {
            data[key] = data.data[key];
          }
        }
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
