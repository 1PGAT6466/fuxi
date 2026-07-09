// ===== 管理面板 =====
// _adminError 已迁移到 utils.js 作为全局工具函数

async function loadOverview(){
  var s=document.getElementById('overviewStats');
  s.innerHTML='<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/admin/metrics-summary');
    s.innerHTML=
      '<div class="stat"><div class="stat-icon" style="background:#fff4ed">📄</div><div><div class="stat-value">'+(d.chunks||0)+'</div><div class="stat-label">文档块 Chunks</div></div></div>'+
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">⚡</div><div><div class="stat-value">'+(d.latency_p50_ms||0)+'ms</div><div class="stat-label">P50 延迟</div></div></div>'+
      '<div class="stat"><div class="stat-icon" style="background:#e3f2fd">✅</div><div><div class="stat-value">'+(d.error_rate!=null?Math.round((1-d.error_rate)*100)+'%':'99%')+'</div><div class="stat-label">可用率</div></div></div>'+
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">⏱</div><div><div class="stat-value">'+(d.uptime_hours||0).toFixed(1)+'h</div><div class="stat-label">运行时间</div></div></div>';
    const m=document.getElementById('overviewMetrics');
    m.innerHTML=
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'+
      '<div><h4 style="font-size:12px;color:var(--text3);margin-bottom:6px">延迟分布</h4>'+
      '<div style="display:flex;align-items:flex-end;gap:8px;height:80px">'+
      ['P50','P95','P99'].map((l,i)=>{const v=[d.latency_p50_ms||150,d.latency_p95_ms||450,d.latency_p99_ms||1200][i];const h=Math.min(80,v/15);return '<div style="flex:1;text-align:center"><div style="height:'+(80-h)+'px"></div><div style="background:var(--pri);height:'+h+'px;border-radius:4px 4px 0 0;opacity:'+(0.4+i*0.3)+'"></div><div style="font-size:10px;color:var(--text3);margin-top:4px">'+l+'<br>'+v+'ms</div></div>'}).join('')+
      '</div></div>'+
      '<div><h4 style="font-size:12px;color:var(--text3);margin-bottom:6px">运行信息</h4>'+
      '<div style="font-size:12px;color:var(--text2);line-height:2">'+
      '<div>⏱ 运行时间: '+(d.uptime_hours||0).toFixed(1)+' 小时</div>'+
      '<div>📊 文档块: '+(d.chunks||0)+'</div>'+
      '<div>🔍 缓存命中: '+(d.cache_hit_rate?Math.round(d.cache_hit_rate*100):'—')+'%</div>'+
      '</div></div></div>';
  }catch(e){_adminError('overviewStats',e.message)}
}

async function loadEval(){
  var s=document.getElementById('evalStats');
  s.innerHTML='<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/evaluation/overview');
    const ss=d.search_stats||{};
    const re=d.rag_eval||{};
    s.innerHTML=
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">🔍</div><div><div class="stat-value">'+(ss.total_searches||0)+'</div><div class="stat-label">检索次数</div></div></div>'+
      '<div class="stat"><div class="stat-icon" style="background:#fff3e0">📊</div><div><div class="stat-value">'+(ss.avg_results||0).toFixed(1)+'</div><div class="stat-label">平均结果数</div></div></div>'+
      '<div class="stat"><div class="stat-icon" style="background:#e3f2fd">⏱</div><div><div class="stat-value">'+(ss.avg_latency_ms||0).toFixed(0)+'</div><div class="stat-label">平均延迟 ms</div></div></div>'+
      '<div class="stat"><div class="stat-icon" style="background:#fce4ec">📋</div><div><div class="stat-value">'+(d.test_cases_count||0)+'</div><div class="stat-label">测试用例</div></div></div>';
    document.getElementById('evalDetail').innerHTML=
      '<div style="font-size:13px;color:var(--text2);line-height:2">'+
      '<div>📉 零结果率: '+((ss.zero_result_rate||0)*100).toFixed(1)+'%</div>'+
      '<div>📊 P50 延迟: '+(ss.p50_latency_ms||0)+'ms</div>'+
      '<div>🧪 RAGAS 评估: '+(re.available?'✅ 可用 ('+(re.test_cases||0)+' 用例)':'⚠️ '+esc(re.hint||'未配置'))+'</div>'+
      '<div style="color:var(--text3);font-size:11px;margin-top:8px">生成时间: '+esc(d.generated_at||'—')+'</div>'+
      '</div>';
  }catch(e){_adminError('evalStats',e.message)}
}

