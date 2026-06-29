// ===== 图谱 =====
async function loadGraph(){
  var container=document.getElementById('graphEntities');
  container.innerHTML='<div style="text-align:center;padding:20px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/graph');
    const nodes=d.nodes||{};const edges=d.edges||[];
    const entries=Object.entries(nodes).slice(0,50);
    if(!entries.length){
      container.innerHTML='<div class="empty"><div class="empty-icon">🕸️</div><h3>知识图谱为空</h3><p>上传文档后系统会自动抽取实体和关系</p></div>';
      var canvas=document.getElementById('graphCanvas');
      var ctx=canvas.getContext('2d');
      canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;
      ctx.clearRect(0,0,canvas.width,canvas.height);
      return;
    }
    container.innerHTML=entries.map(([name,v])=>`<div class="graph-entity"><span style="font-weight:600">${esc(name)}</span><span style="float:right;font-size:11px;color:var(--text3)">${esc(v.type||'')}</span></div>`).join('');
    drawGraph(nodes,edges);
  }catch(e){
    container.innerHTML='<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(e.message)+'</p><button class="btn btn-ghost btn-sm" onclick="loadGraph()" style="margin-top:8px">重试</button></div>';
  }
}

function drawGraph(nodes,edges){
  const canvas=document.getElementById('graphCanvas');
  const ctx=canvas.getContext('2d');
  canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;
  const W=canvas.width,H=canvas.height;
  ctx.clearRect(0,0,W,H);
  const entries=Object.entries(nodes).slice(0,20);
  if(!entries.length)return;
  const nodePos={};
  const cols=Math.min(entries.length,5),rows=Math.ceil(entries.length/cols);
  const cellW=W/(cols+1),cellH=Math.min(H/(rows+1),90);
  entries.forEach(([name],i)=>{
    const col=i%cols,row=Math.floor(i/cols);
    const cx=cellW*(col+1),cy=cellH*(row+1);
    nodePos[name]={x:cx,y:cy};
    const w=Math.min(cellW*0.8,120),h=32;
    ctx.fillStyle='#fafafa';ctx.strokeStyle='#e5e5ea';ctx.lineWidth=1;
    ctx.beginPath();ctx.roundRect(cx-w/2,cy-h/2,w,h,8);ctx.fill();ctx.stroke();
    ctx.fillStyle='#1d1d1f';ctx.font='11px sans-serif';ctx.textAlign='center';
    const label=name.length>8?name.substring(0,7)+'…':name;
    ctx.fillText(label,cx,cy+4);
  });
  edges.forEach(e=>{
    const fromKey=e.from||e.source||'';
    const toKey=e.to||e.target||'';
    const s=fromKey?nodePos[fromKey]:null;
    const t=toKey?nodePos[toKey]:null;
    if(s&&t){
      const relation=e.relation||e.label||'';
      ctx.strokeStyle=relation==='co_occurs'?'rgba(255,103,0,.35)':'rgba(0,122,255,.2)';
      ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(s.x,s.y);ctx.lineTo(t.x,t.y);ctx.stroke();
    }
  });
}
function searchGraph(){
  const q=document.getElementById('graphSearch').value.trim();
  if(!q){loadGraph();return;}
  api('/api/graph?entity='+encodeURIComponent(q)).then(function(d){
    const nodes=d.nodes||{};const edges=d.edges||[];
    const container=document.getElementById('graphEntities');
    const entries=Object.entries(nodes).slice(0,50);
    if(!entries.length){
      container.innerHTML='<div style="padding:12px;text-align:center;color:var(--text3)">未找到相关实体</div>';
      return;
    }
    container.innerHTML=entries.map(([name,v])=>`<div class="graph-entity"><span style="font-weight:600">${esc(name)}</span><span style="float:right;font-size:11px;color:var(--text3)">${esc(v.type||'')}</span></div>`).join('');
    drawGraph(nodes,edges);
  }).catch(function(e){
    toast('图谱搜索失败: '+e.message,'error');
  });
}
