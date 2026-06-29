// ===== 图谱 =====
async function loadGraph(){
  try{
    const d=await api('/api/graph');
    const nodes=d.nodes||{};const edges=d.edges||[];
    const container=document.getElementById('graphEntities');
    const entries=Object.entries(nodes).slice(0,50);
    container.innerHTML=entries.map(([name,v])=>`<div class="graph-entity"><span style="font-weight:600">${esc(name)}</span><span style="float:right;font-size:11px;color:var(--text3)">${v.type||''}</span></div>`).join('');
    drawGraph(nodes,edges);
  }catch(e){document.getElementById('graphEntities').innerHTML='<p style="color:var(--text3)">加载失败</p>'}
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
  // 自适应九宫布局（最多 20 节点 → 5列 × 4行）
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
  // 边：支持 from/to 和 source/target 两种格式
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
  if(q)api('/api/graph?entity='+encodeURIComponent(q)).then(loadGraph).catch(()=>{});
}
