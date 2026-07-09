# 伏羲系统前端 · 第二轮对抗式检测报告

> 版本: v1.44 | 检测日期: 2026-07-09 | 检测轮次: 2
> 基于: 第一轮对抗式检测修复验证 + 新引入问题检查 + 深度安全检查

---

## 一、第一轮修复验证 ✅

### 1.1 marked.js / DOMPurify 加载验证

| 检查项 | 状态 | 详情 |
|--------|------|------|
| marked.min.js 本地文件存在 | ✅ | `js/marked.min.js` (39,972 bytes) |
| dompurify.min.js 本地文件存在 | ✅ | `js/dompurify.min.js` (20,934 bytes) |
| index.html 加载 marked.min.js | ✅ | 第 272 行 `<script src="/static/js/marked.min.js?v=4">` |
| index.html 加载 dompurify.min.js | ✅ | 第 273 行 `<script src="/static/js/dompurify.min.js?v=4">` |
| 同步加载（非 defer/async） | ✅ | 在 auth.js 和 chat.js/defer 之前加载 |
| chat.js XSS 防护链 | ✅ | `marked.parse()` → `DOMPurify.sanitize()` → `innerHTML` |
| wiki.js XSS 防护链 | ✅ | 同 chat.js，且 `_showNodeDetail` 也有二次 `DOMPurify.sanitize()` |

**结论**: marked.js 和 DOMPurify 已正确加载，防护链完整。所有用户内容在渲染前经过 Markdown 解析 + XSS 消毒。

### 1.2 theme.js 正常工作验证

| 检查项 | 状态 | 详情 |
|--------|------|------|
| theme.js 本地文件存在 | ✅ | `js/theme.js` (609 bytes) |
| index.html 加载 theme.js | ✅ | 第 269 行 `<script src="/static/js/theme.js?v=1">` |
| 加载顺序正确 | ✅ | api-client.js 之后、marked/dompurify 之前（Toolbar 使用 Theme.toggle()） |
| Theme.init() 自动执行 | ✅ | 文件末尾自执行，读取 localStorage 恢复主题 |
| Theme.toggle() 功能 | ✅ | 切换 data-theme 属性 + localStorage 持久化 + 按钮图标更新 |
| 主题切换按钮存在 | ✅ | `index.html:138` `<button ... onclick="Theme.toggle()">` |

**结论**: theme.js 已正确加载，不再抛出 `ReferenceError: Theme is not defined`。

### 1.3 登录流程完整性

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 版本号统一为 v1.44 | ✅ | index.html 和 login.html 均为 v1.44 |
| 登录字段 ID 统一 | ✅ | 两页面均为 `loginUser` / `loginPass` |
| login.html 内联脚本字段同步 | ✅ | 使用 `document.getElementById('loginUser').value` |
| 注册功能入口（index.html） | ✅ | `toggleRegisterMode()` 函数 + login-toggle UI |
| 注册功能入口（login.html） | ✅ | `toggleMode()` 内联脚本 |
| auth.js handleLogin 支持注册 | ✅ | 根据 `_isRegisterMode` 调用 `/api/auth/register` |
| 注册成功自动切换登录 | ✅ | 注册成功后颜色变绿 + 自动切回登录模式 |
| Token 格式验证 | ✅ | `/^[A-Za-z0-9._~+\/=-]+$/` in both auth.js and login.html |
| Token 存储安全 | ✅ | sessionStorage（非 localStorage） |
| 401 自动退登 | ✅ | api-client.js 第 105-110 行 |

**结论**: 登录流程完整，注册功能可用，双页面字段 ID 已统一。

### 1.4 搜索功能正常

| 检查项 | 状态 | 详情 |
|--------|------|------|
| renderSearchResults 变量遮蔽已修复 | ✅ | 移除了冗余的 `c = document.getElementById(...)` 赋值 |
| searchResultsList 容器查找 | ✅ | 优先找 `searchResultsList`，回退 `searchResults` |
| 搜索标签页点击 | ✅ | setSearchTab() + data-tab 属性 |

