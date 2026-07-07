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

// 时间格式化
function formatTime(ts) {
  if (!ts) return '';
  var d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
  var pad = function(n) { return n < 10 ? '0' + n : n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
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
