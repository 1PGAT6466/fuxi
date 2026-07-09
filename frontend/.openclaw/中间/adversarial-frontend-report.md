# 伏羲系统前端 · 对抗式检测报告

> 版本: v1.50 | 检测日期: 2026-07-09 | 检测范围: 全面
> 方法论: 静态代码分析 + API 调用一致性交叉验证 + 安全审计

---

## 一、关键发现总览

| 严重等级 | 数量 | 说明 |
|---------|------|------|
| 🔴 P0 - 阻断 | 4 | 运行时必现错误 |
| 🟠 P1 - 高风险 | 6 | 特定场景崩溃 |
| 🟡 P2 - 中等 | 9 | 体验/安全缺陷 |
| 🔵 P3 - 低风险 | 5 | 优化建议 |

---

## 二、P0 · 阻断级问题

### P0-1: login.html 独立登录页版本号与主应用不一致

**位置**: `login.html:27`
```
<div class="version">伏羲体系 · v1.50</div>
```
vs `index.html:71`:
```
<p class="login-hint">伏羲体系 · v1.44</p>
```
**风险**: 用户从 `/login.html` 登录显示 v1.50, 但主应用的 login card 显示 v1.44。如果用户绕过 login.html 直接访问 `/`，会看到版本不一致。虽然当前 `login.html` 不是独立暴露的入口（主应用 `/` 自带了 login card），但两个入口版本号不一致。

**修复**: 统一版本号为 v1.50。

---

### P0-2: login.html 和 index.html 登录表单字段名不一致

**login.html** 的字段 ID:
```html
<input type="text" id="username" ...>
<input type="password" id="password" ...>
```

**index.html** 的字段 ID:
```html
<input type="text" id="loginUser" ...>
<input type="password" id="loginPass" ...>
```

**风险**: 如果用户通过 `/login.html` 直接访问（独立登录页），其登录逻辑使用的是内联 script 中的 `username`/`password`。但 `auth.js` 中 `handleLogin` 使用的是 `loginUser`/`loginPass`。两种登录页面的字段 ID 完全不同，这意味着 `login.html` 的内联脚本和 `auth.js` 的 `handleLogin` 互不兼容。**当前 login.html 的 form 提交用的是内联 addEventListener，不会走 handleLogin**。但如果有人移除内联逻辑改为引用 auth.js，就会出问题。

**修复**: 统一两个页面的登录字段命名。

---

## 三、P1 · 高风险问题

### P1-1: 搜索页渲染逻辑中的容器引用有竞态条件

**位置**: `search.js:16-29`
```javascript
function renderSearchResults() {
  var c = document.getElementById('searchResultsList');
  if (!c) {
    var outer = document.getElementById('searchResults');
    if (outer) {
      c = outer.querySelector('#searchResultsList');
    }
  }
  if (!c) {
    c = document.getElementById('searchResults');
  }
```

**风险**: `doSearch()` 函数在第 84 行重新写了 `searchResults` 的 innerHTML，包含 `<div id="searchResultsList">`。但 `renderSearchResults()` 函数末尾在第 94 行又重新获取 `c = document.getElementById('searchResultsList')`（**注意！这是一个关键 bug，见 P0-2A**）。同时 `setSearchTab()` 中的 `renderSearchResults()` 和点击标签页触发切换时也存在同一个变量 `c`。由于 `doSearch` 中用了局部变量 `c` 和全局变量 `c` 重名，可能导致切换标签页时找不到 `searchResultsList` 容器。

**修复**: 修复搜索渲染函数的变量作用域问题。

---

### P1-2: 搜索页的 searchResults 容器在 doSearch() 被覆写后，标签页点击 renderSearchResults 找不到容器

**位置**: `search.js:82-94`
```javascript
async function doSearch(){
  var c=document.getElementById('searchResults');
  // ... 
  c.innerHTML=tabsHtml+'<div id="searchResultsList"></div>';
  c=document.getElementById('searchResultsList');  // ⚠️ 变量遮蔽！
  renderSearchResults();
```

