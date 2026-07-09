/**
 * @fileoverview 通用工具函数 - 小米风格
 * @module utils
 */

// P3-R2 fix: 安全数值转换，防止 NaN/非数字值导致 toFixed 崩溃
function safeNum(val, def) {
  if (def === undefined) def = 0;
  var n = Number(val);
  return isNaN(n) || !isFinite(n) ? def : n;
}

// HTML 转义（防 XSS）
function esc(s) {
  if (!s) return '';
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(String(s)));
  return div.innerHTML;
}

// 管理面板错误显示（跨 admin.js / services.js 共用）
function _adminError(containerId, msg) {
  var el = document.getElementById(containerId);
  if (el) el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(msg || '未知错误') + '</p></div>';
}
