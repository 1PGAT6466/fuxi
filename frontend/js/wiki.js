// ===== Wiki — 分类树形目录 + 美观内容展示 =====
var _wikiPages = [];
// 分类数据从后端 /api/wiki/categories 获取，不再硬编码
var _wikiCategories = null;
var _catIcons = null;
var _catColors = null;

// 默认分类图标/颜色
var _DEFAULT_CAT_ICON = '📁';
var _DEFAULT_CAT_COLOR = '#95a5a6';

// 内置图标/颜色自动映射（可根据后端分类名匹配）
var _CAT_ICON_MAP = {
  '模具设计':'🔧','机械设计':'⚙️','电气自动化':'⚡','自动化产线':'🏭','网络建设':'🌐',
  '工程技术规范':'📋','公司制度':'📜','IT系统':'💻','AI':'🧠','文档':'📄','知识库':'📚',
  '系统':'💻','开发':'🛠','测试':'🧪','运维':'🔧','安全':'🛡','数据':'📊'
};
var _CAT_COLOR_MAP = {
  '模具设计':'#e74c3c','机械设计':'#3498db','电气自动化':'#f39c12','自动化产线':'#27ae60',
  '网络建设':'#9b59b6','工程技术规范':'#1abc9c','公司制度':'#e67e22','IT系统':'#2980b9',
  'AI':'#8e44ad','文档':'#2980b9','知识库':'#8e44ad','系统':'#27ae60','开发':'#e74c3c',
  '测试':'#f39c12','运维':'#1abc9c','安全':'#e74c3c','数据':'#9b59b6'
};

function _getCatIcon(cat) {
  if (_catIcons && _catIcons[cat]) return _catIcons[cat];
  return _CAT_ICON_MAP[cat] || _DEFAULT_CAT_ICON;
}
function _getCatColor(cat) {
  if (_catColors && _catColors[cat]) return _catColors[cat];
  return _CAT_COLOR_MAP[cat] || _DEFAULT_CAT_COLOR;
}

/**
 * 从后端获取分类列表 → GET /api/wiki (返回 categories 字段)
 * 支持格式:
 *   {pages, categories:['cat1','cat2']}
 *   {pages, categories:[{name, keywords[]}]}
 *   {cat1:[kw1], cat2:[kw2]}
 */
async function _loadWikiCategories() {
  if (_wikiCategories !== null) return _wikiCategories;
  try {
    var d = await api('/api/wiki');
    if (d.categories && Array.isArray(d.categories) && d.categories.length > 0 && typeof d.categories[0] !== 'string') {
      _wikiCategories = {};
      d.categories.forEach(function(cat) {
        _wikiCategories[cat.name || cat.title || '未分类'] = cat.keywords || [];
      });
      _catIcons = d.icons || null;
      _catColors = d.colors || null;
      return _wikiCategories;
    }
    if (d.categories && Array.isArray(d.categories) && d.categories.length > 0) {
      _wikiCategories = {};
      d.categories.forEach(function(cat) { _wikiCategories[cat] = [cat.toLowerCase()]; });
      return _wikiCategories;
    }
    if (typeof d === 'object' && Object.keys(d).length > 0) {
      _wikiCategories = d;
      return _wikiCategories;
    }
    console.warn('[Wiki] 后端 /api/wiki 返回空 categories');
    _wikiCategories = {}; _catIcons = {}; _catColors = {};
    return _wikiCategories;
  } catch(e) {
    console.warn('[Wiki] 无法获取分类列表:', e.message);
    _wikiCategories = {}; _catIcons = {}; _catColors = {};
    return _wikiCategories;
  }
}

/**
 * 将 Wiki 页面归类（基于后端返回的分类关键词）
 * 无匹配时归入「未分类」
 */
function _classifyWikiPage(title, content) {
  if (!_wikiCategories) return '未分类';
  var cats = Object.keys(_wikiCategories);
  if (cats.length === 0) return '未分类';
  var text = (title + ' ' + (content||'')).toLowerCase();
  for (var ci = 0; ci < cats.length; ci++) {
    var cat = cats[ci];
    var keywords = _wikiCategories[cat];
    for (var i = 0; i < keywords.length; i++) {
      if (text.indexOf(keywords[i].toLowerCase()) >= 0) return cat;
    }
  }
  return '未分类';
}

