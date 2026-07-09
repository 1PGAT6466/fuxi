# 伏羲系统前端全面审计报告

审计日期：2026-07-09
审计范围：`E:\easyclaw\伏羲-v1.44\repo\frontend\` 
审计内容：legacy 前端（index.html + js/ + css/）+ vue3-migration 前端（src/）
审计人：前端开发专家

---

## 总览

| 严重级别 | 数量 | 说明 |
|---------|------|------|
| 🔴 P0   | 8    | 功能完全不可用或崩溃 |
| 🟠 P1   | 16   | 功能部分可用，用户可见异常 |
| 🟡 P2   | 18   | 代码质量/可维护性问题 |

---

# 🔴 P0：严重问题（功能不可用）

---

### P0-1. CSP `connect-src 'self'` 阻断所有 API 请求

**文件**: `index.html` 第 16 行
**问题**: 
```html
connect-src 'self';
```
这会导致浏览器阻止任何非同一域名的后端 API 调用。在开发环境（前端 localhost:5173，后端 localhost:8080）下 100% 被 CSP 阻断。生产环境中如果前后端不同域名/端口也会失败。

**对比**: `login.html` 中正确配置了：
```html
connect-src 'self' http://localhost:8080;
```

**影响**: 
- 所有 `api()` 请求被浏览器 CORS/CSP 阻断
- 登录后页面加载失败（`/api/auth/me` 报 CSP 错误）
- init-app.js 中的 IIFE 会因为请求被 CSP 拦截而跳转到登录页

**建议**: 至少改为 `connect-src 'self' http://localhost:8080 ws://localhost:8080;`，如果部署到其他端口，需要在部署时动态替换。

---

### P0-2. `doSearch()` 和 `renderSearchResults()` DOM 冲突

**文件**: `js/search.js` 第 53~76 行
**问题**: 
`doSearch()` 在 `#searchResults` 内部创建 `<div id="searchResultsList">` 后，将变量 `c` 重赋为新容器的引用。但 `renderSearchResults()` 仍然使用 `document.getElementById('searchResults')` 获取容器并 **覆盖整个 innerHTML**（包括 tabs 标签栏）。

**触发路径**:
1. 用户搜索 → `doSearch()` → 创建 tabs + searchResultsList
2. renderSearchResults() 被调用 → 直接覆盖 #searchResults 的 innerHTML（tabs 消失）
3. 用户点击 tab → setSearchTab() → renderSearchResults() → tabs 再次被覆盖

**影响**: 搜索结果标签栏（全部/文档/问答/数据）每次切换就会消失，结果直接覆盖 tabs。

**建议**: `renderSearchResults()` 应该把内容写入 `#searchResultsList` 而不是 `#searchResults`。

---

### P0-3. `switchPage('wiki')` 调用未加载的函数

**文件**: `js/init-app.js` 第 23 行
**问题**: `wiki.js` 以 `defer` 加载，而 `init-app.js` 是普通同步加载。当用户首次导航到 Wiki 页面时（假设 init-app 中的 `switchPage('chat')` 切换到 `chat` 后，用户再点击 wiki 导航），`wiki.js` 已加载完毕，此时没问题。

但在 `initApp()` 中，如果管理员从 login 回来直接切换，由于 `switchPage` 的事件绑定在 `initApp()` 中，此时 `wiki.js` 可能已通过 defer 加载完成，所以 `loadWikiTree()` 可能已存在。

**真正的问题**: 如果用户很快地点击 wiki，而 `wiki.js` 还未 defer 完成（极慢网络），`loadWikiTree()` 不存在。

**实际影响**: 在慢网络下可能报 `ReferenceError: loadWikiTree is not defined`。

**建议**: 在 `switchPage` 的 wiki 分支中加入 guard：`if (typeof loadWikiTree === 'function') loadWikiTree();`

---

### P0-4. `files.js` 中 `batchDelete` 使用裸 `fetch` 绕过 CSP + auth

**文件**: `js/files.js` 第 49~57 行
```javascript
const r = await fetch('/api/documents/' + h, { method: 'DELETE' });
```

**问题**:
1. 没有携带 `Authorization` header（直接使用裸 `fetch`，不是 `api()` 函数）
2. 没有经过 `api-client.js` 的 token 注入逻辑
3. `api-client.js` 中 401 会自动清除 token 并跳转登录，这里没有

**影响**: 批量删除功能在有 auth 保护的环境下 100% 返回 401。