async function loadFlags(){
  var list=document.getElementById('flagsList');
  list.innerHTML='<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/feature-flags');
    const flags=d.flags||d.defaults||{};
    const names={'graphrag_multi_hop':'图多跳遍历','query_rewrite':'查询改写','wiki_search':'Wiki搜索','table_view':'表格视图','rag_answer':'RAG回答','use_reranker':'Reranker重排','session_memory':'对话记忆','auto_clean':'自动清洗','feedback_loop':'反馈闭环'};
    list.innerHTML=Object.entries(flags).map(([name,value])=>{
      const v=typeof value==='object'?value.value:value;
      const label=names[name]||name;
      return '<div class="flag-row"><span class="flag-name">'+esc(label)+'</span><span class="flag-desc">'+esc(name)+'</span><label class="toggle"><input type="checkbox" '+(v?'checked':'')+' onchange="toggleFlag(\''+esc(name)+'\',this.checked)"><span class="slider"></span></label></div>';
    }).join('');
  }catch(e){_adminError('flagsList',e.message)}
}

async function toggleFlag(name,value){
  try{
    await api('/api/feature-flags/'+name,{method:'PUT',body:{value}});
    toast(name+' = '+value,'success');
  }catch(e){toast('切换失败: '+e.message,'error')}
}

async function loadFeedback(){
  var list=document.getElementById('feedbackList');
  list.innerHTML='<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/feedback/weekly');
    const items=Array.isArray(d)?d:(d.feedbacks||d.items||d.feedback_list||[]);
    if(!Array.isArray(items)||!items.length){
      list.innerHTML='<div class="empty"><div class="empty-icon">💬</div><h3>暂无反馈</h3><p>'+esc(d.message||'用户反馈将在这里展示')+'</p></div>';
      return;
    }
    list.innerHTML='<table class="data"><thead><tr><th>时间</th><th>查询</th><th>评分</th><th>反馈</th></tr></thead><tbody>'+
      items.slice(0,20).map(f=>'<tr><td style="white-space:nowrap">'+esc((f.timestamp||f.time||f.created_at||'').substring(0,16))+'</td><td>'+esc((f.query||f.question||f.text||'').substring(0,40))+'</td><td>'+esc(String(f.rating||f.score||'—'))+'</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">'+esc((f.feedback||f.comment||f.content||'').substring(0,60))+'</td></tr>').join('')+
      '</tbody></table>';
  }catch(e){_adminError('feedbackList',e.message)}
}

// ===== 四象状态 =====
var SYMBOLS = {
  shaoyang: { name: '少阳·消化', emoji: '🌱', color: '#4caf50', organs: ['stomach', 'spleen', 'lung', 'small_intestine'] },
  taiyang:  { name: '太阳·筑基', emoji: '☀️', color: '#ff9800', organs: ['kidney', 'liver', 'nose', 'gallbladder', 'limbs', 'skeleton'] },
  shaoyin:  { name: '少阴·炼化', emoji: '🌙', color: '#9c27b0', organs: ['brain'] },
  taiyin:   { name: '太阴·显化', emoji: '🌑', color: '#2196f3', organs: ['skin', 'sanjiao'] }
};

