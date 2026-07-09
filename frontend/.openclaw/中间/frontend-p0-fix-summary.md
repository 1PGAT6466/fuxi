# 伏羲系统前端 P0 关键问题修复摘要

> 修复日期：2026-07-09  
> 修复范围：`repo/frontend/` 目录下 8 个 P0 问题  
> 修复原则：最小改动、向后兼容、代码风格一致

---

## P0-1: CSP `connect-src 'self'` 阻断所有 API 请求

**文件：** `index.html`  
**问题：** `<meta>` 中的 CSP 策略 `connect-src 'self'` 禁止了所有跨域 API 请求，导致登录、搜索、文件管理等全部不可用。  
**修复：** 
```
connect-src 'self';
→ connect-src 'self' http://172.25.30.200:8080 http://localhost:8080;
```
**影响范围：** 安全策略放宽，允许前端向后端 API 发起连接。生产环境建议按实际部署域名配置。

---

## P0-2: `search.js` 中 `doSearch()` 和 `renderSearchResults()` DOM 冲突

**文件：** `js/search.js`  
**问题：**  
- `doSearch()` 先在外层 `#searchResults` 容器中写入标签页 HTML（含 `<div id="searchResultsList">`），然后重新赋值 `c = document.getElementById('searchResultsList')`  
- 但 `renderSearchResults()` 始终操作 `document.getElementById('searchResults')`（外层容器）  
- 当标签页切换调用 `renderSearchResults()` 时，会**覆盖整个外层容器**（包括标签页），导致标签页消失

**修复：**
- `renderSearchResults()` 改为优先查找 `#searchResultsList`（子容器），仅在回退时才用 `#searchResults`
- 添加多层容器查找：先找 `searchResultsList` → 再找 `searchResults` → 最后返回
- 标签栏写入 `searchResults`，结果列表写入 `searchResultsList`，互不冲突

---

## P0-3: `files.js` 批量删除使用裸 `fetch` 无 token

**文件：** `js/files.js`  
**问题：**  
- `batchDelete()` 使用裸 `fetch('/api/documents/' + h, { method: 'DELETE' })` 未携带 Authorization header  
- 单个文件删除按钮的内联 `onclick` 同样使用裸 `fetch`，当后端启用鉴权时删除失败

**修复：**
1. 新增 `deleteFile(hash)` 全局函数，统一处理单个文件删除（带 token + 确认 + 错误处理）
2. `batchDelete()` 改为从 `getToken()` 获取 token 并添加到请求头
3. 所有删除按钮改为调用 `deleteFile()` 而非内联裸 `fetch`
4. 对 `fh`（file_hash）值进行单引号转义，防止 HTML 注入

---

## P0-4: Vue3 `ChatView.vue` 中 `import { logger }` 导入不存在

**文件：** `vue3-migration/src/views/ChatView.vue`  
**问题：** `import { logger } from '@/utils/logger'` 虽然 `logger.ts` 导出了同名 `logger` 常量，但 TypeScript/Vite 在特定环境下因类型接口 `Logger` 与值常量 `logger` 同名可能导致解析歧义。

**修复：**
```typescript
// 旧：
import { logger } from '@/utils/logger';
// 新：
import { createLogger } from '@/utils/logger';
const logger = createLogger('ChatView');
```
使用 `createLogger` 工厂函数创建带模块标识的 logger 实例，避免泛型接口与常量命名的潜在冲突，同时提供更好的日志溯源。

---

## P0-5: `wiki.js` 的 `_addHeadingIds` 正则替换 bug

**文件：** `js/wiki.js`  
**问题：**  
- 使用 `replaced` 布尔标志位在 `html.replace` 回调中控制"仅替换第一个"，但 `String.prototype.replace` 当正则不含 `g` 标志时**本就只替换第一个匹配**
- 然而标记的 HTML 可能包含嵌套的 `<hN>` 标签（如 `<h2>…<h3>…</h3>…</h2>`），导致 `[\s\S]*?` 非贪婪匹配提前截断或错配
- 更严重的是，原始 markdown 中连续的标题（如 `## A` 后紧跟 `### A.1`）渲染后 `<h2>` 和 `<h3>` 顺序对应关系完全依赖 content 行号，而非 HTML 中的实际顺序

