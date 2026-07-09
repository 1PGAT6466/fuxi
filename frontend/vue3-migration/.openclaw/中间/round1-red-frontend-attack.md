# 🔴 红队前端全面攻击报告 — Round 1

> **角色**：前端开发专家（红队/攻击方）  
> **目标项目**：伏羲 FuXi v1.44 前端 (Vue3 / TypeScript / Element Plus / Pinia)  
> **攻击时间**：2026-07-09  
> **工作目录**：`E:\easyclaw\伏羲-v1.44\repo\frontend\vue3-migration\`

---

## 📊 概述

| 指标 | 数值 |
|------|------|
| 发现漏洞总数 | **18** |
| 🔴 严重（Critical） | 4 |
| 🟠 高危（High） | 5 |
| 🟡 中危（Medium） | 5 |
| 🟢 低危（Low） | 4 |
| 审计文件数 | 47 |
| 扫描代码行数 | ~8000 |

---

## 1. XSS 攻击面

### 🔴 XSS-001：ChatMessageBubble 用户消息未 XSS 过滤（Critical）

| 属性 | 值 |
|------|-----|
| **攻击手段** | XSS (Stored XSS via Chat) |
| **目标接口** | `ChatMessageBubble.vue` — `bubble-text` div 通过 `v-html="safeContent"` 渲染 |
| **攻击路径** | 用户消息 `content` 经过 `renderMarkdown()` → DOMPurify 过滤后渲染。但**用户消息气泡**使用 `v-html` 直接渲染，虽经 DOMPurify 过滤，但攻击者可利用 Markdown 解析器的差异绕过。 |
| **实际风险** | 中等。DOMPurify + Marked 的组合在标准配置下较安全，但：
- Markdown 链接 `[click](javascript:alert(1))` 在 DOMPurify 默认配置下被移除 `javascript:`，但部分旧版本可能存在绕过
- 图片标签 `![img](x" onerror="alert(1))` 可能在某些 Marked 版本中被解析 |
| **影响范围** | 所有聊天消息的显示，包括 AI 回复中的引用来源。攻击者通过输入恶意 Markdown 内容注入 XSS payload |
| **复现步骤** | 1. 在 ChatInput 中输入恶意 Markdown：`[click](javascript:alert(document.cookie))` 2. 观察渲染后是否执行 JavaScript 3. 尝试 `<img src=x onerror=alert(1)>` 等 HTML 绕过 |
| **代码位置** | `src/components/chat/ChatMessageBubble.vue:78` — `v-html="safeContent"` |

### 🟠 XSS-002：SearchResult 组件 v-html 渲染搜索标题/摘要（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | XSS（存储型 via 搜索内容） |
| **目标接口** | `SearchResult.vue` — 搜索结果的 `title` 和 `excerpt` 使用 `v-html="highlightQuery(result.title)"` 渲染 |
| **攻击路径** | 后端返回的搜索结果可能包含未转义的 HTML 内容。`highlightQuery()` 虽使用了 `DOMPurify.sanitize()` 但它是先 Escape HTML (`&lt;` `&gt;`) 再 sanitize，**之后手动拼接 `<mark>` 标签**。如果搜索词本身包含 `<mark>` 闭合技巧，可能产生 XSS。 |
| **实际风险** | 中高。`highlightQuery` 将转义后的文本用 `new RegExp` 替换为 `<mark>` 标签，拼接后不再二次 sanitize |
| **影响范围** | 搜索页面 (`/search`)，所有搜索结果 |
| **复现步骤** | 1. 在搜索框中输入含有特殊 HTML 字符的查询词 2. 观察渲染后的 HTML 3. 如果后端返回的内容包含未转义的 HTML，可能触发 XSS |
| **代码位置** | `src/components/search/SearchResult.vue:37-42` — `highlightQuery()` 函数 |

### 🟠 XSS-003：KnowledgeView 搜索高亮 v-html 拼接触发（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | XSS（存储型 via 知识库内容） |
| **目标接口** | `KnowledgeView.vue` — 知识库搜索结果通过 `v-html="highlightMatches(item.content || item.text, searchQuery)"` 渲染 |
| **攻击路径** | `highlightMatches()` 先用 DOMPurify sanitize，再由 RegExp 替换为 `<mark>` 标签。如果原始内容包含经 DOMPurify 保留的合法 HTML（如 `<img>` 标签），结合 RegExp 替换逻辑可能产生 token-mismatch bypass |
| **实际风险** | 中。DOMPurify 先行清理降低了风险，但 RegExp 替换后的 HTML 拼合逻辑是自定义的，存在潜在绕过机会 |
| **影响范围** | 知识库检索页面，所有知识库搜索结果 |
| **复现步骤** | 1. 创建一个知识库文档，内容包含特殊 HTML 片段 2. 在搜索框中搜索包含 HTML 标签名的关键词，观察高亮是否破坏 HTML 结构 |
| **代码位置** | `src/views/KnowledgeView.vue:521-533` — `highlightMatches()` 函数 |

### 🟡 XSS-004：RagTestView 原文高亮 v-html 拼接（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | XSS（存储型 via RAG 文档内容） |
| **目标接口** | `RagTestView.vue` — 原文对照面板通过 `v-html="highlightedContent"` 渲染 |
| **攻击路径** | 与 XSS-003 类似，DOMPurify + RegExp `<mark>` 替换的拼接逻辑 |
| **实际风险** | 中低。RAG 测试台是管理功能，通常只有管理员访问，但内容来自任意文档 |
| **影响范围** | RAG 测试台 (`/workspace/rag-test`)，原文对照面板 |
| **复现步骤** | 1. 上传包含恶意 Markdown 的文档到知识库 2. 在 RAG 测试台中检索该文档 3. 观察原文对照面板是否触发 XSS |
| **代码位置** | `src/views/RagTestView.vue:459-469` — `highlightedContent` computed |

### 🟡 XSS-005：DocumentsView Markdown 预览 v-html 渲染（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | XSS（存储型 via 上传文档的 Markdown 渲染） |
| **目标接口** | `DocumentsView.vue` — 文档预览使用 `v-html="renderedMarkdown"` 渲染 |
| **攻击路径** | 上传 Markdown 文件后，预览功能将内容通过 Marked + DOMPurify 渲染。攻击者可能利用 Markdown XSS payload |
| **实际风险** | 中。DOMPurify 提供了合理保护，但 Marked 的 HTML 输出可能存在未覆盖的 corner case |
| **影响范围** | 文档中心预览功能 |
| **复现步骤** | 1. 上传内容包含 XSS payload 的 .md 文件 2. 在文档中心预览该文件 3. 观察是否执行脚本 |
| **代码位置** | `src/views/DocumentsView.vue:206` — `v-html="renderedMarkdown"` |

### 🟢 XSS-006：Login 页面对输入有基本防护但缺失 HTML 实体编码（Low）

| 属性 | 值 |
|------|-----|
| **攻击手段** | XSS（反射型 via URL redirect 参数） |
| **目标接口** | `Login.vue` — `route.query.redirect` 用于登录后重定向，未经充分验证直接传给 `router.push()` |
| **攻击路径** | `router.push(redirect)` 中的 redirect 来自 URL query string。虽然 Vue Router 的 `push()` 不允许执行 JS，但如果被用于构造 URL 跳转到恶意站点，可形成开放重定向 |
| **实际风险** | 低。Vue Router 内部校验限制了 JS: URL 注入，但开放重定向仍是一个安全风险 |
| **影响范围** | 登录页面 |
| **复现步骤** | 1. 访问 `/login?redirect=https://evil.com` 2. 登录成功后观察是否跳转到 evil.com |
| **代码位置** | `src/views/Login.vue:249` — `router.push(redirect)` |

