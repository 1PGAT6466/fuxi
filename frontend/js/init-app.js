/**
 * @fileoverview 页面切换路由 + 初始化
 * @module init-app
 */

const TITLES = {
  chat: '智能对话', search: '知识搜索', graph: '知识图谱', wiki: 'Wiki 知识',
  files: '文件管理', 'admin-overview': '系统概览',
  'admin-symbols': '系统状态', 'admin-growth': '成长面板',
  'admin-eval': '评测报告',   'admin-flags': 'Feature Flags', 'admin-feedback': '用户反馈',
  'admin-services': '服务管理'
};

function switchPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  var page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  var nav = document.querySelector('.nav-item[data-page="' + name + '"]');
  if (nav) nav.classList.add('active');
  document.getElementById('pageTitle').textContent = TITLES[name] || name;

  // P0-7 fix: 所有延迟加载的函数增加存在性检查
  if (name === 'graph' && typeof loadGraph === 'function') loadGraph();
  if (name === 'wiki' && typeof loadWikiTree === 'function') loadWikiTree();
  if (name === 'files' && typeof loadFiles === 'function') loadFiles();
  if (name === 'admin-overview' && typeof loadOverview === 'function') loadOverview();
  if (name === 'admin-symbols' && typeof loadSymbols === 'function') loadSymbols();
  if (name === 'admin-growth' && typeof loadGrowth === 'function') loadGrowth();
  if (name === 'admin-eval' && typeof loadEval === 'function') loadEval();
  if (name === 'admin-flags' && typeof loadFlags === 'function') loadFlags();
  if (name === 'admin-feedback' && typeof loadFeedback === 'function') loadFeedback();
  if (name === 'admin-services' && typeof loadServices === 'function') loadServices();
}

function initApp() {
  var user = getUser();
  var isAdmin = user.role === 'admin';
  // 根据角色显示/隐藏管理菜单
  var adminSections = document.querySelectorAll('.nav-admin');
  adminSections.forEach(function(el) {
    el.style.display = isAdmin ? 'block' : 'none';
  });

  // 设置用户信息
  var avatar = document.getElementById('userAvatar');
  var userName = document.getElementById('userName');
  var userRole = document.getElementById('userRole');
  if (avatar) avatar.textContent = (user.display_name || user.username || 'U')[0].toUpperCase();
  if (userName) userName.textContent = user.display_name || user.username || '用户';
  if (userRole) {
    userRole.textContent = isAdmin ? '管理员' : '普通用户';
    userRole.className = 'role';
  }

  // 绑定导航点击事件
  document.querySelectorAll('.nav-item').forEach(n => {
    n.addEventListener('click', function() {
      switchPage(this.dataset.page);
    });
  });

  // 默认进入对话页
  switchPage('chat');
}

// 初始化
(function init() {
  var tok = getToken();
  if (!tok) { showLogin(); return; }
  if (!/^[A-Za-z0-9._~+\/=-]+$/.test(tok)) {
    clearAuth();
    showLogin();
    return;
  }
  api('/api/auth/me').then(function(d) {
    if (d && d.username) { showApp(); } else { showLogin(); }
  }).catch(function() { showLogin(); });
})();

// textarea 自动高度
(function() {
  var chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('input', function() {
      this.style.height = '22px';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
  }
})();

// 快捷键支持
document.addEventListener('keydown', function(e) {
  // Ctrl/Cmd + K: 快速搜索
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    switchPage('search');
    var searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.focus();
  }
  // Ctrl/Cmd + /: 切换到对话
  if ((e.ctrlKey || e.metaKey) && e.key === '/') {
    e.preventDefault();
    switchPage('chat');
    var chatInput = document.getElementById('chatInput');
    if (chatInput) chatInput.focus();
  }
  // Escape: 关闭弹窗/返回
  if (e.key === 'Escape') {
    var modals = document.querySelectorAll('.modal.active');
    if (modals.length) {
      modals.forEach(function(m) { m.classList.remove('active'); });
    }
  }
});
