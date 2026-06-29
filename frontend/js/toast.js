/**
 * Toast 消息提示
 * @module toast
 * @fileoverview 统一的消息通知组件
 */
;(function() {
  window.toast = function(msg, type) {
    type = type || 'info';
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function() { t.remove(); }, 3000);
  };
})();