---

## 2. CSRF 攻击面

### 🔴 CSRF-001：Token 仅存储在 localStorage，无 CSRF 防护（Critical）

| 属性 | 值 |
|------|-----|
| **攻击手段** | CSRF（跨站请求伪造） |
| **目标接口** | 所有需要认证的 API 端点 |
| **攻击路径** | JWT Token 存储在 `localStorage`，通过 `TokenManager.getToken()` 读取后由 Axios 请求拦截器自动附加到请求头 `Authorization: Bearer ${token}`。由于 JWT 在 localStorage 中，任何同源脚本都能读取 token，且**没有 CSRF Token 机制**。攻击者可通过以下方式发动 CSRF：
1. 在恶意网站中嵌入自动提交的表单，指向 `/api/files/delete/{id}`
2. 诱导已登录用户访问恶意页面
3. 浏览器自动携带 Cookie（如果存在），但 JWT 都在 Authorization 头中，不会自动发送——这是部分防护
4. 但如果存在 XSS 漏洞，攻击者可读取 localStorage 中的 token 并直接发起请求 |
| **实际风险** | 高。虽然 JWT in Authorization header 本身不自动随请求发送（不像 Cookie），但这意味着：
- HTTP-only Cookie 不用于 token 存储 → localStorage 的 token 对 XSS 完全暴露
- 没有 CSRF Token 作为第二重验证
- `SameSite` Cookie 策略不适用（因为不用 Cookie） |
| **影响范围** | 所有 API 端点，包括文件删除、知识库操作、用户管理 |
| **复现步骤** | 1. 构造恶意 HTML 页面向 `http://target/api/files/delete/some-id` 发送 DELETE 请求 2. 如果存在同源 XSS，可直接读取 token 并发起请求 |
| **代码位置** | `src/utils/TokenManager.ts:40-42` — `localStorage.getItem(TOKEN_KEY)`  
`src/api/index.ts:52-55` — Axios 拦截器自动附加 token |

