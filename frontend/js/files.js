// ===== 文件管理 =====

// 批量操作状态
window._batchSelected = new Set();

// CSV导出
function exportCSV() {
  const files = window._filesData;
  if (!files || !files.length) { toast('没有可导出的数据', 'error'); return; }
  const header = 'file_name,category,created_at\n';
  const rows = files.map(f => {
    const fn = (f.file_name || '').replace(/"/g, '""');
    const cat = (typeof f.category === 'object' ? (f.category.category || f.category.sub_cat || '') : (f.category || '')).replace(/"/g, '""');
    const dt = f.created_at || f.upload_time || '';
    return `"${fn}","${cat}","${dt}"`;
  }).join('\n');
  const blob = new Blob(['\uFEFF' + header + rows], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = '文件列表_' + new Date().toISOString().slice(0, 10) + '.csv';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('导出成功', 'success');
}

// 全选/取消全选
function toggleSelectAll() {
  const files = window._filesData || [];
  const activeCat = window._activeCat || '全部';
  const filtered = activeCat === '全部' ? files : files.filter(f => {
    const cl = typeof f.category === 'object' ? (f.category.category || f.category.sub_cat || '') : (f.category || '');
    return cl === activeCat;
  });
  if (window._batchSelected.size === filtered.length) {
    window._batchSelected.clear();
  } else {
    filtered.forEach(f => { if (f.file_hash) window._batchSelected.add(f.file_hash); });
  }
  if (window._renderFiles) window._renderFiles(activeCat);
}

// 切换单个选中
function toggleBatchSelect(hash) {
  if (window._batchSelected.has(hash)) { window._batchSelected.delete(hash); }
  else { window._batchSelected.add(hash); }
  if (window._renderFiles) window._renderFiles(window._activeCat || '全部');
}

// 批量删除
async function batchDelete() {
  const hashes = [...window._batchSelected];
  if (!hashes.length) { toast('请先选择文件', 'error'); return; }
  if (!confirm(`确认删除选中的 ${hashes.length} 个文件？`)) return;
  let ok = 0, fail = 0;
  for (const h of hashes) {
    try {
      const r = await fetch('/api/documents/' + h, { method: 'DELETE' });
      if (r.ok) ok++; else fail++;
    } catch (e) { fail++; }
  }
  window._batchSelected.clear();
  toast(`删除完成：成功 ${ok}，失败 ${fail}`, fail ? 'error' : 'success');
  loadFiles();
}

async function loadFiles() {
  var grid = document.getElementById('fileGrid');
  grid.innerHTML = '<div style="text-align:center;padding:40px"><div class="loading-dots">加载中<span>.</span><span>.</span><span>.</span></div></div>';
  try {
    const d = await api('/api/documents');
    const files = d.files || d || [];
    if (!files.length) {
      grid.innerHTML = '<div class="empty"><div class="empty-icon">📁</div><h3>暂无文件</h3><p>点击右上角上传文档开始构建知识库</p></div>';
      return;
    }
    const icons = { '.pdf': '📕', '.doc': '📘', '.docx': '📘', '.xls': '📊', '.xlsx': '📊', '.txt': '📝', '.md': '📜', '.csv': '📊' };
    function fileIcon(fn) { const ext = (fn || '').toLowerCase().match(/\.[a-z0-9]+$/); return ext ? icons[ext[0]] || '📄' : '📄' }
    function catLabel(c) { if (typeof c === 'object') return c.category || c.sub_cat || ''; return c || '' }
    const catSet = new Set(); files.forEach(f => { const cl = catLabel(f.category); if (cl) catSet.add(cl) });
    const cats = ['全部', ...[...catSet].sort()];
    let activeCat = '全部';
    window._filesData = files;
    window._renderFiles = function (cat) {
      activeCat = cat;
      window._activeCat = cat;
      let filtered = cat === '全部' ? files : files.filter(f => catLabel(f.category) === cat);
      if (window._fileFilter) filtered = filtered.filter(f => (f.file_name || '').toLowerCase().includes(window._fileFilter));
      const catBtns = cats.map(c => `<button class="btn btn-sm ${c === cat ? 'btn-primary' : 'btn-ghost'}" onclick="window._renderFiles('${c}')" style="margin:0 4px 4px 0">${c}</button>`).join('');
      if (!filtered.length) {
        grid.innerHTML = (cats.length > 1 ? `<div style="margin-bottom:12px">${catBtns}</div>` : '') + '<div class="empty"><div class="empty-icon">🔍</div><h3>没有匹配的文件</h3><p>换个搜索词试试</p></div>';
        return;
      }
      const allSelected = filtered.every(f => f.file_hash && window._batchSelected.has(f.file_hash));
      const batchBar = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">
        <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px;color:var(--text2)">
          <input type="checkbox" ${allSelected ? 'checked' : ''} onchange="toggleSelectAll()" style="cursor:pointer"> 全选
        </label>
        ${window._batchSelected.size ? `<button class="btn btn-sm btn-ghost" style="color:var(--error);font-size:12px" onclick="batchDelete()">🗑 批量删除 (${window._batchSelected.size})</button>` : ''}
        <button class="btn btn-sm btn-ghost" style="font-size:12px" onclick="exportCSV()">📊 导出CSV</button>
      </div>`;
      grid.innerHTML =
        (cats.length > 1 ? `<div style="margin-bottom:12px">${catBtns}</div>` : '') +
        batchBar +
        '<div class="file-grid">' +
        filtered.map(f => {
          var fh = f.file_hash || '';
          var fn = esc(f.file_name || '?');
          const checked = fh && window._batchSelected.has(fh) ? 'checked' : '';
          return '<div class="file-card" style="position:relative">' +
            (fh ? `<div style="position:absolute;top:8px;left:8px"><input type="checkbox" ${checked} onchange="toggleBatchSelect('${fh}')" style="cursor:pointer"></div>` : '') +
            '<div class="file-icon">' + fileIcon(f.file_name) + '</div><div class="file-name">' + fn + '</div><div class="file-meta">' + esc(catLabel(f.category) || '未分类') + '</div><div style="display:flex;gap:8px;margin-top:10px">' + (fh ? '<a href="/api/view/' + encodeURIComponent(fh) + '" target="_blank" class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px">👁 查看</a><a href="/api/download/' + encodeURIComponent(fh) + '" class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px">⬇ 下载</a>' : '') + '<button class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px;color:var(--error)" onclick="event.stopPropagation();if(confirm(\'确认删除 ' + fn.replace(/'/g, "\\'") + '？\')){fetch(\'/api/documents/' + fh + '\',{method:\'DELETE\'}).then(r=>r.json()).then(d=>{toast(\'已删除\',\'success\');loadFiles()}).catch(e=>toast(\'删除失败\',\'error\'))}">🗑 删除</button></div></div>'
        }).join('') +
        '</div>';
    };
    window._renderFiles('全部');

    // 拖拽上传（支持文件夹）
    grid.addEventListener('dragover', function (e) { e.preventDefault(); e.stopPropagation(); grid.style.border = '2px dashed var(--mi-orange)'; grid.style.background = 'rgba(255,103,0,0.03)'; });
    grid.addEventListener('dragleave', function (e) { e.preventDefault(); e.stopPropagation(); grid.style.border = ''; grid.style.background = ''; });
    grid.addEventListener('drop', function (e) {
      e.preventDefault(); e.stopPropagation();
      grid.style.border = ''; grid.style.background = '';
      var items = e.dataTransfer.items;
      if (items && items.length) {
        traverseDropItems(items).then(function(files) {
          if (files.length) uploadFiles(files);
        });
      } else if (e.dataTransfer.files.length) {
        uploadFiles(e.dataTransfer.files);
      }
    });
  } catch (e) {
    grid.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(e.message) + '</p><button class="btn btn-ghost btn-sm" onclick="loadFiles()" style="margin-top:8px">重试</button></div>';
  }
}

// 遍历拖拽的文件/文件夹
async function traverseDropItems(items) {
  var files = [];
  var entries = [];
  for (var i = 0; i < items.length; i++) {
    var entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
    if (entry) entries.push(entry);
  }
  for (var j = 0; j < entries.length; j++) {
    await traverseEntry(entries[j], files);
  }
  return files;
}

function traverseEntry(entry, files) {
  return new Promise(function(resolve) {
    if (entry.isFile) {
      entry.file(function(file) {
        file._fullPath = entry.fullPath;
        files.push(file);
        resolve();
      });
    } else if (entry.isDirectory) {
      var reader = entry.createReader();
      reader.readEntries(function(entries) {
        var promises = entries.map(function(e) { return traverseEntry(e, files); });
        Promise.all(promises).then(resolve);
      });
    } else {
      resolve();
    }
  });
}

async function uploadFiles(files) {
  if (!files || !files.length) return;
  var total = files.length;
  var success = 0;
  var failed = 0;
  toast('开始上传 ' + total + ' 个文件', 'info');
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var fd = new FormData();
    fd.append('file', f);
    if (f._fullPath) fd.append('relative_path', f._fullPath);
    try {
      var r2 = await fetch('/api/upload', { method: 'POST', headers: { 'Authorization': 'Bearer ' + getToken() }, body: fd });
      if (!r2.ok) throw new Error('Upload failed: ' + r2.status);
      success++;
    } catch (e) {
      failed++;
      toast('上传失败: ' + f.name + ': ' + e.message, 'error');
    }
  }
  if (failed === 0) {
    toast('上传完成: ' + success + ' 个文件', 'success');
  } else {
    toast('上传完成: ' + success + ' 成功, ' + failed + ' 失败', 'warning');
  }
  loadFiles();
}
