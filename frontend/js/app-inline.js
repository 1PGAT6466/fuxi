// fetch 统一封装
function fetchWithTimeout(url, options) {
  options = options || {};
  var timeout = options.timeout || 15000;
  delete options.timeout;
  var controller = new AbortController();
  var timer = setTimeout(function() { controller.abort(); }, timeout);
  options.signal = controller.signal;
  return fetch(url, options).finally(function() { clearTimeout(timer); });
}

const API = '';
let enableExternal = true;
let chatHistory = [];
let currentPanel = 'chat';
const adminToken = 'polygon-admin-2024';

// ========== 面板切换 ==========
function switchPanel(name, fromPopState) {
  currentPanel = name;
  document.querySelectorAll('#panel-chat').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.panel-page').forEach(p => p.classList.remove('show'));
  document.querySelectorAll('.nav-icon').forEach(n => n.classList.remove('active'));
  if (name === 'chat') {
    document.getElementById('panel-chat').classList.remove('hidden');
  } else {
    document.getElementById('panel-chat').classList.add('hidden');
    var panel = document.getElementById('panel-' + name);
    if (panel) panel.classList.add('show');
  }
  // Highlight active nav icon
  var navIcons = document.querySelectorAll('.nav-icon');
  navIcons.forEach(function(n) {
    var onclick = n.getAttribute('onclick') || '';
    if (onclick.indexOf("'" + name + "'") !== -1) n.classList.add('active');
  });
  // Update title
  var titles = {chat:'伏羲问答', tools:'常用工具', faq:'常见问题', upload:'上传文档'};
  document.getElementById('topbar-title').textContent = titles[name] || name;
  // Update URL hash (without triggering popstate)
  if (!fromPopState) {
    var newHash = '#' + name;
    if (window.location.hash !== newHash) {
      history.pushState({panel: name}, '', newHash);
    }
  }
  // Load data
  if (name === 'tools') loadTools();
  if (name === 'faq') loadFAQ();
}

// Handle browser back/forward
window.addEventListener('popstate', function(e) {
  var hash = window.location.hash.replace('#', '') || 'chat';
  if (['chat','tools','faq','upload'].indexOf(hash) !== -1) {
    switchPanel(hash, true);
  }
});

// On page load, restore from URL hash
(function() {
  var hash = window.location.hash.replace('#', '');
  if (hash && ['chat','tools','faq','upload'].indexOf(hash) !== -1) {
    // Defer to after DOM ready
    document.addEventListener('DOMContentLoaded', function() {
      switchPanel(hash, true);
    });
  }
})();

// ========== 对话功能 ==========
function toggleExternal() {
  enableExternal = !enableExternal;
  const btn = document.getElementById('ext-btn');
  btn.textContent = enableExternal ? '🌐 联网搜索' : '🌐 仅本地';
  btn.classList.toggle('active', enableExternal);
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const q = input.value.trim();
  if (!q) return;
  
  input.value = '';
  addMessage('user', q);
  addMessage('assistant', '思考中…', true);
  
  chatHistory.push({ role: 'user', content: q });
  saveChatHistory();
  
  try {
    const res = await fetch(API + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, history: chatHistory.slice(-10), stream: false }),
    });
    const data = await res.json();
    
    // 移除 loading
    const msgs = document.getElementById('messages');
    const loading = msgs.querySelector('.loading');
    if (loading) loading.remove();
    
    const answer = data.answer || '未获取到回答';
    const mode = data.mode || 'unknown';
    const sources = data.sources || [];
    
    // 构建来源信息
    let sourceInfo = '';
    if (sources.length > 0) {
      sourceInfo = '<div style="margin-top:8px">';
      sources.slice(0, 3).forEach(s => {
        const name = s.file_name || s.title || s.file || '来源';
        sourceInfo += `<div class="source-card" onclick="window.open('${s.url||'#'}','_blank')">📎 ${name.substring(0,40)}</div>`;
      });
      sourceInfo += '</div>';
    }
    
    addMessage('assistant', renderMarkdown(answer) + sourceInfo);
    chatHistory.push({ role: 'assistant', content: answer });
    saveChatHistory();
    
  } catch(e) {
    const msgs = document.getElementById('messages');
    const loading = msgs.querySelector('.loading');
    if (loading) loading.remove();
    addMessage('assistant', '❌ 请求失败: ' + e.message);
  }
}

function addMessage(role, content, isLoading=false) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + role + (isLoading ? ' loading' : '');
  var feedbackHtml = (!isLoading && role === 'assistant') ? '<div class="msg-feedback"><button onclick="sendFeedback(this,1)" class="fb-btn fb-up">👍</button><button onclick="sendFeedback(this,0)" class="fb-btn fb-down">👎</button></div>' : '';
  div.innerHTML = '<div class="bubble">' + content + '</div>' + feedbackHtml;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function quickAsk(q) {
  document.getElementById('chat-input').value = q;
  switchPanel('chat');
  sendMessage();
}