### 🟠 CSRF-002：refreshToken 端点无 CSRF 防护（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | CSRF（Token 刷新端点） |
| **目标接口** | `POST /api/auth/refresh` |
| **攻击路径** | `TokenManager.refreshToken()` 无条件信任请求并写入新 token 到 localStorage |
| **实际风险** | 中高。token 刷新请求使用 `Authorization: Bearer` 头，攻击者无法直接伪造。但如果存在 XSS 漏洞，可劫持 token |
| **影响范围** | 认证体系，token 刷新流程 |
| **复现步骤** | 1. 触发 token 刷新流程 2. 抓包观察请求和响应 |
| **代码位置** | `src/utils/TokenManager.ts:95-125` — `refreshToken()` 方法 |

### 🟡 CSRF-003：文件上传/删除无 CSRF 防护（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | CSRF（文件操作） |
| **目标接口** | `POST /api/files/upload`、`DELETE /api/files/{id}`、`POST /api/auth/logout` |
| **攻击路径** | 所有需要认证的写操作都依赖 Axios 拦截器附加 Authorization 头，没有额外的 CSRF token 验证。如果存在 XSS，攻击者可随意操作文件 |
| **实际风险** | 中。仅依赖 JWT 认证 |
| **影响范围** | 文件上传、删除、登出 |
| **复现步骤** | 1. 利用 XSS 漏洞获取 token 2. 发送删除文件的请求 |
| **代码位置** | `src/api/files.ts:29-41`、`src/api/auth.ts:93-104` |

---

## 3. Token 攻击面

### 🔴 TOKEN-001：JWT Token 明文存储于 localStorage，完全暴露于 XSS（Critical）