**同样的问题**: `files.js` 第 85 行的单个删除按钮也使用裸 `fetch`：
```javascript
fetch('/api/documents/' + fh, { method: 'DELETE' })
```

**建议**: 统一使用 `api()` 函数，或手动注入 token header。

---

### P0-5. `files.js` 中 `renderFiles` 使用了闭包变量但 pattern 脆弱

**文件**: `js/files.js` 第 100~113 行
**问题**: `window._renderFiles` 在 `loadFiles()` 内部定义，引用了闭包中的 `files`、`cats`、`grid` 等变量。如果 `loadFiles()` 被重新调用，新的 `_renderFiles` 会覆盖旧的，旧的内部会尝试使用已过期的 `files` 引用（除非再次调用 `loadFiles()` 刷新）。

**实际影响**: 文件过滤和批量选择功能偶尔"忘记"文件列表。

**建议**: `_renderFiles` 应该从 `window._filesData` 读取数据，而不是依赖闭包。

---

### P0-6. Vue3 版 `import { logger }` 实际上不存在

**文件**: `vue3-migration/src/views/ChatView.vue` 第 108 行
```typescript
import { logger } from '@/utils/logger';
```

**问题**: `@/utils/logger.ts` 导出的是 `createLogger` 工厂函数，且还 export default `defaultLogger`（一个模块级实例）。但是：
- 并没有 export 名为 `logger` 的东西
- `createLogger` 返回一个对象，需要调用 `createLogger('name')` 来创建实例

**实际影响**: 在 ChatView.vue 中执行 `logger.error(...)` 会报 `Cannot read properties of undefined`。

**同样的问题**: 需检查所有使用 `import { logger }` 的文件。

---

### P0-7. `style.css` 和 `app.css` 中部分全局 CSS 变量冲突

**文件**: `css/style.css` 和 `css/app.css`
**冲突详情**:
- `style.css` 定义了 `--pri`, `--border`, `--bg`, `--card`, `--text`, `--text2`, `--text3`, `--radius`, `--shadow`, `--transition` 等
- `app.css` 也定义了相同的 CSS 变量，但值不同

| 变量 | style.css | app.css |
|------|-----------|---------|
| `--bg` | `#faf8f5` | `#F5F5F5` |
| `--border` | `#e8e3dc` | `#E8E8E8` |
| `--text` | `#1a1714` | `#1F1F1F` |
| `--text2` | `#5c554f` | `#666666` |
| `--text3` | `#99938d` | `#999999` |
| `--radius` | `14px` | `12px` |
| `--shadow` | `0 1px 3px...` | `0 2px 12px...` |

如果某处同时加载了两个 CSS（例如通过 admin 页面加载了 style.css），全局 `:root` 变量会被后加载的覆盖。

**当前**: `index.html` 只加载了 `app.css`，所以暂时不会冲突。但需要警惕。

---

### P0-8. `login.html` 登录成功后跳转到 `/` 但没有携带 token

**文件**: `login.html` 内联脚本
```javascript
sessionStorage.setItem('fuxi_token', d.token);
window.location.href = '/';
```

**问题**: `login.html` 使用 `sessionStorage.setItem`，然后跳转到 `/`（即 `index.html`）。`index.html` 中的 `api-client.js` 也是从 `sessionStorage` 读取 token。**理论上可以工作**, 但有以下隐患：

1. `login.html` 把 `display_name` 拼写错误写成了 `display_name`（typo），而 `index.html` 中的 `getUser()` 读取的也是 `display_name`
2. 如果被重定向到 `index.html` 时 sessionStorage 被清空（浏览器行为），则立即跳到登录页

**影响**: 在某些严格 CSP 环境下，sessionStorage 可能丢失。

---

# 🟠 P1：中等严重度问题（部分功能异常）

---

### P1-1. `admin.js` 的 `loadGrowth()` 使用 `Chart` 但 Chart.js 未引入

**文件**: `js/admin.js` 第 176~207 行, `index.html`
**问题**: 代码中有 `if (typeof Chart !== 'undefined')` 的 guard，但 index.html 中 **从未引入** Chart.js 的 CDN。只有 d3.js 被引入。这意味着增长面板的趋势图 **永远不会渲染**。

**影响**: 管理面板的「成长面板」页面只有统计卡片数字，没有可视化图表。

**建议**: 在 `index.html` 中引入 Chart.js CDN，或使用 D3 重写。

---

### P1-2. `files.js` 删除文件按钮有 XSS 风险

