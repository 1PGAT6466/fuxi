// ====== CONFIG ======
var _chatMode = 'ai'; var _chatFilter = 'all'; var _homeSearchMode = 'search';
var _allFiles = []; var _uploadQueue = []; var _uploadPaused = false; var _uploadAborted = false;

// ====== INIT ======
function init(){
  document.querySelectorAll('.nav-item').forEach(function(item){  // Inject enhanced search styles
  var wtSearchStyle = document.createElement('style');
  wtSearchStyle.textContent = '.src-header{font-size:11px;color:var(--text3);font-weight:600;margin-bottom:4px;padding-bottom:4px;border-bottom:1px solid var(--border)}.src-tag{font-size:9px;padding:2px 6px;border-radius:6px;font-weight:600;flex-shrink:0}.src-tag.wiki{background:#e8f5e9;color:#2e7d32}.src-tag.entity{background:#e3f2fd;color:#1565c0}.msg-wt-hints{margin-top:8px}.wt-entity-hints{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}.we-hints-head{width:100%;font-size:11px;color:var(--text3);font-weight:600;margin-bottom:2px}.we-hint-chip{font-size:12px;padding:4px 12px;border-radius:12px;background:var(--pri-light);color:var(--pri);cursor:pointer;transition:all .15s;border:1px solid transparent}.we-hint-chip:hover{background:var(--pri);color:#fff;border-color:var(--pri)}';
  document.head.appendChild(wtSearchStyle);

    item.addEventListener('click',function(){ switchPage(this.dataset.page); });
  });
  updateTime(); setInterval(updateTime, 30000);
  loadHomeStats();
  loadTools();
  loadFAQ();
  loadFilters();
  checkHealth();
  setInterval(checkHealth, 30000);
  // Periodic home stats refresh (every 120s)
  setInterval(function(){
    if(document.getElementById('page-home')&&document.getElementById('page-home').classList.contains('active')){
      loadHomeStats();
    }
  }, 120000);
  // Delegated click handler for wiki cards
  var wikiEl = document.getElementById('wikiResults');
  if (wikiEl) {
    wikiEl.addEventListener('click', function(e){
      var target = e.target.closest('[data-wiki-id]');
      if (!target) return;
      var id = target.getAttribute('data-wiki-id');
      var action = target.getAttribute('data-action');
      if (action === 'view') { viewWikiPage(id); e.stopPropagation(); }
      if (action === 'delete') { e.stopPropagation(); deleteWikiPage(id); }
    });
  }
  // Delegated click for source rows
  document.addEventListener('click', function(ev){
    var btn = ev.target.closest('.src-btn');
    if(!btn) return;
    var row = btn.closest('.src-row');
    if(!row) return;
    var hash = row.getAttribute('data-hash');
    var fn = row.getAttribute('data-fn')||'';
    if(btn.classList.contains('src-btn-view')) viewSource(hash, fn);
    else if(btn.classList.contains('src-btn-dl')) downloadSource(hash, fn);
  });

}
function updateTime(){ document.getElementById('topbarTime').textContent = new Date().toLocaleString('zh-CN'); }
function toggleSidebar(){ document.getElementById('sidebar').classList.toggle('open'); }

// ====== NAVIGATION ======
var _pageLabels = {
  'home': '首页', 'search': 'AI 搜索', 'files': '文件管理', 'upload': '上传文档',
  'wiki': 'LLM-Wiki', 'eval': '评测仪表板', 'tools': '常用工具', 'faq': '常见问题'
};
function setBreadcrumb(name){
  var bc = document.getElementById('breadcrumb');
  if(!bc) return;
  if(name==='home'){ bc.innerHTML=''; return; }
  bc.innerHTML = '<a href="#" onclick="switchPage(\'home\');return false" style="color:var(--text3);text-decoration:none;font-size:12px">首页</a> <span style="color:var(--text3)">›</span> <span style="font-size:12px;color:var(--pri);font-weight:600">'+(_pageLabels[name]||name)+'</span>';
}
function switchPage(name){
  document.querySelectorAll('.nav-item').forEach(function(n){ n.classList.remove('active'); });
  var nav = document.querySelector('[data-page="'+name+'"]');
  if(nav) nav.classList.add('active');
  document.querySelectorAll('.page').forEach(function(p){ p.classList.remove('active'); });
  var page = document.getElementById('page-'+name);
  if(page) page.classList.add('active');
  document.getElementById('topbarTitle').textContent = nav ? nav.textContent.replace(/[\d—]+$/,'').trim() : name;
  setBreadcrumb(name);
  if(name==='home') loadHomeStats();
  if(name==='files' && _allFiles.length===0) loadFileList();
  if(name==='eval' && !document.getElementById('evalContent').innerHTML.trim()) loadEvalDashboard();
  if(name==='wiki' && !window._wikiLoaded) { window._wikiLoaded=true; loadWikiPages(); loadWikiCategories(); }
  if(name==='tools' && !document.getElementById('toolGrid').innerHTML.trim()) loadTools();
  if(name==='faq' && !document.getElementById('faqGrid').innerHTML.trim()) loadFAQ();
}