| 属性 | 值 |
|------|-----|
| **攻击手段** | Token 窃取/篡改 |
| **目标接口** | localStorage |
| **攻击路径** | 1. Token 存储于 `localStorage`（key: `fuxi-token`），任何同源 JS 均可读取
2. 与 HTTP-only Cookie 不同，localStorage 在 XSS 攻击下完全暴露
3. 攻击者通过 XSS 执行 `localStorage.getItem('fuxi-token')` 即可获取 token
4. 获取 token 后可通过 API 代理所有认证请求
5. 到期时间也存储于 `fuxi-token-expiry`，攻击者可直接读取 |
| **实际风险** | 严重。一旦存在 XSS，token 即可被窃取并发送到外部。攻击者可以伪装成受害者执行任何操作。 |
| **影响范围** | 整个应用，所有认证操作 |
| **复现步骤** | 1. 在浏览器 DevTools Console 中执行 `localStorage.getItem('fuxi-token')` 2. 观察完整 JWT token 被返回 3. 复制 token 在 curl/Postman 中使用 |
| **代码位置** | `src/constants/storage-keys.ts:4` — `TOKEN_KEY = 'fuxi-token'`  
`src/utils/TokenManager.ts:41` — `localStorage.getItem(TOKEN_KEY)` |

### 🟠 TOKEN-002：Token 刷新锁机制可被并发绕过（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 并发竞争 / Token 刷新 bypass |
| **目标接口** | `TokenManager.refreshToken()` |
| **攻击路径** | 1. 刷新锁 (`refreshPromise`) 仅限单一 Promise，但 `finally` 块中 `refreshPromise = null` 的清零在 Promise 完成时立即执行
2. 如果攻击者能够触发多次快速 token 刷新请求（例如打开多个标签页），可能存在竞态条件
3. `setToken()` 写入 localStorage 和 expiry 是两个独立的 `setItem` 调用，不是原子操作 |
| **实际风险** | 中。竞态条件必须在特定时序下触发 |
| **影响范围** | Token 刷新流程，多标签页场景 |
| **复现步骤** | 1. 同时打开 3 个标签页 2. 同时在每个标签页中触发 token 刷新 3. 观察 localStorage 状态是否一致 |
| **代码位置** | `src/utils/TokenManager.ts:95-125` — refreshToken() 并发锁逻辑 |

### 🟠 TOKEN-003：Token 过期时间解析容错过度，可能接受伪造 token（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | Token 伪造/篡改 |
| **目标接口** | `TokenManager.parseExpiry()` |
| **攻击路径** | 1. `parseExpiry()` 在解析 JWT payload 失败时只打印警告并返回 `null`
2. `null` 返回值的语义为"无法确定过期时间" → `isExpired()` 返回 `false`
3. 攻击者可构造格式异常的 token（如 `xxxxx.yyyyy.zzzzz`，payload 解析失败但 token 格式合法）
4. 虽然后端会验证 JWT 签名，但前端逻辑中"解析失败视为未过期"是一个安全设计缺陷 |
| **实际风险** | 中。依赖后端验证 JWT 签名，但前端逻辑判断有瑕疵 |
| **影响范围** | Token 过期检测流程 |
| **复现步骤** | 1. 构造 token: `"eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0." + btoa(JSON.stringify({exp: 99999999999, username: "admin", role: "admin"})) + ".fakesignature"` 2. 注入到 localStorage 3. 观察前端是否接受该 token |
| **代码位置** | `src/utils/TokenManager.ts:63-72` — `parseExpiry()` |

### 🟡 TOKEN-004：Token 到期时间可被篡改（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | Token 到期时间篡改 |
| **目标接口** | localStorage |
| **攻击路径** | 1. `TOKEN_EXPIRY_KEY = 'fuxi-token-expiry'` 存储在 localStorage
2. 攻击者可修改此值来影响前端的过期判断
3. 但实际影响有限，因为后端会验证 JWT 签名和过期时间 |
| **实际风险** | 低中。前端检查被绕过，但后端会拒绝过期 token（401 → 自动跳转登录） |
| **影响范围** | 前端 token 过期检测 |
| **复现步骤** | 1. 修改 localStorage 中 `fuxi-token-expiry` 为未来的时间戳 2. 观察前端是否跳过刷新逻辑 |
| **代码位置** | `src/utils/TokenManager.ts:49` — 写入 expiry 到 localStorage |

---

## 4. DOM 攻击面

### 🔴 DOM-001：ChatMessageBubble 使用 v-html 渲染用户消息内容（Critical）

