/**
 * @fileoverview 通用工具函数 - 小米风格
 * @module utils
 */

// P3-R2 fix: 安全数值转换，防止 NaN/非数字值导致 toFixed 崩溃
function safeNum(val, def) {
  if (def === undefined) def = 0;
  var n = Number(val);
  return isNaN(n) || !isFinite(n) ? def : n;
}

// HTML 转义（防 XSS）
function esc(s) {
  if (!s) return '';
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(String(s)));
  return div.innerHTML;
}

// ===== CRITICAL-5: 搜索高亮安全转义 =====
// 对用户输入的正则特殊字符进行转义，防止正则注入
function escapeRegex(str) {
  if (!str) return '';
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ===== CRITICAL-7: 恶意文件名清洗 =====
// 移除路径遍历、控制字符、Unicode bidi 控制字符
function sanitizeFilename(name) {
  if (!name) return 'unnamed';
  var cleaned = String(name)
    // 移除 null 字节
    .replace(/\x00/g, '')
    // 移除 Unicode bidi 控制字符 (U+200E, U+200F, U+202A-U+202E, U+2066-U+2069)
    .replace(/[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g, '')
    // 移除零宽字符
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    // 移除路径分隔符
    .replace(/[\/\\:*?"<>|]/g, '_')
    // 移除控制字符（保留常见空白）
    .replace(/[\x00-\x1F\x7F]/g, '')
    // 移除连续点号（防路径遍历 ../ 变种）
    .replace(/\.{2,}/g, '_')
    // 移除开头/结尾的空白和点号
    .replace(/^[.\s]+/, '')
    .replace(/[.\s]+$/, '')
    .trim();
  // 长度限制
  if (cleaned.length > 200) {
    var ext = cleaned.lastIndexOf('.');
    if (ext > 0 && ext < cleaned.length - 1) {
      var extPart = cleaned.substring(ext);
      var namePart = cleaned.substring(0, Math.min(ext, 190));
      cleaned = namePart.replace(/[.\s]+$/, '') + extPart;
    } else {
      cleaned = cleaned.substring(0, 200);
    }
  }
  return cleaned || 'unnamed';
}

// ===== CRITICAL-6: 文件上传前端校验 =====
// 允许的文件类型和大小限制
var _ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.md', '.csv'];
var _ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
  'text/markdown',
  'text/csv',
  'text/x-markdown',
  'text/x-csv',
  'application/csv',
  'application/vnd.ms-excel.sheet.macroEnabled.12'
];
var _MAX_FILE_SIZE = 200 * 1024 * 1024; // 200MB

function validateFile(file) {
  var name = (file.name || '').toLowerCase();
  var ext = name.match(/\.[a-z0-9]+$/);
  var detectedExt = ext ? ext[0] : '';

  // 检查扩展名
  if (!detectedExt || _ALLOWED_EXTENSIONS.indexOf(detectedExt) < 0) {
    return { valid: false, reason: '不支持的文件类型: ' + (detectedExt || '未知') + '，允许: ' + _ALLOWED_EXTENSIONS.join(', ') };
  }

  // 特殊处理 .csv 的 MIME 类型（浏览器可能报告 text/csv 或 application/octet-stream）
  var mimeType = (file.type || '').toLowerCase();
  var isValidMime = _ALLOWED_MIME_TYPES.indexOf(mimeType) >= 0;
  var isCsv = detectedExt === '.csv';
  // application/octet-stream 是通用二进制，允许通过（后端会再次校验）
  var isOctetStream = mimeType === 'application/octet-stream' || !mimeType;

  if (!isValidMime && !isOctetStream && !isCsv) {
    return { valid: false, reason: '文件 MIME 类型不匹配: ' + (mimeType || '空') + '，文件: ' + file.name };
  }

  // 检查文件大小
  if (file.size > _MAX_FILE_SIZE) {
    return { valid: false, reason: '文件过大: ' + (file.size / 1024 / 1024).toFixed(1) + 'MB，最大允许 200MB' };
  }
  if (file.size === 0) {
    return { valid: false, reason: '文件为空: ' + file.name };
  }

  return { valid: true };
}

// 批量校验，返回过滤后的有效文件和错误列表
function validateFiles(files) {
  var valid = [];
  var errors = [];
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var result = validateFile(f);
    if (result.valid) {
      valid.push(f);
    } else {
      errors.push(result.reason);
    }
  }
  return { valid: valid, errors: errors };
}

// 管理面板错误显示（跨 admin.js / services.js 共用）
function _adminError(containerId, msg) {
  var el = document.getElementById(containerId);
  if (el) el.innerHTML = '<div class="empty"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>' + esc(msg || '未知错误') + '</p></div>';
}
