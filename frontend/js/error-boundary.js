// 错误边界 - 小米风格错误处理
window.addEventListener('error', function(e) {
  console.error('[ErrorBoundary]', e.error);
  if (typeof toast === 'function') toast('系统异常，请刷新页面', 'error');
});
window.addEventListener('unhandledrejection', function(e) {
  console.error('[ErrorBoundary] Promise:', e.reason);
});

// 带超时的 fetch
function safeFetch(url, options) {
  options = options || {};
  var timeout = options.timeout || 15000;
  var controller = new AbortController();
  var timer = setTimeout(function() { controller.abort(); }, timeout);
  options.signal = controller.signal;
  return fetch(url, options).finally(function() { clearTimeout(timer); });
}

// 加载状态管理
function showLoading(containerId) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:40px;gap:8px">' +
    '<div class="loading-spinner"></div>' +
    '<span style="color:var(--text3);font-size:13px">加载中...</span></div>';
}

function showError(containerId, message, retryFn) {
  var el = document.getElementById(containerId);
  if (!el) return;
  var retryBtn = retryFn ? '<button class="btn btn-ghost btn-sm" style="margin-top:12px" onclick="(' + retryFn.toString() + ')()">重试</button>' : '';
  el.innerHTML = '<div style="text-align:center;padding:40px">' +
    '<div style="font-size:32px;margin-bottom:8px">⚠️</div>' +
    '<div style="color:var(--error);font-size:14px;margin-bottom:8px">' + esc(message || '加载失败') + '</div>' +
    retryBtn + '</div>';
}