async function loadWikiTree() {
  var tree = document.getElementById('wikiTree');
  tree.innerHTML = '<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try {
    // 并行加载分类和页面列表 — 分别捕获错误避免 Promise.all 过早 reject
    var catPromise = _loadWikiCategories().catch(function(e) {
      console.warn('[Wiki] 分类加载失败，使用默认分类:', e.message);
      return {};
    });
    var pagesPromise = api('/api/wiki/pages').catch(function(e) {
      console.warn('[Wiki] 页面列表加载失败:', e.message);
      return { pages: [] };
    });
    var results = await Promise.all([catPromise, pagesPromise]);
    var d = results[1];
    var pages = d.pages || d || [];
    _wikiPages = pages;
    if (!pages.length) {
      tree.innerHTML = '<div style="padding:16px"><div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div><div class="empty"><div class="empty-icon">📚</div><h3>暂无 Wiki 页面</h3><p>上传文档后系统会自动生成</p></div></div>';
      return;
    }
    _renderWikiTree('');
  } catch(e) {
    tree.innerHTML = '<div style="padding:16px"><div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div><div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(e.message)+'</p><button class="btn btn-ghost btn-sm" onclick="loadWikiTree()" style="margin-top:8px">重试</button></div></div>';
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

  var catOrder = Object.keys(groups);
  catOrder.sort(function(a, b) {
    if (a === '未分类') return 1;
    if (b === '未分类') return -1;
    return a.localeCompare(b);
  });
  // P1-9: 如果所有页面都在「未分类」中，显示提示
  var allUnclassified = catOrder.length === 1 && catOrder[0] === '未分类';
  var html = '<div style="padding:0 4px">';
  html += '<div style="font-size:13px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px">📚 目录 <span style="font-size:11px;color:var(--text3);font-weight:400">('+_wikiPages.length+')</span></div>';
  html += '<div style="display:flex;align-items:center;gap:6px;background:var(--bg);border-radius:8px;padding:6px 10px;margin-bottom:12px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color:var(--text3);flex-shrink:0"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><input type="text" placeholder="搜索页面..." value="'+esc(filter)+'" oninput="_renderWikiTree(this.value)" style="flex:1;border:none;background:transparent;font-size:12px;outline:none;font-family:var(--font)"></div>';

  // P1-9: 无分类时显示提示
  if (allUnclassified) {
    html += '<div style="font-size:11px;color:var(--text3);padding:4px 8px;margin-bottom:8px;background:var(--bg);border-radius:6px;line-height:1.5">💡 分类关键词尚未配置，所有页面归入「未分类」。可在后端 /api/wiki 接口返回 categories 字段来启用自动分类。</div>';
  }

  catOrder.forEach(function(cat) {
    var pages = groups[cat];
    if (!pages || !pages.length) return;
    var icon = _getCatIcon(cat);
    var color = _getCatColor(cat);
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
// P0-5 fix: 使用 counter 逐个匹配，避免 replaced 标志位匹配错位
function _addHeadingIds(html, content) {
  if (!content) return html;
  var lines = content.split('\n');
  // 收集所有需要加 id 的标题信息
  var headingMap = {};
  var headingCounter = {};
  for (var i = 0; i < lines.length; i++) {
    var m = lines[i].match(/^(#{1,3})\s+(.+)/);
    if (m) {
      var level = m[1].length;
      var text = m[2].replace(/\*\*/g, '').replace(/\*/g, '').trim();
      var tag = 'h' + level;
      var id = 'heading-' + i;
      if (!headingMap[tag]) headingMap[tag] = [];
      headingMap[tag].push({ id: id, text: text });
    }
  }
  // 对每个 heading 级别，按顺序替换 <hN> 标签
  for (var tag in headingMap) {
    if (!headingMap.hasOwnProperty(tag)) continue;
    var headings = headingMap[tag];
    var idx = 0;
    // 使用全局匹配，逐个替换
    var re = new RegExp('<' + tag + '([^>]*)>', 'gi');
    html = html.replace(re, function(match, attrs) {
      if (idx >= headings.length) return match;
      var h = headings[idx++];
      // 如果已有 id 属性，跳过
      if (attrs && /\bid\s*=/i.test(attrs)) return match;
      return '<' + tag + ' id="' + h.id + '"' + (attrs ? ' ' + attrs.trim() : '') + '>';
    });
  }
  return html;
}


// 智能结构化：将【xxx】：描述 和 **key**：value 模式转为卡片/表格
// P2-14: 先快速检查是否包含模式特征，避免对纯文本页面运行 4 次全量正则替换
// P3-R2: 将正则提取为模块常量，避免每次调用重新编译，并限制处理次数防止大内容性能退化
var _WIKI_ACTION_PATTERN = /(<p>【[^】]+】[：:][^<]*<\/p>\s*){2,}/g;
var _WIKI_ACTION_ITEM_RE = /<p>【([^】]+)】[：:]\s*([^<]*)<\/p>/g;
// R3-3 fix: 允许 value 中包含嵌套 HTML（如 <a>/<code>/<em>），仅禁止跨 <li> 匹配
var _WIKI_KV_FULL_RE = /<li>\s*<strong>([^<]+)<\/strong>[：:]\s*((?:(?!<li[\s>])[\s\S])*?)<\/li>/g;
var _WIKI_KV_NESTED_RE = /<li>\s*<strong>([^<]+)<\/strong>[：:]\s*<ul>([\s\S]*?)<\/ul>\s*<\/li>/g;
var _WIKI_LI_RE = /<li>([^<]*(?:<strong>[^<]*<\/strong>[^<]*)?)<\/li>/g;
var _WIKI_KV_EMPTY_RE = /<li>\s*<strong>([^<]+)<\/strong>[：:]\s*<\/li>/g;
var _WIKI_MAX_REPLACEMENTS = 50;

function _structureContent(html) {
  var hasAction = html.indexOf('【') >= 0;
  var hasKeyValue = html.indexOf('<strong>') >= 0;
  if (!hasAction && !hasKeyValue) return html;  // 跳过无特征内容

  // 模式1: 【操作名】：描述 — 转为操作卡片表格
  if (hasAction) {
    var actionCount = 0;
    html = html.replace(_WIKI_ACTION_PATTERN, function(match) {
      if (actionCount++ >= _WIKI_MAX_REPLACEMENTS) return match;
      var items = [];
      var m;
      _WIKI_ACTION_ITEM_RE.lastIndex = 0;
      while ((m = _WIKI_ACTION_ITEM_RE.exec(match)) !== null) {
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
  }

  // 模式2-4 仅当有 <strong> 标签时才执行
  if (hasKeyValue) {
  var kvCount = 0;
  // 模式2: li 中 **key**：value — 转为定义卡片
  html = html.replace(_WIKI_KV_FULL_RE, function(match, key, value) {
    if (kvCount++ >= _WIKI_MAX_REPLACEMENTS) return match;
    return '<li style="list-style:none;padding:0;margin-bottom:12px"><div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px"><div style="font-weight:600;color:var(--mi-orange);font-size:13px;margin-bottom:4px">' + key.trim() + '</div><div style="color:var(--text2);font-size:13px;line-height:1.7">' + (value.trim() || '') + '</div></div></li>';
  });

  // 模式3: <li>后紧跟 <ul> 的 **key**：嵌套子列表 — 提取为卡片
  kvCount = 0;
  html = html.replace(_WIKI_KV_NESTED_RE, function(match, key, subList) {
    if (kvCount++ >= _WIKI_MAX_REPLACEMENTS) return match;
    var subItems = [];
    var m2;
    _WIKI_LI_RE.lastIndex = 0;
    while ((m2 = _WIKI_LI_RE.exec(subList)) !== null) {
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

  // 模式4: 空值的 key-value（key 后无内容）
  kvCount = 0;
  html = html.replace(_WIKI_KV_EMPTY_RE, function(match, key) {
    if (kvCount++ >= _WIKI_MAX_REPLACEMENTS) return match;
    return '<li style="list-style:none;padding:0;margin-bottom:8px"><div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 14px"><span style="font-weight:600;color:var(--mi-orange);font-size:13px">' + key.trim() + '</span></div></li>';
  });
  }  // end if (hasKeyValue)

  return html;
}



async function loadWikiPage(id) {
  try {
    // 确保分类数据已加载
    if (_wikiCategories === null) await _loadWikiCategories();
    var c = document.getElementById('wikiContent');
    c.innerHTML = '<div style="text-align:center;padding:60px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
    var d = await api('/api/wiki/page/' + id);
    var content = d.content || '';
    if (typeof marked === 'undefined') console.warn('[Wiki] marked.js CDN 加载失败，将回退为纯文本');
    if (typeof DOMPurify === 'undefined') console.warn('[Wiki] DOMPurify CDN 加载失败，安全防护降级');
    var rendered = typeof marked !== 'undefined' ? marked.parse(content) : esc(content);
    if (typeof DOMPurify !== 'undefined') rendered = DOMPurify.sanitize(rendered);

    // 给标题加 id
    rendered = _addHeadingIds(rendered, content);
    rendered = _structureContent(rendered);

    // 分类
    var cat = _classifyWikiPage(d.title, content);
    var catIcon = _getCatIcon(cat);
    var catColor = _getCatColor(cat);

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
