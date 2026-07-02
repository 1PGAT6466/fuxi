// ===== 管理面板 =====
function _adminError(containerId, msg){
  document.getElementById(containerId).innerHTML='<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(msg||'未知错误')+'</p></div>';
}

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

async function loadOrgans(){
  var grid=document.getElementById('organGrid');
  grid.innerHTML='<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/v2/status');
    const bagua=(d.bagua||[]);
    const emojiMap={brain:'🧠',spleen:'🩸',heart:'🫀',kidney:'🫘',liver:'🛡️',nose:'👃',lung:'🫁',skin:'🧖'};
    const dutyMap={brain:'意识中心/决策调度',spleen:'数据存储入藏',heart:'路由调度中枢',kidney:'数据精炼过滤',liver:'质量过滤与免疫',nose:'异常监控告警',lung:'LLM生成蒸馏',skin:'前端UI/系统屏障/触角外探'};
    const baguaGrid=['xun','li','kun','zhen','zhonggong','dui','gen','kan','qian'];
    const items=baguaGrid.map(trigram=>{
      if(trigram==='zhonggong')return {trigram:'zhonggong',symbol:'⊕',organ_name:'中宫·消化',emoji:'🍽️',alive:true,status:'healthy',duty:'消化转化中枢'};
      const b=bagua.find(x=>x.trigram===trigram)||{};
      return {trigram,symbol:b.symbol||'?',organ_name:b.organ_name||trigram,emoji:emojiMap[b.organ_id]||'⚙️',alive:b.alive!==false,status:b.status||'unknown',duty:dutyMap[b.organ_id]||''};
    });
    grid.innerHTML='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">'+
      items.map(b=>{
        const sc=b.alive?'#34c759':'#ff3b30';
        const stText=b.alive?(b.status==='healthy'?'运行中':'忙碌中'):'离线';
        return '<div class="card" style="padding:14px;text-align:center"><div style="font-size:20px;margin-bottom:4px">'+b.symbol+'</div><div style="font-size:24px">'+b.emoji+'</div><div style="font-size:13px;font-weight:600;margin:4px 0">'+esc(b.organ_name)+'</div><div style="font-size:11px;color:var(--text3)">'+esc(b.duty)+'</div><div style="margin-top:6px"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+sc+'"></span><span style="font-size:10px;color:var(--text3);margin-left:4px">'+stText+'</span></div></div>'}).join('')+
      '</div>';
  }catch(e){_adminError('organGrid',e.message)}
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
  shaoyang: { name: '少阳·消化', emoji: '🌱', color: '#4caf50', organs: ['胃', '脾', '肺', '小肠'] },
  taiyang:  { name: '太阳·筑基', emoji: '☀️', color: '#ff9800', organs: ['肾', '肝', '鼻', '胆', '四肢', '骨骼'] },
  shaoyin:  { name: '少阴·炼化', emoji: '🌙', color: '#9c27b0', organs: ['大脑'] },
  taiyin:   { name: '太阴·显化', emoji: '🌑', color: '#2196f3', organs: ['皮肤', '三焦'] }
};

async function loadSymbols(){
  var grid = document.getElementById('symbolGrid');
  var stats = document.getElementById('symbolStats');
  grid.innerHTML = '<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';

  try {
    var symbols = {};
    try { symbols = (await api('/api/v2/status')).symbols || {}; } catch(e) {}

    // 四象卡片
    grid.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px">' +
      Object.entries(SYMBOLS).map(function([id, config]) {
        var s = symbols[id] || {};
        var alive = s.alive !== false;
        var status = s.status || 'idle';
        return '<div class="card" style="padding:20px;border-left:4px solid ' + config.color + '">' +
          '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">' +
          '<span style="font-size:28px">' + config.emoji + '</span>' +
          '<div><div style="font-size:16px;font-weight:600">' + config.name + '</div>' +
          '<div style="font-size:11px;color:var(--text3)">' + config.organs.join('·') + '</div></div></div>' +
          '<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">' +
          '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + (alive ? '#34c759' : '#ff3b30') + '"></span>' +
          '<span style="font-size:12px;color:var(--text3)">' + (alive ? (status === 'processing' ? '处理中' : '运行中') : '离线') + '</span></div>' +
          '</div>';
      }).join('') + '</div>';

    // 统计卡片
    stats.innerHTML =
      '<div class="stat"><div class="stat-icon" style="background:#e8f5e9">🌱</div><div><div class="stat-value">' + Object.keys(SYMBOLS).length + '</div><div class="stat-label">四象模块</div></div></div>' +
      '<div class="stat"><div class="stat-icon" style="background:#e3f2fd">🔗</div><div><div class="stat-value">' + Object.values(symbols).filter(function(s){return s.alive!==false}).length + '</div><div class="stat-label">运行中</div></div></div>';

  } catch(e) { _adminError('symbolGrid', e.message); }
}

// ===== 成长面板 =====
async function loadGrowth(){
  var stats = document.getElementById('growthStats');
  var trends = document.getElementById('growthTrends');
  stats.innerHTML = '<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';

  try {
    var overview = {};
    try { overview = await api('/api/growth/overview'); } catch(e) {}

    // 四象成长指标
    var symbols = [
      { id: 'shaoyang', name: '少阳·提取', metrics: overview.shaoyang || {} },
      { id: 'taiyang', name: '太阳·检索', metrics: overview.taiyang || {} },
      { id: 'shaoyin', name: '少阴·决策', metrics: overview.shaoyin || {} },
      { id: 'taiyin', name: '太阴·体验', metrics: overview.taiyin || {} }
    ];

    stats.innerHTML = symbols.map(function(s) {
      var metricHtml = Object.entries(s.metrics).slice(0, 3).map(function([k, v]) {
        var display = typeof v === 'number' ? (v < 1 ? Math.round(v * 100) + '%' : v.toFixed(1)) : String(v);
        return '<div style="text-align:center;padding:8px;background:var(--bg);border-radius:8px"><div style="font-size:18px;font-weight:600;color:var(--pri)">' + display + '</div><div style="font-size:10px;color:var(--text3);margin-top:4px">' + esc(k) + '</div></div>';
      }).join('');
      return '<div class="stat"><div class="stat-icon" style="background:#fff4ed">' + (SYMBOLS[s.id]||{}).emoji + '</div><div><div class="stat-value">' + (s.metrics.success_rate != null ? Math.round(s.metrics.success_rate * 100) + '%' : '—') + '</div><div class="stat-label">' + s.name + '</div></div></div>';
    }).join('');

    // 趋势图（使用Chart.js）
    if (overview.trend && overview.trend.length > 0) {
      trends.innerHTML = '<canvas id="growthChart" height="200"></canvas>';
      var ctx = document.getElementById('growthChart');
      if (ctx && typeof Chart !== 'undefined') {
        new Chart(ctx, {
          type: 'line',
          data: {
            labels: overview.trend.map(function(t) { return t.date; }),
            datasets: [{
              label: '查询次数',
              data: overview.trend.map(function(t) { return t.query_count; }),
              borderColor: '#FF6700',
              tension: 0.4
            }]
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
          }
        });
      }
    } else {
      trends.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text3)"><div style="font-size:32px;margin-bottom:8px">📈</div><p>成长趋势数据将在系统运行后自动积累</p></div>';
    }

  } catch(e) { _adminError('growthStats', e.message); }
}