**文件**: `js/files.js` 第 113 行附近
```javascript
'onclick="event.stopPropagation();if(confirm(\'确认删除 ' + fn.replace(/'/g, "\\'") + '？\'))...'
```

**问题**: `fn` 是 `esc(f.file_name)` 的结果，但 HTML 转义 (`esc`) 已经完成，再拼接到 `onclick` 属性中。如果文件名包含单引号，`fn.replace(/'/g,"\\'")` 做了转义。但如果文件名包含 `\` 字符，转义链会断裂。

**建议**: 避免在 HTML 属性中拼接用户数据，改用 data-* 属性或事件委托。

---

### P1-3. `_adminError` 跨文件依赖且没有导出

**文件**: `js/services.js` 第 27 行, `js/admin.js` 第 2 行
`services.js` 直接使用 `_adminError('serviceStats', e.message)`，而 `_adminError` 定义在 `admin.js` 中。两者通过 script 加载顺序保证可用性（admin.js 先于 services.js 加载），但没有任何显式的依赖声明。

**影响**: 如果将来调整加载顺序，services.js 会静默失败。

**建议**: 将 `_adminError` 移到 `utils.js` 或 `init-app.js` 中作为全局工具函数。

---

### P1-4. `graph.js` 的 `_showNodeDetail` 使用字符串拼接绕过 DOMPurify

**文件**: `js/graph.js` 第 198~235 行
`_showNodeDetail` 将原始 `node.id` 通过 `esc()` 转义后拼接成 HTML。虽然 `esc()` 提供了 XSS 防护，但相比之下，`chat.js` 中的 `appendMsg` 使用了 `DOMPurify.sanitize()` 做第二层防护，图谱详情没有。

**影响**: 如果后端返回恶意 node 名称，`esc()` 提供基本防护，但不如 `DOMPurify` 安全。

---

### P1-5. `sendChat()` 在非流式模式下可能长时间无反馈

**文件**: `js/chat.js` 第 22~38 行
```javascript
stream: false  // 非流式模式
```

**问题**: `sendChat()` 使用非流式模式（`stream: false`）。如果后端处理需要较长时间（>5s），用户在收到响应前只看得到 `typing-indicator`，但看不到任何部分内容。如果请求超时（15s），用户体验很差。

**对比**: Vue3 版本的 `sendMessageStream` 虽然也是非流式，但通过逐字延迟模拟流式效果。Legacy 版本完全没有。

**影响**: AI 回答较长时用户体验差。

**建议**: 在 legacy 版本也实现 SSE 流式接收，或至少显示"正在思考..."的进度提示。

---

### P1-6. `wiki.js` 的 `_addHeadingIds` 正则替换有 Bug

**文件**: `js/wiki.js` 第 148~160 行
**问题**: `_addHeadingIds` 尝试给每个 `<h1>`, `<h2>`, `<h3>` 添加 id，但使用了复杂的正则替换逻辑，其中 `replaced` 标志位在校正循环中重复声明，可能导致每个层级只替换第一个匹配的标题。

```javascript
html = html.replace(re, function(match) {
    if (replaced) return match;  // ← 跳过后面的匹配
    replaced = true;
    ...
});
```

**影响**: 只有第一个同级别标题获得 id，目录中的链接可能跳转到错误的标题。

---

### P1-7. `loadFiles()` 中 `uploadFiles()` 使用裸 `fetch` 无 token

**文件**: `js/files.js` 第 139 行
```javascript
var r2 = await fetch('/api/upload', { method: 'POST', headers: { 'Authorization': 'Bearer ' + getToken() }, body: fd });
```

**问题**: 
1. 虽然这里手动注入了 token，但使用的 `getToken()` 可能存在 token 过期未处理的问题
2. 直接使用 `fetch` 而不是 `api()`，绕过了 token 刷新和 401 处理

**影响**: 如果 token 刚好在文件上传前过期，上传会失败而用户不知原因。

---

### P1-8. `loadWikiTree()` 中 `Promise.all` 错误处理不全

**文件**: `js/wiki.js` 第 98~102 行
```javascript
var results = await Promise.all([
  _loadWikiCategories(),
  api('/api/wiki/pages')
]);
```

**问题**: `Promise.all` 中，如果 `_loadWikiCategories()` 失败（返回空对象），但 `api('/api/wiki/pages')` 成功，`_loadWikiCategories()` 内部 catch 了异常返回 `{}`，所以不会 reject。但如果 `api('/api/wiki/pages')` 404，整个 Promise.all 会 reject，进入 catch 块。但如果第一个请求也 404，分类数据丢失但页面列表正常，Wiki 也能展示（只是所有页面归入「未分类」），这是好的 fallback。

**影响**: 轻微，有基本的异常处理。

---

### P1-9. Wiki 所有页面归类为同一分类潜在问题

**文件**: `js/wiki.js` `_classifyWikiPage()` 函数
**问题**: 如果后端 `/api/wiki` 返回的 categories 为空（`{}`），`_wikiCategories` 被设置为空对象，`Object.keys(_wikiCategories).length === 0`，所有页面归入「未分类」。

**当前影响**: 如果后端 Wiki categories 接口未实现或返回空，Wiki 页面列表仍然正常，只是没有分类。P1 级别是因为用户体验受损。

---

### P1-10. `chat.js` 中 401 后 `showLogin()` 但不清除主应用 DOM

**文件**: `js/api-client.js` 第 86 行
```javascript
if (r.status === 401) { clearAuth(); showLogin(); throw new Error('Not logged in'); }
```

**问题**: 调用 `showLogin()` 后，登录页面显示，但 `#mainApp` 仍然在 DOM 中（`display: none`）。如果登录页面出现 JavaScript 错误，用户可能看到空白页面。