// ====== HOME STATS ======
function loadHomeStats(){
  // WorldTree hero stats
  fetch('/api/worldtree/stats').then(function(r){ return r.json(); }).then(function(d){
    var nums = document.querySelectorAll('#wtHeroStats .whs-num');
    if(nums.length>=4){
      if(nums[0]) nums[0].textContent = d.wiki_pages||0;
      if(nums[1]) nums[1].textContent = d.entities||0;
      if(nums[2]) nums[2].textContent = d.terms||0;
    }
  }).catch(function(e){ console.log('wt stats err',e); });

  // Health + chunks from /api/health
  fetch('/api/health').then(function(r){ return r.json(); }).then(function(d){
    var nums = document.querySelectorAll('#wtHeroStats .whs-num');
    if(nums.length>=4 && nums[3]) nums[3].textContent = d.total_chunks||0;

    // Sidebar badge
    var badge = document.getElementById('navBadgeFiles');
    if(badge) badge.textContent = d.total_files||'0';

    // Footer
    var sbChunks = document.getElementById('sbChunks');
    if(sbChunks&&d.total_chunks!=null){var _t='📄 '+d.total_chunks+' chunks';if(sbChunks.textContent!=_t)sbChunks.textContent=_t;}
    var sbFiles = document.getElementById('sbFiles');
    if(sbFiles&&d.total_files!=null){var _t='📁 '+d.total_files+' 文件';if(sbFiles.textContent!=_t)sbFiles.textContent=_t;}
  }).catch(function(){});

  // Server status -> health strip
  api('/api/admin/server-status').then(function(d){
    var cpu = d.cpu_percent || 0; var mem = d.memory_percent || 0;
    var disk = d.disk_percent || 0;

    var wtCPU = document.getElementById('wtCPU');
    if(wtCPU&&cpu!=null){var _t='CPU '+cpu+'%';if(wtCPU.textContent!=_t)wtCPU.textContent=_t;}
    var wtMem = document.getElementById('wtMem');
    if(wtMem&&mem!=null){var _t='MEM '+mem+'%';if(wtMem.textContent!=_t)wtMem.textContent=_t;}
    var wtDisk = document.getElementById('wtDisk');
    if(wtDisk&&disk!=null){var _t='DISK '+disk+'%';if(wtDisk.textContent!=_t)wtDisk.textContent=_t;}

    // Uptime
    var wtUptime = document.getElementById('wtUptime');
    if(wtUptime && d.uptime_seconds) {
      var h = Math.floor(d.uptime_seconds/3600);
      var m = Math.floor((d.uptime_seconds%3600)/60);
      wtUptime.textContent = h+'h '+m+'m';
    }

    // Health strip color
    var strip = document.getElementById('wtHealthStrip');
    if(strip){
      strip.className = 'wt-health-strip';
      if(!d.healthy && d.healthy!==undefined) strip.classList.add('warn');
    }

    // Footer resource
    var sbCPU = document.getElementById('sbCPU');
    if(sbCPU&&cpu!=null){var _t='🖥 CPU '+cpu+'%';if(sbCPU.textContent!=_t)sbCPU.textContent=_t;}
    var sbMem = document.getElementById('sbMem');
    if(sbMem&&mem!=null){var _t='💾 MEM '+mem+'%';if(sbMem.textContent!=_t)sbMem.textContent=_t;}
  }).catch(function(e){
    var strip = document.getElementById('wtHealthStrip');
    if(strip) strip.className = 'wt-health-strip down';
    var sbCPU = document.getElementById('sbCPU');
    if(sbCPU&&sbCPU.textContent!='🖥 CPU —')sbCPU.textContent='🖥 CPU —';
    var sbMem = document.getElementById('sbMem');
    if(sbMem&&sbMem.textContent!='💾 MEM —')sbMem.textContent='💾 MEM —';
  });

  // Latest Wiki pages
  fetch('/api/worldtree/wiki/tree').then(function(r){ return r.json(); }).then(function(d){
    var el = document.getElementById('wtDashWikiList');
    if(!el) return;
    var pages = [];
    function walk(nodes, cat){
      if(!nodes) return;
      for(var i=0;i<nodes.length;i++){
        var n = nodes[i];
        if(!n.id && n.children) walk(n.children, n.name||cat);
        if(n.id) pages.push({id:n.id, name:n.name, summary:n.summary, cat:cat||n.name});
        if(n.children) walk(n.children, n.name||cat);
      }
    }
    walk(d.tree||d, '');
    var h = '';
    for(var i=0;i<Math.min(pages.length,8);i++){
      var p = pages[i];
      h += '<div class="wt-page-item" data-wiki-id="'+escapeHtml(p.id)+'" title="'+escapeHtml(p.name)+'" style="cursor:pointer">'
         + '<span class="wt-page-bullet"></span>'
         + '<span class="wt-page-text">'+escapeHtml(p.name)+'</span>'
         + (p.cat ? '<span class="wt-page-cat">'+escapeHtml(p.cat)+'</span>' : '')
         + '</div>';
    }
    if(pages.length===0) h = '<div style="padding:16px;text-align:center;color:var(--text3)">暂无 Wiki 页面</div>';
    el.innerHTML = h;
  }).catch(function(){});

  // Recent entities
  fetch('/api/worldtree/entities?limit=8').then(function(r){ return r.json(); }).then(function(d){
    var el = document.getElementById('wtDashEntityList');
    if(!el) return;
    var entities = d.entities||d||[];
    var typeIcons = {
      'material':'🧱','process':'⚙️','standard':'📏','component':'🔩',
      'equipment':'🏭','software':'💻','network':'🌐','document':'📄',
      'design':'✏️','manufacturing':'🏗️'
    };
    var h = '';
    for(var i=0;i<Math.min(entities.length,8);i++){
      var ent = entities[i];
      var icon = typeIcons[ent.type]||'📌';
      h += '<div class="wtdc-entity-item">'
         + '<span class="wtdc-entity-icon">'+icon+'</span>'
         + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+escapeHtml(ent.name||ent.id||'?')+'</span>'
         + '<span class="wtdc-entity-type">'+escapeHtml(ent.type||'')+'</span>'
         + '</div>';
    }
    if(entities.length===0) h = '<div style="padding:16px;text-align:center;color:var(--text3)">暂无实体</div>';
    el.innerHTML = h;
  }).catch(function(){});
}


// Search related worldtree entities by text keywords
async function searchRelatedEntities(text, container){
  try {
    // Extract potential entity names (2-6 char Chinese/English terms)
    var terms = text.match(/[A-Z]{2,6}|[\u4e00-\u9fa5]{2,6}|[A-Z][a-z]+/g)||[];
    var uniqueTerms = terms.filter(function(t,i){ return terms.indexOf(t)===i; }).slice(0,5);
    var resp = await fetch('/api/search?q='+encodeURIComponent(uniqueTerms.join(' '))+'&limit=5');
    var d = await resp.json();
    var results = d.results||d||[];
    if(!results.length){ container.innerHTML=''; return; }
    var h = '<div class="wt-entity-hints">';
    h += '<div class="we-hints-head">🌳 世界树关联</div>';
    results.slice(0,4).forEach(function(r){
      var name = r.file_name||r.name||r.title||'?';
      h += '<span class="we-hint-chip" onclick="switchPage(\'search\');document.getElementById(\'chatInput\').value=\''+escapeHtml(name)+'\';setTimeout(function(){sendChatMessage();},200)" title=\''+escapeHtml(name)+'\'>🔗 '+escapeHtml(name.substring(0,30))+'</span>';
    });
    h += '</div>';
    container.innerHTML = h;
  } catch(e){ container.innerHTML=''; }
}
// Animate a number counter
var _animatingNums = {};
function animateNum(el, target){
  var key = el.textContent;
  if(_animatingNums[key]) return;
  _animatingNums[key] = true;
  var start = parseInt(el.textContent)||0;
  var duration = 800;
  var startTime = null;
  function step(ts){
    if(!startTime) startTime = ts;
    var progress = Math.min((ts-startTime)/duration, 1);
    // ease-out-expo
    var eased = progress===1 ? 1 : 1 - Math.pow(2, -10*progress);
    var val = Math.round(start + (target-start)*eased);
    el.textContent = val;
    if(progress<1) requestAnimationFrame(step);
    else { el.textContent = target; delete _animatingNums[key]; }
  }
  requestAnimationFrame(step);
}

