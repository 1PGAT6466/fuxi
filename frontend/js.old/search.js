// ===== 搜索结果标签页 =====
var _searchResults = [];
var _currentTab = 'all';

function setSearchTab(tab) {
  _currentTab = tab;
  document.querySelectorAll('.search-tab').forEach(function(el) {
    el.style.borderBottom = el.dataset.tab === tab ? '2px solid #FF6700' : '2px solid transparent';
    el.style.color = el.dataset.tab === tab ? '#FF6700' : 'var(--text2)';
  });
  renderSearchResults();
}

function filterByTab(results, tab) {
  if (tab === 'all') return results;
  if (tab === 'doc') return results.filter(function(r) { return !r._source || r._source === 'doc'; });
  if (tab === 'qa') return results.filter(function(r) { return r._source === 'event' || r._via_event; });
  if (tab === 'data') return results.filter(function(r) { return r._source === 'table_view' || r.chunk_type === 'TABLE'; });
  return results;
}

function renderSearchResults() {
  // P0-2 fix: 使用独立的搜索结果容器，避免与标签页 DOM 冲突
  var c = document.getElementById('searchResultsList');
  // 如果 searchResultsList 不存在（初始搜索前），从 searchResults 中找
  if (!c) {
    var outer = document.getElementById('searchResults');
    if (outer) {
      c = outer.querySelector('#searchResultsList');
    }
  }
  if (!c) {
    // 回退：直接写入外层容器（没有标签页时）
    c = document.getElementById('searchResults');
  }
  if (!c) return;

  var q = document.getElementById('searchInput').value.trim();
  var results = filterByTab(_searchResults, _currentTab);

  if (!results.length) {
    c.innerHTML = '<div class="empty"><div class="empty-icon">🔍</div><h3>未找到相关结果</h3><p>尝试换个关键词</p></div>';
    return;
  }

  c.innerHTML = '<div class="result-list">' + results.map(function(r) {
    var score = (r.score || r._weighted_score || 0);
    var pct = Math.min(100, Math.round(score * 5));
    var sourceTag = r._source || (r.file_name && r.file_name.startsWith('[Wiki]') ? 'wiki' : 'doc');
    var tagColor = sourceTag === 'wiki' ? '#9c27b0' : sourceTag === 'table_view' ? '#ff9800' : sourceTag === 'event' ? '#4caf50' : '#2196f3';
    var tagLabel = sourceTag === 'wiki' ? 'Wiki' : sourceTag === 'table_view' ? '表格' : sourceTag === 'event' ? '问答' : '文档';
    var text = (r.text || '').substring(0, 250);
    var fileName = (r.file_name || '未知文件').replace(/-/g, ' ');
    var keywords = q.split(/\s+/).filter(function(k) { return k; });
    // CRITICAL-5 fix: 使用 escapeRegex() 对搜索词进行正则安全转义
    var hl = esc(text);
    keywords.forEach(function(k) {
      var safePattern = escapeRegex(k);
      if (safePattern) {
        hl = hl.replace(new RegExp('(' + safePattern + ')', 'gi'), '<mark>$1</mark>');
      }
    });
    return '<div class="result" onclick="this.querySelector(\'.result-text\').style.maxHeight=this.querySelector(\'.result-text\').style.maxHeight===\'none\'?\'80px\':\'none\'">' +
      '<div class="result-title"><span style="background:' + tagColor + ';color:#fff;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600">' + tagLabel + '</span> ' + esc(fileName) + '</div>' +
      '<div class="result-text" style="max-height:80px;overflow:hidden;transition:max-height .3s">' + hl + '</div>' +
      '<div class="result-meta"><span>相关性 ' + pct + '%</span><span style="flex:1"><span class="score-bar"><span class="score-fill" style="width:' + pct + '%"></span></span></span>' +
      '<span>' + (r.chunk_index != null ? '#' + (r.chunk_index + 1) : '') + '</span></div></div>';
  }).join('') + '</div>';
}

// ===== 搜索 =====
async function doSearch(){
  var q=document.getElementById('searchInput').value.trim();if(!q)return;
  var c=document.getElementById('searchResults');c.innerHTML='<div class="empty"><p>搜索中...</p></div>';
  try{
    var d=await api('/api/search?q='+encodeURIComponent(q)+'&page_size=20');
    var wikiR=d.wiki_results||[],chunkR=d.chunk_results||[];
    _searchResults=[...wikiR,...chunkR];
    _currentTab='all';

    // 标签页
    var tabsHtml='<div style="display:flex;gap:16px;border-bottom:1px solid var(--border);margin-bottom:16px">'+
      '<span class="search-tab" data-tab="all" onclick="setSearchTab(\'all\')" style="padding:8px 16px;cursor:pointer;border-bottom:2px solid #FF6700;color:#FF6700;font-weight:500">全部</span>'+
      '<span class="search-tab" data-tab="doc" onclick="setSearchTab(\'doc\')" style="padding:8px 16px;cursor:pointer;border-bottom:2px solid transparent;color:var(--text2)">文档</span>'+
      '<span class="search-tab" data-tab="qa" onclick="setSearchTab(\'qa\')" style="padding:8px 16px;cursor:pointer;border-bottom:2px solid transparent;color:var(--text2)">问答</span>'+
      '<span class="search-tab" data-tab="data" onclick="setSearchTab(\'data\')" style="padding:8px 16px;cursor:pointer;border-bottom:2px solid transparent;color:var(--text2)">数据</span>'+
      '</div>';
    c.innerHTML=tabsHtml+'<div id="searchResultsList"></div>';

    renderSearchResults();
  }catch(e){c.innerHTML='<div class="empty"><p style="color:var(--error)">搜索失败</p></div>'}
}
