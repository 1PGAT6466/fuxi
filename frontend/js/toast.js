/**
 * Toast 消息提示 - 小米风格
 * @module toast
 */
;(function() {
  var icons = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ'
  };

  window.toast = function(msg, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    var t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.innerHTML = '<span class="toast-icon">' + (icons[type] || '') + '</span><span>' + esc(msg) + '</span>';
    document.body.appendChild(t);
    // 触发动画
    requestAnimationFrame(function() { t.classList.add('toast-show'); });
    setTimeout(function() {
      t.classList.remove('toast-show');
      setTimeout(function() { t.remove(); }, 300);
    }, duration);
  };
})();
