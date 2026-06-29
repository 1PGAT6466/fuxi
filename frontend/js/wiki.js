// ===== Wiki =====
async function loadWikiTree(){
  try{
    const d=await api('/api/wiki/pages');
    const pages=d.pages||d||[];
    const tree=document.getElementById('wikiTree');
    if(!pages.length){
      tree.innerHTML='<div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div><div class="empty"><div class="empty-icon">📚</div><h3>暂无 Wiki 页面</h3><p>上传文档后系统会自动生成</p></div>';
      return;
    }
    tree.innerHTML='<div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div>'+pages.map(p=>`<div class="wiki-tree-item" data-id="${p.id||p.page_id||''}">${esc(p.title||'未命名')}</div>`).join('');
    tree.querySelectorAll('.wiki-tree-item').forEach(item=>{item.addEventListener('click',function(){loadWikiPage(this.dataset.id)})});
  }catch(e){
    var tree=document.getElementById('wikiTree');
    tree.innerHTML='<div style="font-size:13px;font-weight:600;margin-bottom:12px">📚 目录</div><div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(e.message)+'</p></div>';
  }
}
async function loadWikiPage(id){
  try{
    var c=document.getElementById('wikiContent');
    c.innerHTML='<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
    const d=await api('/api/wiki/page/'+id);
    let rendered=typeof marked!=='undefined'?marked.parse(d.content||''):esc(d.content||'');
    if(typeof DOMPurify!=='undefined')rendered=DOMPurify.sanitize(rendered);
    c.innerHTML=`<h1>${esc(d.title||'')}</h1><div>${rendered}</div>`;
    const active=document.querySelector('.wiki-tree-item.active');if(active)active.classList.remove('active');
    document.querySelectorAll('.wiki-tree-item').forEach(t=>{if(t.textContent===d.title)t.classList.add('active')});
  }catch(e){
    document.getElementById('wikiContent').innerHTML='<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(e.message)+'</p></div>';
  }
}
