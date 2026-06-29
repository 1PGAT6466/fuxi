/**
 * API Client + Token Manager
 * All ASCII-safe, no non-Latin1 characters in any path
 */

var __TK = '***', __UK = '***';
var __STORE = sessionStorage;

function getToken() {
  var v = __STORE.getItem(__TK);
  if (!v) return '';
  // Sanitize: only allow base64url chars
  if (!/^[A-Za-z0-9._~+\/=]+$/.test(v)) {
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
}

async function api(url, opt) {
  var t = getToken();
  if (!opt) opt = {};
  if (!opt.headers) opt.headers = {};
  if (t) opt.headers['Authorization'] = 'Bearer ' + t;
  if (opt.body && typeof opt.body === 'object' && !opt.headers['Content-Type']) {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(opt.body);
  }
  var r = await fetch(url, opt);
  if (r.status === 401) { clearAuth(); showLogin(); throw new Error('Not logged in'); }
  if (r.status === 403) { toast('No permission', 'error'); throw new Error('Forbidden'); }
  if (!r.ok) throw new Error('Request failed: ' + r.status);
  return r.json();
}