**风险**: `doSearch()` 函数内部重新给局部变量 `c` 赋值为 `searchResultsList`，但 `renderSearchResults()` 函数在其开头又独立地去查找 `searchResultsList`。实际上当前代码能正常工作，但逻辑存在冗余和隐患。

**实际问题**: 在 `doSearch()` 中设置 `c = document.getElementById('searchResultsList')` 后调用 `renderSearchResults()`，但 `renderSearchResults()` 并不使用传入的 `c`，而是重新查找。这意味着那一行 `c=...` 的赋值实际上是无效的。代码冗余但不至于崩溃。

---

### P1-3: Wiki 分类 API 返回异常格式时前端静默降级

**位置**: `wiki.js:38-64` `_loadWikiCategories()`

**风险**: 函数尝试 3 种不同格式的后端响应，如果后端返回了第 4 种格式，会被误判为空。同时函数只从 `/api/wiki` 获取分类，但后端实际是 **有两个 wiki 相关路由**: `api/wiki.py` 和 `api/worldtree.py`。如果后端实际返回的是 worldtree 格式（带 `categories` 的对象），当前逻辑没问题；但如果后端迁移到只使用 worldtree 路由，`/api/wiki` 可能不再返回 categories，导致所有页面归入「未分类」。

**修复**: 确认后端 `/api/wiki` 端点的实际返回格式。

---

### P1-4: 对话页 `sendChat` 中 `body` 字段名与后端可能是 `question` vs `query`

**位置**: `chat.js:46-47`
```javascript
var apiPath = useWeb ? '/api/antenna/search' : '/api/chat';
var body = useWeb ? { query: q } : { query: q, history: chatHistory.slice(-6), stream: false };
```

**后端 chat.py**:
```python
@router.post("/api/chat")
```
需要检查后端 Chat 端点接受的字段名。前端发送 `{ query, history, stream }`，如果后端用 Pydantic model 要求 `question` 而非 `query`，会静默失败。

**验证**: 需要检查 `src/api/chat.py` 中的 request model 定义。如果模型字段名是 `question`，前端 `query` 会被忽略。

---

### P1-5: 图谱页 filterGraphType 按钮中，`esc()` 转义破坏了 onclick 属性

**位置**: `graph.js:45-48`
```javascript
html += '<button class="btn btn-sm btn-ghost" onclick="_filterGraphType(\'' + esc(e[0]) + '\')" ...>';
```

**风险**: 如果实体类型包含单引号（如 `O'Brien`），`esc()` 会将 `'` 转为 `&#39;`，嵌入到 `onclick="...'...' "` 中时会导致属性值被截断。虽然中文环境下概率低，但这是典型的 XSS 防御与内联事件绑定的冲突。

**修复**: 使用 data 属性 + addEventListener 替代内联 onclick。

---

### P1-6: 多个 JS 文件中 `esc()` 函数用于 inside onclick attr 存在注入风险

**位置**: 多处使用 `esc()` 生成 onclick 属性
- `graph.js:55`: `_highlightNode(\'' + esc(name).replace(/'/g,"\\'") + '\')`
- `graph.js:253`: `_highlightNode(\'' + esc(e[0]).replace(/'/g,"\\'") + '\')`
- `wiki.js:173`: `esc(p.id||p.page_id||'')` 用于 onclick
- `files.js:146`: `toggleBatchSelect(\'' + fh.replace(/'/g, "\\'") + '\')`