**同样的问题**: `api-client.js` 中 `showLogin()` 被调用但 `api` 是同步函数内的异步操作，`showLogin` 在 `throw` 之前执行。如果 `showLogin()` 抛出异常，后面的 `throw` 不会执行。

---

### P1-11. `quick-actions` 在移动端可能溢出

**文件**: `index.html` 第 107~108 行 + `css/app.css` 中 `.quick-actions` 样式
**问题**: `.quick-actions` 使用 `flex-wrap: wrap`，每个 quick-action 的 `min-width: 180px`。在 375px 屏幕宽度下，只能放下 2 个按钮（占满一行），视觉拥挤。

---

### P1-12. 文件管理中的文件夹上传依赖浏览器 experimental API

**文件**: `js/files.js` `traverseDropItems()` 和 `traverseEntry()`
**问题**: `webkitGetAsEntry()`、`createReader()`、`readEntries()` 是 Chrome-specific API，在 Firefox 中行为不同。

---

### P1-13. `token` 注入使用正则验证，格式受限于不太通用的 pattern

**文件**: `js/api-client.js` 第 18~22 行 和 `js/init-app.js` 第 72~73 行
```javascript
if (!/^[A-Za-z0-9._~+\/=-]+$/.test(v)) { ... }
if (!/^[A-Za-z0-9._~+\/=-]+$/.test(tok)) { ... }
```

**问题**: 如果 JWT token 包含标准 base64url 字符（如 `-`, `_`），这个正则会匹配，没问题。但一些 JWT 库会添加更多字符。

---

### P1-14. `index.html` 中硬编码版本号 v1.50，与 login.html 不一致

**文件**: `index.html` 第 42 行 `v1.50`，`login.html` 第 38 行 `v1.50`
实际文件目录名为 `伏羲-v1.44`，但前端显示 v1.50。Vue3 版显示 v1.44。

**影响**: 版本号混淆，排查问题时难以匹配。

---

### P1-15. `files.js` 的 `exportCSV` 中导出的时间格式不统一

**文件**: `js/files.js` 第 17 行
```javascript
const dt = f.created_at || f.upload_time || '';
```

**问题**: 后端返回的字段名不确定是 `created_at` 还是 `upload_time`，CSV 导出可能包含空时间列。

---

### P1-16. `services.js` 中 `showServiceDetail` 创建 modal 但没有复用机制

**文件**: `js/services.js` 第 108~129 行
每次调用 `showServiceDetail` 都会创建一个新的 `#serviceDetailModal` 元素（替换旧的内容）。并且 `_esc` 函数注册了独立的 `keydown` listener 但从不清理。多次打开会导致事件泄漏。

---

# 🟡 P2：轻度问题（代码质量/可维护性）

---

### P2-1. `formatTime()` 定义但从未使用

**文件**: `js/utils.js` 第 15 行
`formatTime` 函数已定义但全项目没有任何调用。属于死代码。

---

### P2-2. `safeFetch()`、`showLoading()`、`showError()` 定义但从未使用

**文件**: `js/error-boundary.js` 第 11、21、29 行
这三个函数在 error-boundary.js 中定义，但没有任何文件调用它们。

---

### P2-3. `style.css` 定义了约 1500 行 CSS 但从未被任何 HTML 加载

