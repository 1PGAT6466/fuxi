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
    // P1-15: 统一时间字段，兼容多种后端返回格式
    const dt = f.created_at || f.upload_time || f.uploaded_at || f.created || f.date || '未知';
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

// P0-3 + R2 fix: 单个文件删除 — 使用统一 api() 封装
async function deleteFile(hash) {
  if (!hash) return;
  if (!confirm('确认删除该文件？')) return;
  try {
    await api('/api/documents/' + hash, { method: 'DELETE' });
    invalidateCache('/api/documents'); toast('已删除', 'success'); loadFiles();
  } catch (e) { toast('删除失败: ' + (e.message || ''), 'error'); }
}

// P0-3 + R2 fix: 批量删除 — 使用统一 api() 封装
async function batchDelete() {
  const hashes = [...window._batchSelected];
  if (!hashes.length) { toast('请先选择文件', 'error'); return; }
  if (!confirm('确认删除选中的 ' + hashes.length + ' 个文件？')) return;
  let ok = 0, fail = 0;
  for (const h of hashes) {
    try {
      await api('/api/documents/' + h, { method: 'DELETE' });
      ok++;
    } catch (e) { fail++; }
  }
  window._batchSelected.clear();
  invalidateCache('/api/documents');
  toast('删除完成：成功 ' + ok + '，失败 ' + fail, fail ? 'error' : 'success');
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

    // P0-6 fix: store reference to stable file data and avoid stale closure references
    window._filesData = files;
    var _cats = cats;  // capture locally but accessible via closure
    // R4: 文件列表分页
    var _FILE_PAGE_SIZE = 20;
    window._filePageOffset = 0;

    window._renderFiles = function (cat, append) {
      if (!append) window._filePageOffset = 0;
      var activeCat = cat;
      window._activeCat = cat;
      // P0-6 fix: always read from window._filesData to avoid stale closure
      var fileList = window._filesData || files;
      var fileFilterVal = window._fileFilter;

      var filtered = cat === '全部' ? fileList : fileList.filter(function(f) { return catLabel(f.category) === cat; });
      if (fileFilterVal) filtered = filtered.filter(function(f) { return (f.file_name || '').toLowerCase().includes(fileFilterVal); });

      var catBtns = _cats.map(function(c) {
        return '<button class="btn btn-sm ' + (c === activeCat ? 'btn-primary' : 'btn-ghost') + '" data-cat="' + esc(c) + '" onclick="window._renderFiles(this.dataset.cat)" style="margin:0 4px 4px 0">' + esc(c) + '</button>';
      }).join('');

      if (!filtered.length) {
        grid.innerHTML = (_cats.length > 1 ? '<div style="margin-bottom:12px">' + catBtns + '</div>' : '') + '<div class="empty"><div class="empty-icon">🔍</div><h3>没有匹配的文件</h3><p>换个搜索词试试</p></div>';
        return;
      }
      var allSelected = filtered.every(function(f) { return f.file_hash && window._batchSelected.has(f.file_hash); });
      var batchBar = '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">' +
        '<label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px;color:var(--text2)">' +
        '<input type="checkbox" ' + (allSelected ? 'checked' : '') + ' onchange="toggleSelectAll()" style="cursor:pointer"> 全选' +
        '</label>' +
        (window._batchSelected.size ? '<button class="btn btn-sm btn-ghost" style="color:var(--error);font-size:12px" onclick="batchDelete()">🗑 批量删除 (' + window._batchSelected.size + ')</button>' : '') +
        '<button class="btn btn-sm btn-ghost" style="font-size:12px" onclick="exportCSV()">📊 导出CSV</button>' +
        '</div>';

      // R4: 分页渲染
      var showFiles = filtered.slice(0, window._filePageOffset + _FILE_PAGE_SIZE);
      var hasMore = showFiles.length < filtered.length;

      grid.innerHTML =
        (_cats.length > 1 ? '<div style="margin-bottom:12px">' + catBtns + '</div>' : '') +
        batchBar +
        '<div class="file-grid">' +
        showFiles.map(function(f) {
          var fh = f.file_hash || '';
          var fn = esc(f.file_name || '?');
          var checked = fh && window._batchSelected.has(fh) ? 'checked' : '';
          return '<div class="file-card" style="position:relative">' +
            (fh ? '<div style="position:absolute;top:8px;left:8px"><input type="checkbox" ' + checked + ' data-file-hash="' + esc(fh) + '" class="batch-checkbox" style="cursor:pointer"></div>' : '') +
            '<div class="file-icon">' + fileIcon(f.file_name) + '</div><div class="file-name">' + fn + '</div><div class="file-meta">' + esc(catLabel(f.category) || '未分类') + '</div><div style="display:flex;gap:8px;margin-top:10px">' +
            (fh ? '<a href="/api/view/' + encodeURIComponent(fh) + '" target="_blank" class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px">👁 查看</a><a href="/api/download/' + encodeURIComponent(fh) + '" class="btn btn-sm btn-ghost" style="font-size:11px;padding:4px 8px">⬇ 下载</a>' : '') +
            '<button class="btn btn-sm btn-ghost file-delete-btn" data-file-hash="' + esc(fh) + '" style="font-size:11px;padding:4px 8px;color:var(--error)">🗑 删除</button></div></div>';
        }).join('') +
        '</div>' +
        (hasMore ? '<div style="text-align:center;padding:16px 0"><button class="btn btn-ghost btn-sm" onclick="window._filePageOffset+=' + _FILE_PAGE_SIZE + ';window._renderFiles(window._activeCat, true)">加载更多 (' + filtered.length + ' 个文件，已显示 ' + showFiles.length + ')</button></div>' : '');
    };
    window._renderFiles('全部');

    // R2 fix: 事件委托 — data 属性替代内联 onclick，避免 XSS 注入
    grid.addEventListener('click', function(e) {
      // 删除按钮
      var delBtn = e.target.closest('.file-delete-btn');
      if (delBtn) {
        e.stopPropagation();
        var hash = delBtn.getAttribute('data-file-hash');
        if (hash) deleteFile(hash);
        return;
      }
    });
    grid.addEventListener('change', function(e) {
      // 批量选择 checkbox
      if (e.target.classList.contains('batch-checkbox')) {
        var hash = e.target.getAttribute('data-file-hash');
        if (hash) toggleBatchSelect(hash);
      }
    });

    // 拖拽上传（支持文件夹）
    grid.addEventListener('dragover', function (e) { e.preventDefault(); e.stopPropagation(); grid.style.border = '2px dashed var(--mi-orange)'; grid.style.background = 'rgba(255,103,0,0.03)'; });
    grid.addEventListener('dragleave', function (e) { e.preventDefault(); e.stopPropagation(); grid.style.border = ''; grid.style.background = ''; });
    grid.addEventListener('drop', function (e) {
      e.preventDefault(); e.stopPropagation();
      grid.style.border = ''; grid.style.background = '';
      var items = e.dataTransfer.items;
      if (items && items.length) {
        // P2-6 fix: 检测 webkitGetAsEntry API，Firefox 回退到普通文件
        if (!items[0].webkitGetAsEntry) {
          // Firefox 等不支持 webkitGetAsEntry，直接用文件列表
          if (e.dataTransfer.files.length) {
            toast('当前浏览器不支持文件夹上传，仅处理文件', 'info');
            uploadFiles(e.dataTransfer.files);
          }
        } else {
          traverseDropItems(items).then(function(files) {
            if (files.length) uploadFiles(files);
          });
        }
      } else if (e.dataTransfer.files.length) {
        uploadFiles(e.dataTransfer.files);
      }
    });
  } catch (e) {
    grid.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(e.message) + '</p><button class="btn btn-ghost btn-sm" onclick="loadFiles()" style="margin-top:8px">重试</button></div>';
  }
}