function setHomeSearchMode(m){ _homeSearchMode=m;
  document.getElementById('homeModeKw').classList.toggle('active',m==='search');
  document.getElementById('homeModeAI').classList.toggle('active',m==='ai');
}
function quickSearchHome(){
  var q = document.getElementById('homeSearchInput').value.trim(); if(!q) return;
  switchPage('search'); document.getElementById('chatInput').value = q;
    setTimeout(function(){ sendChatMessage(); }, 300);
}

// ====== HEALTH ======
function checkHealth(){
  fetch('/api/health').then(function(r){ return r.json(); }).then(function(d){
    var dot = document.getElementById('sidebarStatusDot');
    var txt = document.getElementById('sidebarStatusText');
    if(d.status==='healthy'){ dot.className='status-dot'; txt.textContent='系统正常 · '+(d.uptime_seconds||0)+'s'; }
    else { dot.className='status-dot warn'; txt.textContent='系统繁忙'; }
    // Also update health strip uptime
    var wtUptime = document.getElementById('wtUptime');
    if(wtUptime && d.uptime_seconds){
      var h = Math.floor(d.uptime_seconds/3600);
      var m = Math.floor((d.uptime_seconds%3600)/60);
      wtUptime.textContent = h+'h '+m+'m';
    }
  }).catch(function(){
    document.getElementById('sidebarStatusDot').className='status-dot off';
    document.getElementById('sidebarStatusText').textContent='离线 · 请检查服务器';
    var strip = document.getElementById('wtHealthStrip');
    if(strip) strip.className = 'wt-health-strip down';
  });
}


// ====== Loading Helpers ======
function showLoading(el, text) {
  if (!el) return;
  el.innerHTML = '<div style="text-align:center;padding:40px"><div class="loading loading-lg"></div><div style="margin-top:12px;font-size:13px;color:var(--text3)">' + (text || '加载中…') + '</div></div>';
}
function showError(el, msg, retryFn) {
  if (!el) return;
  var retry = retryFn ? ' <button class="btn btn-outline" onclick="' + retryFn + '" style="margin-top:8px">重试</button>' : '';
  el.innerHTML = '<div style="text-align:center;padding:40px;color:var(--red)"><div style="font-size:24px;margin-bottom:8px">&#9888;</div><div style="font-size:13px">' + escapeHtml(msg || '加载失败') + '</div>' + retry + '</div>';
}
function showToast(msg, duration) {
  var t = document.getElementById('sidebarToast');
  if (!t) { t = document.createElement('div'); t.id = 'sidebarToast'; t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  setTimeout(function(){ t.classList.remove('show'); }, duration || 2000);
}
// ====== SEARCH ======
// switchChatMode removed - unified to AI-only
function setChatFilter(v){ _chatFilter=v; }
function handleChatKeydown(e){ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); sendChatMessage(); } }
function autoResizeChatInput(){ var t=document.getElementById('chatInput'); t.style.height='';t.style.height=t.scrollHeight+'px'; }

function fillSearch(q) {
  var input = document.getElementById('chatInput');
  input.value = q;
  input.focus();
  autoResizeChatInput();
}
function onInputFocus() {
  var bar = document.querySelector('.chat-input-bar');
  if (bar) bar.style.boxShadow = '0 0 0 3px var(--pri-light)';
}
function onInputBlur() {
  var bar = document.querySelector('.chat-input-bar');
  if (bar) bar.style.boxShadow = '';
}

async function sendChatMessage(){
  var input = document.getElementById('chatInput'); var q = input.value.trim();
  if(!q) return;
  var msgs = document.getElementById('chatMessages');
  var empty = msgs.querySelector('.chat-empty'); if(empty) empty.style.display='none';
  addBubble('user',q);
  input.value=''; input.style.height=''; input.focus();
  var btn = document.getElementById('chatSendBtn'); btn.disabled=true;

  // AI search: streaming mode
  var thinkId = addThinking();
  var bubbleId = null;
  var fullText = '';
  var allSources = [];
  try {
    var resp = await fetch('/api/chat',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({query:q,category:_chatFilter,stream:true,history:chatHistory.slice(-10)})
    });
    removeThinking(thinkId);
    
    if(resp.headers.get('content-type','').indexOf('text/event-stream') !== -1){
      // SSE streaming mode
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';
      
      while(true){
        var result = await reader.read();
        if(result.done) break;
        buffer += decoder.decode(result.value, {stream:true});
        
        var lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line in buffer
        
        for(var i = 0; i < lines.length; i++){
          var line = lines[i].trim();
          if(!line.startsWith('data: ')) continue;
          var data = line.slice(6);
          if(data === '[DONE]') continue;
          
          try{
            var parsed = JSON.parse(data);
            if(parsed.sources){
              allSources = parsed.sources;
              // Create bubble with empty text first
              bubbleId = addBubble('assistant', '', allSources);
            }
            if(parsed.token){
              if(!bubbleId){
                bubbleId = addBubble('assistant', '', []);
              }
              fullText += parsed.token;
              var bodyEl = document.getElementById(bubbleId);
              if(bodyEl){
                bodyEl.innerHTML = formatMarkdown(fullText, bubbleId);
                document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
              }
            }
          }catch(e){}
        }
      }
      
      if(!bubbleId){
        addBubble('assistant', fullText || '未找到相关内容。', allSources);
      }
    } else {
      // Fallback: non-streaming JSON
      var d = await resp.json();
      if(d.answer) addBubble('assistant', d.answer, d.sources||d.results||[]);
      else addBubble('assistant', '未找到相关内容。');
    }
  }catch(e){ removeThinking(thinkId); addBubble('assistant','请求失败：'+e.message); }
  btn.disabled=false;
}