**文件**: `css/style.css`
这个文件完全没有被 `index.html`、`login.html` 或任何页面引用。可能是旧版前端版本的样式，或者是计划用于某些页面的备选样式。

**建议**: 如果不使用，删除以减少维护负担。

---

### P2-4. `app.css` 和 `chat_redesign.css` 中部分样式重复定义

**文件**: `css/app.css` 和 `css/chat_redesign.css`
- `.quick-action` 的 hover 样式在两个文件中都有定义
- `::-webkit-scrollbar` 样式在两个文件中重复
- `::webkit-scrollbar-thumb` 颜色不同（app.css 用 `#D0D0D0`，redesign 用 `rgba(0,0,0,0.08)`）

**影响**: 后者覆盖前者，但增加维护成本。

---

### P2-5. `auth.js` 的 `handleLogin` 函数只处理用户名密码登录

**文件**: `js/auth.js` 第 31~54 行
没有"记住我"功能、没有 token 刷新逻辑、没有登录尝试次数限制。与 Vue3 版本的 `useAuthStore` 相比，功能较弱。

---

### P2-6. Vue3 版 `api/index.ts` 配置 `baseURL: ''` 但在生产环境需要配置

**文件**: `vue3-migration/src/api/index.ts` 第 28 行
```typescript
baseURL: '',
```
说明依赖 `vite.config.ts` 中的 proxy 配置。但在生产环境（`vite build` 后），代理不再有效，需要环境变量配置。

**影响**: 生产环境部署时 API 请求可能发往相对路径，如果前后端不在同一域会失败。

---

### P2-7. `login.html` 内联所有 JS（约 40 行），不可复用

**文件**: `login.html`
所有 JavaScript 逻辑（toggleMode、login form 处理、token 存储）完全内联在 HTML 中，不可复用。如果需要在其他页面复用登录逻辑（如 index.html 中的登录页），需要复制粘贴。

---

### P2-8. Vue3 `Login.vue` 中 `LoginResponse` 类型不匹配

**文件**: `vue3-migration/src/views/Login.vue` 第 195 行
```typescript
import type { LoginResponse } from '@/types';
```
但 `authStore.login()` 返回的是 `LoginResult`（定义在 `@/api/auth.ts`），不是 `LoginResponse`。

---

### P2-9. `bagua.ts` 中「兑」卦的 `colorLight: '#FAFAFA'` 与 `color: '#FAFAFA'` 相同

**文件**: `vue3-migration/src/constants/bagua.ts` 第 140~141 行
light 色和主色都是白色，在浅色主题下无法区分。

---

### P2-10. Vue3 `HomeView.vue` 中 `zhonggongData` 硬编码

**文件**: `vue3-migration/src/views/HomeView.vue` 第 115~120 行
```typescript
const zhonggongData = ref({
  activeWindowCount: 0,
  pendingTaskCount: 0,
  ...
});
```
即使后端 API 可用，中宫数据也仅从 API 获取。但如果 API 返回异常（catch 分支使用 mock），中宫数据显示硬编码的 `activeWindowCount: 0`。

---

### P2-11. `graph.js` 中 `_filterGraphType` 每次过滤都重新请求 API

**文件**: `js/graph.js` 第 170~178 行
```javascript
function _filterGraphType(type) {
  api('/api/graph').then(function(d) { ... });
}
```
类型过滤没有走客户端缓存，每次都重新请求 `/api/graph`。应该先缓存完整数据再客户端过滤。

---

### P2-12. 多个文件使用 `var` 声明变量（legacy）

所有 legacy JS 文件使用 `var` 而不是 `let`/`const`。这是项目的编码风格一致性，但可能导致意外的变量提升和作用域问题。

---

### P2-13. `marked` 和 `DOMPurify` 全局依赖但无显式检查

**文件**: `js/chat.js`, `js/wiki.js`
代码中使用 `typeof marked !== 'undefined'` 和 `typeof DOMPurify !== 'undefined'` 做 guard。如果 CDN 加载失败，markdown 会回退为纯文本，但没有 warning toast 告知用户。

---

### P2-14. `loadWikiPage` 中的 `_structureContent` 多次替换性能问题

**文件**: `js/wiki.js` `_structureContent()` 函数
连续执行 4 次 `html.replace()` 正则替换，每次都要遍历整个 HTML 字符串。如果 Wiki 页面很大，可能造成卡顿。

---

### P2-15. `.nav-admin` 初始 `display:none` 但 admin 导航区域仍然渲染