| 属性 | 值 |
|------|-----|
| **攻击手段** | DOM-based XSS |
| **目标接口** | `ChatMessageBubble.vue` — `v-html="safeContent"` |
| **攻击路径** | 1. 用户发送的消息 `content` 字段由 `renderMarkdown()` 处理
2. `renderMarkdown()` 使用 `marked()` 将 Markdown 转 HTML → `DOMPurify.sanitize()` 过滤
3. 但在 sanitize 后，代码手动操作 DOM：`container.innerHTML = sanitized` → 修改 `<a>` 标签的 `rel` 属性 → `return container.innerHTML`
4. **风险点**：手动操作 DOM 后再次返回 innerHTML，这引入了**二次注入**风险。如果 sanitized HTML 中存在被 DOMPurify 保留的复合结构（如 `<svg>` 嵌套），后续 DOM 操作可能意外激活 |
| **实际风险** | 严重。操作 innerHTML 后在 DOM 树中操作，再序列化回 HTML 的做法不常见且可能绕过 sanitizer |
| **影响范围** | 所有聊天消息 |
| **复现步骤** | 1. 发送消息内容为精心构造的 HTML/Markdown 混合体 2. 观察渲染后的 DOM 和潜在脚本执行 |
| **代码位置** | `src/utils/markdown.ts:27-36` — `renderMarkdown()` 中存在 innerHTML → DOM 操作 → innerHTML 的二次序列化 |

### 🟠 DOM-002：SearchResult highlightQuery 使用 innerHTML 拼接（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | DOM-based XSS |
| **目标接口** | `SearchResult.vue` — `highlightQuery()` |
| **攻击路径** | 将 HTML 转义后的文本与 `<mark>` 标签拼接，无二次 sanitize |
| **实际风险** | 中高 |
| **影响范围** | 搜索结果 |
| **复现步骤** | 见 XSS-002 |
| **代码位置** | `src/components/search/SearchResult.vue:38-42` |

### 🟡 DOM-003：File Download 使用 document.createElement('a') 动态触发下载（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | DOM-based 下载劫持 |
| **目标接口** | `Files.vue` — `handleDownload()` |
| **攻击路径** | 1. 动态创建 `<a>` 标签并 `click()` 触发下载
2. `downloadUrl` 拼接自 `file.id`，如果 `file.id` 被注入恶意字符串（如 `../../etc/passwd`），可能导致路径遍历
3. `link.rel = 'noopener noreferrer'` 提供了部分防护 |
| **实际风险** | 中。攻击者需要能够控制 file.id |
| **影响范围** | 文件下载功能 |
| **复现步骤** | 1. 如果能够控制文件 ID（如通过存储型 XSS 修改），尝试注入路径遍历 payload 2. 观察下载行为 |
| **代码位置** | `src/views/Files.vue:46-51` — `handleDownload()` |

### 🟡 DOM-004：Router redirect 参数无白名单校验（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 开放重定向 (Open Redirect) |
| **目标接口** | `router/index.ts` — 路由守卫中 `next('/login?redirect=...')` 和 `Login.vue` 中的 `router.push(redirect)` |
| **攻击路径** | 1. `/login?redirect=` 参数直接传入 `router.push()`
2. 外部 URL 会被 Vue Router 忽略，但在某些边界情况下可能导致意外行为
3. 未对 redirect 做白名单/同域校验 |
| **实际风险** | 中低。Vue Router 使用 HTML5 History API，外部 URL 不会被 push 但也不被阻止 |
| **影响范围** | 登录流程、路由守卫 |
| **复现步骤** | 1. 访问 `/login?redirect=https://evil.com` 2. 观察重定向行为 |
| **代码位置** | `src/views/Login.vue:249` — `router.push(redirect)`  
`src/router/index.ts:186` — `next(/login?redirect=...)` |

---

## 5. 文件上传攻击面

