// ===== 知识图谱 — D3.js 力导向图 =====
var _graphSimulation = null;
var _graphNodes = [];
var _graphEdges = [];
// 缓存完整图谱数据，避免 _filterGraphType 每次重新请求 API
var _graphCache = null;

async function loadGraph() {
  var container = document.getElementById('graphEntities');
  container.innerHTML = '<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try {
    var d = await api('/api/graph');
    _graphCache = d;  // 缓存完整数据供类型过滤复用
    var nodes = d.nodes || {};
    var edges = d.edges || [];
    var entries = Object.entries(nodes);

    if (!entries.length) {
      container.innerHTML = '<div class="empty"><div class="empty-icon">🕸️</div><h3>知识图谱为空</h3><p>上传文档后系统会自动抽取实体和关系</p></div>';
      _clearCanvas();
      return;
    }

    // 统计
    var typeCounts = {};
    entries.forEach(function(e) {
      var t = (e[1] && e[1].type) || '未知';
      typeCounts[t] = (typeCounts[t] || 0) + 1;
    });

    // 左侧面板 — 统计 + 实体列表
    var html = '<div style="font-size:12px;color:var(--text3);margin-bottom:12px">';
    html += '节点: <strong>' + entries.length + '</strong> | 边: <strong>' + edges.length + '</strong>';
    html += '</div>';

    // 类型过滤
    html += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">';
    html += '<button class="btn btn-sm btn-primary graph-filter-btn" data-type="" style="font-size:11px;padding:3px 8px">全部</button>';
    Object.entries(typeCounts).forEach(function(e) {
      html += '<button class="btn btn-sm btn-ghost graph-filter-btn" data-type="' + esc(e[0]) + '" style="font-size:11px;padding:3px 8px">' + esc(e[0]) + ' (' + e[1] + ')</button>';
    });
    html += '</div>';

    // 实体列表（按连接数排序）
    var connCounts = {};
    edges.forEach(function(e) {
      var s = e.from || e.source || '';
      var t = e.to || e.target || '';
      connCounts[s] = (connCounts[s] || 0) + 1;
      connCounts[t] = (connCounts[t] || 0) + 1;
    });

    var sorted = entries.slice(0, 100).sort(function(a, b) {
      return (connCounts[b[0]] || 0) - (connCounts[a[0]] || 0);
    });

    html += '<div id="graphEntityList">';
    sorted.forEach(function(e) {
      var name = e[0];
      var info = e[1] || {};
      var type = info.type || '';
      var conn = connCounts[name] || 0;
      var colors = {'人物':'#FF6B6B','组织':'#4ECDC4','概念':'#45B7D1','地点':'#96CEB4','技术':'#FFEAA7','产品':'#DDA0DD'};
      var color = colors[type] || '#999';
      html += '<div class="graph-entity" style="cursor:pointer;padding:8px 0;border-bottom:1px solid var(--border-light);display:flex;align-items:center;gap:8px" data-node="' + esc(name) + '">';
      html += '<span style="width:8px;height:8px;border-radius:50%;background:' + color + ';flex-shrink:0"></span>';
      html += '<span style="flex:1;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(name) + '</span>';
      html += '<span style="font-size:10px;color:var(--text3)">' + conn + ' 连接</span>';
      html += '</div>';
    });
    html += '</div>';
    container.innerHTML = html;

    // P1-5/P1-6 fix: 用事件委托替代内联 onclick，防止 XSS 注入
    container.querySelectorAll('.graph-filter-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        _filterGraphType(this.dataset.type || '');
      });
    });
    container.querySelectorAll('.graph-entity[data-node]').forEach(function(el) {
      el.addEventListener('click', function() {
        _highlightNode(this.dataset.node);
      });
    });
    container.querySelectorAll('.graph-neighbor[data-neighbor]').forEach(function(el) {
      el.addEventListener('click', function() {
        _highlightNode(this.dataset.neighbor);
      });
    });

    // 绘制 D3 力导向图
    _drawD3Graph(entries, edges);

  } catch(e) {
    container.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(e.message) + '</p><button class="btn btn-ghost btn-sm" onclick="loadGraph()" style="margin-top:8px">重试</button></div>';
  }
}

function _clearCanvas() {
  var canvas = document.getElementById('graphCanvas');
  var ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (_graphSimulation) { _graphSimulation.stop(); _graphSimulation = null; }
}