**结论**: 搜索功能正常，变量遮蔽问题已修复。

### 1.5 其他已验证的修复

| 编号 | 问题 | 验证结果 |
|------|------|---------|
| P1-5/P1-6 | graph.js 内联 onclick → data 属性 + addEventListener | ✅ graph.js 全部改为事件委托 |
| P2-6 | Firefox 拖拽上传回退 | ✅ 检测 webkitGetAsEntry 不可用 + Toast 提示 |
| P2-7 | 后端 `{status:'error'}` 格式全局处理 | ✅ api-client.js 第 123-125 行 |
| P2-10 | 主应用注册功能入口 | ✅ login-toggle + toggleRegisterMode() |
| P3-5 | D3 拖拽事件清理 | ✅ `d3.select(canvas).on('.drag', null).on('click', null)` |
| P3-6 | chatInput 重复高度处理 | ✅ index.html 移除了 oninput，chat.js 保留兼容性注释 |

---

## 二、第二轮新增发现

### 🟠 N2-1: files.js 中的 deleteFile 仍使用内联 onclick 拼接用户数据（潜在 XSS）

**位置**: `files.js:143`
```javascript
'<button ... onclick="event.stopPropagation();deleteFile(\'' + fh.replace(/'/g, "\\'") + '\')">'
```