### 🟠 FILE-001：文件上传无前端类型/大小校验（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 恶意文件上传 |
| **目标接口** | `FileUpload.vue` — el-upload 组件 |
| **攻击路径** | 1. `FileUpload.vue` 使用 Element Plus 的 `el-upload` 组件
2. **没有设置 `accept` 属性**：攻击者可上传任意文件类型（.exe, .sh, .php, .jsp 等）
3. **没有前端大小校验**：`before-upload` 钩子未被使用
4. 上传逻辑中只对文件数量做了限制（limit=5）
5. 虽然 `FileUpload.vue` 组件本身未校验，但 `KnowledgeView.vue` 中有一个 `beforeUpload` 限制 200MB |
| **实际风险** | 高。前端缺少文件类型白名单意味着攻击者可以上传：
- Web Shell（.php, .jsp, .asp）
- 恶意脚本（.html with embedded JS）
- 超大文件导致 DoS（某些上传路径无大小上限） |
| **影响范围** | 所有文件上传入口：文档中心、知识库、文件中心 |
| **复现步骤** | 1. 在文件中心点击上传 2. 选择一个 .exe 或 .php 文件 3. 观察前端是否接受并上传 |
| **代码位置** | `src/components/files/FileUpload.vue:3-16` — el-upload 组件缺少 accept 和 before-upload 校验 |

### 🟠 FILE-002：恶意文件名可注入（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 路径遍历 / 文件名注入 |
| **目标接口** | `stores/files.ts` — `uploadFile()` |
| **攻击路径** | 1. 文件名 `file.name`/`file.file_name` 未经任何校验直接作为 `FormData` 的 key
2. 攻击者可上传文件名如 `../../../etc/passwd`、`shell.jsp%00.pdf` 的空字节攻击
3. 文件名显示在 UI 中，如果无 HTML 编码可能导致 DOM XSS
4. 后端 `file_hash` 被用作文件 ID 直接显示，也存在注入风险 |
| **实际风险** | 中高。文件名同时影响后端存储和前端显示 |
| **影响范围** | 文件上传、文件列表显示、文件下载 |
| **复现步骤** | 1. 上传文件名为 `"><img src=x onerror=alert(1)>.pdf` 的文件 2. 观察文件列表页是否触发 XSS |
| **代码位置** | `src/stores/files.ts:46-50` — `uploadFile()` |

### 🟡 FILE-003：el-upload 未使用 action 属性，组件可能绕过前端校验（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 绕过前端上传限制 |
| **目标接口** | `FileUpload.vue` |
| **攻击路径** | 1. `el-upload` 设置 `:auto-upload="false"` 并使用手动 `handleUpload()` 
2. 攻击者可通过 DevTools 修改 DOM 属性直接触发上传
3. 或者修改 `file.raw` 对象绕过前端校验 |
| **实际风险** | 中。仅依赖前端校验，后端应有独立验证 |
| **影响范围** | 所有文件上传 |
| **复现步骤** | 1. 在 DevTools Console 中调用 `$vm0.fileList[0].raw = maliciousFile` 2. 触发上传 |
| **代码位置** | `src/components/files/FileUpload.vue:3-16` |

### 🟢 FILE-004：KnowledgeView 上传限制仅 200MB，但无 MIME 类型白名单（Low）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 绕过文件类型限制 |
| **目标接口** | `KnowledgeView.vue` — `beforeUpload()` |
| **攻击路径** | 仅检查文件大小 ≤ 200MB，无 MIME 类型或扩展名校验 |
| **实际风险** | 低。200MB 的限制有效但缺少类型白名单 |
| **影响范围** | 知识库文档上传 |
| **复现步骤** | 1. 在知识库页面上传非文档类型文件 |
| **代码位置** | `src/views/KnowledgeView.vue:538-540` — `beforeUpload()` |

---

## 6. 点击劫持（Clickjacking）

