/**
 * @fileoverview 登录页 — 小米风格
 * @module auth
 */

let _loginRole = 'user';
let _isRegisterMode = false;

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

function toggleRegisterMode() {
  _isRegisterMode = !_isRegisterMode;
  var btn = document.getElementById('loginBtn');
  var toggleEl = document.getElementById('loginToggleText');
  var toggleLink = document.getElementById('loginToggleLink');
  if (btn) btn.textContent = _isRegisterMode ? '注 册' : '登 录';
  if (toggleEl) toggleEl.textContent = _isRegisterMode ? '已有账号？' : '没有账号？';
  if (toggleLink) toggleLink.textContent = _isRegisterMode ? '去登录' : '注册新账号';
  var err = document.getElementById('loginError');
  if (err) err.textContent = '';
}

function handleLogin(e) {
  e.preventDefault();
  var u = document.getElementById('loginUser').value.trim();
  var p = document.getElementById('loginPass').value;
  if (!u || !p) return;
  var btn = document.getElementById('loginBtn');
  var err = document.getElementById('loginError');
  btn.disabled = true;
  btn.textContent = _isRegisterMode ? '注册中...' : '登录中...';
  err.textContent = '';

  var endpoint = _isRegisterMode ? '/api/auth/register' : '/api/auth/login';

  api(endpoint, { method: 'POST', body: { username: u, password: p } })
    .then(function(d) {
      if (_isRegisterMode) {
        // P2-10 fix: 注册成功后自动切换回登录模式
        err.style.color = '#2ecc71';
        err.textContent = '注册成功，请登录';
        _isRegisterMode = false;
        toggleRegisterMode();
        btn.textContent = '登 录';
        setTimeout(function() { err.style.color = ''; }, 3000);
        return;
      }
      // P2-5: 验证 token 格式
      if (!d.token || !/^[A-Za-z0-9._~+\/=-]+$/.test(d.token)) {
        err.textContent = '服务器返回的 token 格式异常';
        return;
      }
      if (_loginRole === 'admin' && d.role !== 'admin') {
        err.textContent = '该账号不是管理员';
        return;
      }
      // CRITICAL-1 fix: 使用加密存储 setAuth
      setAuthSync(d.token, { username: d.username, role: d.role, display_name: d.display_name });
      showApp();
    })
    .catch(function(e) {
      err.textContent = e.message || '操作失败';
    })
    .finally(function() {
      btn.disabled = false;
      if (!_isRegisterMode) btn.textContent = '登 录';
      else btn.textContent = '注 册';
    });
}
