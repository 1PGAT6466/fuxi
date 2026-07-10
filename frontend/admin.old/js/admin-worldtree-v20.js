/**
 * admin-worldtree-v19.js — 世界树 v19 (WorldTree 1.0 Phase 3)
 * 统一四子系统: Wiki四级树 + 知识图谱(书架+力导图) + 元数据 + 术语
 * 全部从 worldtree.db 读取 (API: /api/worldtree/*)
 */
const SUB_TABS = {
  wiki:      { title: '📖 Wiki 精炼知识',     desc: 'AI 蒸馏精炼的知识页面',               fn: loadWiki },
  bookshelf: { title: '📚 知识书架',           desc: '知识图谱实体关系，点击展开关系网',      fn: loadBookshelf },
  metadata:  { title: '🗄️ 元数据',            desc: '文件分类与统计',                       fn: loadMetadata },
  terms:     { title: '📝 术语库',             desc: '企业标准术语',                         fn: loadTerms },
};

function showWorldTree(sub = 'wiki') {
  const v = document.getElementById('view');
  if (!v) return;
  const tab = SUB_TABS[sub] || SUB_TABS['wiki'];
  v.innerHTML = `<div class="page-header"><h2>🌳 ${tab.title}</h2><p>${tab.desc}</p></div>
<div class="admin-card"><div class="ac-body" id="wt-content"><div class="loading" style="padding:40px;text-align:center">⏳ 加载中…</div></div></div>`;
  tab.fn();
}
window.showWorldTree = showWorldTree;


/* ========== Wiki 四级递归展开 (worldtree.db) ========== */
async function loadWiki() {
  const c = document.getElementById('wt-content');
  c.innerHTML = '<div class="loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';
  try {
    const res = await fetch('/api/worldtree/wiki/tree'); const data = await res.json();
    const tree = data.tree || [];
    if (!tree.length) { c.innerHTML = '<div class="empty"><div class="icon">\u{1f4d6}</div><p>\u6682\u65e0 Wiki \u9875\u9762<br><small>\u6587\u6863\u5165\u5e93\u540e\u84b8\u998f\u5f15\u64ce\u5c06\u81ea\u52a8\u751f\u6210</small></p></div>'; return; }

    // Collect all pages + counts
    var allPages = [], totalCount = 0;
    function collect(nodes, cat, depth) {
      if(!nodes) return;
      nodes.forEach(function(n){
        if(n.id && n.name) { allPages.push({id:n.id, name:n.name, summary:n.summary||'', cat:cat, depth:depth}); totalCount++; }
        if(n.children) collect(n.children, n.name||cat, depth+1);
      });
    }
    tree.forEach(function(t){ collect([t], t.name, 0); });

    var h = '';
    // Wiki stats bar
    h += '<div class="wiki-stats-bar">';
    h += '<span class="wsb-stat">\u{1f4d6} <b>'+totalCount+'</b> \u4e2a\u9875\u9762</span>';
    var topCats = tree.map(function(t){ return {name:t.name, count:((t.children||[]).length)}; });
    topCats.forEach(function(c){ h += '<span class="wsb-stat">\u{1f4c1} <b>'+c.count+'</b> '+e(c.name)+'</span>'; });
    h += '</div>';

    // Search
    h += '<div class="wiki-search-wrap"><span class="wiki-search-icon">\u{1f50d}</span><input class="wiki-search-input" id="wikiSearchInput" placeholder="\u641c\u7d22 Wiki \u9875\u9762\u2026" oninput="filterWikiPages()"><span class="wiki-search-clear" id="wikiSearchClear" style="display:none" onclick="clearWikiSearch()">\u2715</span></div>';

    // Wiki dual layout
    h += '<div class="wiki-layout">';

    // Left: category tree
    h += '<div class="wiki-tree-pane" id="wikiTreePane">';
    function renderTree(nodes, depth, parentPath) {
      var out = '';
      nodes.forEach(function(n, i){
        var pathHash = (parentPath||'').replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g,'').split('').reduce(function(s,c){return (s<<5)-s+c.charCodeAt(0)},0)>>>0;
        var nid = 'wtn_' + depth + '_' + i + '_' + (n.name||'').replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g,'').substring(0,14) + '_h' + pathHash;
        if(n.id && n.name) {
          // Leaf page
          out += '<div class="wt-page-item" data-wiki-id="'+ea(n.id)+'" data-wiki-name="'+ea(n.name||'')+'" data-wiki-cat="'+ea(depth>0?nodes[0]&&nodes[0].name||'':n.name)+'" style="padding-left:'+(14+depth*18)+'px">';
          out += '<span class="wt-page-icon">\u{1f4c4}</span><span class="wt-page-name">'+e(n.name||'?')+'</span>';
          var summaryPreview = (n.summary||'').replace(/^#+\s*/,'').substring(0,60);
          if(summaryPreview) out += '<span class="wt-page-summary">'+e(summaryPreview)+'</span>';
          out += '</div>';
        } else {
          // Folder
          var count = n.children?n.children.length:0;
          out += '<div class="wt-folder" data-wt-id="'+nid+'" style="padding-left:'+(depth*16)+'px" onclick="window.toggleWTV2(\u0027'+nid+'\u0027)">';
          out += '<span class="wt-folder-arrow">\u25b8</span><span class="wt-folder-icon">'+(depth===0?'\u{1f4c1}':'\u{1f4c2}')+'</span>';
          out += '<span class="wt-folder-name">'+e(n.name||'')+'</span>' + (parentPath ? '<span class="wt-folder-parent">'+e(parentPath)+'</span>' : '') + '<span class="wt-folder-badge">'+count+'</span></div>';
          out += '<div class="wt-folder-body" id="'+nid+'-body">';
          if(n.children) { var newParent = (parentPath?parentPath+'_':'')+(n.name||''); n.children.forEach(function(ch){ out += renderTree([ch], depth+1, newParent); }); }
          out += '</div>';
        }
      });
      return out;
    }
    h += renderTree(tree, 0);
    h += '</div>';

    // Right: content reader
    h += '<div class="wiki-reader-pane" id="wikiReaderPane">';
    h += '<div class="wiki-reader-empty"><div class="wre-icon">\u{1f4d6}</div><h3>\u9009\u62e9\u4e00\u4e2a Wiki \u9875\u9762</h3><p>\u4ece\u5de6\u4fa7\u76ee\u5f55\u70b9\u51fb\u4efb\u610f\u9875\u9762\u67e5\u770b\u8be6\u7ec6\u5185\u5bb9</p></div>';
    h += '<div class="wiki-reader-content" id="wikiReaderContent" style="display:none"></div>';
    h += '</div>';

    h += '</div>'; // wiki-layout

    c.innerHTML = h;

    // Store data for filtering
    window._wikiData = { tree: tree, allPages: allPages };

    // Click delegation for wiki pages
    c.querySelectorAll('.wt-page-item[data-wiki-id]').forEach(function(el){
      el.addEventListener('click', function(){
        // Highlight
        c.querySelectorAll('.wt-page-item.active').forEach(function(x){ x.classList.remove('active'); });
        el.classList.add('active');
        // Load content
        viewWikiReader(el.dataset.wikiId, el.dataset.wikiName, el.dataset.wikiCat);
      });
    });

    // Keyboard nav
    document.addEventListener('keydown', window._wikiKeyHandler = function(ev){
      if(ev.key==='Escape'){ clearWikiSearch(); }
    });

  } catch(e) { c.innerHTML = '<div class="err-banner">\u26a0\ufe0f Wiki \u52a0\u8f7d\u5931\u8d25\uff1a'+e.message+'</div>'; }
}