async function loadSymbols(){
  var grid = document.getElementById('symbolGrid');
  var stats = document.getElementById('symbolStats');
  grid.innerHTML = '<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';

  try {
    var result = {};
    try { result = await api('/api/symbols/status'); } catch(e) {}
    var symbols = result.symbols || {};
    var organs = result.organs || {};

    // 四象卡片（包含器官）
    grid.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px">' +
      Object.entries(SYMBOLS).map(function([id, config]) {
        var s = symbols[id] || {};
        var alive = s.alive !== false;
        var status = s.status || 'idle';
        var symbolOrgans = config.organs.map(function(organId) {
          var organ = organs[organId] || {};
          var organAlive = organ.alive !== false;
          return '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;background:var(--bg);border-radius:6px;font-size:11px">' +
            '<span style="font-size:14px">' + (organ.emoji || '⚙️') + '</span>' +
            '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(organ.name || organId) + '</span>' +
            '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:' + (organAlive ? '#34c759' : '#ff3b30') + '"></span>' +
            '</div>';
        }).join('');

        return '<div class="card" style="padding:16px;border-left:4px solid ' + config.color + '">' +
          '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">' +
          '<span style="font-size:28px">' + config.emoji + '</span>' +
          '<div><div style="font-size:16px;font-weight:600">' + config.name + '</div></div>' +
          '<div style="margin-left:auto;display:flex;align-items:center;gap:6px">' +
          '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + (alive ? '#34c759' : '#ff3b30') + '"></span>' +
          '<span style="font-size:12px;color:var(--text3)">' + (alive ? '运行中' : '离线') + '</span></div></div>' +
          '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px">' + symbolOrgans + '</div>' +
          '</div>';
      }).join('') + '</div>';

    // 统计卡片
    var aliveOrgans = Object.values(organs).filter(function(o){return o.alive!==false}).length;
    var totalOrgans = Object.keys(organs).length;
    stats.innerHTML =
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">🌱</div><div><div class="stat-value">' + Object.keys(SYMBOLS).length + '</div><div class="stat-label">四象系统</div></div></div>' +
      '<div class="stat"><div class="stat-icon" style="background:#e3f2fd">🫀</div><div><div class="stat-value">' + totalOrgans + '</div><div class="stat-label">器官总数</div></div></div>' +
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">✅</div><div><div class="stat-value">' + aliveOrgans + '</div><div class="stat-label">运行中</div></div></div>';

  } catch(e) { _adminError('symbolGrid', e.message); }
}