function _drawD3Graph(entries, edges) {
  var canvas = document.getElementById('graphCanvas');
  var container = canvas.parentElement;
  var W = container.offsetWidth;
  var H = container.offsetHeight;
  canvas.width = W;
  canvas.height = H;
  var ctx = canvas.getContext('2d');

  if (_graphSimulation) _graphSimulation.stop();

  // P3-5 fix: 清理旧的 D3 事件绑定，防止多次调用 _drawD3Graph 导致事件泄漏
  d3.select(canvas).on('.drag', null).on('click', null);

  // 准备数据
  var nodeMap = {};
  _graphNodes = entries.map(function(e, i) {
    var node = { id: e[0], type: (e[1] && e[1].type) || '未知', index: i };
    nodeMap[e[0]] = node;
    return node;
  });

  _graphEdges = edges.map(function(e) {
    var s = e.from || e.source || '';
    var t = e.to || e.target || '';
    return { source: s, target: t, relation: e.relation || e.label || '' };
  }).filter(function(e) { return nodeMap[e.source] && nodeMap[e.target]; });

  var typeColors = {'人物':'#FF6B6B','组织':'#4ECDC4','概念':'#45B7D1','地点':'#96CEB4','技术':'#FFEAA7','产品':'#DDA0DD'};
  var defaultColor = '#ADB5BD';

  // D3 力导向仿真
  _graphSimulation = d3.forceSimulation(_graphNodes)
    .force('link', d3.forceLink(_graphEdges).id(function(d) { return d.id; }).distance(100))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(30))
    .on('tick', ticked);

  // 拖拽
  d3.select(canvas)
    .call(d3.drag()
      .container(canvas)
      .subject(function(event) {
        var x = event.x, y = event.y;
        var closest = null, minDist = Infinity;
        _graphNodes.forEach(function(n) {
          var dx = n.x - x, dy = n.y - y;
          var dist = dx * dx + dy * dy;
          if (dist < minDist && dist < 900) { minDist = dist; closest = n; }
        });
        return closest;
      })
      .on('start', function(event) {
        if (!event.active) _graphSimulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      })
      .on('drag', function(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      })
      .on('end', function(event) {
        if (!event.active) _graphSimulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      })
    );

  // 点击
  d3.select(canvas).on('click', function(event) {
    var x = event.offsetX, y = event.offsetY;
    var clicked = null, minDist = Infinity;
    _graphNodes.forEach(function(n) {
      var dx = n.x - x, dy = n.y - y;
      var dist = dx * dx + dy * dy;
      if (dist < minDist && dist < 400) { minDist = dist; clicked = n; }
    });
    if (clicked) _showNodeDetail(clicked);
  });

  function ticked() {
    ctx.clearRect(0, 0, W, H);

    // 绘制边
    _graphEdges.forEach(function(e) {
      if (!e.source || !e.target) return;
      var sx = e.source.x || 0, sy = e.source.y || 0;
      var tx = e.target.x || 0, ty = e.target.y || 0;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.strokeStyle = e.relation === 'co_occurs' ? 'rgba(255,103,0,.2)' : 'rgba(0,122,255,.15)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // 关系标签
      if (e.relation && e.relation !== 'co_occurs') {
        var mx = (sx + tx) / 2, my = (sy + ty) / 2;
        ctx.fillStyle = 'rgba(0,0,0,.4)';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(e.relation.substring(0, 8), mx, my - 4);
      }
    });

    // 绘制节点
    _graphNodes.forEach(function(n) {
      if (n.x === undefined) return;
      var color = typeColors[n.type] || defaultColor;
      var r = 6;

      // 节点圆
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // 标签
      ctx.fillStyle = '#1d1d1f';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      var label = n.id.length > 6 ? n.id.substring(0, 5) + '…' : n.id;
      ctx.fillText(label, n.x, n.y + r + 12);
    });
  }
}

function _highlightNode(name) {
  _graphNodes.forEach(function(n) {
    if (n.id === name) {
      // 高亮该节点
      n.fx = n.x;
      n.fy = n.y;
      setTimeout(function() { n.fx = null; n.fy = null; }, 2000);
    }
  });
  if (_graphSimulation) _graphSimulation.alpha(0.3).restart();
}

