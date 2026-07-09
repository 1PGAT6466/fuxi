// ===== 对话 =====
var chatHistory = [];
var _webSearchEnabled = false;
var _currentAbortController = null;   // SSE 流式中止控制器
var _streamSpeed = 30;                // 打字机速度 (ms/字)，可调

function toggleWebSearch() {
  _webSearchEnabled = !_webSearchEnabled;
  var btn = document.getElementById('btnWebSearch');
  if (btn) btn.classList.toggle('active', _webSearchEnabled);
}

function quickChat(text) {
  document.getElementById('chatInput').value = text;
  sendChat();
}

/**
 * 停止当前正在进行的 SSE 流式响应
 */
function stopStreaming() {
  if (_currentAbortController) {
    _currentAbortController.abort();
    _currentAbortController = null;
  }
}

/**
 * 发送对话消息 — SSE 流式版本
 * 后端 POST /api/chat/send 返回 SSE 格式（Content-Type: text/event-stream）
 * 数据帧格式: data: {"delta":"文本片段","done":false}
 */
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

  // Web 搜索走非流式分支
  if (useWeb) {
    var lid = appendMsg('loading', '');
    var progressTimer = setTimeout(function() {
      var el = document.getElementById(lid);
      if (el) {
        var bubble = el.querySelector('.msg-bubble');
        if (bubble) bubble.innerHTML = '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div><div style="font-size:11px;color:var(--text3);margin-top:6px">正在搜索，请耐心等待...</div>';
      }
    }, 3000);
    try {
      var d = await api('/api/antenna/search', { method: 'POST', body: { query: q }, timeout: 30000 });
      clearTimeout(progressTimer);
      removeMsg(lid);
      var answer = d.answer || '未能生成回答';
      appendMsg('ai', answer, d.sources, d.trace);
      chatHistory.push({ role: 'assistant', content: answer });
    } catch (e) {
      clearTimeout(progressTimer);
      removeMsg(lid);
      var errMsg = e.message;
      if (e.message.indexOf('超时') >= 0) errMsg = '请求超时，请稍后重试';
      else if (errMsg.indexOf('Not logged') >= 0) errMsg = '登录已过期，请重新登录';
      appendMsg('error', '请求失败: ' + errMsg);
    }
    return;
  }

  // ===== SSE 流式模式 =====
  await sendChatSSE(q);
}

/**
 * SSE 流式对话核心
 */
var _SSE_MAX_RETRIES = 3;
var _SSE_BASE_DELAY = 1000; // 1s base

