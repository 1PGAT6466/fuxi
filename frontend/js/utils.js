/**
 * @fileoverview 通用工具函数 - 小米风格
 * @module utils
 */

// HTML 转义（防 XSS）
function esc(s) {
  if (!s) return '';
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(String(s)));
  return div.innerHTML;
}

// 输入清理（防注入）
function sanitizeInput(s) {
  if (!s) return '';
  return String(s).replace(/<[^>]*>/g, '').replace(/javascript:/gi, '').replace(/on\w+\s*=/gi, '');
}

// 防抖函数
function debounce(fn, delay) {
  var timer;
  return function() {
    var args = arguments;
    var ctx = this;
    clearTimeout(timer);
    timer = setTimeout(function() { fn.apply(ctx, args); }, delay || 300);
  };
}

// 管理面板错误显示（跨 admin.js / services.js 共用）
function _adminError(containerId, msg) {
  var el = document.getElementById(containerId);
  if (el) el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(msg || '未知错误') + '</p></div>';
}

// 节流函数
function throttle(fn, limit) {
  var inThrottle;
  return function() {
    var args = arguments;
    var ctx = this;
    if (!inThrottle) {
      fn.apply(ctx, args);
      inThrottle = true;
      setTimeout(function() { inThrottle = false; }, limit || 300);
    }
  };
}