function formatSearchResults(results){
  var html = '<div style="font-weight:600;margin-bottom:8px">找到 '+results.length+' 条相关结果：</div>';
  results.forEach(function(r,i){
    var text = (r.text_preview||r.text||'').substring(0,250);
    var fn = r.file_name||'未知文件';
    html += '<div style="margin-bottom:10px;padding:8px;background:var(--bg);border-radius:8px;font-size:13px">';
    html += '<div style="font-weight:600;color:var(--pri);margin-bottom:2px">'+(i+1)+'. <span class="source-ref" onclick="viewSource(\''+escapeHtml(r.file_hash||'')+'\',\''+escapeHtml(fn)+'\')">'+escapeHtml(fn)+'</span></div>';
    html += '<div>'+escapeHtml(text)+'</div></div>';
  });
  return html;
}

function addBubble(role,text,sources){
  var msgs = document.getElementById('chatMessages');
  var isAI = role==='assistant';
  var html = '<div class="msg-bubble '+role+'">';
  html += '<div class="msg-avatar '+role+'">'+(isAI?'🤖':'👤')+'</div>';
  var bubbleId = 'bubble_'+Date.now()+'_'+Math.random().toString(36).slice(2,6);
  html += '<div class="msg-content '+role+'"><div class="msg-body" id="'+bubbleId+'">'+formatMarkdown(text, bubbleId)+'</div>';
  if(sources && sources.length>0 && isAI){
    html += '<div class="msg-sources">';
    html += '<div class="src-header">📚 参考来源</div>';
    sources.slice(0,5).forEach(function(s,i){
      var fn = s.file_name||'来源'+(i+1);
      var fh = s.file_hash||'';
      var tag = '';
      if(s.wiki_page_id) tag = '<span class="src-tag wiki">Wiki</span>';
      else if(s.entity_name) tag = '<span class="src-tag entity">实体</span>';
      html += '<div class="src-row" id="src_'+bubbleId+'_'+(i+1)+'" data-ref-id="'+(i+1)+'" data-msg="'+bubbleId+'" data-hash="'+escapeHtml(fh)+'" data-fn="'+escapeHtml(fn)+'">';
      html += '<span class="src-file">📄 '+escapeHtml(fn.substring(0,55))+'</span>'+tag;
      html += '<span class="src-actions">';
      html += '<button class="src-btn src-btn-view">📋 查看</button>';
      html += '<button class="src-btn src-btn-dl">⬇ 下载</button>';
      html += '</span></div>';
    });
    html += '</div>';
  }
  // WorldTree entity hints — async fetch
  if(isAI && text){
    html += '<div class="msg-wt-hints" id="msg-hints-'+Date.now()+'"><span style="font-size:11px;color:var(--text3)">🔗 关联实体查询中…</span></div>';
  }
  html += '<div class="msg-time">'+new Date().toLocaleTimeString()+'</div></div></div>';
  msgs.insertAdjacentHTML('beforeend',html);
  msgs.scrollTop = msgs.scrollHeight;
  // Trigger entity search after render
  if(isAI && text){
    var hintsEl = msgs.querySelector('.msg-wt-hints:last-child');
    if(hintsEl) searchRelatedEntities(text.substring(0,120), hintsEl);
  }
}

function addThinking(){
  var id = 'think_'+Date.now();
  document.getElementById('chatMessages').insertAdjacentHTML('beforeend',
    '<div class="msg-bubble assistant" id="'+id+'"><div class="msg-avatar assistant">🤖</div><div class="msg-body">思考中<span class="thinking-dots">...</span></div></div>');
  return id;
}
function removeThinking(id){ var el=document.getElementById(id); if(el) el.remove(); }

function viewSource(hash,fn){
  var ext = (fn||'').toLowerCase().split('.').pop();
  var isPDF = (ext === 'pdf');
  var isImage = /^(png|jpg|jpeg|gif|bmp|webp|svg)$/.test(ext);
  var isOffice = /^(docx|doc|xlsx|xls|pptx|ppt)$/.test(ext);
  var isBinary = isPDF || isImage || isOffice || /^(dwg|dxf|step|stp|stl|igs|zip|rar|7z|tar|gz|exe|dll)$/.test(ext);
  
  if (isPDF) {
    // PDF: try to open raw file in new tab, fallback to download
    var dlUrl = '/api/download/'+encodeURIComponent(hash);
    var viewUrl = '/api/view/'+encodeURIComponent(hash);
    window.open(viewUrl, '_blank');
    return;
  }
  if (isImage) {
    // Image: show in modal
    var overlay = document.createElement('div'); overlay.className='modal-overlay';
    overlay.innerHTML = '<div class="modal" style="max-width:90vw;max-height:90vh"><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()">✕</button><h3>🖼️ '+escapeHtml(fn||'图片预览')+'</h3><div style="text-align:center;padding:16px"><img src="'+'/api/download/'+encodeURIComponent(hash)+'" style="max-width:100%;max-height:70vh" onerror="this.parentElement.innerHTML=\'<div style=color:var(--red);padding:40px>⚠️ 无法加载图片，请尝试下载</div>\'"/></div></div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click',function(e){ if(e.target===overlay) overlay.remove(); });
    return;
  }
  if (isBinary) {
    // Office / CAD / archives: show metadata preview + download button
    var overlay = document.createElement('div'); overlay.className='modal-overlay';
    overlay.innerHTML = '<div class="modal" style="max-width:800px"><button class="modal-close" onclick="this.closest(".modal-overlay").remove()">X</button><h3> '+escapeHtml(fn||'文档预览')+'</h3><div style="text-align:center;padding:40px"><p style="font-size:48px;margin-bottom:16px"> '+(isPDF ? '?' : isOffice ? '?' : isImage ? '?' : '?')+'</p><p style="font-size:14px;color:var(--text2);margin-bottom:8px">'+escapeHtml(fn)+'</p><p style="font-size:13px;color:var(--text3);margin-bottom:20px">此文件为二进制格式，无法直接预览文本内容</p><button onclick="downloadSource(\''+hash+'\',\''+escapeHtml(fn)+'\')" style="padding:10px 24px;font-size:14px;background:var(--pri);color:#fff;border:none;border-radius:8px;cursor:pointer">? 下载原始文件</button></div></div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click',function(e){ if(e.target===overlay) overlay.remove(); });
    return;
  }
  
  // Text files (md, txt, csv, json, xml, py, js, html, css, log, etc.): preview as text
  var overlay = document.createElement('div'); overlay.className='modal-overlay';
  overlay.innerHTML = '<div class="modal" style="max-width:800px"><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()">✕</button><h3>📄 '+escapeHtml(fn||'文档预览')+'</h3><pre style="max-height:70vh;overflow:auto;white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.6;background:#f8f9fa;padding:16px;border-radius:8px">加载中…</pre></div>';
  document.body.appendChild(overlay);
  overlay.addEventListener('click',function(e){ if(e.target===overlay) overlay.remove(); });
  var pre = overlay.querySelector('pre');
  var url = '/api/search/chunk/'+encodeURIComponent(fn||hash);
  fetch(url).then(function(r){ return r.json(); }).then(function(d){
    pre.textContent = (d.text||d.content||d.preview||'无法加载内容').substring(0,10000);
  }).catch(function(){ pre.textContent='加载失败，请尝试下载'; });
}

