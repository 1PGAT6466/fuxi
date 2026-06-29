// 错误边界 - API 报错不白屏
window.addEventListener('error', function(e) { console.error('[ErrorBoundary]', e.error); });
window.addEventListener('unhandledrejection', function(e) { console.error('[ErrorBoundary] Promise:', e.reason); });

function safeFetch(url, options) {
  options = options || {};
  var timeout = options.timeout || 15000;
  var controller = new AbortController();
  var timer = setTimeout(function() { controller.abort(); }, timeout);
  options.signal = controller.signal;
  return fetch(url, options).finally(function() { clearTimeout(timer); });
}
