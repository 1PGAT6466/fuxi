// 主题切换
var Theme = {
  init: function() {
    var saved = localStorage.getItem('fuxi-theme') || 'light';
    this.apply(saved);
  },
  toggle: function() {
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    this.apply(current === 'light' ? 'dark' : 'light');
  },
  apply: function(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('fuxi-theme', theme);
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
};
Theme.init();