function _filterGraphType(type) {
  // 优先从缓存获取，避免每次过滤都重新请求 API
  var d = _graphCache;
  if (d) {
    _filterAndDraw(d, type);
  } else {
    api('/api/graph').then(function(resp) {
      _graphCache = resp;
      _filterAndDraw(resp, type);
    });
  }
}

function _filterAndDraw(d, type) {
  var nodes = d.nodes || {};
  var edges = d.edges || [];
  if (type) {
    var filtered = {};
    Object.entries(nodes).forEach(function(e) {
      if ((e[1] && e[1].type) === type) filtered[e[0]] = e[1];
    });
    nodes = filtered;
  }
  _drawD3Graph(Object.entries(nodes), edges);
}

function _showNodeDetail(node) {
  // 在面板中显示详情（使用 DOMPurify 二次防护）
  var panel = document.getElementById('graphEntities');
  var html = '<div style="padding:12px">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">';
  html += '<h4 style="font-size:14px;font-weight:600">' + esc(node.id) + '</h4>';
  html += '<button class="btn btn-sm btn-ghost graph-back-btn" style="font-size:11px">← 返回</button>';
  html += '</div>';
  html += '<div style="font-size:12px;color:var(--text3);margin-bottom:8px">类型: <strong>' + esc(node.type) + '</strong></div>';

  // 关联实体
  var neighbors = [];
  _graphEdges.forEach(function(e) {
    var sid = typeof e.source === 'object' ? e.source.id : e.source;
    var tid = typeof e.target === 'object' ? e.target.id : e.target;
    if (sid === node.id) neighbors.push({ name: tid, relation: e.relation, dir: '→' });
    if (tid === node.id) neighbors.push({ name: sid, relation: e.relation, dir: '←' });
  });

  if (neighbors.length) {
    html += '<div style="font-size:12px;font-weight:600;margin:12px 0 6px">关联实体 (' + neighbors.length + ')</div>';
    neighbors.forEach(function(n) {
      html += '<div style="padding:4px 0;font-size:12px;color:var(--text2);cursor:pointer" class="graph-neighbor" data-neighbor="' + esc(n.name) + '">';
      html += n.dir + ' ' + esc(n.name) + ' <span style="color:var(--text3)">(' + esc(n.relation) + ')</span>';
      html += '</div>';
    });
  }
  html += '</div>';
  // 二次清洗
  if (typeof DOMPurify !== 'undefined') html = DOMPurify.sanitize(html);
  panel.innerHTML = html;
  // 绑定节点详情内的返回按钮和邻居点击
  var backBtn = panel.querySelector('.graph-back-btn');
  if (backBtn) backBtn.addEventListener('click', function() { loadGraph(); });
  panel.querySelectorAll('.graph-neighbor[data-neighbor]').forEach(function(el) {
    el.addEventListener('click', function() {
      _highlightNode(this.dataset.neighbor);
    });
  });
}

function searchGraph() {
  var q = document.getElementById('graphSearch').value.trim();
  if (!q) { loadGraph(); return; }
  api('/api/graph?entity=' + encodeURIComponent(q)).then(function(d) {
    var nodes = d.nodes || {};
    var edges = d.edges || [];
    var entries = Object.entries(nodes);
    if (!entries.length) {
      document.getElementById('graphEntities').innerHTML = '<div style="padding:12px;text-align:center;color:var(--text3)">未找到相关实体</div>';
      _clearCanvas();
      return;
    }
    _drawD3Graph(entries, edges);
    // 重绘列表
    var html = '<div style="font-size:12px;color:var(--text3);margin-bottom:8px">搜索结果: ' + entries.length + ' 个实体</div>';
    entries.forEach(function(e) {
      html += '<div class="graph-entity" style="cursor:pointer;padding:8px 0;border-bottom:1px solid var(--border-light)" data-node="' + esc(e[0]) + '"><span style="font-weight:600">' + esc(e[0]) + '</span><span style="float:right;font-size:11px;color:var(--text3)">' + esc((e[1]&&e[1].type)||'') + '</span></div>';
    });
    document.getElementById('graphEntities').innerHTML = html;
    // 绑定搜索结果的实体点击事件
    document.getElementById('graphEntities').querySelectorAll('.graph-entity[data-node]').forEach(function(el) {
      el.addEventListener('click', function() {
        _highlightNode(this.dataset.node);
      });
    });
  }).catch(function(e) {
    toast('图谱搜索失败: ' + e.message, 'error');
  });
}
