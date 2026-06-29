// ===== Wiki — 分类树形目录 =====
var _wikiPages = [];
var _wikiCategories = {
  "模具设计": ["模具","连接器","端子","注塑","成型","型腔","分模","滑块"],
  "机械设计": ["机械","材料","标准件","公差","轴承","齿轮","紧固件","联轴器","丝杆","导轨"],
  "电气自动化": ["电气","PLC","传感器","伺服","电机","变频","HMI","SCADA","继电器"],
  "自动化产线": ["自动化","产线","装配线","流水线","机器人","AGV","机械手","视觉"],
  "网络建设": ["网络","VLAN","路由","交换","DHCP","DNS","防火墙","AP","拓扑","子网"],
  "工程技术规范": ["规范","标准","ISO","GB","工艺","SOP","技术要求","验收","品质","SPC","FMEA"],
  "公司制度": ["制度","人事","财务","行政","培训","安全","采购","项目管理","会议","合同"],
  "IT系统": ["IT系统","操作手册","泛微","E-cology","SAP","OA","ERP","MES","PLM","WMS","流程引擎","门户引擎"],
  "AI": ["RAG","AI","LLM","机器学习","NLP","检索","分块","Embedding","Agent","评测","召回","Rerank"]
};

function _classifyWikiPage(title, content) {
  var text = (title + ' ' + (content||'')).toLowerCase();
  for (var cat in _wikiCategories) {
    var keywords = _wikiCategories[cat];
    for (var i = 0; i < keywords.length; i++) {
      if (text.indexOf(keywords[i].toLowerCase()) >= 0) return cat;
    }
  }
  return '其他';
}

async function loadWikiTree() {
  var tree = document.getElementById('wikiTree');
  tree.innerHTML = '<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try {
    var d = await api('/api/wiki/pages');
    var pages = d.pages || d || [];
    _wikiPages = pages;
    if (!pages.length) {
      tree.innerHTML = '<div style="padding:16px"><div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div><div class="empty"><div class="empty-icon">📚</div><h3>暂无 Wiki 页面</h3><p>上传文档后系统会自动生成</p></div></div>';
      return;
    }
    _renderWikiTree('');
  } catch(e) {
    tree.innerHTML = '<div style="padding:16px"><div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div><div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(e.message)+'</p></div></div>';
  }
}

function _renderWikiTree(filter) {
  var tree = document.getElementById('wikiTree');
  var filtered = filter ? _wikiPages.filter(function(p) { return (p.title||'').toLowerCase().indexOf(filter.toLowerCase()) >= 0; }) : _wikiPages;

  // 分类
  var groups = {};
  filtered.forEach(function(p) {
    var cat = _classifyWikiPage(p.title, p.content);
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(p);
  });

  var catOrder = ['模具设计','机械设计','电气自动化','自动化产线','网络建设','工程技术规范','公司制度','IT系统','AI','其他'];
  var catIcons = {'模具设计':'🔧','机械设计':'⚙️','电气自动化':'⚡','自动化产线':'🏭','网络建设':'🌐','工程技术规范':'📋','公司制度':'📜','IT系统':'💻','AI':'🧠','其他':'📁'};
  var html = '<div style="padding:0 4px">';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px">📚 目录 <span style="font-size:11px;color:var(--text3);font-weight:400">('+_wikiPages.length+')</span></div>';
  html += '<div style="display:flex;align-items:center;gap:6px;background:var(--bg);border-radius:8px;padding:6px 10px;margin-bottom:12px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color:var(--text3);flex-shrink:0"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><input type="text" placeholder="搜索页面..." value="'+esc(filter)+'" oninput="_renderWikiTree(this.value)" style="flex:1;border:none;background:transparent;font-size:12px;outline:none;font-family:var(--font)"></div>';

  catOrder.forEach(function(cat) {
    var pages = groups[cat];
    if (!pages || !pages.length) return;
    var icon = catIcons[cat] || '📁';
    html += '<div class="wiki-cat" style="margin-bottom:8px">';
    html += '<div onclick="this.parentElement.querySelector(\'.wiki-cat-items\').classList.toggle(\'hidden\')" style="display:flex;align-items:center;gap:6px;padding:6px 8px;cursor:pointer;border-radius:6px;font-size:12px;font-weight:600;color:var(--text2);transition:all .15s" onmouseenter="this.style.background=\'var(--bg)\'" onmouseleave="this.style.background=\'transparent\'">';
    html += '<span style="font-size:14px">'+icon+'</span>';
    html += '<span>'+esc(cat)+'</span>';
    html += '<span style="font-size:10px;color:var(--text3);margin-left:auto">'+pages.length+'</span>';
    html += '</div>';
    html += '<div class="wiki-cat-items" style="padding-left:20px">';
    pages.forEach(function(p) {
      html += '<div class="wiki-tree-item" data-id="'+esc(p.id||p.page_id||'')+'" onclick="loadWikiPage(this.dataset.id)">'+esc(p.title||'未命名')+'</div>';
    });
    html += '</div></div>';
  });

  html += '</div>';
  tree.innerHTML = html;
}

async function loadWikiPage(id) {
  try {
    var c = document.getElementById('wikiContent');
    c.innerHTML = '<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
    var d = await api('/api/wiki/page/' + id);
    var rendered = typeof marked !== 'undefined' ? marked.parse(d.content || '') : esc(d.content || '');
    if (typeof DOMPurify !== 'undefined') rendered = DOMPurify.sanitize(rendered);

    // 面包屑
    var cat = _classifyWikiPage(d.title, d.content);
    var breadcrumb = '<div style="font-size:12px;color:var(--text3);margin-bottom:16px;display:flex;align-items:center;gap:6px"><span style="cursor:pointer;color:var(--mi-orange)" onclick="loadWikiTree()">📚 目录</span> <span>›</span> <span>'+esc(cat)+'</span> <span>›</span> <span style="color:var(--text);font-weight:500">'+esc(d.title||'')+'</span></div>';

    c.innerHTML = breadcrumb + '<h1>' + esc(d.title || '') + '</h1><div>' + rendered + '</div>';
    document.querySelectorAll('.wiki-tree-item').forEach(function(t) {
      t.classList.toggle('active', t.dataset.id === id);
    });
  } catch(e) {
    document.getElementById('wikiContent').innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(e.message) + '</p></div>';
  }
}
