// ===== 文件管理 =====
async function loadFiles(){
  var grid=document.getElementById('fileGrid');
  grid.innerHTML='<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try{
    const d=await api('/api/documents');
    const files=d.files||d||[];
    if(!files.length){
      grid.innerHTML='<div class="empty"><div class="empty-icon">📁</div><h3>暂无文件</h3><p>点击右上角上传文档开始构建知识库</p></div>';
      return;
    }
    const icons={'.pdf':'📕','.doc':'📘','.docx':'📘','.xls':'📊','.xlsx':'📊','.txt':'📝','.md':'📜','.csv':'📊'};
    function fileIcon(fn){const ext=(fn||'').toLowerCase().match(/\.[a-z0-9]+$/);return ext?icons[ext[0]]||'📄':'📄'}
    function catLabel(c){if(typeof c==='object')return c.category||c.sub_cat||'';return c||''}
    const catSet=new Set();files.forEach(f=>{const cl=catLabel(f.category);if(cl)catSet.add(cl)});
    const cats=['全部',...[...catSet].sort()];
    let activeCat='全部';
    window._filesData=files;
    window._renderFiles=function(cat){
      activeCat=cat;
      window._activeCat=cat;let filtered=cat==='全部'?files:files.filter(f=>catLabel(f.category)===cat);if(window._fileFilter)filtered=filtered.filter(f=>(f.file_name||'').toLowerCase().includes(window._fileFilter));
      const catBtns=cats.map(c=>`<button class="btn btn-sm ${c===cat?'btn-primary':'btn-ghost'}" onclick="window._renderFiles('${c}')" style="margin:0 4px 4px 0">${c}</button>`).join('');
      if(!filtered.length){
        grid.innerHTML=(cats.length>1?`<div style="margin-bottom:12px">${catBtns}</div>`:'')+'<div class="empty"><div class="empty-icon">🔍</div><h3>没有匹配的文件</h3><p>换个搜索词试试</p></div>';
        return;
      }
      grid.innerHTML=
        (cats.length>1?`<div style="margin-bottom:12px">${catBtns}</div>`:'')+
        '<div class="file-grid">'+
        filtered.map(f=>{
        var fh=f.file_hash||'';
        var fn=esc(f.file_name||'?');
        return '<div class="file-card" style="position:relative"><div class="file-icon">'+fileIcon(f.file_name)+'</div><div class="file-name">'+fn+'</div><div class="file-meta">'+esc(catLabel(f.category)||'未分类')+'</div><div style="display:flex;gap:8px;margin-top:10px">'+(fh?'<a href="/api/view/'+encodeURIComponent(fh)+'" target="_blank" class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px">👁 查看</a><a href="/api/download/'+encodeURIComponent(fh)+'" class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px">⬇ 下载</a>':'')+'<button class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px;color:var(--error)" onclick="event.stopPropagation();if(confirm(\'确认删除 '+fn.replace(/'/g,"\\'")+'？\')){fetch(\'/api/documents/'+fh+'\',{method:\'DELETE\'}).then(r=>r.json()).then(d=>{toast(\'已删除\',\'success\');loadFiles()}).catch(e=>toast(\'删除失败\',\'error\'))}">🗑 删除</button></div></div>'}).join('')+
        '</div>';
    };
    window._renderFiles('全部');
  }catch(e){
    grid.innerHTML='<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>'+esc(e.message)+'</p><button class="btn btn-ghost btn-sm" onclick="loadFiles()" style="margin-top:8px">重试</button></div>';
  }
}
async function uploadFiles(files){
  if(!files||!files.length)return;
  for(const f of files){
    const fd=new FormData();fd.append('file',f);
    try{
      toast('上传中: '+f.name,'info');
      const r2=await fetch('/api/upload',{method:'POST',headers:{'Authorization':'Bearer '+getToken()},body:fd}); if(!r2.ok)throw new Error('Upload failed: '+r2.status);
      toast('上传成功: '+f.name,'success');
    }catch(e){toast('上传失败: '+f.name+': '+e.message,'error')}
  }
  loadFiles();
}