// ===== 成长面板（完整版）=====
async function loadGrowth(){
  var stats = document.getElementById('growthStats');
  var trends = document.getElementById('growthTrends');
  stats.innerHTML = '<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';

  try {
    var overview = {};
    try { overview = await api('/api/growth/overview'); } catch(e) {}

    // 四象成长指标卡片
    var symbolConfigs = [
      { id: 'shaoyang', name: '少阳·提取', color: '#4caf50', metrics: ['extraction_success_rate', 'entity_coverage', 'extraction_latency_p95'], desc: '文档→碎片+事件+实体' },
      { id: 'taiyang', name: '太阳·检索', color: '#ff9800', metrics: ['recall_at_10', 'cache_hit_rate', 'search_latency_p95'], desc: '查询→精排结果' },
      { id: 'shaoyin', name: '少阴·决策', color: '#9c27b0', metrics: ['confidence_avg', 'retry_rate', 'hallucination_rate'], desc: '问题→答案' },
      { id: 'taiyin', name: '太阴·体验', color: '#2196f3', metrics: ['request_count', 'error_rate', 'p95_latency'], desc: '一个入口，一个出口' }
    ];

    var symbolData = overview.symbols || {};
    var totalEvents = overview.total_events || 0;
    var phase = overview.phase || 'Phase 1';

    // 总览卡片
    var summaryHtml = '<div class="card" style="padding:16px;margin-bottom:16px;background:linear-gradient(135deg,#FF6700 0%,#ff9800 100%);color:#fff">' +
      '<div style="display:flex;justify-content:space-between;align-items:center">' +
      '<div><div style="font-size:14px;opacity:0.9">成长引擎</div><div style="font-size:24px;font-weight:700">' + phase + '</div></div>' +
      '<div style="text-align:right"><div style="font-size:14px;opacity:0.9">总事件数</div><div style="font-size:24px;font-weight:700">' + totalEvents + '</div></div>' +
      '</div></div>';

    // 四象卡片
    var cardsHtml = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px">' +
      symbolConfigs.map(function(config) {
        var data = symbolData[config.id] || {};
        var metrics = data.metrics || {};
        var eventCount = data.event_count || 0;

        var metricHtml = config.metrics.map(function(key) {
          var val = metrics[key];
          var display = val != null ? (typeof val === 'number' ? (val < 1 ? Math.round(val * 100) + '%' : val.toFixed(1)) : String(val)) : '—';
          var label = {extraction_success_rate:'提取成功率',entity_coverage:'实体覆盖率',extraction_latency_p95:'提取延迟P95',recall_at_10:'Recall@10',cache_hit_rate:'缓存命中率',search_latency_p95:'检索延迟P95',confidence_avg:'平均置信度',retry_rate:'重试率',hallucination_rate:'幻觉拦截率',request_count:'请求次数',error_rate:'错误率',p95_latency:'P95延迟'}[key] || key;
          var color = val != null ? (val < 0.3 ? '#ff3b30' : val < 0.7 ? '#ff9500' : '#34c759') : 'var(--text3)';
          return '<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">' +
            '<span style="font-size:12px;color:var(--text3)">' + label + '</span>' +
            '<span style="font-size:14px;font-weight:600;color:' + color + '">' + display + '</span></div>';
        }).join('');

        // sparkline 占位
        var sparkline = '<div style="height:40px;margin-top:8px;background:var(--bg);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:10px;color:var(--text3)">╱╲╱╲ 趋势</div>';

        return '<div class="card" style="padding:16px;border-top:3px solid ' + config.color + '">' +
          '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">' +
          '<span style="font-size:28px">' + (SYMBOLS[config.id]||{}).emoji + '</span>' +
          '<div><div style="font-size:16px;font-weight:600">' + config.name + '</div>' +
          '<div style="font-size:11px;color:var(--text3)">' + config.desc + '</div></div>' +
          '<div style="margin-left:auto;text-align:right"><div style="font-size:20px;font-weight:700;color:' + config.color + '">' + eventCount + '</div><div style="font-size:10px;color:var(--text3)">事件</div></div></div>' +
          metricHtml + sparkline + '</div>';
      }).join('') + '</div>';

    stats.innerHTML = summaryHtml + cardsHtml;

    // 趋势图
    if (overview.trend && overview.trend.length > 0) {
      trends.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
        '<canvas id="growthChartQuery" height="200"></canvas>' +
        '<canvas id="growthChartLatency" height="200"></canvas>' +
        '<canvas id="growthChartConfidence" height="200"></canvas>' +
        '<canvas id="growthChartEvents" height="200"></canvas></div>';

      if (typeof Chart !== 'undefined') {
        var labels = overview.trend.map(function(t) { return t.date; });

        // 查询趋势
        var ctxQ = document.getElementById('growthChartQuery');
        if (ctxQ) new Chart(ctxQ, { type: 'line', data: { labels: labels, datasets: [{ label: '查询次数', data: overview.trend.map(function(t) { return t.query_count; }), borderColor: '#FF6700', tension: 0.4, fill: true, backgroundColor: 'rgba(255,103,0,0.1)' }] }, options: { responsive: true, plugins: { title: { display: true, text: '查询趋势' } }, scales: { y: { beginAtZero: true } } } });

        // 延迟趋势
        var ctxL = document.getElementById('growthChartLatency');
        if (ctxL) new Chart(ctxL, { type: 'line', data: { labels: labels, datasets: [{ label: '平均延迟(ms)', data: overview.trend.map(function(t) { return t.avg_latency_ms || 0; }), borderColor: '#2196f3', tension: 0.4, fill: true, backgroundColor: 'rgba(33,150,243,0.1)' }] }, options: { responsive: true, plugins: { title: { display: true, text: '延迟趋势' } }, scales: { y: { beginAtZero: true } } } });

        // 置信度趋势
        var ctxC = document.getElementById('growthChartConfidence');
        if (ctxC) new Chart(ctxC, { type: 'line', data: { labels: labels, datasets: [{ label: '平均置信度', data: overview.trend.map(function(t) { return t.avg_confidence || 0; }), borderColor: '#4caf50', tension: 0.4, fill: true, backgroundColor: 'rgba(76,175,80,0.1)' }] }, options: { responsive: true, plugins: { title: { display: true, text: '置信度趋势' } }, scales: { y: { beginAtZero: true, max: 1 } } } });

        // 事件趋势
        var ctxE = document.getElementById('growthChartEvents');
        if (ctxE) new Chart(ctxE, { type: 'bar', data: { labels: labels, datasets: [{ label: '事件数', data: overview.trend.map(function(t) { return t.event_count || 0; }), backgroundColor: 'rgba(255,103,0,0.6)' }] }, options: { responsive: true, plugins: { title: { display: true, text: '事件趋势' } }, scales: { y: { beginAtZero: true } } } });
      }
    } else {
      trends.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text3)"><div style="font-size:32px;margin-bottom:8px">📈</div><p>成长趋势数据将在系统运行后自动积累</p><p style="font-size:12px;margin-top:8px">系统运行后，每100次查询自动记录一次成长指标</p></div>';
    }

  } catch(e) { _adminError('growthStats', e.message); }
}