function downloadSource(hash,fn){
  // Use file_hash for download (more reliable)
  var url = '/api/download/'+encodeURIComponent(hash||fn);
  var a = document.createElement('a'); a.href=url; a.download=fn||'document'; a.rel='noopener'; a.click();
}

function formatMarkdown(md, msgId){
  if(!md) return '';
  var id = msgId || '';
  // Use marked.js if available, fallback to basic rendering
  if(typeof marked !== 'undefined'){
    try {
      marked.setOptions({breaks:true, gfm:true, headerIds:false, mangle:false});
      var html = marked.parse(md);
      // Post-process: add citation badges
      html = html.replace(/\[Wiki\s+(\d+)\]/g, '<span class="cite-badge cite-wiki" data-ref="$1" data-msg="'+id+'" onclick="highlightSource(this)">Wiki $1</span>');
      html = html.replace(/\[Ref\s+(\d+)\]/g, '<span class="cite-badge cite-ref" data-ref="$1" data-msg="'+id+'" onclick="highlightSource(this)">Ref $1</span>');
      html = html.replace(/\[来源[:：]\s*(.+?)\]/g, '<span class="cite-badge cite-src">📄 $1</span>');
      html = html.replace(/\*\*来源(\d+)\*\*/g, '<span class="cite-badge cite-src-num" data-ref="$1" data-msg="'+id+'" onclick="highlightSource(this)">来源$1</span>');
      return html;
    } catch(e) { /* fallback below */ }
  }
  // Fallback: basic markdown
  var html = md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  html = html.replace(/\[Wiki\s+(\d+)\]/g, '<span class="cite-badge cite-wiki" data-ref="$1" data-msg="'+id+'" onclick="highlightSource(this)">Wiki $1</span>');
  html = html.replace(/\[Ref\s+(\d+)\]/g, '<span class="cite-badge cite-ref" data-ref="$1" data-msg="'+id+'" onclick="highlightSource(this)">Ref $1</span>');
  html = html.replace(/\[来源[:：]\s*(.+?)\]/g, '<span class="cite-badge cite-src">📄 $1</span>');
  html = html.replace(/\*\*来源(\d+)\*\*/g, '<span class="cite-badge cite-src-num" data-ref="$1" data-msg="'+id+'" onclick="highlightSource(this)">来源$1</span>');
  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Headers
  html = html.replace(/^### (.+)/gm, '<h4>$1</h4>').replace(/^## (.+)/gm, '<h3>$1</h3>').replace(/^# (.+)/gm, '<h2>$1</h2>');
  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Lists
  html = html.replace(/^[\-\*] (.+)/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  html = html.replace(/^(\d+)\. (.+)/gm, '<li>$2</li>');
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--pri)">$1</a>');
  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  return html;
}
function escapeHtml(s){ if(!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

function highlightSource(el) {
  var refNum = el.getAttribute('data-ref');
  var msgId = el.getAttribute('data-msg');
  if (!refNum || !msgId) return;
  // 找到对应的来源行
  var srcRow = document.getElementById('src_'+msgId+'_'+refNum);
  if (!srcRow) return;
  // 移除之前的高亮
  document.querySelectorAll('.src-row.highlight').forEach(function(r){ r.classList.remove('highlight'); });
  // 高亮当前行
  srcRow.classList.add('highlight');
  // 滚动到可见区域
  srcRow.scrollIntoView({behavior:'smooth',block:'center'});
  // 3秒后自动取消高亮
  setTimeout(function(){ srcRow.classList.remove('highlight'); }, 3000);
}


// ====== FILE MANAGEMENT ======
var _filePage = 1;
var _filePageSize = 50;

function loadFileList(){
  fetch('/api/documents?page=1&page_size=500').then(function(r){ return r.json(); }).then(function(d){
    var files = d.files||[];
    _allFiles = files;
    _filePage = 1;
    renderFileListPaged(_allFiles);
  }).catch(function(){ document.getElementById('fileListContainer').innerHTML='<div style="text-align:center;padding:40px;color:var(--text3)">加载失败</div>'; });
}

function renderFileListPaged(files){
  var container = document.getElementById('fileListContainer');
  var total = files.length;
  if(!total){ container.innerHTML='<div style="text-align:center;padding:40px;color:var(--text3)">暂无文件</div>'; document.getElementById('navBadgeFiles').textContent='0'; return; }

  var totalPages = Math.ceil(total / _filePageSize);
  if (_filePage > totalPages) _filePage = totalPages;
  var start = (_filePage - 1) * _filePageSize;
  var pageFiles = files.slice(start, start + _filePageSize);

  var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">';
  html += '<span style="font-size:13px;color:var(--t3)">共 <b>' + total + '</b> 个文件 · 第 <b>' + _filePage + '</b>/' + totalPages + ' 页</span>';
  html += '<div style="display:flex;gap:6px">';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage=1;renderFileListPaged(_allFiles)"' + (_filePage<=1?' disabled':'') + '>« 首页</button>';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage--;renderFileListPaged(_allFiles)"' + (_filePage<=1?' disabled':'') + '>‹ 上一页</button>';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage++;renderFileListPaged(_allFiles)"' + (_filePage>=totalPages?' disabled':'') + '>下一页 ›</button>';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage=' + totalPages + ';renderFileListPaged(_allFiles)"' + (_filePage>=totalPages?' disabled':'') + '>末页 »</button>';
  html += '</div></div>';

  html += '<table><thead><tr><th>文件名</th><th>类型</th><th>日期</th><th>操作</th></tr></thead><tbody>';
  pageFiles.forEach(function(f){
    var fn = f.file_name||f.name||'未知';
    var ft = (f.file_type||f.type||'').toUpperCase();
    var date = (f.created_at||f.date||'').substring(0,10);
    var icon = ft.includes('PDF')?'📕':ft.includes('DOC')?'📘':ft.includes('XLS')?'📗':ft.includes('DWG')||ft.includes('DXF')?'📐':ft.includes('STEP')||ft.includes('STL')?'🧊':'📄';
    html += '<tr><td><span class="file-name" onclick="viewSource(\''+escapeHtml(f.file_hash||'')+'\',\''+escapeHtml(fn)+'\')"><span class="file-icon">'+icon+'</span>'+escapeHtml(fn)+'</span></td>';
    html += '<td>'+ft+'</td><td>'+date+'</td>';
    html += '<td><button class="btn btn-outline btn-sm" onclick="viewSource(\''+escapeHtml(f.file_hash||'')+'\',\''+escapeHtml(fn)+'\')">📋 查看</button> <button class="btn btn-outline btn-sm" onclick="downloadSource(\''+escapeHtml(f.file_hash||'')+'\',\''+escapeHtml(fn)+'\')">⬇ 下载</button></td></tr>';
  });
  html += '</tbody></table>';

  // Bottom pagination
  html += '<div style="display:flex;justify-content:center;align-items:center;gap:8px;margin-top:16px">';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage=1;renderFileListPaged(_allFiles)"' + (_filePage<=1?' disabled':'') + '>«</button>';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage--;renderFileListPaged(_allFiles)"' + (_filePage<=1?' disabled':'') + '>‹</button>';
  var maxBtns = 7;
  var pStart = Math.max(1, _filePage - 3);
  var pEnd = Math.min(totalPages, pStart + maxBtns - 1);
  if (pEnd - pStart < maxBtns - 1) pStart = Math.max(1, pEnd - maxBtns + 1);
  if (pStart > 1) html += '<span style="color:var(--t3);font-size:12px">…</span>';
  for (var pi = pStart; pi <= pEnd; pi++) {
    html += '<button class="btn btn-outline btn-sm" style="' + (pi===_filePage?'background:var(--pri);color:#fff;border-color:var(--pri)':'') + '" onclick="_filePage=' + pi + ';renderFileListPaged(_allFiles)">' + pi + '</button>';
  }
  if (pEnd < totalPages) html += '<span style="color:var(--t3);font-size:12px">…</span>';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage++;renderFileListPaged(_allFiles)"' + (_filePage>=totalPages?' disabled':'') + '>›</button>';
  html += '<button class="btn btn-outline btn-sm" onclick="_filePage=' + totalPages + ';renderFileListPaged(_allFiles)"' + (_filePage>=totalPages?' disabled':'') + '>»</button>';
  html += '</div>';

  container.innerHTML = html;
  document.getElementById('navBadgeFiles').textContent = total;
}

function filterFiles(){
  var q = (document.getElementById('fileSearchInput').value||'').toLowerCase();
  var filtered = q ? _allFiles.filter(function(f){ var fn=(f.file_name||f.name||'').toLowerCase(); return fn.includes(q); }) : _allFiles;
  _filePage = 1;
  renderFileListPaged(filtered);
}

// ====== UPLOAD ======
function onFilesPicked(input){
  var files = Array.from(input.files);
  if(!files.length) return;
  _uploadQueue = files; _uploadPaused=false; _uploadAborted=false;
  document.getElementById('uploadMsg').textContent = '准备上传 '+files.length+' 个文件…';
  document.getElementById('uploadMsg').className = 'upload-msg';
  processUpload();
}
async function processUpload(){
  var bar = document.getElementById('uploadProgress'); var barFill = document.getElementById('uploadBar');
  var msg = document.getElementById('uploadMsg');
  document.getElementById('pauseBtn').disabled=false; document.getElementById('cancelBtn').disabled=false;
  bar.style.display='block'; barFill.style.width='0%';
  var total = _uploadQueue.length; var done = 0; var failed = 0;

  for(var i=0;i<_uploadQueue.length;i++){
    if(_uploadAborted){ msg.textContent='上传已取消'; msg.className='upload-msg err'; break; }
    while(_uploadPaused && !_uploadAborted){ await sleep(500); }
    if(_uploadAborted) break;
    var file = _uploadQueue[i];
    msg.textContent = '上传中 ('+(i+1)+'/'+total+'): '+file.name;
    var form = new FormData(); form.append('file',file);
    try {
      var r = await fetch('/api/upload',{method:'POST',body:form});
      if(r.ok){ done++; } else { failed++; }
    }catch(e){ failed++; }
    barFill.style.width = ((i+1)/total*100)+'%';
  }
  if(!_uploadAborted){
    msg.textContent = '✅ 完成：'+done+' 成功'+(failed>0?'，'+failed+' 失败':'');
    msg.className = 'upload-msg '+(failed>0?'err':'ok');
  }
  document.getElementById('pauseBtn').disabled=true; document.getElementById('cancelBtn').disabled=true;
  bar.style.display='none';
  _uploadQueue = [];
}
function pauseUpload(){ _uploadPaused=!_uploadPaused; document.getElementById('pauseBtn').textContent=_uploadPaused?'▶ 继续':'⏸ 暂停'; }
function cancelUpload(){ _uploadAborted=true; }
function sleep(ms){ return new Promise(function(r){ setTimeout(r,ms); }); }

// ====== WIKI ======
function loadWikiCategories(){
  fetch('/api/wiki/stats').then(function(r){return r.json()}).then(function(d){
    var sel=document.getElementById('wikiCatFilter');
    Object.keys(d.category_distribution||{}).forEach(function(c){
      var opt=document.createElement('option'); opt.value=c; opt.textContent=c+' ('+d.category_distribution[c]+')'; sel.appendChild(opt);
    });
    document.getElementById('wikiInfo').textContent = d.total_pages+' 页 · '+d.categories+' 分类';
    document.getElementById('navBadgeWiki').textContent = d.total_pages||'—';
  });
}
function loadWikiPages(cat){
  var url='/api/wiki/pages?limit=50'; if(cat) url+='&category='+encodeURIComponent(cat);
  fetch(url).then(function(r){return r.json()}).then(function(d){
    document.getElementById('wikiResults').innerHTML = (d.pages||[]).map(function(p){
      return '<div class="result-card" data-wiki-id="'+p.id+'" data-action="view" style="cursor:pointer;padding:16px;margin-bottom:8px">'+
        '<div style="display:flex;justify-content:space-between;align-items:center">'+
        '<div><div style="font-weight:600;color:var(--pri)">'+escapeHtml(p.title)+'</div>'+
        '<div style="font-size:11px;color:var(--text3);margin-top:3px">'+(p.tags||[]).map(function(t){return '<span style="display:inline-block;background:var(--bg);padding:2px 8px;border-radius:4px;margin-right:4px;font-size:11px">'+escapeHtml(t)+'</span>'}).join('')+'</div></div>'+
        '<button data-wiki-id="'+p.id+'" data-action="delete" style="padding:4px 10px;font-size:11px;background:#fee;color:#c33;border:1px solid #fcc;border-radius:4px;cursor:pointer;white-space:nowrap">删除</button></div>'+
        '<div style="font-size:12px;color:var(--text3);margin-top:4px">'+(p.summary||'').substring(0,200)+'</div></div>';
    }).join('')||'<div style="text-align:center;padding:40px;color:var(--text3)">暂无页面</div>';
  });
}

function uploadWikiFile(file){
  if(!file) return;
  var s=document.getElementById('wikiUploadStatus');
  s.style.display='block'; s.className='wiki-upload-processing'; s.textContent='上传中: '+file.name;
  var fd=new FormData(); fd.append('file',file);
  fd.append('source','wiki_upload');
  fetch('/api/wiki/upload',{method:'POST',body:fd})
    .then(function(r){return r.json();})
    .then(function(d){
      if(d.ok){ s.className='wiki-upload-ok'; s.textContent='已上传: '+file.name+' - 等待提炼入库';
        setTimeout(function(){s.style.display='none';loadWikiPages();},3000); }
      else { s.className='wiki-upload-err'; s.textContent='上传失败: '+(d.error||'未知错误'); }
    }).catch(function(e){ s.className='wiki-upload-err'; s.textContent='网络错误'; });
}
function searchWiki(){
  var q=document.getElementById('wikiSearchInput').value.trim(); if(!q) return loadWikiPages();
  fetch('/api/wiki/search?q='+encodeURIComponent(q)+'&limit=20').then(function(r){return r.json()}).then(function(d){
    document.getElementById('wikiResults').innerHTML = (d.pages||d.results||[]).map(function(p){
      return '<div class="result-card" data-wiki-id="'+p.id+'" data-action="view" style="cursor:pointer;padding:16px;margin-bottom:8px">'+
        '<div style="font-weight:600;color:var(--pri)">'+escapeHtml(p.title)+'</div>'+
        '<div style="font-size:11px;color:var(--text3);margin-top:3px">'+(p.tags||[]).map(function(t){return '<span style="display:inline-block;background:var(--bg);padding:2px 8px;border-radius:4px;margin-right:4px;font-size:11px">'+escapeHtml(t)+'</span>'}).join('')+'</div>'+
        '<div style="font-size:12px;color:var(--text3);margin-top:4px">'+(p.summary||p.content||'').substring(0,200)+'</div>'+
        '<button data-wiki-id="'+p.id+'" data-action="delete" style="margin-top:6px;padding:4px 10px;font-size:11px;background:#fee;color:#c33;border:1px solid #fcc;border-radius:4px;cursor:pointer">删除</button></div>';
    }).join('')||'<div style="text-align:center;padding:40px;color:var(--text3)">未找到</div>';
  });
}

function deleteWikiPage(pid){
  if(!confirm('确认删除此Wiki页面？')) return;
  fetch('/api/wiki/page/'+pid,{method:'DELETE'}).then(function(r){return r.json()}).then(function(d){
    if(d.ok){ alert('已删除'); searchWiki(); } else { alert('删除失败: '+(d.error||'')); }
  });
}
function viewWikiPage(pid){
  var detail=document.getElementById('wikiPageDetail'); detail.style.display='block';
  detail.innerHTML='<div style="text-align:center;padding:20px">加载中…</div>';
  document.getElementById('wikiResults').style.display='none';
  fetch('/api/wiki/page/'+pid).then(function(r){return r.json()}).then(function(p){
    detail.innerHTML = '<div style="background:var(--card);border-radius:var(--radius);padding:24px;box-shadow:var(--shadow)">'+
      '<div style="display:flex;justify-content:space-between;margin-bottom:16px"><h3>'+escapeHtml(p.title)+'</h3>'+
      '<button class="btn btn-outline btn-sm" onclick="closeWikiPage()">← 返回</button></div>'+
      '<div class="msg-body">'+formatMarkdown(p.content||'')+'</div></div>';
  });
}
function closeWikiPage(){ document.getElementById('wikiPageDetail').style.display='none'; document.getElementById('wikiResults').style.display='grid'; }

// ====== EVAL ======
function loadEvalDashboard(){
  fetch('/api/dashboard').then(function(r){return r.json()}).then(function(d){
    var st=d.status||{},ret=d.retrieval||{},rag=d.ragas||{},rr=d.rerank||{};
    var html = '<div style="text-align:center;margin-bottom:16px;color:var(--text2);font-size:13px">📁 '+(st.total_files||'—')+' 文件 · 🧩 '+(st.total_chunks||'—')+' chunks · 🔢 '+(st.vector_count||'—')+' 向量 · 🕐 '+(st.timestamp||'—')+'</div>';
    html += '<div class="eval-section-title">🔍 L1 检索层</div><div class="eval-grid">';
    html += evCard('Recall@5',ret.recall_at_5,100,'%','e53935'); html += evCard('Recall@10',ret.recall_at_10,100,'%','ff6700');
    html += evCard('MRR',ret.mrr,1,'','07c160'); html += evCard('Latency',ret.avg_latency_ms,2000,'ms','00bcd4');
    html += '</div><div class="eval-section-title">🧪 L2-L4 RAGAS</div><div class="eval-grid">';
    html += evCard('Context Precision',rag.context_precision,1,'%','e53935'); html += evCard('Context Recall',rag.context_recall,1,'%','ff6700');
    html += evCard('Faithfulness',rag.faithfulness,1,'%','07c160'); html += evCard('Answer Relevancy',rag.answer_relevancy,1,'%','00bcd4');
    html += '</div><div class="eval-section-title">🔄 Rerank</div><div class="eval-grid" style="grid-template-columns:repeat(2,1fr)">';
    html += '<div class="eval-card"><div class="card-label">模型</div><div class="card-value" style="font-size:16px;color:var(--pri)">'+(rr.model||'—')+'</div></div>';
    html += evCard('平均分',rr.avg_rerank_score,1,'','ff6700');
    html += '</div>';
    document.getElementById('evalContent').innerHTML = html;
  });
}
function evCard(label,val,max,suffix,color){
  var v = (typeof val==='number')?val:parseFloat(val)||0;
  var pct = Math.min(v/max*100,100);
  var display = (max===1)?(v*100).toFixed(0)+'%' : v.toFixed(1)+suffix;
  return '<div class="eval-card"><div class="card-label">'+label+'</div><div class="card-value" style="color:#'+color+'">'+display+'</div><div class="card-bar"><div class="card-bar-fill" style="width:'+pct+'%"></div></div></div>';
}

// ====== TOOLS & FAQ ======
function loadTools(){
  fetch('/api/tools').then(function(r){return r.json()}).then(function(d){
    var tools = Array.isArray(d) ? d : (d.tools||d.data||[]);
    if(!tools.length){ document.getElementById('toolGrid').innerHTML='<div style="text-align:center;padding:40px;color:var(--text3)">暂无工具</div>'; return; }
    var categories = {};
    tools.forEach(function(t){
      var cat = t.category||t.group||'其他';
      if(!categories[cat]) categories[cat]=[];
      categories[cat].push(t);
    });
    var html = '';
    for(var cat in categories){
      html += '<div class="tool-category">';
      html += '<div class="tc-head"><span class="tc-icon">'+catIcon(cat)+'</span>'+cat+'</div>';
      html += '<div class="tc-grid">';
      categories[cat].forEach(function(t){
        var status = t.available!==false ? '<span class="tool-status available">可用</span>' : '<span class="tool-status offline">暂未开放</span>';
        var avCls = t.available!==false ? '' : ' disabled';
        html += '<div class="tool-item'+avCls+'" onclick="toolAction(\''+escapeHtml(t.url||'')+'\',\''+escapeHtml(t.name||'')+'\')">';
        html += '<span class="tool-item-icon">'+escapeHtml(t.icon||'🔧')+'</span>';
        html += '<div class="tool-item-body">';
        html += '<div class="tool-item-name">'+escapeHtml(t.name||t.title||'工具')+status+'</div>';
        html += '<div class="tool-item-desc">'+escapeHtml(t.desc||t.description||'暂无描述')+'</div>';
        html += '</div>';
        html += '<span class="tool-item-arrow">→</span>';
        html += '</div>';
      });
      html += '</div></div>';
    }
    document.getElementById('toolGrid').innerHTML = html;
  }).catch(function(){});
}
function catIcon(cat){
  var m = {'网络':'🌐','办公':'📋','IT':'🖥','HR':'👥','生产':'🏭','安全':'🔒','管理':'⚙️'};
  return m[cat]||'📦';
}
function toolAction(url, name){
  if(!url || url==='#'){ quickSearch(name); return; }
  if(url.startsWith('#')){ return; }
  window.open(url, '_blank');
}
function loadFAQ(){
  var _DEFAULT_FAQ = [
    {q:'RAG 系统包含哪些关键技术？',cat:'AI知识'},
    {q:'PA66 工程塑料的机械性能参数',cat:'材料'},
    {q:'企业网络 VLAN 划分最佳实践',cat:'网络'},
    {q:'自动化产线中 PLC 选型要点',cat:'自动化'},
    {q:'知识库文档上传支持哪些格式？',cat:'使用'},
    {q:'连接器PIN针正向力设计原则',cat:'设计'},
    {q:'Foxconn 连接器塑胶材料选择',cat:'材料'},
    {q:'泛微OA流程引擎配置方法',cat:'办公'},
    {q:'伺服电机选型 HG-KN 系列',cat:'自动化'},
    {q:'PCB焊接温度曲线控制要点',cat:'制造'},
    {q:'如何配置 DHCP 和 DNS 服务？',cat:'网络'},
    {q:'模具冷却系统设计要点',cat:'设计'},
  ];
  fetch('/api/faq').then(function(r){return r.json()}).then(function(d){
    var faqs = (Array.isArray(d) && d.length) ? d : ((d&&d.faqs&&d.faqs.length) ? d.faqs : ((d&&d.data&&d.data.length) ? d.data : _DEFAULT_FAQ));
    var grouped = {};
    faqs.forEach(function(f){
      var q = f.question||f.q||f.title||'';
      var cat = f.category||f.cat||'常见问题';
      if(!grouped[cat]) grouped[cat]=[];
      grouped[cat].push(q);
    });
    var html = '';
    for(var cat in grouped){
      html += '<div class="faq-section">';
      html += '<div class="faq-section-head"><span class="faq-cat-icon">'+faqCatEmoji(cat)+'</span>'+cat+'<span class="faq-cat-count">'+grouped[cat].length+' 条</span></div>';
      html += '<div class="faq-list">';
      grouped[cat].forEach(function(q,i){
        html += '<div class="faq-card" onclick="quickSearch(\''+escapeHtml(q)+'\')">';
        html += '<span class="faq-num">'+(i+1)+'</span>';
        html += '<span class="faq-text">'+escapeHtml(q)+'</span>';
        html += '<span class="faq-arr">↗</span>';
        html += '</div>';
      });
      html += '</div></div>';
    }
    document.getElementById('faqGrid').innerHTML = html||'<div style="text-align:center;padding:40px;color:var(--text3)">暂无常见问题</div>';
  }).catch(function(){});
}
function faqCatEmoji(cat){
  var m={'AI知识':'🧠','材料':'🧱','网络':'🌐','自动化':'🏭','使用':'📖','设计':'📐','办公':'📋','制造':'🔧','常见问题':'💡'};
  return m[cat]||'💡';
}
function loadFilters(){
  api('/api/admin/stats').then(function(d){
    var cats = d.categories||d.category_distribution||{};
    var sel = document.getElementById('chatFilter');
    Object.keys(cats).slice(0,10).forEach(function(c){ var opt=document.createElement('option'); opt.value=c; opt.textContent=c; sel.appendChild(opt); });
  }).catch(function(){});
}
function quickSearch(q){ switchPage('search'); document.getElementById('chatInput').value=q; sendChatMessage(); }
function quickSearchSuggestion(q){ switchPage('search'); document.getElementById('chatInput').value=q; setTimeout(function(){ sendChatMessage(); }, 200); }

// ====== START ======
document.addEventListener('DOMContentLoaded',init);