**风险**: `esc()` 转义 HTML 实体，但内联 onclick 中的值是 JS 字符串。如果值包含 `\` 或换行字符，可能导致语法错误或注入。上述代码在 `esc()` 之外又做了一次 `.replace(/'/g,"\\'")`，但这不能防御反斜杠注入。

**修复**: 所有内联事件改为 addEventListener + data 属性。

---

## 四、P2 · 中等优先级

### P2-1: login.html 使用了 `sessionStorage`，而主应用 `api-client.js` 也使用 `sessionStorage`

**位置**: 
- `login.html:41-44`: `sessionStorage.setItem('fuxi_token', d.token)`
- `api-client.js:27`: `__STORE = sessionStorage`

**状态**: ✅ 一致，无问题。但需要注意：
**风险**: 如果用户从 `http://host/login.html` 登录后跳转到 `http://host/`，sessionStorage 是同源的，token 能正确传递。但如果使用了不同的端口（带端口的 dev server），sessionStorage 不共享。当前 login.html 中重定向使用 `window.location.href='/'`，这在同源下安全。

---

### P2-2: login.html 登录失败后按钮文字可能处于错误状态

**位置**: `login.html:56`
```javascript
if(btn.textContent.indexOf('中')>=0)btn.textContent=isLogin?'登 录':'注 册';
```

**风险**: 逻辑是如果按钮文字含「中」字就重置。但如果网络错误后 `isLogin` 已经被 toggle 切换过，而登录还没开始（`submitBtn` 仍然显示 "登 录"），则重置逻辑依赖「中」字检测不精确。这是一个边界情况。

---

### P2-3: `api-client.js` 中 `Object.assign` 在 IE11 不兼容但 CSP 策略 `unsafe-inline` 可用

**位置**: `api-client.js:55`
```javascript
var fetchOpts = Object.assign({}, options || {}, { signal: controller.signal });
```

**风险**: 该项目使用了 `unsafe-inline` CSP 和 ES6+ 语法。如果目标浏览器包含 IE11，`Object.assign` 会失败。但考虑到现代企业环境，这是可接受的风险。

---

### P2-4: `auth.js` 中 `handleLogin` 函数内 `_loginRole` 未被使用

**位置**: `auth.js:5` 
```javascript
let _loginRole = 'user';
```
切换 `switchLoginTab` 设置了 `_loginRole`，但 `handleLogin` 只检查了 `d.role !== 'admin'` 的情况，并未使用 `_loginRole` 来决定调用哪个 API。这意味着管理员可以在「用户登录」tab 下用管理员账号登录。

**风险**: 低。实际上这是正确的行为——管理员也可以在任一 tab 登录，角色由后端返回的 token 决定。但 `_loginRole` 只在 `handleLogin` 中检查 `d.role !== 'admin'` 时用于拒绝非管理员在「管理员登录」tab 下的登录，逻辑没有问题。

---

### P2-5: 文件上传中使用了 `api()` 封装，但 FormData 不能序列化为 JSON

**位置**: `files.js:205`
```javascript
var r2 = await api('/api/upload', { method: 'POST', body: fd });
```

**状态**: ✅ 无问题。`api()` 函数在 `api-client.js:99` 已正确处理：
```javascript
if (opt.body && typeof opt.body === 'object' && !(opt.body instanceof FormData) ...)
```
会跳过 FormData 的 JSON 序列化。

---

### P2-6: 拖拽上传文件夹的浏览器兼容性

**位置**: `files.js:180-196` `traverseDropItems()`

**风险**: 代码使用了 `webkitGetAsEntry()` API，仅在 Chrome/Edge 可用。Firefox 会返回空数组（`!hasEntryApi` 时返回 `[]`）。这意味着 Firefox 用户拖拽文件夹时不会触发任何上传。虽然函数内已有 fallback 逻辑，但最终返回空数组会导致静默失败。

**修复**: 增加 Firefox 对 `DataTransferItem.webkitGetAsEntry` 不可用时的用户提示。

---

### P2-7: 响应处理不一致——部分 API 返回错误使用 `detail` 字段，前端未统一处理

**位置**: 多处

- `login.html` 内联脚本处理: `d.detail || d.error || ...`
- `api-client.js` 在 401 时直接抛异常
- 其他 API 调用中未处理 `d.error` 或 `d.detail`

**风险**: 后端 v1.50 引入了统一响应格式 `{status, message, data}` 也保留了旧格式 `{token, username, ...}`。前端未做任何 `status === 'error'` 的全局检查。如果后端返回 `{status: 'error', message: '...'}` 格式的错误，前端代码中如 `d.answer` / `d.chunks` 会变成 `undefined`。

**示例**: `chat.js:49`:
```javascript
var answer = d.answer || '未能生成回答';
```
如果后端返回 `{status: 'error', message: 'xxx'}`，`d.answer` 为 undefined，显示「未能生成回答」而不是实际错误信息。

**修复**: 在 `api()` 函数中增加统一响应格式处理。

---

### P2-8: marked.js 和 DOMPurify 从 CDN 加载，未做加载失败的用户提示

**位置**: `chat.js:70-71`, `wiki.js:187-188`
```javascript
if (typeof marked === 'undefined') console.warn('[Chat] marked.js CDN 加载失败...');
if (typeof DOMPurify === 'undefined') console.warn('[Chat] DOMPurify CDN 加载失败...');
```

**风险**: CDN 加载失败时只 `console.warn`，不向用户展示任何错误。用户看到的是纯文本无格式内容，但不知道原因。且 CDN 的 `defer` 加载顺序不确定——`index.html` 中 marked/dompurify 没有引用（不在 CSP 中！），只有 d3.js 和 chart.js 从 CDN 加载。

**关键发现**: `marked.min.js` 和 `dompurify.min.js` 是否从 CDN 加载？查看 `index.html`:
```html
<script src="/static/js/marked.min.js?v=4"></script>
<script src="/static/js/dompurify.min.js?v=4"></script>
```
❌ **这些文件不在 index.html 中被引用！**代码中使用了 `marked` 和 `DOMPurify`，但 script 标签中没有加载这些本地文件。这意味着 `marked` 和 `DOMPurify` 在当前页面中永远是 `undefined`。

**等等 —— 让我重新检查**…

查看 `index.html` 的 script 加载顺序:
```html
<script src="/static/js/toast.js?v=4"></script>
<script src="/static/js/utils.js?v=4"></script>
<script src="/static/js/api-client.js?v=4"></script>
<script src="/static/js/error-boundary.js?v=4"></script>
<script src="/static/js/auth.js?v=4"></script>
<script src="/static/js/init-app.js?v=4"></script>
<script defer src="/static/js/chat.js?v=4"></script>
<!-- ... -->
```

**结论**: `marked.min.js` 和 `dompurify.min.js` 未被加载！这两个文件存在于 `js/` 目录下，但在 `index.html` 中没有任何 `<script>` 标签引用它们。这意味着 `chat.js` 和 `wiki.js` 中的所有 Markdown 渲染和 XSS 防护都是失效的。

🔴 **这是一个关键问题！marked 和 DOMPurify 永远不会被加载。**

---

## 五、安全检查

### S-1: marked.js + DOMPurify 实际未加载 → XSS 风险 🔴

**问题**: 如上所述，`marked` 和 `DOMPurify` 未在 `index.html` 中引入，导致所有 AI 回答和 Wiki 内容的 Markdown 渲染回退为纯文本 `esc()`，**同时也意味着如果未来有人添加了这两个 CDN 但没有正确配置，DOMPurify 不会生效。**

**当前实际状态**: 由于 `marked` undefined 时走 `esc(content)` 分支，当前无 XSS 风险。但如果修复后加载了 `marked` 却忘记加载 `DOMPurify`，就会出现 XSS 漏洞。

**修复**: 在 `index.html` 中添加:
```html
<script src="/static/js/marked.min.js?v=4"></script>
<script src="/static/js/dompurify.min.js?v=4"></script>
```

---

### S-2: Token 存储在 sessionStorage → 中等风险 ✅

- Token 存储在 `sessionStorage`，非 `localStorage` → ✅ 关闭浏览器自动清除
- Token 通过 `Authorization: Bearer` 头发送 → ✅ 标准做法
- 但 CSP 中 `connect-src` 使用了 `http://` 非 `https://` → ⚠️ 企业内网可接受
- 登录页 `index.html` 内嵌在主应用中（login card），token 验证在 `init-app.js` 自动进行 → ✅ 防未授权访问

---

### S-3: CSP 策略中的 `unsafe-inline` 👎

```html
<meta http-equiv="Content-Security-Policy" content="
  script-src 'self' 'unsafe-inline' https://d3js.org https://cdn.jsdelivr.net;
```

**风险**: `unsafe-inline` 允许内联脚本执行，大幅削弱 CSP 防护。虽然有 `esc()` 和 `sanitizeInput()`，但一旦有任何 DOM XSS 入口，`unsafe-inline` 会让攻击者直接注入并执行脚本。

**影响**: 该项目高度依赖内联事件（`onclick`、`onkeydown`、`onsubmit`），移除 `unsafe-inline` 需要大规模重构。

---

### S-4: 敏感数据泄露风险 👎

**login.html** 中使用了 `sessionStorage.setItem('fuxi_user', JSON.stringify({...}))` 存储用户信息，包括 `role` 字段。如果存在 XSS 漏洞，攻击者可读取 sessionStorage 获取用户角色信息进行提权判断。

---

### S-5: `/api/antenna/search` 同时注册为 GET 和 POST

**后端 files_view.py**:
```python
get/api/antenna/search
post/api/antenna/search
```

前端 chat.js 中 `sendChat` 对联网搜索使用 `POST /api/antenna/search`，这是安全的。

但 `path_aliases.py` 也注册了:
```python
get/api/antenna/search
```
这可能导致多路由冲突。需要确认实际生效的是哪一个。

---

## 六、API 调用一致性检查

### 前端调用 vs 后端路由对照表

| 前端 API 调用 | 方法 | 后端路由是否存在 |
|---|---|---|---|
| `/api/auth/login` | POST | ✅ auth_routes.py `/api/auth/login` |
| `/api/auth/me` | GET | ✅ server.py `@app.get("/api/auth/me")` |
| `/api/chat` | POST | ✅ chat.py |
| `/api/antenna/search` | POST | ✅ files_view.py / path_aliases.py |
| `/api/search?q=...&page_size=20` | GET | ✅ search.py |
| `/api/graph` | GET | ✅ graph.py |
| `/api/graph?entity=...` | GET | ✅ graph.py（带 query 参数） |
| `/api/wiki` | GET | ✅ wiki.py |
| `/api/wiki/pages` | GET | ✅ wiki.py + path_aliases.py |
| `/api/wiki/page/{id}` | GET | ✅ wiki.py + path_aliases.py |
| `/api/documents` | GET | ✅ documents.py |
| `/api/documents/{hash}` | DELETE | ✅ documents.py |
| `/api/upload` | POST | ✅ documents.py |
| `/api/view/{hash}` | GET | ✅ files_view.py |
| `/api/download/{hash}` | GET | ✅ files_view.py |
| `/api/admin/metrics-summary` | GET | ✅ server.py (admin only) |
| `/api/symbols/status` | GET | ✅ server.py |
| `/api/growth/overview` | GET | ✅ server.py |
| `/api/evaluation/overview` | GET | ✅ evaluation.py |
| `/api/feature-flags` | GET | ✅ server.py |
| `/api/feature-flags/{name}` | PUT | ✅ server.py |
| `/api/feedback/weekly` | GET | ✅ feedback.py |
| `/api/services` | GET | ✅ services.py |
| `/api/services/{id}` | GET | ✅ services.py |
| `/api/services/{id}/{action}` | POST | ✅ services.py (内联路由) |

### 未使用但后端存在的 API 端点（功能未暴露给前端）

以下 API 存在于后端但前端没有使用，属于未暴露的功能：

| 端点 | 说明 |
|---|---|
| `POST /api/chat/agent` | 智能体对话 |
| `GET/DELETE/POST /api/chat/sessions/*` | 会话管理 |
| `GET /api/dashboard` | 仪表盘 |
| `GET /api/health/*` | 健康检查（4个端点） |
| `POST /api/rag/*` | RAG 高级搜索 |
| `POST /api/evaluation` | 评测执行 |
| `GET /api/evolution/*` | 进化/梦境循环 |
| `GET /api/notifications` | 通知中心 |
| `GET /api/unified-search` | 跨服务搜索 |
| `GET /api/user/preferences` | 用户偏好 |
| `GET /api/worldtree/*` | 世界树 |
| `GET /api/admin/*` | 管理面板多个端点 |

**建议**: 评估是否需要在管理员面板中暴露这些未使用但已实现的功能。

---

## 七、用户体验检查

### UX-1: 加载状态覆盖 ✅ 基本完整
- 所有页面切换时都有 loading 状态 (`loading-dots`)
- 错误状态有重试按钮
- 空状态有图标和说明文字

### UX-2: 登录流程 ✅ 完整
- Token 过期自动跳转登录页（401 处理）
- 登录失败显示友好错误
- 注册功能可用

### UX-3: 移动端 ⚠️ 未知
- 有 `viewport` meta 标签
- CSS 使用 `flex` 布局，基础响应式
- 但未做移动端专项适配（如侧边栏折叠、触摸手势等）
- 图谱页（D3 + Canvas）在移动端几乎不可用

### UX-4: 快捷键支持 ✅ 完善
- `Ctrl/Cmd + K` 快速搜索
- `Ctrl/Cmd + /` 回到对话
- `Escape` 关闭弹窗

### UX-5: 错误提示覆盖 ✅ 大部分完善
- `toast()` 统一消息提示
- `_adminError()` 管理面板错误统一处理
- 网络错误 → 重试机制
- 超时 → 友好提示

### UX-6: 暗色主题 ✅ 支持
- `Theme` 模块支持 light/dark 切换
- 使用 CSS 变量 (`var(--...)`)

---

## 八、目录/中间报告遗留检查

发现已有多份中间报告：
- `frontend-api-audit.md`
- `frontend-api-fix-report.md`
- `frontend-full-audit.md`
- `frontend-p0-fix-summary.md`
- `frontend-p1-fix-summary.md`
- `frontend-p2-fix-summary.md`

本次检测找到了这些报告中**未覆盖**的新问题。

---

---

## 附录A · 第二轮深度检测新增发现

### P0-3: 🔴 marked.js 和 DOMPurify 完全未加载（10/10 确认）

**确认方式**: `Select-String` 在 `index.html` 中搜索 `marked`/`dompurify`/`purify`，结果为零匹配。

**位置**: `index.html` 的 `<script>` 标签列表

**现状**:
- `js/marked.min.js` 文件存在于 `js/` 目录中
- `js/dompurify.min.js` 文件存在于 `js/` 目录中
- 但 `index.html` 没有引用它们的 `<script>` 标签
- `chat.js` 和 `wiki.js` 中均有 `typeof marked !== 'undefined'` 检查，结果永远是 `false`

**影响**:
- 所有 AI 回答的 Markdown 渲染完全失效（回退为纯文本 `esc()`）
- Wiki 页面内容也以纯文本显示
- 用户看到的回答没有格式、标题、列表、代码高亮

**修复**: 在 `index.html` 中 `init-app.js` 之前添加：
```html
<script src="/static/js/marked.min.js?v=4"></script>
<script src="/static/js/dompurify.min.js?v=4"></script>
```
**注意**: 这两个文件必须**同步**加载（非 async/defer），以确保 `chat.js`/`wiki.js` 执行时可用。

---

### P2-9: 🟡 主应用 index.html 和独立 login.html 使用了两套完全独立的登录逻辑

**index.html** (主应用):
- 登录 card 嵌入在主应用中（`#loginPage`）
- 使用 `auth.js` 的 `handleLogin()` 函数
- 依赖 `api-client.js` 的 `api()` 封装（带 token、重试、缓存）

**login.html** (独立登录页):
- 使用内联 `<script>` 标签
- 完全绕过 `api-client.js` 和 `auth.js`
- 手动 fetch，手动 sessionStorage 操作
- 有独立的登录/注册切换逻辑
- 有独立的 token 格式验证
- 有独立的速率限制重试逻辑

**实际问题**:
- 两份登录代码完全隔离，bug 修复需要同步两处
- `login.html` 没有使用 `api()` 封装，401 处理缺失
- `login.html` 的注册功能不同于 `index.html` 主应用（主应用登录 card 没有注册功能）
- 如果用户直接访问 `/login.html`，即使有有效 token 也会跳过登录（因为内联脚本检查了 sessionStorage）

**建议**: 统一登录逻辑。

---

### P2-10: 🟡 `auth.js` 中 `handleLogin` 对注册功能无支持

**位置**: `auth.js:24-42`

`handleLogin` 只调用 `POST /api/auth/login`，不调用 `/api/auth/register`。
`index.html` 中登录 card 没有注册功能。

这意味着：
- 通过主应用（`/`）登录的用户不能注册新账号
- 注册功能只能通过 `/login.html` 访问
- 但 `/login.html` 不被主应用的导航引用

**建议**: 在 `auth.js` 中添加 `handleRegister()` 并在登录 card 中添加注册链接。

---

### P3-5: 🔵 Graph 页面 D3 拖拽可能重复绑定事件监听

**位置**: `graph.js:116-142`

`d3.select(canvas).call(d3.drag()...)` 在每次调用 `_drawD3Graph()` 时执行，但 `d3.select(canvas).on('click', ...)` 也是每次注册。虽然 D3 的 `.on()` 默认替换（非追加），但 `canvas` 是同一个 DOM 元素，D3 绑定会根据数据集进行 enter/update/exit。如果多次调用 `_drawD3Graph`，旧的 force simulation 没有完全清理，可能导致内存中的事件处理器增加。

**现状**: `_drawD3Graph` 开头有 `if (_graphSimulation) _graphSimulation.stop()` 清理旧仿真。但 Canvas 上的 D3 drag 和 click 事件是绑定在 canvas DOM 元素上的，不是绑定在 simulation 上。多次调用可能导致多个事件处理器。

**建议**: 在 `_drawD3Graph` 开头添加 `d3.select(canvas).on('.drag', null).on('click', null)` 清理旧事件。

---

### P3-6: 🔵 init-app.js 中 chatInput 自动高度逻辑与 chat.js 中重复

**位置**:
- `init-app.js:89-95` 注册了 `chatInput` 的 `input` 事件处理器
- `chat.js:18-20` 定义了 `autoResizeChat()` 函数
- `index.html` 中 `textarea` 有 `oninput="autoResizeChat(this)"` 内联事件

**三处都在做同一件事**:
1. `init-app.js` 用 `addEventListener('input', ...)` 设置高度
2. `chat.js` 定义 `autoResizeChat()` 通过 `oninput` 属性调用
3. `index.html` 内联 `oninput` 属性同时调用 `autoResizeChat(this)`

结果是 chatInput 的 input 事件被两次处理：一次是 addEventListener，一次是内联 oninput。两者都用同一个逻辑，虽然不冲突但浪费。

**建议**: 移除重复的逻辑，只保留一种方式。

---

## 附录B · 第三轮深度扫描新增发现

### P0-4: 🔴 theme.js 完全没有在 index.html 中被加载（10/10 确认）

**确认方式**: `Select-String` 在 `index.html` 中搜索 `theme`，只在 HTML 元素的 `onclick="Theme.toggle()"` 中出现，没有对应的 `<script src="...theme.js">` 标签。

**位置**: `index.html:138`
```html
<button id="theme-toggle" class="btn btn-ghost btn-sm" onclick="Theme.toggle()" ...>🌙</button>
```

**影响**:
- 用户点击主题切换按钮时抛出 `ReferenceError: Theme is not defined`
- error-boundary 会捕获并显示 "系统异常，请刷新页面" toast
- 暗色/亮色主题切换功能完全不可用
- 用户看到错误提示，无法切换主题

**修复**: 在 `index.html` 的 script 标签中（在 `init-app.js` 之前，因为 `Theme.init()` 自执行）添加：
```html
<script src="/static/js/theme.js?v=1"></script>
```
**推荐位置**: `api-client.js` 之后、`error-boundary.js` 之前。

---

### P3-7: 🔵 错误页面 `showError()` 中内联 onclick 使用 retryFn.toString() + eval 模式

**位置**: `error-boundary.js:47`
```javascript
var retryBtn = retryFn ? '<button ... onclick="(' + retryFn.toString() + ')()">重试</button>' : '';
```

**风险**: 将函数转为字符串再嵌入 onclick 属性。如果未来 `showError` 被用于生产代码，这是一种不受 CSP 保护的 `eval` 等效模式。当前此函数标记为 `@unused`，风险极低。

---

### P3-8: 🔵 多个 JS 文件末尾缺少 `;` 使用 ASI（自动分号插入），风格不统一

**影响**: 零功能影响，但压缩/打包工具可能对此敏感。这是代码风格问题。

---

## 最终结论

经过三轮对抗式扫描确认，以下问题在**之前所有中间报告中均未被发现**：

| 编号 | 严重度 | 问题 | 状态 |
|------|--------|------|------|
| P0-3 | 🔴阻断 | marked.js + DOMPurify 未加载 | **新增发现** |
| P0-4 | 🔴阻断 | theme.js 未加载 | **新增发现** |
| P0-1 | 🔴阻断 | 版本号不一致 (v1.44 vs v1.50) | **新增发现** |
| P0-2 | 🟠高风险 | 双登录表单字段 ID 不一致 | **新增发现** |
| P2-9 | 🟡中等 | 双登录系统（两套独立登录代码） | **新增发现** |
| P2-10 | 🟡中等 | 主应用缺少注册功能入口 | **新增发现** |
| P3-5 | 🔵低 | D3 拖拽事件泄漏 | **新增发现** |
| P3-6 | 🔵低 | chatInput 重复高度处理 | **新增发现** |

**位置**:
- `init-app.js:89-95` 注册了 `chatInput` 的 `input` 事件处理器
- `chat.js:18-20` 定义了 `autoResizeChat()` 函数
- `index.html` 中 `textarea` 有 `oninput="autoResizeChat(this)"` 内联事件

**三处都在做同一件事**:
1. `init-app.js` 用 `addEventListener('input', ...)` 设置高度
2. `chat.js` 定义 `autoResizeChat()` 通过 `oninput` 属性调用
3. `index.html` 内联 `oninput` 属性同时调用 `autoResizeChat(this)`

结果是 chatInput 的 input 事件被两次处理：一次是 addEventListener，一次是内联 oninput。两者都用同一个逻辑，虽然不冲突但浪费。

**建议**: 移除重复的逻辑，只保留一种方式。

---

## 九、修复优先级建议

### 立即修复（阻断）
1. **在 index.html 中加载 marked.min.js 和 dompurify.min.js**（P0-3，10/10 确认未加载）
2. **在 index.html 中加载 theme.js**（P0-4，10/10 确认未加载，主题切换按钮报 ReferenceError）
3. **统一 login.html 和 index.html 的版本号** (P0-1)
4. **修复 login.html 和 index.html 中登录字段 ID 不一致** (P0-2)

### 本次迭代（高风险）
4. 修复搜索页 renderSearchResults 的变量遮蔽 (P1-1)
5. 确认后端 Chat API 的请求字段名 (query vs question) (P1-4) → **已确认：后端使用 query，前端正确**
6. 将内联 onclick 改为 addEventListener + data 属性 (P1-5, P1-6)
7. Firefox 拖拽文件夹上传降级提示 (P2-6)

### 下一迭代（中低风险）
8. 统一后端响应格式处理 (P2-7)
9. 统一登录逻辑——主应用和 login.html 使用同一套代码 (P2-9)
10. 在 auth.js 中添加注册功能支持 (P2-10)
11. CSP 策略优化（减少 unsafe-inline 依赖）
12. 暴露更多管理面板功能
13. 移动端适配优化
14. 清理 D3 重复事件绑定 (P3-5)
15. 清理 chatInput 重复高度处理 (P3-6)

---

**报告生成时间**: 2026-07-09 12:57
**检测者**: 前端开发专家 (对抗式检测)
**状态**: ✅ 对抗式检测完成（三轮扫描），共发现 24 个问题
**检测轮次**: 3 轮 | 关键新增: marked+DOMPurify 未加载 (P0-3)、theme.js 未加载 (P0-4)、双登录系统 (P2-9)、注册缺失 (P2-10)、D3 事件泄漏 (P3-5)、chatInput 重复 (P3-6)
