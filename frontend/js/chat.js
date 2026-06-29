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
      html += '<div class="msg-sources">';
      sources.slice(0, 5).forEach(function(s, i) {
        var fh = s.file_hash || '';
        var fn = esc(s.file_name || s.title || 'Ref ' + (i + 1));
        var icon = fn.endsWith('.pdf') ? '📕' : (fn.endsWith('.doc') || fn.endsWith('.docx')) ? '📘' : (fn.endsWith('.xls') || fn.endsWith('.xlsx')) ? '📊' : '📄';
        html += '<div class="source-card" style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;background:var(--card);border:1px solid var(--border);border-radius:8px;cursor:pointer;font-size:12px;transition:all .15s" onmouseenter="this.style.borderColor=\'var(--mi-orange)\';this.style.background=\'rgba(255,103,0,0.04)\'" onmouseleave="this.style.borderColor=\'var(--border)\';this.style.background=\'var(--card)\'">';
        html += '<span>' + icon + '</span>';
        html += '<span style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + fn + '</span>';
        if (fh) {
          html += '<span style="display:flex;gap:4px">';
          html += '<a href="/api/view/' + encodeURIComponent(fh) + '" target="_blank" style="color:var(--mi-orange);text-decoration:none;font-weight:500" title="查看原文">查看</a>';
          html += '<span style="color:var(--border)">|</span>';
          html += '<a href="/api/download/' + encodeURIComponent(fh) + '" style="color:var(--mi-orange);text-decoration:none;font-weight:500" title="下载">下载</a>';
          html += '</span>';
        }
        html += '</div>';
      });
      html += '</div>';
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
