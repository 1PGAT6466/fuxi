/**
 * @fileoverview 登录页 — 小米风格
 * @module auth
 */

let _loginRole = 'user';

function switchLoginTab(role) {
  _loginRole = role;
  document.querySelectorAll('.login-tab').forEach(function(t){ t.classList.remove('active'); });
  document.getElementById(role === 'admin' ? 'tabAdmin' : 'tabUser').classList.add('active');
  document.getElementById('loginError').textContent = '';
}

function showLogin() {
  document.getElementById('loginPage').style.display = 'flex';
  document.getElementById('mainApp').style.display = 'none';
}

function showApp() {
  document.getElementById('loginPage').style.display = 'none';
  document.getElementById('mainApp').style.display = 'flex';
  initApp();
}

function logout() {
  clearAuth();
  showLogin();
}

function handleLogin(e) {
  e.preventDefault();
  var u = document.getElementById('loginUser').value.trim();
  var p = document.getElementById('loginPass').value;
  if (!u || !p) return;
  var btn = document.getElementById('loginBtn');
  var err = document.getElementById('loginError');
  btn.disabled = true;
  btn.textContent = '登录中...';
  err.textContent = '';

  api('/api/auth/login', { method: 'POST', body: { username: u, password: p } })
    .then(function(d) {
      // P2-5: 验证 token 格式
      if (!d.token || !/^[A-Za-z0-9._~+\/=-]+$/.test(d.token)) {
        err.textContent = '服务器返回的 token 格式异常';
        return;
      }
      if (_loginRole === 'admin' && d.role !== 'admin') {
        err.textContent = '该账号不是管理员';
        return;
      }
      setAuth(d.token, { username: d.username, role: d.role, display_name: d.display_name });
      showApp();
    })
    .catch(function(e) {
      err.textContent = e.message || '登录失败';
    })
    .finally(function() {
      btn.disabled = false;
      btn.textContent = '登 录';
    });
}