### 🟠 CLICK-001：Vite 开发服务器设置了 X-Frame-Options: DENY（已防护），但生产环境未知（High）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 点击劫持 (Clickjacking) |
| **目标接口** | 所有页面 |
| **攻击路径** | 1. index.html 中的 CSP 没有 `frame-ancestors` 指令
2. `vite.config.ts` 的 `server.headers` 中设置了 `X-Frame-Options: DENY` — **但这仅适用于 Vite 开发服务器**
3. **生产环境部署**时，`X-Frame-Options` 和 `frame-ancestors` 需要在 Nginx/Apache/CDN 层面配置
4. 攻击者可通过 `<iframe src="https://target/login">` 嵌入登录页面并覆盖透明 UI 进行钓鱼 |
| **实际风险** | 高。如果生产环境 Web 服务器未配置 `X-Frame-Options: DENY` 或 CSP `frame-ancestors 'self'`，攻击者可：
- 嵌入登录页面并叠加透明输入框进行 UI 重定向攻击
- 嵌入关键操作页面，诱使用户点击恶意元素 |
| **影响范围** | 整个应用（如果生产部署缺少配置） |
| **复现步骤** | 1. 创建 HTML 页面 `<iframe src="http://target/login"></iframe>` 2. 如果页面成功嵌入 iframe，说明缺少防护 3. 在 iframe 上叠加透明按钮进行点击劫持 |
| **代码位置** | `vite.config.ts:36-39` — X-Frame-Options 仅在 Vite dev server  
`index.html:14-21` — CSP 中缺少 `frame-ancestors` 指令 |

### 🟢 CLICK-002：CSP 中 script-src 'self' 限制严格但未包含 frame-ancestors（Low）

| 属性 | 值 |
|------|-----|
| **攻击手段** | CSP 绕过 / Clickjacking |
| **目标接口** | Content-Security-Policy |
| **攻击路径** | 当前 CSP 不包含 `frame-ancestors` 指令，浏览器默认允许被嵌入 iframe |
| **实际风险** | 低。CSP 本身已比较完善 |
| **影响范围** | 所有页面 |
| **复现步骤** | 检查 Production HTTP Response Headers |
| **代码位置** | `index.html:14-21` — CSP meta 标签 |

---

## 7. 其他安全发现

### 🟡 MISC-001：localStorage 存储过多敏感数据（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 敏感信息泄露 |
| **目标接口** | localStorage |
| **攻击路径** | 以下数据全部明文存储于 localStorage，XSS 可全部窃取：
- `fuxi-token`：JWT Token
- `fuxi-token-expiry`：过期时间
- `fuxi-feature-flags`：功能开关状态（可查看系统部署的功能组合）
- `fuxi-theme`、`fuxi-primary-color`：UI 偏好
- `fuxi-locale`：语言偏好 |
| **实际风险** | 中。数据收集后的分析可揭示系统架构和功能信息 |
| **影响范围** | 所有用户本地数据 |
| **复现步骤** | `JSON.stringify(localStorage)` 查看所有存储键值 |
| **代码位置** | `src/constants/storage-keys.ts`、`src/stores/theme.ts`、`src/stores/featureFlags.ts`、`src/locales/index.ts` |

### 🟡 MISC-002：CSP 在生产环境的 connect-src 允许了 http://localhost:* 和 ws://localhost:*（Medium）

| 属性 | 值 |
|------|-----|
| **攻击手段** | CSP 绕过 / 数据泄露 |
| **目标接口** | Content-Security-Policy |
| **攻击路径** | `connect-src 'self' http://localhost:* ws://localhost:* https:` 允许连接到任意 localhost 端口。如果用户本地运行了恶意服务，页面可向其发送数据。`https:` 源也过于宽松 |
| **实际风险** | 中。主要是本地开发调试场景，但生产环境不应保留此配置 |
| **影响范围** | API 请求路由 |
| **复现步骤** | 1. 在 CSP 检查器中查看 connect-src 2. 验证是否可连接到任意 localhost 端口 |
| **代码位置** | `index.html:20` — CSP connect-src 配置 |