**修复：**
1. 两遍扫描：第一遍从 content 中收集所有标题信息（级别、文本、ID），按 `h1/h2/h3` 分组存入 `headingMap`
2. 第二遍对每个标签，使用 `/<hN([^>]*)>/gi` 全局匹配，按 `headingMap` 中的顺序逐个插入 `id` 属性
3. 跳过已有 `id` 属性的标签，避免重复
4. 支持在已有属性的标签上追加 `id`（如 `<h2 class="xxx">` → `<h2 id="heading-3" class="xxx">`）

---

## P0-6: `files.js` 的 `loadFiles` 闭包引用导致过滤异常

**文件：** `js/files.js`  
**问题：**  
- `window._renderFiles` 定义在 `loadFiles()` 内，依赖闭包中的 `files` 变量进行过滤
- 当 `loadFiles()` 被重新调用后（如上传完成），创建了新的 `_renderFiles`，但旧的 `window._fileFilter` 仍然保留
- `_renderFiles` 内部的 `files` 闭包引用指向首次加载时的数组引用（尽管 `window._filesData` 也指向同一引用），但如果数据更新发生了引用替换（如 `files = [...newData]`），闭包内的 `files` 仍是旧引用
- 同时 ES6 `const`/`let` 混合 `var` 声明导致了作用域不一致（`files` 用 `const` 声明，闭包内使用 `=>` 箭头函数）

**修复：**
1. `_renderFiles` 内部改为统一通过 `window._filesData` 读取文件列表（而非闭包 `files`）
2. 所有箭头函数改为 `function(){}` 语法，与项目中其他 JS 文件风格保持一致
3. 过滤逻辑统一：`var fileList = window._filesData || files;` 优先走全局引用
4. 分类按钮字符串中的单引号进行 `\\.replace(/'/g, "\\\\'")` 转义

---

## P0-7: `switchPage('wiki')` 慢网络下函数未加载

**文件：** `js/init-app.js`  
**问题：**  
- `switchPage()` 中直接调用 `loadWikiTree()`、`loadGraph()` 等延迟加载的函数
- `wiki.js` 通过 `<script defer>` 加载，在慢网络下可能尚未执行
- 调用不存在的函数会导致 `ReferenceError`，页面白屏且控制台报错

**修复：**
所有 `switchPage` 中的函数调用增加 `typeof` 存在性检查：
```javascript
// 旧：
if (name === 'wiki') loadWikiTree();
// 新：
if (name === 'wiki' && typeof loadWikiTree === 'function') loadWikiTree();
```
覆盖函数：`loadGraph`、`loadWikiTree`、`loadFiles`、`loadOverview`、`loadSymbols`、`loadGrowth`、`loadEval`、`loadFlags`、`loadFeedback`、`loadServices`

---

## P0-8: `login.html` token 传递健壮性问题

**文件：** `login.html`  
**问题：**  
1. CSP `connect-src 'self' http://localhost:8080` 未包含实际的 API 服务器地址 `172.25.30.200:8080`
2. 错误处理过于简单：`catch(err){el.textContent='网络错误，请重试'}` 无重试机制
3. `sessionStorage.setItem` 可能因隐私模式/存储满而失败，但未被捕获
4. `window.location.href='/'` 在 Token 未成功写入时即跳转

**修复：**
1. CSP 添加 `http://172.25.30.200:8080` 到 `connect-src`
2. 添加最多 2 次自动重试（指数退避：1s、2s）
3. `sessionStorage.setItem` 用 try-catch 包裹，存储失败时显示明确提示
4. Token 有效性检查：`if(!d.token)` 防止无 Token 跳转
5. 区分网络错误和鉴权错误（401）

---

## 修改文件清单

| 文件 | P0 编号 | 改动类型 |
|------|---------|----------|
| `index.html` | P0-1 | CSP 策略 |
| `login.html` | P0-8 | CSP + 重试逻辑 |
| `js/search.js` | P0-2 | DOM 选择器修复 |
| `js/files.js` | P0-3, P0-6 | Token 添加 + 闭包修复 |
| `js/wiki.js` | P0-5 | 正则替换逻辑重写 |
| `js/init-app.js` | P0-7 | 函数存在性检查 |
| `vue3-migration/src/views/ChatView.vue` | P0-4 | Logger 导入修复 |

## 兼容性说明

- 所有修复保持向后兼容，使用 `var` / `function` 语法与项目现有风格一致
- CSP 策略变更仅放宽了 `connect-src`，其他指令未变动
- 未新增外部依赖
- 未修改任何 CSS 或 HTML 结构
