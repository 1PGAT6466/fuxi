/**
 * @fileoverview 页面切换路由 + 初始化
 * @module init-app
 */

const TITLES = {
  chat: '智能对话', search: '知识搜索', graph: '知识图谱', wiki: 'Wiki 知识',
  files: '文件管理', 'admin-overview': '系统概览', 'admin-organs': '器官状态',
  'admin-symbols': '四象状态', 'admin-growth': '成长面板',
  'admin-eval': '评测报告', 'admin-flags': 'Feature Flags', 'admin-feedback': '用户反馈'
};

function switchPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  var page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  var nav = document.querySelector('.nav-item[data-page="' + name + '"]');
  if (nav) nav.classList.add('active');
  document.getElementById('pageTitle').textContent = TITLES[name] || name;

  if (name === 'graph') loadGraph();
  if (name === 'wiki') loadWikiTree();
  if (name === 'files') { if (typeof loadFiles === 'function') loadFiles(); }
  if (name === 'admin-overview') loadOverview();
  if (name === 'admin-organs') loadOrgans();
  if (name === 'admin-symbols') loadSymbols();
  if (name === 'admin-growth') loadGrowth();
  if (name === 'admin-eval') loadEval();
  if (name === 'admin-flags') loadFlags();
  if (name === 'admin-feedback') loadFeedback();
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
  if (!/^[A-Za-z0-9._~+\/=]+$/.test(tok)) {
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
