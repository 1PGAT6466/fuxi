async function loadServices() {
  var stats = document.getElementById('serviceStats');
  var grid = document.getElementById('serviceGrid');
  stats.innerHTML = '<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  grid.innerHTML = '';

  try {
    var list = await api('/api/services');
    if (!Array.isArray(list)) list = [];

    var running = list.filter(function(s) { return s.status === 'running'; }).length;
    var stopped = list.length - running;

    stats.innerHTML =
      '<div class="stat"><div class="stat-icon" style="background:#e3f2fd">🖥</div><div><div class="stat-value">' + list.length + '</div><div class="stat-label">服务总数</div></div></div>' +
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">✅</div><div><div class="stat-value">' + running + '</div><div class="stat-label">运行中</div></div></div>' +
      '<div class="stat"><div class="stat-icon" style="background:#fff4ed">⏸</div><div><div class="stat-value">' + stopped + '</div><div class="stat-label">已停止</div></div></div>';

    if (!list.length) {
      grid.innerHTML = '<div class="empty"><div class="empty-icon">⚙️</div><h3>暂无服务</h3><p>服务注册后将在此显示</p></div>';
      return;
    }

    grid.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px">' +
      list.map(function(s) { return renderServiceCard(s); }).join('') + '</div>';
  } catch(e) {
    _adminError('serviceStats', e.message);
  }
}

function renderServiceCard(s) {
  var isRunning = s.status === 'running';
  var statusColor = isRunning ? '#34c759' : '#ff3b30';
  var statusText = isRunning ? '运行中' : '已停止';
  var btnLabel = isRunning ? '停止' : '启动';
  var btnClass = isRunning ? 'btn-ghost' : 'btn-orange';
  var icon = '⚙️';
  var typeLabel = esc(s.service_type || '');
  var version = esc(s.version || '');

  return '<div class="card" style="padding:16px">' +
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">' +
    '<span style="font-size:28px">' + icon + '</span>' +
    '<div style="flex:1;min-width:0">' +
    '<div style="font-size:15px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(s.name || s.id) + '</div>' +
    '<div style="font-size:11px;color:var(--text3)">' + esc(s.id) + (version ? ' · v' + version : '') + '</div>' +
    '</div>' +
    '<div style="display:flex;align-items:center;gap:6px">' +
    '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + statusColor + '"></span>' +
    '<span style="font-size:12px;color:var(--text3)">' + statusText + '</span>' +
    '</div></div>' +
    (typeLabel ? '<div style="font-size:12px;color:var(--text2);margin-bottom:12px;padding:6px 10px;background:var(--bg);border-radius:6px">类型: ' + typeLabel + '</div>' : '') +
    '<div style="display:flex;gap:8px">' +
    '<button class="btn ' + btnClass + ' btn-sm" onclick="toggleService(\'' + esc(s.id) + '\',\'' + (isRunning ? 'stop' : 'start') + '\')">' + btnLabel + '</button>' +
    '<button class="btn btn-ghost btn-sm" onclick="showServiceDetail(\'' + esc(s.id) + '\')">详情</button>' +
    '</div></div>';
}

async function toggleService(serviceId, action) {
  try {
    var res = await api('/api/services/' + serviceId + '/' + action, { method: 'POST' });
    toast(action === 'start' ? '服务已启动' : '服务已停止', 'success');
    loadServices();
  } catch(e) {
    toast('操作失败: ' + e.message, 'error');
  }
}

async function showServiceDetail(serviceId) {
  try {
    var d = await api('/api/services/' + serviceId);
    var isRunning = d.status === 'running';
    var statusColor = isRunning ? '#34c759' : '#ff3b30';

    var html = '<div style="padding:8px 0;font-size:13px;color:var(--text2);line-height:2.2">' +
      '<div><strong style="color:var(--text)">服务ID:</strong> ' + esc(d.id) + '</div>' +
      '<div><strong style="color:var(--text)">名称:</strong> ' + esc(d.name) + '</div>' +
      '<div><strong style="color:var(--text)">版本:</strong> ' + esc(d.version || '—') + '</div>' +
      '<div><strong style="color:var(--text)">类型:</strong> ' + esc(d.service_type || '—') + '</div>' +
      '<div><strong style="color:var(--text)">状态:</strong> <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + statusColor + ';vertical-align:middle;margin-right:4px"></span>' + esc(d.status) + '</div>' +
      '<div><strong style="color:var(--text)">API前缀:</strong> ' + esc(d.api_prefix || '—') + '</div>' +
      '<div><strong style="color:var(--text)">描述:</strong> ' + esc(d.description || '暂无描述') + '</div>' +
      '<div><strong style="color:var(--text)">注册时间:</strong> ' + esc(d.registered_at || '—') + '</div>' +
      '<div><strong style="color:var(--text)">上次检查:</strong> ' + esc(d.last_health_check || '—') + '</div>' +
      (d.error_message ? '<div><strong style="color:var(--error)">错误:</strong> ' + esc(d.error_message) + '</div>' : '') +
      '</div>';

    if (d.capabilities && d.capabilities.length) {
      html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">' +
        '<div style="font-size:12px;color:var(--text3);margin-bottom:8px">能力列表</div>' +
        '<div style="display:flex;flex-wrap:wrap;gap:6px">' +
        d.capabilities.map(function(c) {
          return '<span style="font-size:12px;padding:4px 10px;border-radius:6px;background:rgba(255,103,0,0.06);color:var(--mi-orange)">' + esc(typeof c === 'string' ? c : c.name || JSON.stringify(c)) + '</span>';
        }).join('') + '</div></div>';
    }

    var modal = document.getElementById('serviceDetailModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'serviceDetailModal';
      modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:9000;background:rgba(0,0,0,0.4);backdrop-filter:blur(4px);align-items:center;justify-content:center';
      modal.onclick = function(e) { if (e.target === modal) modal.style.display = 'none'; };
      document.body.appendChild(modal);
    }
    modal.innerHTML = '<div class="card" style="width:440px;max-height:80vh;overflow-y:auto;padding:24px">' +
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">' +
      '<h3 style="font-size:16px;font-weight:600">服务详情</h3>' +
      '<button class="btn-icon" onclick="document.getElementById(\'serviceDetailModal\').style.display=\'none\'" style="font-size:18px;color:var(--text3)">&times;</button>' +
      '</div>' + html + '</div>';
    modal.style.display = 'flex';
    document.addEventListener('keydown', function _esc(e) {
      if (e.key === 'Escape') { modal.style.display = 'none'; document.removeEventListener('keydown', _esc); }
    });
  } catch(e) {
    toast('获取详情失败: ' + e.message, 'error');
  }
}