**风险**: `fh` 是 `f.file_hash`，来自后端 `/api/documents`。虽然 file_hash 通常由后端生成（MD5/SHA256），不能由用户直接控制，但：
1. 如果后端存在 SSRF/文件遍历漏洞，攻击者可能伪造包含特殊字符的 file_hash
2. `replace(/'/g, "\\'")` 只处理单引号，**不处理反斜杠 `\`**。如果 `fh` 包含 `\'` 序列（如 `a\'-onmouseover=alert(1)//`），经过替换后变为 `a\\'`，但 onclick 属性解析时仍有风险
3. 如果 file_hash 包含换行符 `\n` 或 HTML 注释符 `-->`，也可能破坏 HTML 结构

**严重等级**: 🟠 P1（中等 — 后端生成值，但数据路径存在理论风险）

**建议**: 改用 data 属性 + addEventListener 模式：
```javascript
'<button class="delete-file-btn" data-hash="' + esc(fh) + '">'
panel.querySelector('.delete-file-btn').addEventListener('click', function(e) {
    e.stopPropagation();
    deleteFile(this.dataset.hash);
});
```

### 🟡 N2-2: files.js 中的 toggleBatchSelect 也使用类似的内联 onchange

**位置**: `files.js:138`
```javascript
'<input type="checkbox" ... onchange="toggleBatchSelect(\'' + fh.replace(/'/g, "\\'") + '\')">'
```

**风险**: 与 N2-1 相同类型的内联事件注入风险。由于 `toggleBatchSelect` 函数接受 `hash` 参数并直接操作 `window._batchSelected`（一个 Set），即使注入也只会影响低风险的批量选择状态，但不能完全排除触发更复杂攻击链的可能性。

**严重等级**: 🟡 P2（低风险 — 影响范围小）

**建议**: 与 N2-1 一起修复。

### 🟡 N2-3: files.js 中 `deleteFile` 函数绕过 `api()` 封装直接使用 fetch

**位置**: `files.js:53-58`
```javascript
async function deleteFile(hash) {
  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const r = await fetch('/api/documents/' + hash, { method: 'DELETE', headers: headers });
```

**风险**: `deleteFile` 和 `batchDelete` 直接使用 `fetch` 而非 `api()` 封装：
- 缺少超时控制（没有 AbortController）
- 缺少自动重试
- 缺少统一响应格式处理（`{status:'error'}` 不会被检测）
- 但已手动添加了 Authorization header

**严重等级**: 🟡 P2（质量缺陷 — 与 api() 封装不一致）

**建议**: 改用 `api()` 封装：
```javascript
await api('/api/documents/' + hash, { method: 'DELETE' });
```

### 🔵 N2-4: 管理面板 loadOverview/loadEval 中数值强制转换不够安全

**位置**: `admin.js:8-23`
```javascript
'<div class="stat-value">'+(d.chunks||0)+'</div>'
'<div class="stat-value">'+(d.latency_p50_ms||0)+'ms</div>'
```

**风险**: 使用 `||0` 做数值兜底，但如果后端返回的是字符串如 `"123<script>"`，则 `<script>` 部分会直接插入 innerHTML。虽然当前 `(d.chunks||0)` 在遇到此类字符串时会返回该字符串本身（非 falsy），但后端返回的数据类型通常是可控的。

**严重等级**: 🔵 P3（极低风险 — 后端内部 API，管理员仅限）

### 🔵 N2-5: login.html 中 CSS 样式版本注释标记为 v1.50

**位置**: `css/login.css:1`
```css
/* 伏羲登录页样式 v1.50 */
```

**风险**: 与 login.html 的 `v1.44` 不一致。虽然不影响功能，但容易在维护时引起混淆。

**严重等级**: 🔵 P3（纯美观 — CSS 注释）

**建议**: 将 `v1.50` 改为 `v1.44`。

### 🔵 N2-6: wiki.js 的 `_structureContent()` 函数中有多次全局正则替换，性能风险

**位置**: `wiki.js:211-268`

**风险**: 对页面内容执行 4 次全局正则替换（模式 1-4），每次都用 `html.replace()` 扫描整个 HTML 字符串。对于超长 Wiki 页面（>10KB），这可能导致明显的渲染延迟。

**当前已有快速路径**: `_structureContent()` 函数开头有 `hasAction` 和 `hasKeyValue` 检查，这是性能优化的好措施。

**严重等级**: 🔵 P3（性能优化建议）

---

## 三、深度安全检查

### 3.1 XSS 注入测试

| 攻击向量 | 防护机制 | 状态 |
|---------|---------|------|
| 对话 AI 回复注入 `<script>alert(1)</script>` | DOMPurify.sanitize() | ✅ 安全 |
| Wiki 内容注入 `<img src=x onerror=alert(1)>` | DOMPurify.sanitize() | ✅ 安全 |
| 图谱实体名注入 `<svg onload=alert(1)>` | esc() → data 属性 | ✅ 安全 |
| 搜索关键词注入 `<script>` 标签 | esc() + 高亮处理 | ✅ 安全 |
| 文件名注入 `"><script>` | esc() | ✅ 安全 |
| file_hash 注入（见 N2-1/N2-2） | 仅 replace 单引号 | ⚠️ 缺一层防护 |
| 管理面板的数据值注入 | 后端内部 API | ⚠️ 低风险 |

**总体评估**: XSS 防护覆盖全面，DOMPurify + esc() 双重防护链路正确。**N2-1/N2-2 是唯一的残余风险**。

### 3.2 Token 存储安全

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 存储位置 | ✅ | sessionStorage（关闭浏览器自动清除） |
| 传输方式 | ✅ | `Authorization: Bearer` header |
| Token 格式验证 | ✅ | `/^[A-Za-z0-9._~+\/=-]+$/` 正则 |
| 无效 token 自动清理 | ✅ | `getToken()` 中格式验证失败自动清除 |
| 401 响应处理 | ✅ | 自动 clearAuth() + 跳转登录 |
| CSP 保护 | ⚠️ | 使用了 `unsafe-inline`（企业内网环境可接受） |
| 用户信息泄露 | ✅ | 存储在 sessionStorage 但用户角色等需要保护 |
| console.log 泄露 | ✅ | 无敏感信息泄露 |

### 3.3 敏感信息泄露

| 检查项 | 状态 |
|--------|------|
| Token 出现在 URL | ✅ 无 |
| Token 在 console 输出 | ✅ 无 |
| 密码明文存储 | ✅ 无（通过 POST body 传输） |
| 错误信息泄露 | ⚠️ error-boundary 中 `e.error` 输出到 console（调试用，合理） |
| Directory listing | ✅ N/A（由后端控制） |
| CSP 缺少 HTTPS 要求 | ⚠️ connect-src 使用了 `http://`（企业内网） |

---

## 四、代码质量

### 4.1 未发现的新 JS 错误风险

- 所有 DOM 选择器使用存在性检查（`if (el)` / `if (page)`）
- `init-app.js` 中 switchPage 使用 `typeof ... === 'function'` 检查
- graph.js 使用缓存 `_graphCache` 防止重复 API 请求
- files.js 中的 `window._renderFiles` 使用 Stable 闭包避免 DOM 泄漏

### 4.2 修复引入的新问题

✅ **未发现修复引入的新问题**。第一轮修复的所有改动（添加 script 标签、修改内联 onclick、统一字段 ID）均未破坏现有功能。

---

## 五、总结

### 5.1 第一轮修复验证 — 全部通过 ✅

| 修复编号 | 描述 | 验证结果 |
|---------|------|---------|
| P0-3 | marked.js + DOMPurify 加载 | ✅ 已正确加载 |
| P0-4 | theme.js 加载 | ✅ 已正确加载 |
| P0-1 | 版本号统一 v1.44 | ✅ 两页面统一 |
| P0-2 | 登录字段 ID 统一 | ✅ loginUser/loginPass |
| P1-5/P1-6 | 内联 onclick → data 属性 | ✅ graph.js 已全改 |
| P2-6 | Firefox 拖拽上传回退 | ✅ 已实现 |
| P2-7 | 统一响应格式处理 | ✅ api() 封装已加 |
| P2-10 | 注册功能入口 | ✅ 前后端均支持 |
| P3-5 | D3 事件泄漏 | ✅ 已清理 |
| P3-6 | chatInput 重复处理 | ✅ 已统一 |

### 5.2 第二轮新增发现汇总

| 编号 | 严重度 | 问题 | 位置 |
|------|--------|------|------|
| N2-1 | 🟠 P1 | deleteFile onclick 内联拼接 file_hash | files.js:143 |
| N2-2 | 🟡 P2 | toggleBatchSelect onchange 内联拼接 | files.js:138 |
| N2-3 | 🟡 P2 | deleteFile/batchDelete 绕过 api() 封装 | files.js:53-70 |
| N2-4 | 🔵 P3 | admin 面板数值强制转换不够安全 | admin.js:8-23 |
| N2-5 | 🔵 P3 | login.css 版本注释 v1.50 vs 实际 v1.44 | css/login.css:1 |
| N2-6 | 🔵 P3 | Wiki 全局正则性能风险 | wiki.js:211-268 |

### 5.3 整体评估

**安全等级**: ⭐⭐⭐⭐ (4/5)

- ✅ XSS 防护：DOMPurify + esc() 双层防护，关键路径已覆盖
- ✅ Token 安全：sessionStorage + 格式验证 + Bearer 传输
- ⚠️ 残余风险：files.js 中 2 处内联事件拼接（低风险，file_hash 由后端生成）
- ⚠️ 一致性缺陷：deleteFile 绕过 api() 统一封装
- ✅ 代码质量：无明显 bug，无控制台错误

**结论**: 第一轮修复全部生效，系统整体安全且功能完整。第二轮发现 6 个低风险问题，其中 N2-1/N2-2 建议修复以消除最后的内联事件注入风险。

---

**报告生成时间**: 2026-07-09 13:14
**检测者**: 前端开发专家 (第二轮对抗式检测)
**状态**: ✅ 第二轮检测完成，共发现 0 个阻断级、1 个高风险、2 个中等风险、3 个低风险问题
**下一轮建议**: 修复 N2-1/N2-2（files.js 内联事件），修复后可进入端到端测试阶段