// View wiki page in reader pane
async function viewWikiReader(pageId, pageName, pageCat) {
  var reader = document.getElementById('wikiReaderContent');
  var empty = document.querySelector('.wiki-reader-empty');
  if(!reader) return;
  reader.style.display = 'block';
  if(empty) empty.style.display = 'none';

  reader.innerHTML = '<div class="wiki-reader-loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';

  try {
    var r = await fetch('/api/worldtree/wiki/' + encodeURIComponent(pageId));
    var d = await r.json();
    var html = '';

    // Breadcrumb
    html += '<div class="wr-breadcrumb"><span class="wr-bc-cat">'+e(pageCat||'')+'</span><span class="wr-bc-sep">\u203a</span><span class="wr-bc-title">'+e(pageName||'\u672a\u77e5\u9875\u9762')+'</span></div>';

    // Title
    html += '<h2 class="wr-title">'+e(pageName||'\u672a\u77e5\u9875\u9762')+'</h2>';

    // Content
    var content = d.content || d.summary || '';
    if(content){
      var formatted = content
        .replace(/^### (.+)$/gm, '<h4 class="wr-h4">$1</h4>')
        .replace(/^## (.+)$/gm, '<h3 class="wr-h3">$1</h3>')
        .replace(/^# (.+)$/gm, '<h2 class="wr-h2">$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.+?)`/g, '<code class="wr-code">$1</code>')
        .replace(/\n- (.+)/g, '\n<li class="wr-li">$1</li>')
        .replace(/\n/g, '<br>');
      html += '<div class="wr-content">'+formatted+'</div>';
    }else{
      html += '<div class="wr-content wr-empty">\u6682\u65e0\u5185\u5bb9</div>';
    }

    // Meta footer
    html += '<div class="wr-footer">';
    html += '<span>\u{1f4c2} '+e(pageCat||'')+'</span>';
    html += '<span>ID: '+e(d.id||pageId||'')+'</span>';
    html += '<button class="btn btn-outline btn-sm" onclick="deleteWikiPage(\u0027'+pageId.replace(/'/g,'\\u0027')+'\u0027)" style="color:var(--red);margin-left:auto">\u{1f5d1} \u5220\u9664</button>';
    html += '</div>';

    reader.innerHTML = html;
    reader.scrollTop = 0;
  }catch(e){
    reader.innerHTML = '<div class="err-banner">\u52a0\u8f7d\u5931\u8d25: '+e.message+'</div>';
  }
}

// Wiki search filter
function filterWikiPages() {
  var q = (document.getElementById('wikiSearchInput')||{}).value||'';
  var clear = document.getElementById('wikiSearchClear');
  if(clear) clear.style.display = q ? '' : 'none';

  var items = document.querySelectorAll('.wt-page-item[data-wiki-id]');
  var folders = document.querySelectorAll('.wt-folder');
  var hasResults = false;

  if(!q){
    // Reset
    items.forEach(function(i){ i.style.display = ''; });
    folders.forEach(function(f){ f.style.display = ''; });
    return;
  }

  var ql = q.toLowerCase();
  items.forEach(function(i){
    var name = (i.dataset.wikiName||'').toLowerCase();
    var summary = (i.textContent||'').toLowerCase();
    var match = name.includes(ql) || summary.includes(ql);
    i.style.display = match ? '' : 'none';
    if(match) hasResults = true;
  });

  // Show/hide folders based on visible items
  folders.forEach(function(f){
    var body = document.getElementById((f.dataset.wtId||'')+'-body');
    var visibleItems = body ? body.querySelectorAll('.wt-page-item[data-wiki-id]:not([style*="display: none"])').length : 0;
    f.style.display = q ? (visibleItems > 0 ? '' : 'none') : '';
    if(body && q && visibleItems > 0) { body.classList.add('open'); f.querySelector('.wt-folder-arrow').textContent = '\u25be'; }
  });
}
function clearWikiSearch() {
  var input = document.getElementById('wikiSearchInput');
  if(input) input.value = '';
  filterWikiPages();
}
window.filterWikiPages = filterWikiPages;
window.clearWikiSearch = clearWikiSearch;
window.viewWikiReader = viewWikiReader;


window.toggleWTV2 = function(id) {
  const body = document.getElementById(id + '-body');
  const folder = document.querySelector('[data-wt-id="' + id + '"]');
  if (body) { body.classList.toggle('open'); if (folder) { const arrow = folder.querySelector('.wt-folder-arrow'); if (arrow) arrow.textContent = body.classList.contains('open') ? '▾' : '▸'; } }
};

/* ========== 知识图谱书架 + 1-hop 展开 (worldtree.db) ========== */
let _graphData = null;

async function loadBookshelf() {
  var c = document.getElementById('wt-content');
  c.innerHTML = '<div class="loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';
  try {
    var r = await fetch('/api/worldtree/entities');
    var d = await r.json();
    var entities = d.entities || [];
    _graphData = { nodes: entities, edges: [] };

    var h = '<div class="back-link" onclick="showWorldTree(\'wiki\')">\u2190 \u8fd4\u56de\u4e16\u754c\u6811 Wiki</div>';
    h += '<div style="margin-bottom:8px;color:var(--text3);font-size:12px">\u5171 <b>' + entities.length + '</b> \u4e2a\u5b9e\u4f53</div>';
    
    var types = {};
    entities.forEach(function(en){ var t = en.type || 'unknown'; types[t] = (types[t]||0) + 1; });
    var typeKeys = Object.keys(types).sort(function(a,b){return types[b]-types[a]});
    h += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">';
    h += '<span class="graph-chip active" onclick="filterBookCards(\'\')" style="cursor:pointer;padding:4px 12px;border-radius:12px;font-size:11px;background:var(--pri);color:#fff">\u5168\u90e8(' + entities.length + ')</span>';
    typeKeys.forEach(function(t){
      h += '<span class="graph-chip" onclick="filterBookCards(\'' + t.replace(/'/g,'\\x27') + '\')" style="cursor:pointer;padding:4px 12px;border-radius:12px;font-size:11px;background:var(--bg);color:var(--text2)">' + t + '(' + types[t] + ')</span>';
    });
    h += '</div>';
    
    h += '<div class="bookshelf-grid" id="bsGrid">' + renderBookCards(entities).join('') + '</div>';
    c.innerHTML = h;
  } catch(e) { c.innerHTML = '<div class="err-banner">\u26a0\ufe0f \u52a0\u8f7d\u5931\u8d25: ' + e.message + '</div>'; }
}
window.loadBookshelf = loadBookshelf;


function filterBookCards(type) {
  var entities = (_graphData && _graphData.nodes) || [];
  var filtered = type ? entities.filter(function(en){ return (en.type||'unknown') === type; }) : entities;
  document.querySelectorAll('.graph-chip').forEach(function(ch){ ch.classList.remove('active'); ch.style.background='var(--bg)'; ch.style.color='var(--text2)'; });
  var target = type ? Array.from(document.querySelectorAll('.graph-chip')).find(function(ch){ return ch.textContent.startsWith(type); }) : document.querySelector('.graph-chip');
  if (target) { target.classList.add('active'); target.style.background='var(--pri)'; target.style.color='#fff'; }
  var grid = document.getElementById('bsGrid');
  if (grid) grid.innerHTML = renderBookCards(filtered).join('');
}
window.filterBookCards = filterBookCards;


function renderBookCards(entities) {
  var typeLabels = {"concept":"\u6982\u5ff5","network_device":"\u7f51\u7edc","operation_manual":"\u6d41\u7a0b","standard_part":"\u6807\u51c6\u4ef6","supplier":"\u4f9b\u5e94\u5546"};
  return entities.map(function(en){
    var type = en.type || "unknown";
    var coverClass = type === "concept" ? "eb-concept" : type === "network_device" ? "eb-network" : type === "operation_manual" ? "eb-manual" : type === "standard_part" ? "eb-part" : type === "supplier" ? "eb-supplier" : "eb-default";
    var icon = type === "concept" ? "\u{1f4a1}" : type === "network_device" ? "\u{1f310}" : type === "operation_manual" ? "\u{1f4cb}" : type === "standard_part" ? "\u{1f527}" : type === "supplier" ? "\u{1f3ed}" : "\u{1f4e6}";
    var spineLabel = typeLabels[type] || type;
    var name = en.name || "?";
    var shortName = name.length > 16 ? name.substring(0,14)+"..." : name;
    var mentions = en.mentions || 1;
    var entId = (en.id||"").replace(/'/g,"\\x27");
    var safeName = name.replace(/'/g,"\\x27");
    return '<div class="entity-book" onclick="toggleBookCard(this,\'' + entId + '\',\'' + safeName + '\')">' +
      '<div class="eb-cover ' + coverClass + '">' +
        '<span class="eb-spine-label">' + e(spineLabel) + '</span>' +
        '<span class="eb-cover-title">' + e(shortName) + '</span>' +
        '<span class="eb-cover-icon">' + icon + '</span>' +
      '</div>' +
      '<div class="eb-body">' +
        '<div class="eb-name" title="' + e(name) + '">' + e(name) + '</div>' +
        '<div class="eb-type">' + e(type) + '</div>' +
        '<div class="eb-meta">\u{1f4cd} ' + mentions + '\u6b21\u63d0\u53ca</div>' +
      '</div>' +
      '<div class="eb-expand" id="ebd-' + (en.id||"").replace(/[^a-zA-Z0-9]/g,"") + '">\u23f3 \u52a0\u8f7d\u5173\u8054\u5b9e\u4f53\u2026</div>' +
    '</div>';
  });
}


async function toggleBookCard(el, entityId, entityName) {
  var expand = el.querySelector('.eb-expand');
  if (el.classList.contains('expanded')) { el.classList.remove('expanded'); return; }
  el.classList.add('expanded');
  if (!expand || expand.dataset.loaded) return;
  try {
    var r = await fetch('/api/worldtree/entities');
    var d = await r.json();
    var all = d.entities || [];
    var entity = all.find(function(en){ return en.id === entityId; });
    var related = all.filter(function(en){ return en.id !== entityId && en.category_path === (entity?entity.category_path:''); }).slice(0, 5);
    var h2 = '<div style="font-size:11px;color:var(--text3);margin-bottom:6px">';
    if (entity && entity.category_path) h2 += '\u{1f4c2} ' + e(entity.category_path.replace(/>/g,' \u203a '));
    h2 += '</div>';
    if (related.length) {
      h2 += '<div style="font-size:11px;color:var(--text2);margin-bottom:2px">\u{1f517} \u540c\u5206\u7c7b\u5b9e\u4f53:</div>';
      related.forEach(function(re){ h2 += '<div style="font-size:12px;padding:2px 0">\u00b7 ' + e(re.name||'?') + ' <span style="color:var(--text3)">(' + (re.type||'') + ')</span></div>'; });
    } else { h2 += '<div style="font-size:11px;color:var(--text3)">\u6682\u65e0\u5173\u8054\u5b9e\u4f53</div>'; }
    expand.innerHTML = h2;
    expand.dataset.loaded = '1';
  } catch(e2) { expand.innerHTML = '<div style="color:var(--red);font-size:11px">\u52a0\u8f7d\u5931\u8d25</div>'; }
}
window.toggleBookCard = toggleBookCard;



function renderGraphCards(nodes, filterType) {
  const filtered = filterType && filterType !== 'all' ? nodes.filter(n => (n.type||'unknown') === filterType) : nodes;
  return filtered.slice(0, 80).map(n => {
    const iconMap = {material:'🧱',standard_part:'🔩',supplier:'🏭',network_device:'🌐',project:'🏗',sensor:'📡',concept:'💡',operation_manual:'📘',person:'👤',document:'📑',vlan:'🔢'};
    const icon = iconMap[n.type] || '📌';
    const name = n.name || '?';
    const entId = n.id || n.name;
    return `<div class="graph-card" data-entity="${ea(entId)}" data-entity-name="${ea(name)}" onclick="openEntityDetail('${ea(entId)}','${ea(name)}')">
      <span class="graph-card-icon">${icon}</span>
      <span class="graph-card-name">${e(name)}</span>
      <span class="graph-card-type">${e(n.type||'?')}</span>
      ${n.mentions ? '<span class="graph-card-mentions">' + n.mentions + '次</span>' : ''}
    </div>`;
  });
}

window.filterGraphNodes = function(type) {
  document.querySelectorAll('.graph-chip').forEach(c => c.classList.toggle('active', c.dataset.type === type));
  const cards = document.getElementById('graphCards');
  if (cards && _graphData) cards.innerHTML = renderGraphCards(_graphData.nodes, type).join('');
};

/* ========== 实体详情 + 1-hop 关系展开 ========== */
window.openEntityDetail = async function(entityId, entityName) {
  const c = document.getElementById('wt-content');
  if (!c) return;
  
  const decodedId = decodeURIComponent(entityId);
  const decodedName = decodeURIComponent(entityName);
  
  c.innerHTML = '<div style="padding:40px;text-align:center">⏳ 加载中…</div>';
  
  try {
    const [relRes, wikiRes] = await Promise.all([
      fetch('/api/worldtree/relations?entity_id=' + encodeURIComponent(decodedId)).then(r => r.json()).catch(() => ({ relations: [] })),
      fetch('/api/worldtree/entity/' + encodeURIComponent(decodedId) + '/wiki').then(r => r.json()).catch(() => ({ wiki_pages: [] })),
    ]);
    
    const node = _graphData ? _graphData.nodes.find(n => (n.id||n.name) === decodedName || n.id === decodedId) : null;
    const etype = node ? node.type : 'unknown';
    
    let html = '<div style="margin-bottom:12px"><button onclick="loadBookshelf()" class="btn btn-outline btn-sm">← 返回书架</button></div>';
    html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px"><span class="graph-card-icon" style="font-size:24px">📖</span><h3 style="margin:0;color:var(--pri)">' + e(decodedName) + '</h3><span class="graph-chip" style="background:var(--pri-light);color:var(--pri)">' + e(etype) + '</span></div>';
    
    // 关联实体 (1-hop)
    const rels = relRes.relations || [];
    if (rels.length) {
      html += '<h4 style="font-size:13px;margin-bottom:8px">🔗 关联实体 (' + rels.length + '个)</h4><div class="graph-cards">';
      rels.forEach(r => {
        html += `<div class="graph-card" onclick="openEntityDetail('${ea(r.id)}','${ea(r.name)}')" style="cursor:pointer">
          <span class="graph-card-icon">📌</span>
          <span class="graph-card-name">${e(r.name)}</span>
          <span class="graph-card-type">${e(r.type||'?')} · ${e(r.relation||'related_to')}</span>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="empty" style="padding:20px"><p>暂无关联实体</p><p style="font-size:11px;color:var(--text3)">蒸馏引擎将在更多数据入库后构建关系</p></div>';
    }
    
    // 关联 Wiki
    const wps = wikiRes.wiki_pages || [];
    html += '<h4 style="font-size:13px;margin:16px 0 8px">📖 关联 Wiki 页面 (' + wps.length + '个)</h4>';
    if (wps.length) {
      wps.forEach(p => {
        html += `<div class="wt-page-item" style="cursor:pointer;padding:8px" onclick="viewWPInline('${ea(p.id)}')">
          <span class="wt-page-icon">📄</span><span class="wt-page-name">${e(p.title||'?')}</span>
          <span style="font-size:11px;color:var(--text3)">${e(p.category_path||'')}</span></div>`;
      });
    } else {
      html += '<div style="color:var(--text3);font-size:12px;padding:8px">暂无关联页面</div>';
    }
    
    c.innerHTML = html;
  } catch(er) { c.innerHTML = '<div class="err-banner">⚠️ 加载失败: ' + er.message + '</div>'; }
};

/* ========== 元数据 ========== */
async function loadMetadata() {
  var c = document.getElementById('wt-content');
  c.innerHTML = '<div class="loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';
  try {
    var [fr, dr] = await Promise.all([
      fetch('/api/documents?limit=500').then(function(r){return r.json()}),
      fetch('/api/worldtree/stats').then(function(r){return r.json()})
    ]);
    var files = fr.files || [], stats = dr || {};

    var h = '<div class="meta-stats-row">';
    h += '<div class="meta-stat-tile"><div class="mst-num">'+files.length+'</div><div class="mst-lbl">\u6587\u4ef6</div></div>';
    h += '<div class="meta-stat-tile"><div class="mst-num">'+(stats.wiki_pages||0)+'</div><div class="mst-lbl">Wiki \u9875</div></div>';
    h += '<div class="meta-stat-tile"><div class="mst-num">'+(stats.entities||0)+'</div><div class="mst-lbl">\u5b9e\u4f53</div></div>';
    h += '<div class="meta-stat-tile"><div class="mst-num">'+(stats.terms||0)+'</div><div class="mst-lbl">\u672f\u8bed</div></div>';
    h += '</div>';

    var cats = {}; files.forEach(function(f){ var cat = f.category||'\u672a\u5206\u7c7b'; cats[cat]=(cats[cat]||0)+1; });
    var catEntries = Object.entries(cats).sort(function(a,b){return b[1]-a[1]});
    var maxCat = catEntries.length?catEntries[0][1]:1;
    var palette = ['#ff6700','#20a8d8','#07c160','#6f42c1','#e53935','#8b6914','#4a7c59','#e91e63'];

    h += '<div class="meta-panels">';
    h += '<div class="meta-panel"><div class="mp-head"><span class="mp-icon" style="background:#fff3e0">\u{1f4ca}</span>\u5206\u7c7b\u5206\u5e03</div><div class="mp-body">';
    catEntries.slice(0,10).forEach(function(e,i){
      var pct = Math.max(Math.round(e[1]/maxCat*100), 3);
      var label = e2(e[0]);
      var shortLabel = label.length > 14 ? label.substring(0,12)+'..' : label;
      h += '<div class="mb-row"><span class="mb-label" title="'+label+'">'+shortLabel+'</span>';
      h += '<div class="mb-track"><div class="mb-fill" style="width:'+pct+'%;background:'+palette[i%8]+'"></div></div>';
      h += '<span class="mb-val">'+e[1]+'</span></div>';
    });
    h += '</div></div>';

    var fmts = {}; files.forEach(function(f){ var ext = (f.file_type||(f.file_name||'').split('.').pop()||'?').toUpperCase(); fmts[ext]=(fmts[ext]||0)+1; });
    var fmtEntries = Object.entries(fmts).sort(function(a,b){return b[1]-a[1]});
    var maxFmt = fmtEntries.length?fmtEntries[0][1]:1;
    h += '<div class="meta-panel"><div class="mp-head"><span class="mp-icon" style="background:#e3f2fd">\u{1f4d0}</span>\u683c\u5f0f\u5206\u5e03</div><div class="mp-body">';
    fmtEntries.forEach(function(e,i){
      var pct = Math.max(Math.round(e[1]/maxFmt*100), 3);
      h += '<div class="mb-row"><span class="mb-label">'+e2(e[0])+'</span>';
      h += '<div class="mb-track"><div class="mb-fill" style="width:'+pct+'%;background:'+palette[(i+3)%8]+'"></div></div>';
      h += '<span class="mb-val">'+e[1]+'</span></div>';
    });
    h += '</div></div></div>';

    h += '<div class="meta-panel meta-panel-wide"><div class="mp-head"><span class="mp-icon" style="background:#e8f5e9">\u{1f4cb}</span>\u6587\u4ef6\u6e05\u5355';
    h += '<input class="doc-search-input" id="metaSearchInput" placeholder="\u{1f50d} \u641c\u7d22\u6587\u4ef6\u540d\u2026" oninput="filterMetaFiles()" style="margin-left:auto;max-width:240px">';
    h += '</div><div class="mp-body" style="padding:0"><div style="overflow-x:auto">';
    h += '<table class="file-table" id="metaFileTable"><thead><tr><th>\u6587\u4ef6\u540d</th><th>\u5206\u7c7b</th><th>\u7c7b\u578b</th><th>\u65f6\u95f4</th></tr></thead><tbody>';
    files.forEach(function(f){
      var icons = {pdf:'\u{1f4d5}',xlsx:'\u{1f4ca}',docx:'\u{1f4dd}',pptx:'\u{1f4ca}'};
      var icon = icons[(f.file_type||'').toLowerCase()] || '\u{1f4c4}';
      h += '<tr><td><div class="file-row-name"><span class="file-row-icon">'+icon+'</span><span class="file-row-text">'+e2((f.file_name||'?').replace(/\\/g,' / '))+'</span></div></td>';
      h += '<td><span class="file-type-tag">'+e2(f.category||'')+'</span></td>';
      h += '<td><span class="file-type-tag">'+(f.file_type||'').toUpperCase()+'</span></td>';
      h += '<td>'+(f.created_at||'').substring(0,10)+'</td></tr>';
    });
    h += '</tbody></table></div></div></div>';

    window._metaFiles = files;
    c.innerHTML = h;
  } catch(e) { c.innerHTML = '<div class="err-banner">\u26a0\ufe0f \u52a0\u8f7d\u5931\u8d25: '+e.message+'</div>'; }
}
window.loadMetadata = loadMetadata;


function filterMetaFiles() {
  var q = (document.getElementById('metaSearchInput').value||'').toLowerCase();
  var files = window._metaFiles||[];
  var filtered = q?files.filter(function(f){return (f.file_name||'').toLowerCase().includes(q)||(f.category||'').toLowerCase().includes(q);}):files;
  var tbody = document.querySelector('#metaFileTable tbody');
  if(!tbody) return;
  tbody.innerHTML = filtered.map(function(f){
    var icons = {pdf:'\u{1f4d5}',xlsx:'\u{1f4ca}',docx:'\u{1f4dd}',pptx:'\u{1f4ca}'};
    var icon = icons[(f.file_type||'').toLowerCase()] || '\u{1f4c4}';
    return '<tr><td><div class="file-row-name"><span class="file-row-icon">'+icon+'</span><span class="file-row-text">'+e2((f.file_name||'?').replace(/\\/g,' / '))+'</span></div></td><td><span class="file-type-tag">'+e2(f.category||'')+'</span></td><td><span class="file-type-tag">'+(f.file_type||'').toUpperCase()+'</span></td><td>'+(f.created_at||'').substring(0,10)+'</td></tr>';
  }).join('');
}
window.filterMetaFiles = filterMetaFiles;

async function loadTerms() {
  var c = document.getElementById('wt-content');
  c.innerHTML = '<div class="loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';
  try {
    var r = await fetch('/api/worldtree/terms?limit=2000');
    var d = await r.json();
    var terms = d.terms || [];

    var groups = {};
    terms.forEach(function(t){
      var df = t.definition || '';
      var cat = t.category || '';
      if (!cat) {
        if (df.includes('\u7f51\u7edc')||df.includes('IP')||df.includes('\u534f\u8bae')||df.includes('VLAN')) cat = '\u7f51\u7edc\u901a\u4fe1';
        else if (df.includes('\u5c3a\u5bf8')||df.includes('\u6807\u51c6')||df.includes('\u89c4\u683c')||df.includes('ISO')||df.includes('GB/')) cat = '\u6807\u51c6\u89c4\u683c';
        else if (df.includes('\u6750\u6599')||df.includes('\u5851\u6599')||df.includes('\u91d1\u5c5e')||df.includes('\u5408\u91d1')) cat = '\u6750\u6599\u5de5\u7a0b';
        else if (df.includes('\u7535\u6c14')||df.includes('\u7535\u8def')||df.includes('\u7535\u538b')||df.includes('\u4f20\u611f\u5668')) cat = '\u7535\u6c14\u7535\u5b50';
        else if (df.includes('\u673a\u68b0')||df.includes('\u96f6\u4ef6')||df.includes('\u52a0\u5de5')||df.includes('\u8f34\u627f')) cat = '\u673a\u68b0\u5236\u9020';
        else if (df.includes('\u7ba1\u7406')||df.includes('\u6d41\u7a0b')||df.includes('\u5236\u5ea6')||df.includes('OA')) cat = '\u7ba1\u7406\u6d41\u7a0b';
        else cat = '\u5176\u4ed6';
      }
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(t);
    });

    var catNames = Object.keys(groups).sort(function(a,b){return groups[b].length-groups[a].length});
    var catColors = {
      '\u7f51\u7edc\u901a\u4fe1': '#20a8d8',
      '\u6807\u51c6\u89c4\u683c': '#8b6914',
      '\u6750\u6599\u5de5\u7a0b': '#07c160',
      '\u7535\u6c14\u7535\u5b50': '#e53935',
      '\u673a\u68b0\u5236\u9020': '#ff6700',
      '\u7ba1\u7406\u6d41\u7a0b': '#6f42c1',
      '\u5176\u4ed6': '#78909c'
    };

    var h = '<div class="term-toolbar">';
    h += '<div class="term-stats">\u{1f4dd} \u5171 <b>'+terms.length+'</b> \u4e2a\u672f\u8bed \u00b7 <b>'+catNames.length+'</b> \u4e2a\u5206\u7c7b</div>';
    h += '<input class="doc-search-input" id="termSearchInput" placeholder="\u{1f50d} \u641c\u7d22\u672f\u8bed\u2026" oninput="filterTerms()" style="max-width:300px;margin-left:auto">';
    h += '</div>';

    h += '<div class="term-chips">';
    catNames.forEach(function(cat){
      var color = catColors[cat] || '#78909c';
      h += '<span class="term-chip" style="border-color:'+color+';color:'+color+'" onclick="scrollToTermCat(\u0027'+cat.replace(/'/g,'\u0027')+'\u0027)">'+e(cat)+' ('+groups[cat].length+')</span>';
    });
    h += '</div>';

    h += '<div class="term-grid" id="termGrid">';
    catNames.forEach(function(cat, ci){
      var items = groups[cat];
      var color = catColors[cat] || '#78909c';
      h += '<div class="term-section" id="ts-'+ci+'"><div class="ts-head" style="border-left:4px solid '+color+'">'+e(cat)+' <span class="ts-count">'+items.length+'\u6761</span></div>';
      h += '<div class="ts-body">';
      items.forEach(function(t){
        var term = t.term || '?';
        var def = t.definition || '';
        var defPreview = def.length > 80 ? def.substring(0,78)+'...' : def;
        var tid = (t.id||'').replace(/'/g,'\u0027');
        var tterm = term.replace(/'/g,'\u0027');
        var tdef = def.replace(/\\/g,'\\\\').replace(/'/g,'\u0027');
        var tcat = cat.replace(/'/g,'\u0027');
        h += '<div class="term-card" onclick="showTermDetail(\u0027'+tid+'\u0027,\u0027'+tterm+'\u0027,\u0027'+tdef+'\u0027,\u0027'+tcat+'\u0027)">';
        h += '<div class="tc-term">'+e(term)+'</div>';
        if(defPreview) h += '<div class="tc-def">'+e(defPreview)+'</div>';
        h += '</div>';
      });
      h += '</div></div>';
    });
    h += '</div>';
    c.innerHTML = h;
  } catch(e) { c.innerHTML = '<div class="err-banner">\u26a0\ufe0f \u52a0\u8f7d\u5931\u8d25: '+e.message+'</div>'; }
}
window.loadTerms = loadTerms;




function showTermDetail(id, term, def, cat) {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
  overlay.innerHTML = '<div class="modal-card"><div class="mc-header"><div class="mc-title">\u{1f4dd} '+e(term||'?')+'</div><button class="mc-close" onclick="this.closest(\u0027.modal-overlay\u0027).remove()">\u2715</button></div><div class="mc-body"><div class="mc-def">'+e(def||'\u65e0\u5b9a\u4e49')+'</div><div class="mc-meta"><span class="mc-cat"><span class="mc-cat-dot" style="background:var(--pri)"></span>'+e(cat||'\u672a\u5206\u7c7b')+'</span><span class="mc-id">ID: '+e(id||'')+'</span></div></div></div>';
  document.body.appendChild(overlay);
}
window.showTermDetail = showTermDetail;


function scrollToTermCat(cat) {
  var sections = document.querySelectorAll('.ts-head');
  for(var i=0;i<sections.length;i++){
    if(sections[i].textContent.startsWith(cat)){
      sections[i].scrollIntoView({behavior:'smooth',block:'start'});
      break;
    }
  }
}
window.scrollToTermCat = scrollToTermCat;


function filterTerms() {
  var q = (document.getElementById('termSearchInput').value||'').toLowerCase();
  document.querySelectorAll('.term-section').forEach(function(section){
    var cards = section.querySelectorAll('.term-card');
    var visible = false;
    cards.forEach(function(card){
      var match = !q || (card.textContent||'').toLowerCase().includes(q);
      card.style.display = match ? '' : 'none';
      if(match) visible = true;
    });
    section.style.display = visible ? '' : 'none';
  });
  document.querySelectorAll('.term-chip').forEach(function(chip){
    var catName = chip.textContent.replace(/\s*\(\d+\)\s*$/,'');
    var section = Array.from(document.querySelectorAll('.ts-head')).find(function(h){ return h.textContent.startsWith(catName); });
    chip.style.opacity = section && section.closest('.term-section') && section.closest('.term-section').style.display !== 'none' ? '1' : '0.35';
  });
}
window.filterTerms = filterTerms;


function toggleTermCat(el) {}




function md(t) { if(!t)return''; return t.replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/^# (.+)$/gm,'<h1>$1</h1>').replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/\n/g,'<br>'); }
function e(s) { if(!s)return''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function e2(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
window.e2 = e2;

function ea(s) { if(!s)return''; return String(s).replace(/&/g,'&amp;').replace(/'/g,'&#39;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }


// ====== STARTUP BOOTSTRAP ======
function viewDocByHash(hash) {
  if (!hash) return;
  var url = '/api/download/' + encodeURIComponent(hash);
  var w = window.open(url, '_blank');
  if (!w) window.location.href = url;
}


function downloadDocByHash(hash) {
  if (!hash) return;
  var a = document.createElement('a');
  a.href = '/api/download/' + encodeURIComponent(hash);
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function uploadAdminFile(file) {
  if (!file) return;
  var formData = new FormData();
  formData.append('file', file);
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload', true);
  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      var pct = Math.round(e.loaded / e.total * 100);
      var bar = document.getElementById('uploadAdminBar');
      if (bar) { bar.style.width = pct + '%'; bar.textContent = pct + '%'; }
    }
  };
  xhr.onload = function() {
    if (xhr.status === 200) {
      alert('上传成功！');
      if (typeof loadDocuments === 'function') loadDocuments();
    } else {
      alert('上传失败: ' + xhr.statusText);
    }
  };
  xhr.onerror = function() { alert('上传请求失败'); };
  xhr.send(formData);
}
window.uploadAdminFile = uploadAdminFile;

function initAdmin() {
  document.getElementById("navWorldTreeSub").classList.add("open");
  // Home page is Dashboard - only Dashboard stays highlighted
  document.querySelectorAll(".nav-item[data-nav].active").forEach(function(n) { n.classList.remove("active"); });
  document.querySelector('.nav-item[data-nav="dashboard"]').classList.add('active');
  // Nav click handler: route to correct page, never hide WorldTree sub-nav
  document.querySelectorAll('.nav-item[data-nav]').forEach(function(item) {
    item.addEventListener('click', function(e) {
      var nav = this.dataset.nav;
      var sub = this.dataset.sub;

      // Skip the WorldTree parent toggle - handled separately
      if (nav === 'worldtree' && !sub) return;

      // Highlight active item
      document.querySelectorAll('.nav-item[data-nav]').forEach(function(n) { n.classList.remove('active'); });
      this.classList.add('active');
      // Also highlight the WorldTree parent when a sub-item is active
      if (sub) {
        var wtParent = document.getElementById('navWorldTree');
        if (wtParent) wtParent.classList.add('active');
      }

      var title = this.textContent.replace(/[^a-zA-Z0-9\u4e00-\u9fff\s]+$/, '').trim();
      document.getElementById('topbarTitle').textContent = title;

      if (nav === 'dashboard') loadDashboard();
      else if (nav === 'documents') loadDocuments();
      else if (nav === 'worldtree') showWorldTree(sub || 'wiki');
      else if (nav === 'evaluation') loadEvaluation();
      else if (nav === 'evolution') loadEvolution();
      else if (nav === 'config') loadConfig();
    });
  });
  var wtNav = document.getElementById('navWorldTree');
  if (wtNav) {
    wtNav.addEventListener('click', function(e) {
      e.stopPropagation();
      var s = document.getElementById('navWorldTreeSub');
      if (s) {
        if (s.classList.contains('open')) { s.classList.remove('open'); document.getElementById('navWtArrow').textContent = '▾'; }
        else { s.classList.add('open'); document.getElementById('navWtArrow').textContent = '▴'; }
      }
    });
  }
  
// File management: delegate doc-view-btn clicks
  document.getElementById('view').addEventListener('click', function(e) {
    var btn = e.target.closest('.doc-view-btn');
    if (btn) { viewDocByHash(btn.dataset.hash); }
  });

var updateTime = function() { document.getElementById('topbarTime').textContent = new Date().toLocaleString('zh-CN'); };
  updateTime(); setInterval(updateTime, 30000);
  checkHealth(); setInterval(checkHealth, 60000);
  loadDashboard();
}

function checkHealth() {
  fetch('/api/health').then(function(r) { return r.json(); }).then(function(d) {
    var dot = document.getElementById('statusDot');
    var txt = document.getElementById('statusText');
    if (d.status === 'healthy') { dot.className = 'status-dot'; txt.textContent = '系统正常 ' + (d.uptime_seconds||0) + 's'; }
    else { dot.className = 'status-dot warn'; txt.textContent = '系统繁忙'; }
  }).catch(function() {
    document.getElementById('statusDot').className = 'status-dot off';
    document.getElementById('statusText').textContent = '离线';
  });
}

async function loadDashboard() {
  var v = document.getElementById('view');
  v.innerHTML = '<div class="loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';
  try {
    var [r1, r2] = await Promise.all([
      fetch('/api/health').then(function(r){return r.json()}),
      fetch('/api/admin/server-status').then(function(r){return r.json()})
    ]);
    var d = r1, s = r2;
    var min = Math.floor((d.uptime_seconds||0)/60);
    var h = Math.floor(min/60), m = min % 60;
    var ut = h + 'h ' + m + 'm';
    var sc = d.status==='healthy'?'green':'orange';
    var st = d.status==='healthy'?'\u7cfb\u7edf\u6b63\u5e38':'\u7cfb\u7edf\u7e41\u5fd9';

    var wt = await fetch('/api/worldtree/stats').then(function(r){return r.json()});

    var hh = '<div class="health-strip">';
    hh += '<div class="hs-dot '+sc+'"></div><span class="hs-val">'+st+'</span>';
    hh += '<span class="hs-item">\u26a1 \u8fd0\u884c <b>'+ut+'</b></span>';
    hh += '<span class="hs-item">\u{1f5a5} CPU <b>'+(s.cpu||0).toFixed(1)+'%</b></span>';
    hh += '<span class="hs-item">\u{1f4be} \u5185\u5b58 <b>'+(s.memory||0).toFixed(1)+'%</b></span>';
    hh += '<span class="hs-item">\u{1f4c0} \u78c1\u76d8 <b>'+(s.disk||0).toFixed(1)+'%</b></span>';
    hh += '<span class="hs-item" style="margin-left:auto">\u{1f333} \u4e16\u754c\u6811 v19</span>';
    hh += '</div>';

    hh += '<div class="kpi-ribbon">';
    hh += kpiR('\u{1f4c4}', d.total_files||0, '\u6587\u6863\u6570', '\u5df2\u5165\u5e93\u539f\u59cb\u6587\u6863');
    hh += kpiR('\u{1f9e9}', d.total_chunks||0, '\u77e5\u8bc6\u7247\u6bb5', '\u8bed\u4e49\u5206\u5757\u540e\u7684\u68c0\u7d22\u5355\u5143');
    hh += kpiR('\u{1f333}', d.graph_entities||0, '\u77e5\u8bc6\u5b9e\u4f53', '\u4e16\u754c\u6811\u63d0\u53d6\u7684\u5b9e\u4f53');
    hh += kpiR('\u{1f4d6}', wt.wiki_pages||0, 'Wiki \u9875\u9762', 'AI \u84b8\u998f\u7cbe\u70bc\u77e5\u8bc6');
    hh += kpiR('\u{1f3f7}', wt.terms||0, '\u672f\u8bed\u5e93', '\u4f01\u4e1a\u6807\u51c6\u672f\u8bed');
    hh += kpiR('\u23f1', ut, '\u8fd0\u884c\u65f6\u95f4', '\u7cfb\u7edf\u8fde\u7eed\u8fd0\u884c');
    hh += '</div>';

    hh += '<div class="wt-grid-3">';
    hh += admCard('\u{1f4e1}','var(--green-light)','\u670d\u52a1\u72b6\u6001',
      ar('\u4e3b\u670d\u52a1 :8080','\u{1f7e2} \u8fd0\u884c\u4e2d','var(--green)')+
      ar('Embedder :8081','\u{1f7e2} '+(d.embedder||'ready'),'var(--green)')+
      ar('Distiller :8093','\u{1f7e2} v2 \u6bcf5\u5206\u949f\u84b8\u998f','var(--green)')+
      ar('\u88c5\u8f7d\u673a :8090','\u{1f7e2} '+(d.loader||'ready'),'var(--green)')+
      ar('ChromaDB',d.chroma_storage||'ok','')+
      ar('Vector Store',d.vector_store||'ready',''));
    hh += admCard('\u{1f9e0}','var(--purple-light)','AI \u5f15\u64ce',
      ar('LLM \u6a21\u578b','DeepSeek-V3','')+
      ar('Embed \u6a21\u578b','bge-large-zh-v1.5','')+
      ar('Reranker','Qwen3-Reranker-8B','')+
      ar('\u84b8\u998f\u5f15\u64ce','v3 (\u6bcf5\u5206\u949f)','')+
      ar('\u5411\u91cf\u7ef4\u5ea6','1024','')+
      ar('LLM \u63d0\u4f9b\u5546','DeepSeek',''));
    hh += admCard('\u{1f4ca}','var(--pri-light)','\u77e5\u8bc6\u7edf\u8ba1',
      ar('Wiki \u9875\u9762',wt.wiki_pages||0,'')+
      ar('\u77e5\u8bc6\u5b9e\u4f53',wt.entities||0,'')+
      ar('\u5b9e\u4f53\u5173\u7cfb',wt.entity_relations||0,'')+
      ar('\u672f\u8bed\u5e93',wt.terms||0,'')+
      ar('\u6587\u6863\u6570',d.total_files||0,'')+
      ar('Chunks',d.total_chunks||0,''));
    hh += '</div>';

    var cpuCol = s.cpu>80?'var(--red)':s.cpu>50?'var(--pri)':'var(--green)';
    var memCol = s.memory>80?'var(--red)':s.memory>50?'var(--pri)':'var(--green)';
    hh += admCard2('\u{1f4c8}','var(--blue-light)','\u7cfb\u7edf\u8d44\u6e90',
      resBar('CPU',s.cpu||0,cpuCol)+
      resBar('\u5185\u5b58',s.memory||0,memCol)+
      resBar('\u78c1\u76d8',s.disk||0,'var(--pri2)'));

    hh += '<div class="adm-card"><div class="adm-hd"><div class="adm-icon" style="background:var(--pri-light)">\u26a1</div>\u5feb\u901f\u5bfc\u822a</div><div class="adm-bd"><div class="quick-nav">';
    hh += qn('\u{1f4d6}','Wiki \u6d4f\u89c8','showWorldTree(\'wiki\')');
    hh += qn('\u{1f4da}','\u5b9e\u4f53\u4e66\u67b6','showWorldTree(\'bookshelf\')');
    hh += qn('\u{1f4dd}','\u672f\u8bed\u68c0\u7d22','showWorldTree(\'terms\')');
    hh += qn('\u{1f5c4}','\u5143\u6570\u636e','showWorldTree(\'metadata\')');
    hh += qn('\u{1f4c1}','\u6587\u4ef6\u7ba1\u7406','loadDocuments()');
    hh += qn('\u2699','\u7cfb\u7edf\u914d\u7f6e','loadConfig()');
    hh += '</div></div></div>';

    v.innerHTML = hh;
  } catch(e) { v.innerHTML = '<div class="err-banner">\u26a0\ufe0f \u52a0\u8f7d\u5931\u8d25: '+e.message+'</div>'; }
}
window.loadDashboard = loadDashboard;

function kpiR(icon,val,label,sub){return '<div class="kr-item"><div class="kr-icon">'+icon+'</div><div class="kr-value">'+val+'</div><div class="kr-label">'+label+'</div><div class="kr-sub">'+(sub||'')+'</div></div>';}
function admCard(icon,bg,title,body){return '<div class="adm-card"><div class="adm-hd"><div class="adm-icon" style="background:'+bg+'">'+icon+'</div>'+title+'</div><div class="adm-bd">'+body+'</div></div>';}
function admCard2(icon,bg,title,body){return '<div class="adm-card"><div class="adm-hd"><div class="adm-icon" style="background:'+bg+'">'+icon+'</div>'+title+'</div><div class="adm-bd">'+body+'</div></div>';}
function ar(label,val,color){return '<div class="adm-row"><span>'+label+'</span><span'+(color?' style="color:'+color+'"':'')+'>'+val+'</span></div>';}
function resBar(label,val,color){return '<div class="res-bar-h"><div class="rb-label"><span>'+label+'</span><span>'+(val||0).toFixed(1)+'%</span></div><div class="rb-track"><div class="rb-fill" style="width:'+(val||0)+'%;background:'+color+'"></div></div></div>';}
function qn(icon,label,onclick){return '<div class="qn-item" onclick="'+onclick+'"><span class="qn-icon">'+icon+'</span>'+label+'</div>';}


function statCard(icon, color, label, value, unit) {
  return '<div class="stat-card"><div class="sc-icon ' + color + '">' + icon + '</div><div><div class="sc-val">' + value + '</div><div class="sc-lbl">' + label + '</div></div></div>';
}


async function loadDocuments() {
  var v = document.getElementById('view');
  v.innerHTML = '<div class="loading">⏳ 加载中…</div>';
  try {
    var r = await fetch('/api/documents?page=1&limit=500');
    var d = await r.json();
    _adminAllFiles = d.files || [];

    var h = '';

    // Upload zone (exactly like home page)
    h += '<div class="upload-zone" id="adminUploadZone" style="margin-bottom:20px">';
    h += '<h3>拖拽文件到此处，或点击上传</h3>';
    h += '<p class="uz-hint">自动分词、向量化、入库 · 单文件 ≤ 200MB</p>';
    h += '<div class="upload-row">';
    h += '<label class="btn btn-primary" id="adminUploadFileBtn" style="cursor:pointer">📎 上传文件<input type="file" id="adminFileInput" multiple onchange="adminOnFilesPicked(this)" style="display:none"></label>';
    h += '<label class="btn btn-secondary" style="cursor:pointer">📂 上传文件夹<input type="file" id="adminFolderInput" webkitdirectory onchange="adminOnFilesPicked(this)" style="display:none"></label>';
    h += '<button class="btn btn-outline btn-sm" onclick="adminPauseUpload()" id="adminPauseBtn" disabled>⏸ 暂停</button>';
    h += '<button class="btn btn-outline btn-sm" style="color:var(--red)" onclick="adminCancelUpload()" id="adminCancelBtn" disabled>✕ 取消</button>';
    h += '</div>';
    h += '<div class="upload-msg" id="adminUploadMsg"></div>';
    h += '<div class="upload-progress" id="adminUploadProgress"><div class="upload-progress-bar" id="adminUploadBar"></div></div>';
    h += '</div>';

    // Toolbar: search + refresh
    h += '<div class="file-toolbar">';
    h += '<input id="fileSearchInput" type="text" placeholder="搜索文件名…" style="flex:1;min-width:200px;padding:8px 14px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit;outline:none" oninput="adminFilterFiles()">';
    h += '<button class="btn btn-outline btn-sm" onclick="loadDocuments()">🔄 刷新</button>';
    h += '</div>';

    // File table
    h += '<div class="file-list" id="adminFileList"></div>';

    v.innerHTML = h;

    // Drag & drop on upload zone
    var zone = document.getElementById('adminUploadZone');
    if (zone) {
      zone.addEventListener('dragover', function(e) { e.preventDefault(); e.stopPropagation(); this.classList.add('dragover'); });
      zone.addEventListener('dragleave', function(e) { e.preventDefault(); e.stopPropagation(); this.classList.remove('dragover'); });
      zone.addEventListener('drop', function(e) { e.preventDefault(); e.stopPropagation(); this.classList.remove('dragover'); var files = e.dataTransfer.files; if (files.length) { _adminUploadQueue = Array.from(files); _adminUploadPaused = false; _adminUploadAborted = false; adminRenderUploadUI(files.length); adminProcessUpload(); } });
    }

    adminRenderFileList(_adminAllFiles);
  } catch(e) { v.innerHTML = '<div class="err-banner">⚠️ 加载失败: ' + e.message + '</div>'; }
}

// ====== File List Renderer ======
var _adminFilePage = 1;
var _adminFilePageSize = 20;
var _adminAllFiles = [];

function adminRenderFileList(files) {
  _adminAllFiles = files;
  _adminFilePage = 1;
  _adminRenderPage();
}

function _adminRenderPage() {
  var files = _adminAllFiles;
  var total = files.length;
  var totalPages = Math.ceil(total / _adminFilePageSize);
  if (_adminFilePage > totalPages) _adminFilePage = totalPages || 1;
  var start = (_adminFilePage - 1) * _adminFilePageSize;
  var pageFiles = files.slice(start, start + _adminFilePageSize);

  var container = document.getElementById('adminFileList');
  if (!container) return;

  var h = '';

  // Top pagination
  h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">';
  h += '<span style="font-size:13px;color:var(--text3)">共 <b>' + total + '</b> 个文件 · 第 <b>' + _adminFilePage + '</b>/' + totalPages + ' 页</span>';
  h += '<div style="display:flex;gap:6px">';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage=1;_adminRenderPage()"' + (_adminFilePage<=1?' disabled':'') + '>« 首页</button>';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage--;_adminRenderPage()"' + (_adminFilePage<=1?' disabled':'') + '>‹ 上一页</button>';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage++;_adminRenderPage()"' + (_adminFilePage>=totalPages?' disabled':'') + '>下一页 ›</button>';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage=' + totalPages + ';_adminRenderPage()"' + (_adminFilePage>=totalPages?' disabled':'') + '>末页 »</button>';
  h += '</div></div>';

  // Table
  h += '<table class="platform-file-table"><thead><tr><th>文件名</th><th>类型</th><th>日期</th><th>操作</th></tr></thead><tbody>';
  pageFiles.forEach(function(f) {
    var fn = f.file_name || f.name || '未知';
    var ft = (f.file_type || '').toUpperCase();
    var date = (f.created_at || '').substring(0, 10);
    var icon = '';
    if (ft.includes('PDF')) icon = '📕';
    else if (ft.includes('DOC')) icon = '📘';
    else if (ft.includes('XLS')) icon = '📗';
    else if (ft.includes('PPT')) icon = '📄';
    else if (ft.includes('DWG') || ft.includes('DXF')) icon = '📐';
    else if (ft.includes('STEP') || ft.includes('STP')) icon = '🧊';
    else icon = '📄';
    var hash = f.file_hash || '';
    var safeFn = fn.replace(/\\/g, ' / ').replace(/'/g, '&#39;');
    var escFn = safeFn.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    h += '<tr>';
    h += '<td><span class="file-name" style="cursor:pointer" onclick="adminViewSource(\'' + hash.replace(/'/g, '\\x27') + '\',\'' + safeFn.replace(/'/g, '\\x27') + '\')"><span class="file-icon">' + icon + '</span>' + escFn + '</span></td>';
    h += '<td>' + (ft || '—') + '</td>';
    h += '<td>' + date + '</td>';
    h += '<td>';
    h += '<button class="btn btn-outline btn-sm" onclick="adminViewSource(\'' + hash.replace(/'/g, '\\x27') + '\',\'' + safeFn.replace(/'/g, '\\x27') + '\')">📋 查看</button> ';
    h += '<button class="btn btn-outline btn-sm" onclick="adminDownloadSource(\'' + hash.replace(/'/g, '\\x27') + '\',\'' + safeFn.replace(/'/g, '\\x27') + '\')">⬇ 下载</button>';
    h += '</td></tr>';
  });
  h += '</tbody></table>';

  // Bottom pagination
  h += '<div style="display:flex;justify-content:center;align-items:center;gap:8px;margin-top:16px">';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage=1;_adminRenderPage()"' + (_adminFilePage<=1?' disabled':'') + '>«</button>';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage--;_adminRenderPage()"' + (_adminFilePage<=1?' disabled':'') + '>‹</button>';
  var maxBtns = 7;
  var pStart = Math.max(1, _adminFilePage - 3);
  var pEnd = Math.min(totalPages, pStart + maxBtns - 1);
  if (pEnd - pStart < maxBtns - 1) pStart = Math.max(1, pEnd - maxBtns + 1);
  if (pStart > 1) h += '<span style="color:var(--text3);font-size:12px">…</span>';
  for (var pi = pStart; pi <= pEnd; pi++) {
    h += '<button class="btn btn-outline btn-sm" style="' + (pi===_adminFilePage?'background:var(--pri);color:#fff;border-color:var(--pri)':'') + '" onclick="_adminFilePage=' + pi + ';_adminRenderPage()">' + pi + '</button>';
  }
  if (pEnd < totalPages) h += '<span style="color:var(--text3);font-size:12px">…</span>';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage++;_adminRenderPage()"' + (_adminFilePage>=totalPages?' disabled':'') + '>›</button>';
  h += '<button class="btn btn-outline btn-sm" onclick="_adminFilePage=' + totalPages + ';_adminRenderPage()"' + (_adminFilePage>=totalPages?' disabled':'') + '>»</button>';
  h += '</div>';

  container.innerHTML = h;
}

function adminFilterFiles() {
  var q = (document.getElementById('fileSearchInput').value || '').toLowerCase();
  var all = _adminAllFiles;
  var filtered = q ? all.filter(function(f) { return (f.file_name||f.name||'').toLowerCase().includes(q); }) : all;
  _adminFilePage = 1;
  adminRenderFileList(filtered);
}

// ====== View & Download (same as home page) ======
function adminViewSource(hash, fn) {
  var ext = (fn || '').toLowerCase().split('.').pop();
  var isPDF = (ext === 'pdf');
  var isImage = /^(png|jpg|jpeg|gif|bmp|webp|svg)$/.test(ext);
  var isOffice = /^(docx|doc|xlsx|xls|pptx|ppt)$/.test(ext);
  var isBinary = isPDF || isImage || isOffice || /^(dwg|dxf|step|stp|stl|igs|zip|rar|7z|tar|gz|exe|dll)$/.test(ext);

  if (isPDF) {
    window.open('/api/view/' + encodeURIComponent(hash), '_blank');
    return;
  }

  var overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });

  var title = (fn||'').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  if (isBinary) {
    overlay.innerHTML = '<div class="modal" style="background:var(--card);border-radius:var(--radius);max-width:500px;width:90vw;box-shadow:0 20px 60px rgba(0,0,0,.3)"><div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)"><h3 style="font-size:16px;margin:0">📄 ' + title + '</h3><button style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text3)" onclick="this.closest(\'div\').parentElement.remove()">✕</button></div><div style="text-align:center;padding:40px"><p style="font-size:48px;margin-bottom:16px">📦</p><p style="font-size:14px;color:var(--text2);margin-bottom:8px">二进制格式文件</p><p style="font-size:13px;color:var(--text3);margin-bottom:20px">无法在线预览，请下载后查看</p><button onclick="adminDownloadSource(\'' + hash.replace(/'/g,'\\x27') + '\',\'' + title.replace(/'/g,'\\x27') + '\');this.closest(\'div\').parentElement.remove()" style="padding:10px 24px;font-size:14px;background:var(--pri);color:#fff;border:none;border-radius:8px;cursor:pointer">⬇ 下载原始文件</button></div></div>';
  } else {
    overlay.innerHTML = '<div class="modal" style="background:var(--card);border-radius:var(--radius);max-width:800px;width:90vw;max-height:90vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.3)"><div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border)"><h3 style="font-size:16px;margin:0">📄 ' + title + '</h3><button style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text3)" onclick="this.closest(\'div\').parentElement.remove()">✕</button></div><div style="padding:20px"><pre style="max-height:60vh;overflow:auto;white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.6;background:#f8f9fa;padding:16px;border-radius:8px">加载中…</pre></div></div>';
    var pre = overlay.querySelector('pre');
    fetch('/api/documents/' + encodeURIComponent(hash)).then(function(r) { return r.json(); }).then(function(d) {
      var chunks = d.chunks || [];
      var text = '';
      chunks.forEach(function(c) { text += (c.text || c.content || '') + '\n---\n'; });
      pre.textContent = text.substring(0, 10000) || '无文本内容';
    }).catch(function() { pre.textContent = '加载失败，请尝试下载'; });
  }

  document.body.appendChild(overlay);
}

function adminDownloadSource(hash, fn) {
  var a = document.createElement('a');
  a.href = '/api/download/' + encodeURIComponent(hash);
  a.download = fn || 'document';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ====== Upload (exactly like home page) ======
var _adminUploadQueue = [];
var _adminUploadPaused = false;
var _adminUploadAborted = false;

function adminOnFilesPicked(input) {
  var files = Array.from(input.files);
  if (!files.length) return;
  _adminUploadQueue = files;
  _adminUploadPaused = false;
  _adminUploadAborted = false;
  adminRenderUploadUI(files.length);
  // Fetch remote file hashes first to skip duplicates
  adminFetchRemoteHashes().then(function() {
    adminProcessUpload();
  });
}

function adminRenderUploadUI(total) {
  var msg = document.getElementById('adminUploadMsg');
  var bar = document.getElementById('adminUploadProgress');
  var barFill = document.getElementById('adminUploadBar');
  var pauseBtn = document.getElementById('adminPauseBtn');
  var cancelBtn = document.getElementById('adminCancelBtn');
  if (msg) { msg.textContent = '准备上传 ' + total + ' 个文件…'; msg.className = 'upload-msg'; }
  if (bar) bar.style.display = 'block';
  if (barFill) barFill.style.width = '0%';
  if (pauseBtn) pauseBtn.disabled = false;
  if (cancelBtn) cancelBtn.disabled = false;
  var upBtn = document.getElementById('adminUploadFileBtn');
  if (upBtn) upBtn.disabled = true;
}

var _adminRemoteHashes = {};

async function adminFetchRemoteHashes() {
  try {
    var r = await fetch('/api/files');
    var d = await r.json();
    _adminRemoteHashes = {};
    (d.files || []).forEach(function(f) {
      if (f.hash) _adminRemoteHashes[f.hash] = true;
      var key = f.name + '|' + f.size;
      _adminRemoteHashes[key] = true;
    });
  } catch(e) {
    _adminRemoteHashes = {};
  }
}

async function adminProcessUpload() {
  var bar = document.getElementById('adminUploadProgress');
  var barFill = document.getElementById('adminUploadBar');
  var msg = document.getElementById('adminUploadMsg');
  var pauseBtn = document.getElementById('adminPauseBtn');
  var cancelBtn = document.getElementById('adminCancelBtn');
  if (pauseBtn) pauseBtn.disabled = false;
  if (cancelBtn) cancelBtn.disabled = false;

  _adminUploadAbortController = new AbortController();
  var total = _adminUploadQueue.length;
  var done = 0;
  var skipped = 0;
  var failed = 0;

  for (var i = 0; i < total; i++) {
    if (_adminUploadAborted) {
      if (msg) { msg.textContent = '上传已取消'; msg.className = 'upload-msg err'; }
      break;
    }
    while (_adminUploadPaused && !_adminUploadAborted) {
      await new Promise(function(r) { setTimeout(r, 500); });
    }
    if (_adminUploadAborted) break;

    var file = _adminUploadQueue[i];
    if (!file) { failed++; continue; }
    if (msg) msg.textContent = '检查 (' + (i+1) + '/' + total + '): ' + (file.name || '?');
    // Check dedup by name+size
    var dedupKey = file.name + '|' + file.size;
    if (_adminRemoteHashes[dedupKey]) {
      skipped++;
      if (barFill) barFill.style.width = ((i+1) / total * 100) + '%';
      continue;
    }
    if (msg) msg.textContent = '上传中 (' + (i+1) + '/' + total + '): ' + (file.name || '?');

    var fd = new FormData();
    fd.append('file', file);
    try {
      var resp;
    try {
      resp = await fetch('/api/upload', { method: 'POST', body: fd, signal: _adminUploadAbortController.signal });
    } catch(fetchErr) {
      if (fetchErr.name === 'AbortError') { if (msg) msg.textContent = '上传已取消'; break; }
      failed++;
      if (barFill) barFill.style.width = ((i+1) / total * 100) + '%';
      continue;
    }
      var j = await resp.json();
      if (j.status === 'ok') done++; else failed++;
    } catch(e) {
      failed++;
      if (barFill) barFill.style.width = ((i+1) / total * 100) + '%';
      continue;
    }

    if (barFill) barFill.style.width = ((i+1) / total * 100) + '%';
  }

  if (!_adminUploadAborted) {
    if (msg) {
      var parts = [];
      parts.push(done + ' 成功');
      if (skipped > 0) parts.push(skipped + ' 跳过(已存在)');
      if (failed > 0) parts.push(failed + ' 失败');
      msg.textContent = '✅ 完成：' + parts.join('，');
      msg.className = 'upload-msg ' + (failed>0?'err':'ok');
    }
  }

  var upBtn2 = document.getElementById('adminUploadFileBtn');
  if (upBtn2) upBtn2.disabled = false;
  if (pauseBtn) { pauseBtn.disabled = true; pauseBtn.textContent = '⏸ 暂停'; }
  if (cancelBtn) { cancelBtn.disabled = true; }
  if (bar) bar.style.display = 'none';
  _adminUploadQueue = [];
}

function adminPauseUpload() {
  _adminUploadPaused = !_adminUploadPaused;
  var btn = document.getElementById('adminPauseBtn');
  if (btn) btn.textContent = _adminUploadPaused ? '▶ 继续' : '⏸ 暂停';
}
function adminCancelUpload() {
  _adminUploadAborted = true;
  if (_adminUploadAbortController) {
    _adminUploadAbortController.abort();
  }
}

async function loadConfig() {
  var v = document.getElementById('view');
  v.innerHTML = '<div class="loading">\u23f3 \u52a0\u8f7d\u4e2d\u2026</div>';
  try {
    var [r1, r2, r3] = await Promise.all([
      fetch('/api/health').then(function(r){return r.json()}),
      fetch('/api/admin/server-status').then(function(r){return r.json()}),
      fetch('/api/worldtree/stats').then(function(r){return r.json()})
    ]);
    var d = r1, s = r2, wt = r3;
    var min = Math.floor((d.uptime_seconds||0)/60), uptimeH = Math.floor(min/60), uptimeM = min % 60;
    var cpu = s.cpu || 0, mem = s.memory || 0, disk = s.disk || 0;

    var html = '';

    // === Health snapshot bar ===
    var healthy = d.status === 'healthy';
    html += '<div class="cfg-health-bar '+(healthy?'':'cfg-hb-warn')+'">';
    html += '<span class="cfg-hb-dot '+(healthy?'':'warn')+'"></span>';
    html += '<span class="cfg-hb-text">'+(healthy?'\u7cfb\u7edf\u6b63\u5e38 \u00b7 \u5df2\u8fd0\u884c '+uptimeH+'h '+uptimeM+'m':'\u7cfb\u7edf\u5f02\u5e38')+'</span>';
    html += '<span class="cfg-hb-right">\u{1f4c5} ' + new Date().toLocaleString('zh-CN') + '</span>';
    html += '</div>';

    // === Service Grid ===
    html += '<div class="cfg-section-title">\u{1f6e0} \u6838\u5fc3\u670d\u52a1</div>';
    html += '<div class="cfg-svc-grid">';
    var svcs = [
      {icon:'\u{1f310}', name:'\u4e3b\u670d\u52a1', port:':8080', ok:true, detail:'HTTP API \u00b7 kb-server', uptime:uptimeH+'h '+uptimeM+'m'},
      {icon:'\u{1f9ec}', name:'Embedder', port:':8081', ok:d.embedder==='ready', detail:'bge-large-zh-v1.5 \u00b7 1024d', uptime:''},
      {icon:'\u2699', name:'Distiller', port:':8093', ok:true, detail:'v2 \u00b7 \u6bcf5\u5206\u949f\u84b8\u998f', uptime:''},
      {icon:'\u{1f4e4}', name:'\u88c5\u8f7d\u673a', port:':8090', ok:(d.loader||'').includes('ready'), detail:d.loader||'ready', uptime:''},
      {icon:'\u{1f4be}', name:'ChromaDB', port:'', ok:d.chroma_storage&&d.chroma_storage.includes('ok'), detail:d.chroma_storage||'', uptime:''},
      {icon:'\u2705', name:'Vector Store', port:'', ok:d.vector_store&&d.vector_store.includes('ready'), detail:d.vector_store||'', uptime:''},
    ];
    svcs.forEach(function(svc){
      html += '<div class="cfg-svc-card">';
      html += '<div class="csc-top"><span class="csc-icon">'+svc.icon+'</span><span class="csc-status '+(svc.ok?'csc-ok':'csc-err')+'">'+(svc.ok?'\u25cf \u6b63\u5e38':'\u25cb \u5f02\u5e38')+'</span></div>';
      html += '<div class="csc-name">'+e(svc.name)+' <span class="csc-port">'+svc.port+'</span></div>';
      html += '<div class="csc-detail">'+e(svc.detail)+'</div>';
      if(svc.uptime) html += '<div class="csc-uptime">\u23f1 '+svc.uptime+'</div>';
      html += '</div>';
    });
    html += '</div>';

    // === AI Engine ===
    html += '<div class="cfg-section-title">\u{1f9e0} AI \u5f15\u64ce</div>';
    html += '<div class="cfg-ai-row">';
    html += '<div class="cfg-ai-card"><span class="cai-label">LLM</span><span class="cai-val">DeepSeek-V3</span><span class="cai-prov">DeepSeek</span></div>';
    html += '<div class="cfg-ai-card"><span class="cai-label">Embed</span><span class="cai-val">BGE-Large-ZH</span><span class="cai-prov">v1.5 \u00b7 1024d</span></div>';
    html += '<div class="cfg-ai-card"><span class="cai-label">Reranker</span><span class="cai-val">Qwen3-Reranker</span><span class="cai-prov">8B</span></div>';
    html += '</div>';

    // === Knowledge Stats ===
    html += '<div class="cfg-section-title">\u{1f4ca} \u77e5\u8bc6\u7edf\u8ba1</div>';
    html += '<div class="cfg-kpi-row">';
    html += cfgKpi('\u{1f4d6}',wt.wiki_pages,'Wiki \u9875\u9762','\u84b8\u998f\u5f15\u64ce\u63d0\u70bc');
    html += cfgKpi('\u{1f333}',wt.entities,'\u77e5\u8bc6\u5b9e\u4f53','\u4e16\u754c\u6811\u63d0\u53d6');
    html += cfgKpi('\u{1f4dd}',wt.terms,'\u672f\u8bed\u6761\u76ee','\u4f01\u4e1a\u6807\u51c6\u672f\u8bed');
    html += cfgKpi('\u{1f4c4}',d.total_files||0,'\u6587\u6863\u6570','\u539f\u59cb\u6587\u6863');
    html += cfgKpi('\u{1f9e9}',d.total_chunks||0,'\u5206\u5757\u6570','\u8bed\u4e49\u5206\u5757');
    html += '</div>';

    // === System Resources ===
    html += '<div class="cfg-section-title">\u{1f4c8} \u7cfb\u7edf\u8d44\u6e90</div>';
    html += '<div class="cfg-res-panel">';
    html += cfgResBar('CPU', cpu, cpu>80?'#e53935':cpu>50?'#ff9800':'#4caf50', '\u5904\u7406\u5668\u4f7f\u7528\u7387');
    html += cfgResBar('\u5185\u5b58', mem, mem>80?'#e53935':mem>50?'#ff9800':'#ff6700', '\u7269\u7406\u5185\u5b58\u5360\u7528');
    html += cfgResBar('\u78c1\u76d8', disk, disk>80?'#e53935':disk>50?'#ff9800':'#20a8d8', '\u5b58\u50a8\u5360\u7528');
    html += '</div>';

    // === System Info ===
    html += '<div class="cfg-info-card">';
    html += '<span class="cic-label">\u{1f333} \u4e16\u754c\u6811</span><span class="cic-val">v19</span>';
    html += '<span class="cic-sep">\u00b7</span>';
    html += '<span class="cic-label">worldtree.db</span>';
    html += '<span class="cic-sep">\u00b7</span>';
    html += '<span class="cic-label">\u84b8\u998f\u5f15\u64ce</span><span class="cic-val">\u8fd0\u884c\u4e2d</span>';
    html += '</div>';

    // Auto-refresh config every 30s
  window._configRefreshId && clearInterval(window._configRefreshId);
  window._configRefreshId = setInterval(function(){
    if(document.getElementById('view')&&document.getElementById('view').querySelector('.cfg-health-bar')){
      loadConfig();
    }
  }, 30000);
  v.innerHTML = html;
  } catch(e) { v.innerHTML = '<div class="err-banner">\u26a0\ufe0f \u52a0\u8f7d\u5931\u8d25: '+e.message+'</div>'; }
}

function cfgKpi(icon, val, label, sub) {
  return '<div class="cfg-kpi"><span class="ck-icon">'+icon+'</span><div class="ck-body"><span class="ck-val">'+(val||0)+'</span><span class="ck-label">'+label+'</span><span class="ck-sub">'+sub+'</span></div></div>';
}
function cfgResBar(label, val, color, detail) {
  var pct = (val||0).toFixed(1);
  return '<div class="cfg-res-row"><div class="crr-info"><span class="crr-name">'+label+'</span><span class="crr-detail">'+detail+'</span></div><div class="crr-bar-wrap"><div class="crr-bar"><div class="crr-fill" style="width:'+pct+'%;background:'+color+'"></div></div><span class="crr-val" style="color:'+color+'">'+pct+'%</span></div></div>';
}

document.addEventListener('DOMContentLoaded', initAdmin);


window.uploadAdminFile = uploadAdminFile;


// ============ 评测中心 ============
async function loadEvaluation() {
  var v = document.getElementById('view');
  v.innerHTML = '<div class="loading">⏳ 加载评测数据…</div>';
  try {
    var r = await fetch('/api/evaluation/overview?days=7').then(function(r){return r.json()});
    if (!r.total_searches) {
      v.innerHTML = '<div class="err-banner">📭 暂无搜索数据，请先使用搜索功能</div>';
      return;
    }

    var zr = r.zero_result || {};
    var lt = r.latency_ms || {};
    var sc = r.score || {};

    var h = '<div class="admin-stats">';
    h += evalStat('🔍','orange','搜索总量', r.total_searches||0, '次 (7天)');
    h += evalStat('🎯','blue','零结果率', (zr.rate*100).toFixed(1)+'%', zr.count+' 次');
    h += evalStat('⚡','green','P95延迟', lt.p95+'ms', '平均 '+lt.avg+'ms');
    h += evalStat('📊','purple','平均分数', sc.avg||'?', sc.sample_count+' 样本');
    h += '</div>';

    h += '<div class="admin-grid2">';
    
    // 延迟分布
    h += '<div class="admin-card"><div class="ac-head">⚡ 延迟分布</div><div class="ac-body">';
    h += resBarP('P50', lt.p50||0, lt.max||10000, '#5d8a5a');
    h += resBarP('P95', lt.p95||0, lt.max||10000, '#c2593a');
    h += resBarP('P99', lt.p99||0, lt.max||10000, '#b8483e');
    h += '<div class="srv-uptime">最大: '+(lt.max||0)+'ms | 平均: '+(lt.avg||0)+'ms</div>';
    h += '</div></div>';

    // 每日趋势
    h += '<div class="admin-card"><div class="ac-head">📅 每日搜索量</div><div class="ac-body">';
    var trend = r.daily_trend || {};
    var keys = Object.keys(trend).sort();
    var maxV = Math.max.apply(null, Object.values(trend).concat([1]));
    keys.forEach(function(d){
      var w = (trend[d]/maxV*100).toFixed(0);
      h += '<div class="bar-row"><span class="bar-label">'+d.slice(5)+'</span><span class="bar-track"><span class="bar-fill" style="width:'+w+'%"></span></span><span class="bar-val">'+trend[d]+'</span></div>';
    });
    h += '</div></div>';
    h += '</div>';

    // Top 查询
    var tq = r.top_queries || [];
    h += '<div class="admin-card"><div class="ac-head">🔥 热门查询 Top 10</div><div class="ac-body">';
    tq.forEach(function(q,i){
      h += '<div class="hq-item hq-clickable" onclick="openSearchLeaf(\''+escAttr(q.query)+'\')" title="点击搜索"><span class="hq-rank">'+(i+1)+'</span><span class="hq-query">'+esc(q.query)+'</span><span class="hq-meta">'+q.count+'次</span></div>';
    });
    h += '</div></div>';

    // 零结果查询
    var zq = r.zero_result_queries || [];
    if (zq.length > 0) {
      h += '<div class="admin-card"><div class="ac-head">⚠️ 零结果查询</div><div class="ac-body">';
      zq.forEach(function(q,i){
        h += '<div class="hq-item hq-clickable" onclick="openSearchLeaf(\''+escAttr(q.query)+'\')" title="点击搜索"><span class="hq-rank" style="background:var(--red-light);color:var(--red)">'+(i+1)+'</span><span class="hq-query">'+esc(q.query)+'</span><span class="hq-meta">'+q.count+'次</span></div>';
      });
      h += '</div></div>';
    }

    v.innerHTML = h;
  } catch(e) { v.innerHTML = '<div class="err-banner">⚠️ 加载失败: '+e.message+'</div>'; }
}
window.loadEvaluation = loadEvaluation;

// ============ 进化中心 ============
async function loadEvolution() {
  var v = document.getElementById('view');
  v.innerHTML = '<div class="loading">⏳ 加载进化数据…</div>';
  try {
    var r = await fetch('/api/evolution/overview?days=30').then(function(r){return r.json()});
    var w = r.wiki || {};
    var g = r.graph || {};
    var f = r.feedback || {};

    var h = '<div class="admin-stats">';
    h += evalStat('📖','orange','Wiki 页面', w.total_pages||0, '健康度 '+(w.health_score||0)+'%');
    h += evalStat('🕸️','blue','知识实体', g.total_entities||0, g.total_relations+' 关系');
    h += evalStat('📝','green','日报数', f.daily_reports_count||0, '反馈 '+f.total_feedback_entries+' 条');
    h += evalStat('🔄','purple','纠错数', f.correction_count||0, '反馈闭环中');
    h += '</div>';

    // Wiki 分类 — 仅展示一级大类汇总
    h += '<div class="admin-card"><div class="ac-head">📖 Wiki 知识分类</div><div class="ac-body" id="wikiCatBars">加载中…</div></div>';
    fetch('/api/worldtree/wiki/tree').then(function(r){return r.json()}).then(function(treeData){
      var cats = (treeData && treeData.tree) ? treeData.tree : [];
      var items = cats.map(function(l1){ return {name: l1.name, count: l1.count || 0}; });
      var maxC = Math.max.apply(null, items.map(function(c){return c.count;}).concat([1]));
      var html2 = '';
      items.forEach(function(c, idx){
        var ww = (c.count/maxC*100).toFixed(0);
        // 不同大类用不同渐变色，视觉区分
        var palettes = [
          'linear-gradient(90deg, #c2593a, #d9826a)',
          'linear-gradient(90deg, #7a9a5e, #9fb87a)',
          'linear-gradient(90deg, #5a7fa0, #7a9fc0)',
          'linear-gradient(90deg, #b08a4a, #d0aa6a)',
          'linear-gradient(90deg, #8a5a9a, #aa7aba)',
          'linear-gradient(90deg, #4a8a8a, #6aaaaa)',
          'linear-gradient(90deg, #9a5a5a, #ba7a7a)',
          'linear-gradient(90deg, #5a9a8a, #7abaaa)'
        ];
        var grad = palettes[idx % palettes.length];
        html2 += '<div class="bar-row bar-row-l1" title="'+esc(c.name)+' ('+c.count+' 页)"><span class="bar-label">'+esc(c.name)+'</span><span class="bar-track"><span class="bar-fill" style="width:'+ww+'%;background:'+grad+'"></span></span><span class="bar-val">'+c.count+'</span></div>';
      });
      document.getElementById('wikiCatBars').innerHTML = html2 || '<div style="color:var(--text3)">暂无分类</div>';
    }).catch(function(){
      document.getElementById('wikiCatBars').innerHTML = '<div style="color:var(--text3)">加载失败</div>';
    });

    // 实体类型
    var types = g.entity_types || {};
    h += '<div class="admin-card"><div class="ac-head">🕸️ 知识图谱实体类型</div><div class="ac-body">';
    h += '<div class="graph-chips">';
    for (var t in types) {
      h += '<span class="graph-chip active">'+esc(t)+': '+types[t]+'</span>';
    }
    h += '</div></div></div>';

    // 进化建议
    var actions = w.actions || [];
    if (actions.length > 0) {
      h += '<div class="admin-card"><div class="ac-head">💡 进化建议</div><div class="ac-body">';
      actions.forEach(function(a){
        var icon = a==='update_stale'?'📝':a==='improve_low_quality'?'⚠️':'✅';
        var text = a==='update_stale'?'有 '+w.stale_pages+' 个 Wiki 页面超过30天未更新':a==='improve_low_quality'?'有 '+w.low_quality_pages+' 个页面质量较低':'';
        h += '<div class="act-row"><span>'+icon+'</span><span>'+text+'</span></div>';
      });
      h += '</div></div>';
    } else {
      h += '<div class="admin-card"><div class="ac-head">💡 进化建议</div><div class="ac-body">✅ Wiki 健康度 100%，无需操作</div></div>';
    }

    v.innerHTML = h;
  } catch(e) { v.innerHTML = '<div class="err-banner">⚠️ 加载失败: '+e.message+'</div>'; }
}
window.loadEvolution = loadEvolution;

// 工具函数
function evalStat(icon, color, label, value, sub) {
  var cls = color==='orange'?'c-orange':color==='blue'?'c-blue':color==='green'?'c-green':'c-purple';
  return '<div class="admin-stat"><div class="as-icon '+cls+'">'+icon+'</div><div><div class="as-val">'+value+'</div><div class="as-lbl">'+label+ (sub?' · '+sub:'') +'</div></div></div>';
}
function resBarP(label, val, max, color) {
  var pct = max>0 ? Math.min(100, (val/max*100)) : 0;
  return '<div class="res-row"><span class="res-lbl">'+label+'</span><span class="res-track"><span class="res-fill" style="width:'+pct+'%;background:'+(color||'var(--pri)')+'"></span></span><span class="res-val">'+(val||0)+'ms</span></div>';
}
function esc(s) { return (s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }


function escAttr(s) { return (s||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;'); }
function openSearchLeaf(query) {
  var url = '/?q=' + encodeURIComponent(query);
  window.open(url, '_blank');
}