function clearChat() {
  document.getElementById('messages').innerHTML = '<div class="msg system">对话已清空。有什么可以帮你？</div>';
  chatHistory = [];
  localStorage.removeItem('fuxi-chat-history');
}

function saveChatHistory() {
  try {
    localStorage.setItem('fuxi-chat-history', JSON.stringify(chatHistory.slice(-20)));
    renderHistoryList();
  } catch(e) {}
}

function renderHistoryList() {
  const el = document.getElementById('chat-history');
  const items = chatHistory.filter(h => h.role === 'user').slice(-15);
  el.innerHTML = items.map((h,i) => 
    `<div class="history-item" onclick="replayChat(${i})">
      <div>${h.content.substring(0,30)}…</div>
    </div>`
  ).join('');
}

function replayChat(idx) {
  switchPanel('chat');
}

// ========== 简单 Markdown 渲染 ==========
function renderMarkdown(text) {
  if (!text) return '';
  var raw = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>');
  return (typeof DOMPurify !== 'undefined') ? DOMPurify.sanitize(raw) : raw;
}

// ========== 常用工具 ==========
async function loadTools() {
  const el = document.getElementById('tools-grid');
  try {
    const res = await fetch(API + '/api/tools');
    const data = await res.json();
    const tools = data.tools || [];
    el.innerHTML = tools.map(t => `
      <div class="tool-card2"
           onclick="window.open('${t.url||'#'}','_blank')">
        <div class="ic">${t.icon||'🔧'}</div>
        <div class="nm">${t.name||''}</div>
        <div class="ds">${t.desc||''}</div>
      </div>
    `).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--text-dim)">加载失败</div>';
  }
}

// ========== 常见问题 ==========
async function loadFAQ() {
  const el = document.getElementById('faq-list');
  try {
    const res = await fetch(API + '/api/faq');
    const data = await res.json();
    const faqs = data.faqs || data.faq || [];
    el.innerHTML = faqs.length === 0 
      ? '<div class="empty-msg">暂无常见问题</div>'
      : faqs.map(f => `
        <div class="faq-item2"
             onclick="switchPanel('chat');document.getElementById('chat-input').value='${f.question||''}';sendMessage()">
          <div class="q">${f.question||''}</div>
          <div class="a">${(f.answer||'').substring(0,80)}…</div>
        </div>
      `).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--text-dim)">加载失败</div>';
  }
}

// ========== 用户上传 ==========
async function userUpload(fileList) {
  const status = document.getElementById('upload-status');
  const files = Array.from(fileList);
  
  for (const file of files) {
    status.textContent = `上传中: ${file.name}…`;
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(API + '/api/upload', {
        method: 'POST',
        body: form,
        headers: { 'x-admin-token': adminToken },
      });
      const data = await res.json();
      status.textContent = data.ok ? `✅ ${file.name} 上传成功` : `❌ ${file.name}: ${data.error||'失败'}`;
    } catch(e) {
      status.textContent = `❌ ${file.name} 上传失败`;
    }
  }
}

// 上传拖拽
document.addEventListener('DOMContentLoaded', () => {
  const zone = document.getElementById('user-upload-zone');
  if (zone) {
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--orange)'; });
    zone.addEventListener('dragleave', () => zone.style.borderColor = 'var(--orange)');
    zone.addEventListener('drop', e => { e.preventDefault(); userUpload(e.dataTransfer.files); });
  }
  
  // 恢复历史
  try {
    const saved = localStorage.getItem('fuxi-chat-history');
    if (saved) chatHistory = JSON.parse(saved);
    renderHistoryList();
  } catch(e) {}
  
  // 自动调整 textarea 高度
  const ta = document.getElementById('chat-input');
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  });
});

// Time updater
(function updateTime(){
  var el = document.getElementById('topbar-time');
  if (el) {
    var d = new Date();
    el.textContent = d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
  }
  setTimeout(updateTime, 30000);
})();
</script>

// ========== 反馈功能 ==========
async function sendFeedback(btn, rating) {
  var bubble = btn.closest('.msg').querySelector('.bubble');
  var text = bubble ? bubble.textContent.substring(0, 200) : '';
  var lastUserMsg = chatHistory.filter(h => h.role === 'user').pop();
  var query = lastUserMsg ? lastUserMsg.content : '';
  
  try {
    await fetch(API + '/api/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: query, answer: text, rating: rating ? 5 : 1, source: 'web'})
    });
    btn.parentElement.innerHTML = rating ? '✅ 已赞' : '✅ 已反馈';
  } catch(e) {
    btn.parentElement.innerHTML = '❌ 反馈失败';
  }
}