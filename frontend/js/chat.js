// ===== 对话 =====
var chatHistory = [];
var _webSearchEnabled = false;

function toggleWebSearch() {
  _webSearchEnabled = !_webSearchEnabled;
  var btn = document.getElementById('btnWebSearch');
  if (btn) btn.classList.toggle('active', _webSearchEnabled);
}

function quickChat(text) {
  document.getElementById('chatInput').value = text;
  sendChat();
}

function autoResizeChat(el) {
  el.style.height = '22px';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

async function sendChat(forceWeb) {
  var input = document.getElementById('chatInput');
  var q = input.value.trim();
  if (!q) return;
  var useWeb = forceWeb || _webSearchEnabled;
  input.value = '';
  input.style.height = '22px';
  var empty = document.getElementById('chatEmpty');
  if (empty) empty.style.display = 'none';
  var prefix = useWeb ? '🌐 ' : '';
  appendMsg('user', prefix + q);
  chatHistory.push({ role: 'user', content: q });
  var lid = appendMsg('loading', '<span class=loading-dots>AI 思考中<span>.</span><span>.</span><span>.</span></span>' + (useWeb ? ' (联网搜索)' : ''));
  try {
    var apiPath = useWeb ? '/api/antenna/search' : '/api/chat';
    var body = useWeb ? { query: q } : { query: q, history: chatHistory.slice(-6), stream: false };
    var d = await api(apiPath, { method: 'POST', body: body });
    removeMsg(lid);
    var answer = d.answer || '未能生成回答';
    appendMsg('ai', answer, d.sources, d.trace);
    chatHistory.push({ role: 'assistant', content: answer });
  } catch (e) {
    removeMsg(lid);
    appendMsg('error', '请求失败: ' + e.message);
  }
}

function appendMsg(role, content, sources, trace) {
  var c = document.getElementById('chatMsgs');
  var id = 'm-' + Date.now();
  var div = document.createElement('div');
  div.id = id;
  div.className = 'msg ' + role;
  if (role === 'user') {
    div.innerHTML = '<div class="msg-avatar">U</div><div class="msg-bubble">' + esc(content) + '</div>';
  } else if (role === 'loading') {
    div.innerHTML = '<div class="msg-avatar">AI</div><div class="typing">' + content + '</div>';
  } else if (role === 'error') {
    div.innerHTML = '<div class="msg-avatar">!</div><div class="msg-bubble" style="color:var(--error)">' + esc(content) + '</div>';
  } else {
    var rendered = typeof marked !== 'undefined' ? marked.parse(content) : esc(content);
    if (typeof DOMPurify !== 'undefined') rendered = DOMPurify.sanitize(rendered);
    var html = '<div class="msg-avatar">AI</div><div class="msg-bubble">' + rendered;
    if (sources && sources.length) {
      html += '<div class="msg-sources">' + sources.slice(0, 5).map(function(s, i) {
        return '<span class="source-chip">📄 ' + esc(s.file_name || s.title || 'Ref ' + (i + 1)) + '</span>';
      }).join('') + '</div>';
    }
    if (trace && trace.steps) {
      html += '<div class="msg-trace">' + trace.steps.map(function(s) {
        return '<div class="trace-step"><span class="tool">' + esc(s.tool || s.type) + '</span><span>' + esc(s.status || '') + '</span><span class="ms">' + (s.latency_ms ? s.latency_ms.toFixed(0) + 'ms' : '') + '</span></div>';
      }).join('') + '</div>';
    }
    html += '</div>';
    div.innerHTML = html;
  }
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
  return id;
}

function removeMsg(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
}
