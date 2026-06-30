// ===== Wiki — 分类树形目录 + 美观内容展示 =====
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

var _catIcons = {'模具设计':'🔧','机械设计':'⚙️','电气自动化':'⚡','自动化产线':'🏭','网络建设':'🌐','工程技术规范':'📋','公司制度':'📜','IT系统':'💻','AI':'🧠','其他':'📁'};
var _catColors = {'模具设计':'#e74c3c','机械设计':'#3498db','电气自动化':'#f39c12','自动化产线':'#27ae60','网络建设':'#9b59b6','工程技术规范':'#1abc9c','公司制度':'#e67e22','IT系统':'#2980b9','AI':'#8e44ad','其他':'#95a5a6'};

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

  var groups = {};
  filtered.forEach(function(p) {
    var cat = _classifyWikiPage(p.title, p.content);
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(p);
  });

  var catOrder = ['模具设计','机械设计','电气自动化','自动化产线','网络建设','工程技术规范','公司制度','IT系统','AI','其他'];
  var html = '<div style="padding:0 4px">';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px">📚 目录 <span style="font-size:11px;color:var(--text3);font-weight:400">('+_wikiPages.length+')</span></div>';
  html += '<div style="display:flex;align-items:center;gap:6px;background:var(--bg);border-radius:8px;padding:6px 10px;margin-bottom:12px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color:var(--text3);flex-shrink:0"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><input type="text" placeholder="搜索页面..." value="'+esc(filter)+'" oninput="_renderWikiTree(this.value)" style="flex:1;border:none;background:transparent;font-size:12px;outline:none;font-family:var(--font)"></div>';

  catOrder.forEach(function(cat) {
    var pages = groups[cat];
    if (!pages || !pages.length) return;
    var icon = _catIcons[cat] || '📁';
    var color = _catColors[cat] || '#999';
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

// 提取 markdown 中的标题作为目录
function _extractToc(content) {
  if (!content) return [];
  var toc = [];
  var lines = content.split('\n');
  for (var i = 0; i < lines.length; i++) {
    var m = lines[i].match(/^(#{1,3})\s+(.+)/);
    if (m) {
      var level = m[1].length;
      var text = m[2].replace(/\*\*/g, '').replace(/\*/g, '').trim();
      var id = 'heading-' + i;
      toc.push({ level: level, text: text, id: id });
    }
  }
  return toc;
}

// 给渲染后的 HTML 中的标题加 id（用于目录跳转）
function _addHeadingIds(html, content) {
  if (!content) return html;
  var lines = content.split('\n');
  var headingIdx = 0;
  for (var i = 0; i < lines.length; i++) {
    var m = lines[i].match(/^(#{1,3})\s+(.+)/);
    if (m) {
      var level = m[1].length;
      var tag = 'h' + level;
      var id = 'heading-' + i;
      // 替换第一个匹配的 <hN> 为 <hN id="...">
      var re = new RegExp('<' + tag + '>([\\s\\S]*?)</' + tag + '>');
      var replaced = false;
      html = html.replace(re, function(match) {
        if (replaced) return match;
        replaced = true;
        return '<' + tag + ' id="' + id + '">' + match.slice(tag.length + 2, -(tag.length + 3)) + '</' + tag + '>';
      });
    }
  }
  return html;
}


// 智能结构化：将【xxx】：描述 和 **key**：value 模式转为卡片/表格
function _structureContent(html) {
  // 模式1: 【操作名】：描述 — 转为操作卡片表格
  var actionPattern = /(<p>【[^】]+】[：:][^<]*<\/p>\s*){2,}/g;
  html = html.replace(actionPattern, function(match) {
    var items = [];
    var re = /<p>【([^】]+)】[：:]\s*([^<]*)<\/p>/g;
    var m;
    while ((m = re.exec(match)) !== null) {
      items.push({ action: m[1], desc: m[2].trim() });
    }
    if (items.length < 2) return match;
    var table = '<div style="margin:16px 0"><table style="width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;font-size:13px"><thead><tr><th style="background:var(--bg);padding:10px 14px;text-align:left;font-weight:600;color:var(--text3);font-size:12px;width:120px">操作</th><th style="background:var(--bg);padding:10px 14px;text-align:left;font-weight:600;color:var(--text3);font-size:12px">说明</th></tr></thead><tbody>';
    items.forEach(function(it, i) {
      var bg = i % 2 === 0 ? '' : ' style="background:rgba(0,0,0,0.01)"';
      table += '<tr' + bg + '><td style="padding:10px 14px;border-bottom:1px solid var(--border);font-weight:600;color:var(--mi-orange)">【' + esc(it.action) + '】</td><td style="padding:10px 14px;border-bottom:1px solid var(--border);color:var(--text2)">' + esc(it.desc) + '</td></tr>';
    });
    table += '</tbody></table></div>';
    return table;
  });

  // 模式2: li 中 **key**：value — 转为定义卡片
  // 匹配 <li><strong>key</strong>：value</li> 或 <li><strong>key</strong>：<br>
  html = html.replace(/<li>\s*<strong>([^<]+)<\/strong>[：:]\s*([^<]*(?:<br>\s*<\/li>|<\/li>))/g, function(match, key, value) {
    return '<li style="list-style:none;padding:0;margin-bottom:12px"><div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px"><div style="font-weight:600;color:var(--mi-orange);font-size:13px;margin-bottom:4px">' + key.trim() + '</div><div style="color:var(--text2);font-size:13px;line-height:1.7">' + (value.trim() || '') + '</div></div></li>';
  });

  // 模式3: <li>后紧跟 <ul> 的 **key**：嵌套子列表 — 提取为卡片
  // 匹配 <li><strong>key</strong>：<ul>子项</ul></li>
  html = html.replace(/<li>\s*<strong>([^<]+)<\/strong>[：:]\s*<ul>([\s\S]*?)<\/ul>\s*<\/li>/g, function(match, key, subList) {
    // 提取子项
    var subItems = [];
    var re2 = /<li>([^<]*(?:<strong>[^<]*<\/strong>[^<]*)?)<\/li>/g;
    var m2;
    while ((m2 = re2.exec(subList)) !== null) {
      subItems.push(m2[1].trim());
    }
    var card = '<li style="list-style:none;padding:0;margin-bottom:12px"><div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px"><div style="font-weight:600;color:var(--mi-orange);font-size:13px;margin-bottom:8px">' + key.trim() + '</div>';
    if (subItems.length) {
      card += '<ul style="margin:0;padding-left:16px;font-size:13px;color:var(--text2);line-height:1.8">';
      subItems.forEach(function(si) {
        card += '<li style="margin-bottom:4px">' + si + '</li>';
      });
      card += '</ul>';
    }
    card += '</div></li>';
    return card;
  });

  // 模式4: 连续的 <li><strong>key</strong>：value</li> (无嵌套) — 已被模式2处理
  // 但如果模式2没匹配到（因为 value 在下一行），再试一次
  html = html.replace(/<li>\s*<strong>([^<]+)<\/strong>[：:]\s*<\/li>/g, function(match, key) {
    return '<li style="list-style:none;padding:0;margin-bottom:8px"><div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 14px"><span style="font-weight:600;color:var(--mi-orange);font-size:13px">' + key.trim() + '</span></div></li>';
  });

  return html;
}



async function loadWikiPage(id) {
  try {
    var c = document.getElementById('wikiContent');
    c.innerHTML = '<div style="text-align:center;padding:60px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
    var d = await api('/api/wiki/page/' + id);
    var content = d.content || '';
    var rendered = typeof marked !== 'undefined' ? marked.parse(content) : esc(content);
    if (typeof DOMPurify !== 'undefined') rendered = DOMPurify.sanitize(rendered);

    // 给标题加 id
    rendered = _addHeadingIds(rendered, content);
    rendered = _structureContent(rendered);

    // 分类
    var cat = _classifyWikiPage(d.title, content);
    var catIcon = _catIcons[cat] || '📁';
    var catColor = _catColors[cat] || '#999';

    // 提取目录
    var toc = _extractToc(content);

    // 面包屑
    var breadcrumb = '<div style="font-size:12px;color:var(--text3);margin-bottom:20px;display:flex;align-items:center;gap:6px">';
    breadcrumb += '<span style="cursor:pointer;color:var(--mi-orange)" onclick="loadWikiTree()">📚 目录</span>';
    breadcrumb += '<span style="opacity:0.4">›</span>';
    breadcrumb += '<span style="background:'+catColor+'15;color:'+catColor+';padding:2px 8px;border-radius:4px;font-size:11px">'+catIcon+' '+esc(cat)+'</span>';
    breadcrumb += '<span style="opacity:0.4">›</span>';
    breadcrumb += '<span style="color:var(--text);font-weight:500">'+esc(d.title||'')+'</span>';
    breadcrumb += '</div>';

    // 标题卡片
    var titleCard = '<div style="background:linear-gradient(135deg,'+catColor+'08,'+catColor+'04);border:1px solid '+catColor+'15;border-radius:12px;padding:20px 24px;margin-bottom:20px">';
    titleCard += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">';
    titleCard += '<span style="font-size:28px">'+catIcon+'</span>';
    titleCard += '<div>';
    titleCard += '<h1 style="font-size:22px;font-weight:700;margin:0;line-height:1.3">'+esc(d.title||'')+'</h1>';
    titleCard += '<div style="font-size:12px;color:var(--text3);margin-top:4px">'+esc(cat)+' · Wiki 知识页面</div>';
    titleCard += '</div></div>';
    if (d.summary) {
      titleCard += '<div style="font-size:13px;color:var(--text2);line-height:1.6;margin-top:8px;padding-top:12px;border-top:1px solid '+catColor+'10">'+esc(d.summary)+'</div>';
    }
    titleCard += '</div>';

    // 目录侧栏
    var tocHtml = '';
    if (toc.length > 2) {
      tocHtml = '<div style="background:var(--bg);border-radius:10px;padding:16px;margin-bottom:20px">';
      tocHtml += '<div style="font-size:12px;font-weight:600;color:var(--text3);margin-bottom:10px;text-transform:uppercase;letter-spacing:1px">📑 目录</div>';
      toc.forEach(function(t) {
        var indent = (t.level - 1) * 12;
        tocHtml += '<div style="padding:4px 0;padding-left:'+indent+'px">';
        tocHtml += '<a href="#'+t.id+'" style="font-size:12px;color:var(--text2);text-decoration:none;transition:color .15s" onmouseenter="this.style.color=\'var(--mi-orange)\'" onmouseleave="this.style.color=\'var(--text2)\'">';
        tocHtml += (t.level > 1 ? '<span style="opacity:0.3;margin-right:4px">└</span>' : '') + esc(t.text);
        tocHtml += '</a></div>';
      });
      tocHtml += '</div>';
    }

    // 内容区域
    var contentCard = '<div class="wiki-rendered" style="font-size:14px;line-height:1.9;color:var(--text)">'+rendered+'</div>';

    // 组装
    c.innerHTML = breadcrumb + titleCard + tocHtml + contentCard;

    // 高亮当前目录项
    document.querySelectorAll('.wiki-tree-item').forEach(function(t) {
      t.classList.toggle('active', t.dataset.id === id);
    });
  } catch(e) {
    document.getElementById('wikiContent').innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(e.message) + '</p></div>';
  }
}
