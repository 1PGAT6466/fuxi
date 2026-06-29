// ===== 文件管理 =====
async function loadFiles(){
  try{
    const d=await api('/api/documents');
    const files=d.files||d||[];
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
      document.getElementById('fileGrid').innerHTML=
        (cats.length>1?`<div style="margin-bottom:12px">${catBtns}</div>`:'')+
        '<div class="file-grid">'+
        filtered.map(f=>`<div class="file-card" onclick="window.open('/api/view/'+encodeURIComponent('${f.file_hash||''}'),'_blank')"><div class="file-icon">${fileIcon(f.file_name)}</div><div class="file-name">${esc(f.file_name||'?')}</div><div class="file-meta">${catLabel(f.category)||'未分类'}</div></div>`).join('')+
        '</div>'||'<div class="empty"><div class="empty-icon">📁</div><h3>暂无文件</h3><p>点击右上角上传</p></div>';
    };
    window._renderFiles('全部');
  }catch(e){}
}
async function uploadFiles(files){
  if(!files||!files.length)return;
  for(const f of files){
    const fd=new FormData();fd.append('file',f);
    try{
      toast('上传中: '+f.name,'info');
      const r2=await fetch('/api/upload',{method:'POST',headers:{'Authorization':'Bearer '+getToken()},body:fd}); if(!r2.ok)throw new Error('Upload failed: '+r2.status);
      toast('上传成功: '+f.name,'success');
    }catch(e){toast('上传失败: '+f.name,'error')}
  }
  loadFiles();
}
