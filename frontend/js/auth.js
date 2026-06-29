/**
 * @fileoverview 登录/注册页面
 * @module auth
 */

let isLoginMode = true;

function toggleMode() {
  isLoginMode = !isLoginMode;
  document.getElementById('loginBtn').textContent = isLoginMode ? '登 录' : '注 册';
  document.getElementById('toggleText').textContent = isLoginMode ? '没有账号？' : '已有账号？';
  document.getElementById('toggleLink').textContent = isLoginMode ? '注册新账号' : '去登录';
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

document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = document.getElementById('loginUser').value.trim(), p = document.getElementById('loginPass').value;
  if (!u || !p) return;
  const btn = document.getElementById('loginBtn'), err = document.getElementById('loginError');
  btn.disabled = true; btn.textContent = isLoginMode ? '登录中...' : '注册中...'; err.textContent = '';
  try {
    const ep = isLoginMode ? '/api/auth/login' : '/api/auth/register';
    const d = await api(ep, { method: 'POST', body: { username: u, password: p } });
    if (isLoginMode) {
      setAuth(d.token, { username: d.username, role: d.role, display_name: d.display_name });
      showApp();
    } else {
      err.style.color = '#34c759'; err.textContent = '注册成功，请登录';
      isLoginMode = true; document.getElementById('loginBtn').textContent = '登 录';
    }
  } catch(e) {
    err.textContent = e.message || '操作失败';
  } finally {
    btn.disabled = false; btn.textContent = isLoginMode ? '登 录' : '注 册';
  }
});
