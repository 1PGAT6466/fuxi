// ===== Wiki =====
async function loadWikiTree(){
  try{
    const d=await api('/api/wiki/pages');
    const pages=d.pages||d||[];
    const tree=document.getElementById('wikiTree');
    tree.innerHTML='<div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div>'+pages.map(p=>`<div class="wiki-tree-item" onclick="loadWikiPage('${p.id||p.page_id}')">${esc(p.title||'未命名')}</div>`).join('');
  }catch(e){}
}
async function loadWikiPage(id){
  try{
    const d=await api('/api/wiki/page/'+id);
    const c=document.getElementById('wikiContent');
    c.innerHTML=`<h1>${esc(d.title||'')}</h1><div>${typeof marked!=='undefined'?marked.parse(d.content||''):d.content||''}</div>`;
    const active=document.querySelector('.wiki-tree-item.active');if(active)active.classList.remove('active');
    document.querySelectorAll('.wiki-tree-item').forEach(t=>{if(t.textContent===d.title)t.classList.add('active')});
  }catch(e){}
}
