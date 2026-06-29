/**
 * @fileoverview 页面切换路由 + 初始化
 * @module init-app
 */

const TITLES = {
  chat: '智能对话', search: '知识搜索', graph: '知识图谱', wiki: 'Wiki 知识',
  files: '文件管理', 'admin-overview': '系统概览', 'admin-organs': '器官状态',
  'admin-eval': '评测报告', 'admin-flags': 'Feature Flags', 'admin-feedback': '用户反馈'
};

function switchPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  const nav = document.querySelector('.nav-item[data-page="' + name + '"]');
  if (nav) nav.classList.add('active');
  document.getElementById('pageTitle').textContent = TITLES[name] || name;
  
  if (name === 'graph') loadGraph();
  if (name === 'wiki') loadWikiTree();
  if (name === 'files') { if (typeof loadFiles === 'function') loadFiles(); }
  if (name === 'admin-overview') loadOverview();
  if (name === 'admin-organs') loadOrgans();
  if (name === 'admin-eval') loadEval();
  if (name === 'admin-flags') loadFlags();
  if (name === 'admin-feedback') loadFeedback();
}

function initApp() {
  document.querySelectorAll('.nav-item').forEach(n => {
    n.addEventListener('click', () => switchPage(n.dataset.page));
  });
  switchPage('chat');
}

// 初始化
(function init() {
  const tok = getToken();
  if (!tok) { showLogin(); return; }
  api('/api/auth/me').then(d => {
    if (d && d.username) { showApp(); } else { showLogin(); }
  }).catch(() => { showLogin(); });
})();

// textarea 自动高度
(function() {
  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
  }
})();
