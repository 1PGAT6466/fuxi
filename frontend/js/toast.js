// Toast 通知组件
var Toast = {
  show: function(msg, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    var container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px';
      document.body.appendChild(container);
    }
    var icons = {success:'✅', error:'❌', warning:'⚠️', info:'ℹ️'};
    var colors = {success:'#2E7D32', error:'#C62828', warning:'#E65100', info:'#1565C0'};
    var toast = document.createElement('div');
    toast.style.cssText = 'padding:12px 20px;border-radius:10px;background:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);display:flex;align-items:center;gap:8px;font-size:14px;animation:toastIn 0.3s ease;max-width:360px;border-left:4px solid ' + (colors[type]||colors.info);
    toast.innerHTML = '<span>' + (icons[type]||'') + '</span><span>' + msg + '</span>';
    container.appendChild(toast);
    setTimeout(function() { toast.style.opacity='0'; toast.style.transform='translateX(100px)'; setTimeout(function(){ toast.remove(); }, 300); }, duration);
  },
  success: function(m,d) { this.show(m,'success',d); },
  error: function(m,d) { this.show(m,'error',d); },
  warning: function(m,d) { this.show(m,'warning',d); },
  info: function(m,d) { this.show(m,'info',d); }
};
