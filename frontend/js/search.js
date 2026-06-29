// ===== 搜索 =====
async function doSearch(){
  const q=document.getElementById('searchInput').value.trim();if(!q)return;
  const c=document.getElementById('searchResults');c.innerHTML='<div class="empty"><p>搜索中...</p></div>';
  try{
    const d=await api('/api/search?q='+encodeURIComponent(q)+'&page_size=20');
    const wikiR=d.wiki_results||[],chunkR=d.chunk_results||[];
    const results=[...wikiR,...chunkR];
    // 显示图上下文提示
    const gc=d.graph_context||d.reflection;
    if(!results.length){c.innerHTML='<div class="empty"><div class="empty-icon">🔍</div><h3>未找到相关结果</h3><p>尝试换个关键词</p><div style="margin-top:16px">'+['组织权限','人事管理','知识管理','公文管理','流程引擎'].map(k=>`<span class="quick-q" onclick="document.getElementById('searchInput').value='${k}';doSearch()">${k}</span>`).join(' ')+'</div>';return}
    c.innerHTML=`<div class="result-list">${results.map((r,i)=>{
      const score=(r.score||r._weighted_score||0);
      const pct=Math.min(100,Math.round(score*5));
      const sourceTag=r._source||(r.file_name&&r.file_name.startsWith('[Wiki]')?'wiki':'doc');
      const tagColor=sourceTag==='wiki'?'#9c27b0':sourceTag==='table_view'?'#ff9800':'#2196f3';
      const tagLabel=sourceTag==='wiki'?'Wiki':sourceTag==='table_view'?'表格':'文档';
      const text=(r.text||'').substring(0,250);
      const fileName=(r.file_name||'未知文件').replace('泛微协同办公平台E-cology8.0版本','').replace(/-/g,' ');
      const keywords=q.split(/\s+/).filter(k=>k);
      let hl=esc(text);
      keywords.forEach(k=>{hl=hl.replace(new RegExp('('+k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi'),'<mark>$1</mark>')});
      return `<div class="result" onclick="this.querySelector('.result-text').style.maxHeight=this.querySelector('.result-text').style.maxHeight==='none'?'80px':'none'">
        <div class="result-title"><span style="background:${tagColor};color:#fff;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600">${tagLabel}</span> ${esc(fileName)}</div>
        <div class="result-text" style="max-height:80px;overflow:hidden;transition:max-height .3s">${hl}</div>
        <div class="result-meta">
          <span>相关性 ${pct}%</span><span style="flex:1"><span class="score-bar"><span class="score-fill" style="width:${pct}%"></span></span></span>
          <span>${r.chunk_index!=null?'#'+(r.chunk_index+1):''}</span>
        </div></div>`}).join('')}</div>`;
  }catch(e){c.innerHTML='<div class="empty"><p style="color:var(--error)">搜索失败</p></div>'}
}
