// 错误边界 - 小米风格错误处理
window.addEventListener('error', function(e) {
  console.error('[ErrorBoundary]', e.error);
  if (typeof toast === 'function') toast('系统异常，请刷新页面', 'error');
});
window.addEventListener('unhandledrejection', function(e) {
  console.error('[ErrorBoundary] Promise:', e.reason);
});