async function sendChatSSE(query) {
  var loadingId = appendMsg('loading-stream', '');
  var answerId = null;
  var answerText = '';
  var sources = null;
  var trace = null;
  var lastErr = null;

  // R4: SSE 重连循环（最多 3 次重试 + 指数退避）
  for (var _attempt = 0; _attempt <= _SSE_MAX_RETRIES; _attempt++) {
    // 重试时重置状态（保留已累计的 answerText 用于 UI 显示）
    var abortController = new AbortController();
    _currentAbortController = abortController;

    // 流式进度计时器
    var progressEl = null;
    var progressTimer = setTimeout(function() {
      var el = document.getElementById(loadingId);
      if (el) {
        progressEl = el.querySelector('.stream-progress');
        if (progressEl) progressEl.style.display = 'block';
      }
    }, 2000);

    var token = (typeof getTokenAsync === 'function') ? await getTokenAsync() : (getToken ? getToken() : '');
    var csrfToken = (typeof getCSRFToken === 'function') ? getCSRFToken() : '';
    var fetchTimeoutMs = 60000;

    try {
      var headers = { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' };
      if (token) headers['Authorization'] = 'Bearer ' + token;
      if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
      var resp = await __fetchWithTimeout('/api/chat/send', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ query: query, history: chatHistory.slice(-6), stream: true }),
        signal: abortController.signal
      }, fetchTimeoutMs);

    // HTTP 状态码检查
    if (resp.status === 401) {
      if (typeof clearAuth === 'function') clearAuth();
      if (typeof showLogin === 'function') showLogin();
      throw new Error('Not logged in');
    }
    if (resp.status === 403) throw new Error('Forbidden');
    if (resp.status === 429) throw new Error('请求过于频繁，请稍后重试');
    if (resp.status >= 500) throw new Error('服务器错误 (' + resp.status + ')，请稍后重试');
    if (!resp.ok) throw new Error('请求失败: HTTP ' + resp.status);

    // 检查 Content-Type 是否为 SSE
    var contentType = resp.headers.get('Content-Type') || '';
    if (contentType.indexOf('text/event-stream') < 0 && contentType.indexOf('application/json') < 0) {
      // 非预期的响应类型
      var rawText = await resp.text();
      if (rawText.trim().startsWith('{')) {
        try {
          var jsonData = JSON.parse(rawText);
          if (jsonData && jsonData.status === 'error') {
            throw new Error(jsonData.message || '请求失败');
          }
          // 非流式 JSON 兜底
          answerText = jsonData.answer || jsonData.data.answer || '未能生成回答';
          sources = jsonData.sources || (jsonData.data && jsonData.data.sources);
          trace = jsonData.trace || (jsonData.data && jsonData.data.trace);
        } catch (parseErr) {
          throw new Error('响应格式异常');
        }
      } else {
        throw new Error('响应格式异常: ' + contentType);
      }
    }

    // 如果还没从 JSON 兜底拿到结果，走 SSE 流式解析
    if (!answerText) {
      var reader = resp.body.getReader();
      var decoder = new TextDecoder('utf-8');
      var buffer = '';
      var lastRenderTime = 0;
      var RENDER_INTERVAL = 50; // 每 50ms 最多渲染一次

      while (true) {
        var result = await reader.read();
        if (result.done) break;

        // decode 流数据（stream: true 避免截断多字节 UTF-8）
        buffer += decoder.decode(result.value, { stream: true });

        // 按行解析 SSE 帧
        var lines = buffer.split('\n');
        // 最后一行可能不完整，保留到下次
        buffer = lines.pop();

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line) continue;

          // SSE data 帧: "data: {...}"
          if (line.indexOf('data:') === 0) {
            var jsonStr = line.substring(5).trim();
            if (!jsonStr) continue;

            // 特殊标记: [DONE] (OpenAI 兼容)
            if (jsonStr === '[DONE]') continue;

            try {
              var chunk = JSON.parse(jsonStr);

              // 提取 delta 文本
              var delta = chunk.delta || chunk.content || '';
              if (delta) {
                answerText += delta;

                // 首次收到文本时，将 loading 替换为 ai 消息
                if (!answerId) {
                  removeMsg(loadingId);
                  clearTimeout(progressTimer);
                  answerId = appendMsg('ai-stream', answerText, null, null);
                  var answerEl = document.getElementById(answerId);
                  if (answerEl) {
                    answerEl.querySelector('.msg-bubble').classList.add('streaming');
                  }
                } else {
                  // 节流更新渲染
                  var now = Date.now();
                  if (now - lastRenderTime >= RENDER_INTERVAL) {
                    updateStreamingBubble(answerId, answerText);
                    lastRenderTime = now;
                  }
                }
              }

              // done 标记: 流结束
              if (chunk.done) {
                sources = chunk.sources || null;
                trace = chunk.trace || null;
              }

              // 错误帧
              if (chunk.error) {
                throw new Error(chunk.error);
              }

            } catch (parseErr) {
              if (parseErr.message && parseErr.message !== 'Unexpected end of JSON input') {
                throw parseErr;
              }
              // JSON 不完整，放回 buffer
              buffer = line + '\n' + buffer;
              break;
            }
          }
        }
      }

      // flush 剩余 buffer（最后一段可能不完整的 JSON）
      var remainder = decoder.decode();
      if (remainder) buffer += remainder;
    }

    // 清理
    clearTimeout(progressTimer);
    _currentAbortController = null;

    // 最终渲染
    if (!answerText) answerText = '未能生成回答';
    if (answerId) {
      updateStreamingBubble(answerId, answerText, true);
      removeMsg(answerId);
      appendMsg('ai', answerText, sources, trace);
    } else {
      removeMsg(loadingId);
      appendMsg('ai', answerText, sources, trace);
    }
    chatHistory.push({ role: 'assistant', content: answerText });
    return; // 成功，退出函数

  } catch (e) {
    clearTimeout(progressTimer);
    _currentAbortController = null;

    // 用户主动中止不重试，不显示错误
    if (e.name === 'AbortError') {
      removeMsg(loadingId);
      if (answerId) {
        updateStreamingBubble(answerId, answerText, true);
        if (answerText) {
          removeMsg(answerId);
          appendMsg('ai', answerText + '\n\n*[已中止]*', null, null);
          chatHistory.push({ role: 'assistant', content: answerText });
        }
      }
      return;
    }

    // 认证错误不重试
    if (e.message && (e.message.indexOf('Not logged') >= 0 || e.message.indexOf('Forbidden') >= 0 || e.message.indexOf('频繁') >= 0)) {
      break;
    }

    lastErr = e;

    // 可重试的错误：网络错误、超时、5xx
    var isRetryable = e.message && (e.message.indexOf('超时') >= 0 || e.message.indexOf('网络') >= 0 ||
      e.message.indexOf('fetch') >= 0 || e.message.indexOf('Network') >= 0 ||
      e.message.indexOf('服务器错误') >= 0 || e.message.indexOf('格式异常') >= 0);

    if (isRetryable && _attempt < _SSE_MAX_RETRIES) {
      // 指数退避: 1s, 2s, 4s
      var delay = _SSE_BASE_DELAY * Math.pow(2, _attempt);
      // 显示重试提示
      var retryEl = document.getElementById(loadingId);
      if (retryEl) {
        var progressDiv = retryEl.querySelector('.stream-progress');
        if (progressDiv) {
          progressDiv.style.display = 'block';
          progressDiv.textContent = '连接中断，正在重连 (' + (_attempt + 1) + '/' + _SSE_MAX_RETRIES + ')…';
        }
      }
      await new Promise(function(r) { setTimeout(r, delay); });
      continue; // 进入下一次重试
    }

    // 不可重试或重试耗尽，跳出循环
    break;
  }
  } // end for loop

  // 所有重试失败，显示错误
  if (lastErr) {
    removeMsg(loadingId);
    if (answerId) removeMsg(answerId);
    var errMsg = lastErr.message || '未知错误';
    if (errMsg.indexOf('超时') >= 0) errMsg = '⏱️ 请求超时，AI 响应时间较长，请稍后重试';
    else if (errMsg.indexOf('Not logged') >= 0) errMsg = '🔒 登录已过期，请重新登录';
    else if (errMsg.indexOf('Forbidden') >= 0) errMsg = '🚫 没有权限访问该资源';
    else if (errMsg.indexOf('频繁') >= 0) errMsg = '⏳ 请求过于频繁，请稍后重试';
    else if (errMsg.indexOf('网络') >= 0 || errMsg.indexOf('fetch') >= 0 || errMsg.indexOf('Network') >= 0) errMsg = '🌐 网络连接失败，请检查网络后重试';
    else if (errMsg.indexOf('JSON') >= 0 || errMsg.indexOf('格式异常') >= 0) errMsg = '📡 服务器响应格式异常，请联系管理员';
    else errMsg = '❌ ' + errMsg;
    appendMsg('error', '请求失败: ' + errMsg);
  }
}