// 遍历拖拽的文件/文件夹
// P1-12: webkitGetAsEntry 是 Chrome-specific API，Firefox 中不可用，回退到普通文件列表
async function traverseDropItems(items) {
  var files = [];
  var entries = [];
  var hasEntryApi = false;
  for (var i = 0; i < items.length; i++) {
    if (items[i].webkitGetAsEntry) {
      var entry = items[i].webkitGetAsEntry();
      if (entry) { entries.push(entry); hasEntryApi = true; }
    }
  }
  // Firefox fallback: 如果 webkitGetAsEntry 不可用，直接使用 e.dataTransfer.files
  if (!hasEntryApi) return [];
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

  // CRITICAL-6 fix: 前端文件类型/大小校验
  var validation = validateFiles(files);
  if (validation.errors.length) {
    var errMsg = validation.errors.slice(0, 3).join('; ');
    if (validation.errors.length > 3) errMsg += '; ...共 ' + validation.errors.length + ' 个错误';
    toast('文件校验失败: ' + errMsg, 'error');
  }
  if (!validation.valid.length) return;

  var validFiles = validation.valid;
  var total = validFiles.length;
  var success = 0;
  var failed = 0;
  toast('开始上传 ' + total + ' 个文件', 'info');
  for (var i = 0; i < validFiles.length; i++) {
    var f = validFiles[i];
    var fd = new FormData();
    // CRITICAL-7 fix: 文件名清洗后上传
    var safeName = sanitizeFilename(f.name);
    var cleanedFile = f;
    if (safeName !== f.name) {
      try {
        cleanedFile = new File([f], safeName, { type: f.type, lastModified: f.lastModified });
      } catch(e) {
        // 某些环境不支持 File 构造函数，使用原始文件（后端会再次校验）
      }
    }
    fd.append('file', cleanedFile);
    if (f._fullPath) fd.append('relative_path', f._fullPath);
    try {
      var r2 = await api('/api/upload', { method: 'POST', body: fd });
      if (!r2 || r2.error) throw new Error('Upload failed');
      success++;
    } catch (e) {
      failed++;
      toast('上传失败: ' + safeName + ': ' + e.message, 'error');
    }
  }
  if (failed === 0) {
    invalidateCache('/api/documents');
    toast('上传完成: ' + success + ' 个文件', 'success');
  } else {
    invalidateCache('/api/documents');
    toast('上传完成: ' + success + ' 成功, ' + failed + ' 失败', 'warning');
  }
  loadFiles();
}