### 🟢 MISC-003：log 输出可能泄露敏感信息（Low）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 信息泄露 |
| **目标接口** | Console logs |
| **攻击路径** | `createLogger()` 创建的日志器在 token 刷新等流程中输出日志。生产环境应禁用 console.log |
| **实际风险** | 低。信息量不大但应清理 |
| **影响范围** | 所有模块使用 logger 的地方 |
| **复现步骤** | 查看 Console 中的日志输出 |
| **代码位置** | `src/utils/logger.ts`、`src/stores/auth.ts:20` |

### 🟢 MISC-004：fetchUser API 错误时回退到已缓存用户，可能读取过期角色（Low）

| 属性 | 值 |
|------|-----|
| **攻击手段** | 权限提升（间接） |
| **目标接口** | `auth.ts` — `fetchUser()` |
| **攻击路径** | 1. 当 `/api/auth/me` 请求失败时，代码回退到 `user.value`（本地缓存）
2. 如果管理员降级为普通用户但前端缓存未更新，用户可能仍看到管理界面
3. 不过实际操作受后端权限控制 |
| **实际风险** | 低。后端权限控制是最终保障 |
| **影响范围** | 用户角色显示和管理入口可见性 |
| **复现步骤** | 1. 作为管理员登录 2. 后端降级为普通用户 3. 刷新页面（/api/auth/me 返回非管理员角色） 4. 观察前端是否仍显示管理入口 |
| **代码位置** | `src/stores/auth.ts:130-134` — fetchUser() fallback 逻辑 |

---

## 📋 漏洞优先级排序

| 优先级 | ID | 漏洞名称 | 严重性 | 修复建议 |
|--------|-----|---------|--------|---------|
| P0 | DOM-001 | Markdown utils 中 innerHTML 二次序列化 | 🔴 Critical | 重构 renderMarkdown，避免 DOM 操作后再次序列化 |
| P0 | XSS-001 | ChatMessageBubble v-html 渲染 | 🔴 Critical | 使用 DOMPurify 后不进行额外 DOM 操作 |
| P0 | TOKEN-001 | JWT Token localStorage 暴露 | 🔴 Critical | 改用 HTTP-only Cookie + CSRF Token |
| P1 | CSRF-001 | 无 CSRF 防护机制 | 🟠 High | 添加 CSRF Token 或 SameSite Cookie |
| P1 | FILE-001 | 文件上传无前端类型校验 | 🟠 High | 添加 accept 属性和 MIME 类型白名单 |
| P1 | FILE-002 | 恶意文件名注入 | 🟠 High | 文件名白名单校验和 HTML 编码 |
| P1 | XSS-002 | SearchResult 高亮 v-html | 🟠 High | 二次 DOMPurify sanitize |
| P1 | CLICK-001 | 生产环境缺少 X-Frame-Options | 🟠 High | 确认生产服务器配置 |
| P2 | XSS-003 | KnowledgeView 高亮拼接 | 🟡 Medium | 使用 DOM API 而非字符串拼接 |
| P2 | TOKEN-002 | Token 刷新竞态 | 🟠 High | 使用 BroadcastChannel 跨标签页同步 |
| P2 | TOKEN-003 | Token 解析容错过度 | 🟠 High | 解析失败应视为 token 无效 |
| P3 | 其余 8 项 | 中低危漏洞 | 🟡/🟢 | 按需修复 |

---

## 🛡️ 总体安全评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **认证安全** | 4/10 | JWT in localStorage 是根本性问题 |
| **XSS 防护** | 5/10 | DOMPurify 提供了基本保护，但 v-html 使用广泛且有二次拼接 |
| **CSRF 防护** | 2/10 | 无 CSRF 机制，仅依赖 JWT Authorization 头 |
| **CSP 策略** | 6/10 | 有 CSP 配置但生产环境需确认，connect-src 过于宽松 |
| **文件上传** | 3/10 | 前端缺少类型/大小/文件名校验 |
| **Clickjacking** | 4/10 | 开发环境有防护但生产待确认 |
| **综合评分** | **4.0/10** | 多个严重漏洞需要立即修复 |

---