/**
 * 更新流式消息气泡内容
 * @param {string} msgId - 消息 DOM ID
 * @param {string} text  - 累积文本
 * @param {boolean} done - 是否完成（去除 streaming class）
 */
function updateStreamingBubble(msgId, text, done) {
  var el = document.getElementById(msgId);
  if (!el) return;
  var bubble = el.querySelector('.msg-bubble');
  if (!bubble) return;

  if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
    // 流式过程中用纯文本渲染（避免 Markdown 不完整导致格式错乱）
    if (!done) {
      bubble.innerHTML = esc(text);
    } else {
      var rendered = marked.parse(text);
      if (typeof DOMPurify !== 'undefined') rendered = DOMPurify.sanitize(rendered);
      bubble.innerHTML = rendered;
      bubble.classList.remove('streaming');
    }
  } else {
    bubble.textContent = text;
    if (done) bubble.classList.remove('streaming');
  }

  // 滚动到底部
  var c = document.getElementById('chatMsgs');
  if (c) c.scrollTop = c.scrollHeight;
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
    // 兼容旧的非流式 loading
    div.innerHTML = '<div class="msg-avatar">AI</div><div class="msg-bubble"><div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div></div>';
  } else if (role === 'loading-stream') {
    // SSE 流式加载态：带动画点 + 进度文字
    div.innerHTML = '<div class="msg-avatar">AI</div><div class="msg-bubble">' +
      '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>' +
      '<div class="stream-progress" style="display:none;font-size:11px;color:var(--text3);margin-top:6px">AI 正在生成回复…</div>' +
      '</div>';
  } else if (role === 'ai-stream') {
    // SSE 流式输出态：占位，内容由 updateStreamingBubble 逐字更新
    div.innerHTML = '<div class="msg-avatar">AI</div><div class="msg-bubble streaming">' + esc(content || '') + '<span class="stream-cursor">▍</span></div>';
  } else if (role === 'error') {
    div.innerHTML = '<div class="msg-avatar">!</div><div class="msg-bubble" style="color:var(--error)">' + esc(content) + '</div>';
  } else {
    if (typeof marked === 'undefined') console.warn('[Chat] marked.js CDN 加载失败，将回退为纯文本');
    if (typeof DOMPurify === 'undefined') console.warn('[Chat] DOMPurify CDN 加载失败，安全防护降级');
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