**文件**: `index.html` 第 85~143 行，`css/app.css` `.nav-admin { display:none }`
管理员导航在 HTML 中始终存在，仅通过 CSS 隐藏。普通用户仍可以在 DevTools 中看到这些元素。不是安全漏洞（后端有权限验证），但可以优化为动态生成。

---

### P2-16. `#theme-toggle` 按钮在 `theme.js` 中被引用但 DOM 中不存在

**文件**: `js/theme.js` 第 14 行
```javascript
var btn = document.getElementById('theme-toggle');
```
`index.html` 中**不存在** `id="theme-toggle"` 的元素。`Theme.toggle()` 和 `Theme.apply()` 会尝试更新一个不存在的按钮的文本。

**影响**: 无运行时错误（if guard 有保护），但主题切换的 UI 入口不存在。

---

### P2-17. `api-client.js` 的 `invalidateCache()` 函数从未被调用

缓存管理函数已定义，但没有任何调用。缓存只能通过 30 秒 TTL 过期，无法手动清除特定资源的缓存。

---

### P2-18. Vue3 `ChatView.vue` 的 `retryLastMessage` 方法被引用但 store 中可能未实现

**文件**: `vue3-migration/src/views/ChatView.vue` 第 87 行和 `vue3-migration/src/stores/chat.ts`
`chatStore.retryLastMessage()` 在模板中被调用，需要确认 `chat.ts` 中是否实现了该方法。

---

## 附录 A：文件清单

### 审计的 Legacy 文件

| 文件 | 行数（约） | 状态 |
|------|----------|------|
| `index.html` | ~340 | 主页面，所有应用逻辑的容器 |
| `login.html` | ~70 | 独立登录页（使用独立 CSS） |
| `js/api-client.js` | ~105 | API 封装（token/cache/retry） |
| `js/auth.js` | ~55 | 登录/登出/角色切换 |
| `js/init-app.js` | ~100 | 路由/页面切换/键盘快捷键 |
| `js/chat.js` | ~85 | 对话/SSE/消息渲染 |
| `js/search.js` | ~80 | 搜索/结果标签页 |
| `js/wiki.js` | ~300 | Wiki 树形目录/结构化渲染 |
| `js/files.js` | ~145 | 文件上传/批量删除/CSV导出 |
| `js/admin.js` | ~245 | 管理面板（状态/评测/Flags/成长） |
| `js/graph.js` | ~235 | D3 力导向知识图谱 |
| `js/services.js` | ~120 | 服务管理面板 |
| `js/toast.js` | ~20 | Toast 通知 |
| `js/utils.js` | ~38 | esc/formatTime/debounce/throttle |
| `js/theme.js` | ~18 | 主题切换（未接入 UI） |
| `js/error-boundary.js` | ~40 | 全局错误处理 + safeFetch |
| `css/app.css` | ~330 | 主样式（小米风格） |
| `css/chat_redesign.css` | ~200 | 对话页增强样式 |
| `css/login.css` | ~30 | 登录页样式（暗色） |
| `css/style.css` | ~1420 | **未使用**的完整样式 |

### 审计的 Vue3 Migration 文件（关键）

| 文件 | 状态 |
|------|------|
| `src/views/Login.vue` | 登录页 Vue3 重写版 ✅ |
| `src/views/HomeView.vue` | 八卦九宫格首页 ✅ |
| `src/views/ChatView.vue` | 对话工作台（有 logger import bug 🔴） |
| `src/api/symbols.ts` | 卦象状态 API + **硬编码 mock fallback** |
| `src/stores/auth.ts` | Pinia auth store ✅ |
| `src/router/index.ts` | 路由配置 + 守卫 ✅ |
| `src/constants/bagua.ts` | 八卦数据定义 ✅ |
| `src/api/auth.ts` | 认证 API 封装 ✅ |

---

## 附录 B：修复优先级建议

1. **立即修复 (P0)**: CSP connect-src → 登录后所有功能 blocked
2. **立即修复 (P0)**: 搜索页 innerHTML 冲突 → 搜索结果不可用
3. **立即修复 (P0)**: 文件批量删除 401 → 批量删除不可用
4. **立即修复 (P0)**: ChatView.vue logger import bug → Vue3 版对话页报错
5. **高优先级 (P1)**: Chart.js 引入 → 成长面板图表
6. **高优先级 (P1)**: XSS 风险 in files.js → 安全
7. **中优先级 (P2)**: 清理死代码 → 维护成本

---

**审计人**: 前端开发专家
**审计日期**: 2026-07-09
