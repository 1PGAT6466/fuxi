# 伏羲 v1.50 前端数据流深度追踪报告

> 生成时间: 2026-07-06 | 来源: 全量代码静态分析  
> 前端版本: 两套架构（vanilla JS `frontend/` + Vue 3 `frontend/vue3-migration/`）

---

## 一、前端 API 调用全量清单

### 1.1 Vanilla JS 前端（`frontend/index.html` + `frontend/js/*.js`）

Vanilla JS 前端通过统一的 `api()` 函数（定义在 `frontend/js/api-client.js`）发起所有请求。  
Token 存储在 `sessionStorage`，请求时通过 `Authorization: Bearer <token>` 携带。

| # | 页面/功能 | API 路径 | 方法 | 触发文件 | 后端路由源 | 状态 |
|---|----------|---------|------|---------|----------|------|
| 1 | 登录 | `/api/auth/login` | POST | auth.js | auth_routes.py ✅ | ✅ 正常 |
| 2 | 验证会话 | `/api/auth/me` | GET | init-app.js | server.py:373 ✅ | ✅ 正常 |
| 3 | 智能对话 | `/api/chat` | POST | chat.js | chat.py ✅ | ✅ 正常 |
| 4 | Web搜索 | `/api/antenna/search` | GET | chat.js (useWeb) | files_view.py ✅ | ⚠️ 返回空数组 |
| 5 | 知识搜索 | `/api/search?q=&page_size=20` | GET | search.js | search.py ✅ | ✅ 正常 |
| 6 | 知识图谱 | `/api/graph` | GET | graph.js | graph.py ✅ | ✅ 正常 |
| 7 | 图谱搜索 | `/api/graph?entity=` | GET | graph.js | graph.py ✅ | ✅ 正常 |
| 8 | Wiki页列表 | `/api/wiki/pages` | GET | wiki.js | wiki.py ✅ | ⚠️ 硬编码返回 `{pages:[]}` |
| 9 | Wiki页详情 | `/api/wiki/page/{id}` | GET | wiki.js | wiki.py ✅ | ⚠️ 硬编码返回空内容 |
| 10 | 文件列表 | `/api/documents` | GET | files.js | documents.py ✅ | ✅ 正常 |
| 11 | 文件上传 | `/api/upload` | POST | files.js | documents.py ✅ | ✅ 正常 |
| 12 | 文件删除 | `/api/documents/{hash}` | DELETE | files.js | ❌ 未注册 | 🔴 断裂 |
| 13 | 文件查看 | `/api/view/{hash}` | GET | chat.js/files.js | files_view.py ✅ | ✅ 正常 |
| 14 | 文件下载 | `/api/download/{hash}` | GET | chat.js/files.js | files_view.py ✅ | ✅ 正常 |
| 15 | 系统概览 | `/api/admin/metrics-summary` | GET | admin.js:loadOverview | server.py:438 ✅ | ✅ 正常 |
| 16 | 评测报告 | `/api/evaluation/overview` | GET | admin.js:loadEval | evaluation.py ✅ | ⚠️ 硬编码返回空 |
| 17 | Feature Flags | `/api/feature-flags` | GET | admin.js:loadFlags | server.py:355 ✅ | ✅ 正常 |
| 18 | Flag切换 | `/api/feature-flags/{name}` | PUT | admin.js:toggleFlag | server.py:361 ✅ | ✅ 正常 |
| 19 | 用户反馈 | `/api/feedback/weekly` | GET | admin.js:loadFeedback | feedback.py ✅ | ⚠️ 硬编码返回 `{feedbacks:[]}` |
| 20 | 四象状态 | `/api/symbols/status` | GET | admin.js:loadSymbols | server.py:290 ✅ | ⚠️ 可能返回空 |
| 21 | 成长概览 | `/api/growth/overview` | GET | admin.js:loadGrowth | server.py:296 ✅ | ⚠️ 可能返回空 |
| 22 | 服务列表 | `/api/services/` | GET | services.js | fuxi_platform/gateway.py ⚠️ | 🔴 未注册到 server.py |
| 23 | 服务详情 | `/api/services/{id}` | GET | services.js | gateway.py ⚠️ | 🔴 未注册到 server.py |
| 24 | 服务启动 | `/api/services/{id}/start` | POST | services.js | gateway.py ⚠️ | 🔴 未注册到 server.py |
| 25 | 服务停止 | `/api/services/{id}/stop` | POST | services.js | gateway.py ⚠️ | 🔴 未注册到 server.py |

### 1.2 Vue 3 前端（`frontend/vue3-migration/`）

Vue 3 前端通过 `axios` + `src/api/index.ts` 封装。  
Token 存储在 `localStorage`，通过拦截器添加 `Authorization: Bearer <token>`。

| # | 功能 | API 路径 | 方法 | 触发来源 | 后端路由 | 状态 |
|---|------|---------|------|---------|---------|------|
| V1 | 登录 | `/api/auth/login` | POST | stores/auth.ts | auth_routes.py ✅ | ✅ |
| V2 | 获取用户 | `/api/auth/me` | GET | stores/auth.ts | server.py ✅ | ✅ |
| V3 | 智能对话 | `/api/chat` | POST | stores/chat.ts | chat.py ✅ | ✅ |
| V4 | 知识搜索 | `/api/search?q=&top_k=10` | GET | views/Search.vue | search.py ✅ | ⚠️ 期待的 `data.results` 格式与后端不一致 |
| V5 | Wiki列表 | `/api/wiki?page=&page_size=&category=&q=` | GET | views/Wiki.vue | wiki.py ✅ | ⚠️ 期待 `data.pages`，后端只返回空 |
| V6 | Wiki创建 | `/api/wiki` | POST | views/Wiki.vue | ❌ wiki.py 无 POST | 🔴 |
| V7 | Wiki更新 | `/api/wiki/{id}` | PUT | views/Wiki.vue | ❌ wiki.py 无 PUT | 🔴 |
| V8 | 文件列表 | `/api/files` | GET | stores/files.ts | ❌ 未注册 | 🔴 |
| V9 | 文件上传 | `/api/files/upload` | POST | stores/files.ts | ❌ 未注册 | 🔴 |
| V10 | 文件删除 | `/api/files/{id}` | DELETE | stores/files.ts | ❌ 未注册 | 🔴 |
| V11 | 文件下载 | `/api/files/{id}/download` | GET | views/Files.vue | ❌ 未注册 | 🔴 |
| V12 | 管理概览 | `/api/admin/status` | GET | components/admin/SystemStatus.vue | admin.py ✅ | ⚠️ 期待 `data.system/knowledge/api/users` 结构 |
| V13 | 文档管理 | `/api/admin/documents` | GET | components/admin/KnowledgePanel.vue | admin.py ✅ | ✅ |
| V14 | 文档重建 | `/api/admin/documents/{id}/reindex` | POST | KnowledgePanel.vue | ❌ | 🔴 |
| V15 | 文档删除 | `/api/admin/documents/{id}` | DELETE | KnowledgePanel.vue | ❌ | 🔴 |
| V16 | 评测列表 | `/api/admin/evaluations` | GET | components/admin/EvaluationPanel.vue | admin.py ✅ | ✅ |
| V17 | 评测运行 | `/api/admin/evaluations/run` | POST | EvaluationPanel.vue | admin.py ✅ | ✅ |
| V18 | 用户列表 | `/api/admin/users` | GET | components/admin/UserPanel.vue | admin.py ✅ | ✅ |
| V19 | 创建用户 | `/api/admin/users` | POST | UserPanel.vue | ❌ | 🔴 |
| V20 | 更新用户 | `/api/admin/users/{id}` | PUT | UserPanel.vue | ❌ | 🔴 |
| V21 | 重置密码 | `/api/admin/users/{id}/reset-password` | POST | UserPanel.vue | ❌ | 🔴 |
| V22 | 删除用户 | `/api/admin/users/{id}` | DELETE | UserPanel.vue | ❌ | 🔴 |

---

## 二、页面数据流详细分析

### 2.1 搜索流程（Vanilla JS `search.js`）

```
用户输入关键词 → Enter
  │
  ├─ doSearch()
  │    │
  │    └─ api('/api/search?q=...&page_size=20')
  │         │ 后端返回: {wiki_results: [], chunk_results: [], query, page, page_size, total}
  │         │ 前端处理: _searchResults = [...wiki_results, ...chunk_results]
  │         │
  │         └─ renderSearchResults()
  │              │ 渲染字段: r.text, r.score, r._weighted_score, r.file_name, r._source, r.chunk_index
  │              │ 来源标签: r._source → wiki/doc/event/table_view
  │              │ 关键词高亮: 在 r.text 中用 <mark> 包裹匹配词
  │              │ 相关性: Math.min(100, Math.round(score * 5)) → %
  │              │
  │              └─ 标签页: 全部 / 文档 / 问答 / 数据（前端 filterByTab 纯客户端过滤）
  │                    过滤逻辑:
  │                    - "doc": r._source === 'doc' 或 无 _source
  │                    - "qa": r._source === 'event' 或 r._via_event
  │                    - "data": r._source === 'table_view' 或 r.chunk_type === 'TABLE'
```

**期望 vs 现实**: 后端 `hybrid_search()` 返回的每个结果中包含 `text`, `score`, `file_name`, `_source` 等字段，前端直接使用。数据格式基本匹配。

### 2.2 搜索流程（Vue 3 `Search.vue`）

```
Search.vue handleSearch()
  │
  └─ apiClient.get('/api/search', { params: { q, top_k: 10 } })
       │ 期待的返回格式: { results: [{id, title, excerpt, score, source?, date?}], total }
       │
       └─ 实际后端返回: { wiki_results: [...], chunk_results: [...], query, page, page_size, total }
            🔴 格式完全不匹配！前端期待 data.results 数组，后端没有这个字段。
```

### 2.3 对话流程（Vanilla JS `chat.js`）

```
用户输入问题 → sendChat()
  │
  ├─ 普通对话:
  │    POST /api/chat  body: { query, history: [...最近6轮], stream: false }
  │    返回期望: { answer: "...", sources: [{file_hash, file_name, title}], trace: {steps: [...]} }
  │
  ├─ Web搜索模式 (_webSearchEnabled=true):
  │    GET /api/antenna/search?q=...
  │    返回期望: { answer: "..." }  但后端 files_view.py 返回 { results: [], query, source, message }
  │    🔴 格式不匹配！前端读 d.answer，但 antenna/search 返回的是 d.results
  │
  └─ 渲染:
       - answer: marked.parse() → DOMPurify.sanitize() → 渲染
       - sources: 显示为可点击的来源卡片（查看/下载链接）
         - 查看: <a href="/api/view/{file_hash}">
         - 下载: <a href="/api/download/{file_hash}">
       - trace: 显示步骤信息（tool, status, latency_ms）
```

### 2.4 Wiki 数据流（Vanilla JS `wiki.js`）

```
进入 Wiki 页面 → loadWikiTree()
  │
  ├─ GET /api/wiki/pages
  │    后端返回: { pages: [], total: 0 }  ← ⚠️ 硬编码空数组
  │
  ├─ 前端自己做了伪分类:
  │    _classifyWikiPage(title, content) 通过内置关键词匹配归类到 10 个类别
  │    (_wikiCategories 硬编码在前端代码中)
  │
  └─ 点击页面 → loadWikiPage(id)
       GET /api/wiki/page/{id}
       后端返回: { id, title: "", content: "" }  ← ⚠️ 硬编码空内容
       
       前端渲染:
         - 面包屑: 目录 → 分类 → 标题
         - 标题卡片: 标题 + 分类标签 + summary
         - 自动目录 (TOC): 从 markdown 提取 h1-h3
         - 结构化渲染: 识别 【xxx】：... 和 **key**：value 转为卡片/表格
         - markdown: marked.parse() → DOMPurify.sanitize()
```

**🔴 核心问题**: Wiki 的 `/api/wiki/pages` 和 `/api/wiki/page/{id}` 都是空壳（兼容层 stub），返回空数据。前端的所有 Wiki 渲染逻辑完全依赖这些空返回，因此 Wiki 功能实际不可用。

### 2.5 知识图谱数据流（`graph.js`）

```
loadGraph() / searchGraph()
  │
  ├─ GET /api/graph               (完整图)
  ├─ GET /api/graph?entity=xxx     (按实体搜索)
  │
  │  后端返回: { nodes: {entity_name: {type, ...}}, edges: [{from/source, to/target, relation/label}] }
  │  来源: src/db/data_store.py → load_graph() → knowledge_graph.json
  │
  ├─ 左侧面板:
  │    - 统计: 节点数、边数
  │    - 类型过滤按钮: 人物/组织/概念/地点/技术/产品
  │    - 实体列表（按连接数排序，list 100）
  │
  └─ Canvas 渲染 (D3.js):
       - 力导向图 (forceSimulation)
       - 节点颜色: 按类型（人物=#FF6B6B, 组织=#4ECDC4, 概念=#45B7D1, ...）
       - 关系标签: 显示在前 8 个字符
       - 拖拽: 支持节点拖拽
       - 点击: 显示节点详情 + 关联实体列表
```

**期望字段**: `nodes[key].type`, `edges[].from`/`source`, `edges[].to`/`target`, `edges[].relation`/`label` — 与 `load_graph()` 格式一致，基本匹配。

### 2.6 认证数据流（Vanilla JS + Vue 3 对比）

| 特性 | Vanilla JS | Vue 3 |
|------|-----------|-------|
| Token 存储 | `sessionStorage` | `localStorage` |
| 读取方式 | `__STORE.getItem(__TK)` → 直接读 | `localStorage.getItem('token')` → 通过 store |
| 请求携带 | `Authorization: Bearer <token>` | `Authorization: Bearer <token>` |
| 过期处理 | 401 → `clearAuth()` + `showLogin()` | 401 → `localStorage.removeItem('token')` + 跳转 `/login` |
| 用户信息 | `setAuth(token, user)` 存为 JSON | 单独 `fetchUser()` 拉取 `/api/auth/me` |

**🔴 关键不一致**: Vanilla JS 使用 `sessionStorage`（关闭标签页失效），Vue 3 使用 `localStorage`（持久化）。两个前端可能同时运行时会出现 token 不一致。

### 2.7 文件管理数据流（Vanilla JS `files.js`）

```
loadFiles()
  │
  ├─ GET /api/documents
  │    后端返回: { files: [{file_name, file_hash, category, chunk_count}], total, page, page_size }
  │
  ├─ 前端渲染:
  │    - 分类过滤: 按 f.category（支持 object 格式 {category, sub_cat} 和 string 格式）
  │    - 文件卡片: 图标（按扩展名） + 文件名 + 分类 + 查看/下载/删除按钮
  │    - 批量操作: 多选 + 批量删除
  │    - CSV导出: 纯前端生成
  │
  ├─ 上传:
  │    POST /api/upload  (FormData: file + relative_path)
  │    后端返回: { status: "ok", file_name, chunks, duration_ms }
  │
  └─ 删除:
       DELETE /api/documents/{file_hash}
       🔴 后端 documents.py 没有注册 DELETE 路由！
```

### 2.8 管理面板数据流（`admin.js`）

每个管理子页面独立加载数据：

| 页面 | API | 期望字段 | 后端返回 | 状态 |
|------|-----|---------|---------|------|
| 系统概览 | `/api/admin/metrics-summary` | chunks, latency_p50_ms, latency_p95_ms, latency_p99_ms, error_rate, uptime_hours, cache_hit_rate | generate_health_summary() | ⚠️ 需确认字段匹配 |
| 系统状态 | `/api/symbols/status` | symbols, organs (含 alive, status, emoji, name) | get_symbols_status() | ⚠️ 硬编码可能为空 |
| 成长面板 | `/api/growth/overview` | total_events, phase, symbols[].metrics[].*, trend[] | get_growth_overview() | ⚠️ 硬编码可能为空 |
| 评测报告 | `/api/evaluation/overview` | search_stats.total_searches, search_stats.avg_results, search_stats.avg_latency_ms, search_stats.zero_result_rate, search_stats.p50_latency_ms, rag_eval.*, test_cases_count | evaluation.py → 硬编码空 | 🔴 永远返回 0 |
| Feature Flags | `/api/feature-flags` | flags: {name: value} | load_flags() ✅ | ✅ |
| 用户反馈 | `/api/feedback/weekly` | feedbacks[] / items[] / feedback_list[] | feedback.py → {feedbacks:[]} | ⚠️ 硬编码空 |
| 服务管理 | `/api/services/` | [{id, name, version, status, service_type, ...}] | ❌ 未注册 | 🔴 404 |

### 2.9 服务管理数据流（`services.js`）

```
loadServices()
  ├─ GET /api/services/          → 期待 [{id, name, version, status, service_type, api_prefix}]
  ├─ GET /api/services/{id}      → 期待 {id, name, version, description, service_type, status, api_prefix, capabilities, registered_at, last_health_check, error_message}
  ├─ POST /api/services/{id}/start  → 期待 {ok: true}
  └─ POST /api/services/{id}/stop   → 期待 {ok: true}
```

**🔴 全部断裂**: `fuxi_platform/gateway.py` 定义了这些路由，但 `register_platform_routes()` **从未在 `server.py` 中被调用**。所有 `/api/services/*` 请求都会返回 404。

---

## 三、数据断层分析

### 3.1 🔴 必然失败的前端 API 调用（后端路由不匹配）

| 调用方 | API | 问题 | 影响 |
|--------|-----|------|------|
| **Vanilla (files.js)** | `DELETE /api/documents/{hash}` | documents.py 未注册 DELETE 路由 | 文件删除 500/405 |
| **Vanilla (services.js)** | `GET/POST /api/services/*` | 网关未注册到 server.py | 服务管理页完全 404 |
| **Vue3 (Wiki.vue)** | `POST /api/wiki` | wiki.py 无 POST 路由 | Wiki 创建失败 |
| **Vue3 (Wiki.vue)** | `PUT /api/wiki/{id}` | wiki.py 无 PUT 路由 | Wiki 编辑失败 |
| **Vue3 (stores/files.ts)** | `GET/POST/DELETE /api/files/*` | 后端无 `/api/files` 路由（只有 `/api/documents`） | 文件管理完全不可用 |
| **Vue3 (UserPanel.vue)** | `POST /api/admin/users` | admin.py 无 POST 路由 | 创建用户失败 |
| **Vue3 (UserPanel.vue)** | `PUT /api/admin/users/{id}` | admin.py 无 PUT 路由 | 编辑用户失败 |
| **Vue3 (UserPanel.vue)** | `POST /api/admin/users/{id}/reset-password` | admin.py 无此路由 | 重置密码失败 |
| **Vue3 (UserPanel.vue)** | `DELETE /api/admin/users/{id}` | admin.py 无 DELETE 路由 | 删除用户失败 |
| **Vue3 (KnowledgePanel.vue)** | `POST /api/admin/documents/{id}/reindex` | admin.py 无此路由 | 重建索引失败 |
| **Vue3 (KnowledgePanel.vue)** | `DELETE /api/admin/documents/{id}` | admin.py 无 DELETE 路由 | 删除文档失败 |

### 3.2 🔴 前端期望但后端不返回的数据

| 调用方 | API | 前端期待的字段 | 后端实际返回 | 影响 |
|--------|-----|---------------|------------|------|
| **Vue3 Search.vue** | `/api/search` | `data.results: [{id, title, excerpt, score, source, date}]` | `{wiki_results, chunk_results, query, ...}` | 🔴 搜索页显示空 |
| **Vue3 Wiki.vue** | `/api/wiki` | `data.pages: [{id, title, category, tags, content, updatedAt, author}]` | `{pages: [], total: 0}` | 🔴 Wiki 永远空 |
| **Vue3 Wiki.vue** | `/api/wiki/{id}` | 完整页面对象 | 不存在 | 🔴 404 |
| **Vanilla wiki.js** | `/api/wiki/pages` | `pages: [{id, title, content, summary}]` | `{pages: [], total: 0}` | 🟡 Wiki 列表空 |
| **Vanilla wiki.js** | `/api/wiki/page/{id}` | `{id, title, content, summary}` | `{id, title: "", content: ""}` | 🟡 Wiki 内容空 |
| **Vanilla admin.js** | `/api/evaluation/overview` | `search_stats.{total_searches, avg_results, avg_latency_ms, zero_result_rate, p50_latency_ms}` | `{search_stats: {}, rag_eval: {}, test_cases_count: 0}` | 🟡 评测面板显示 0 |
| **Vanilla admin.js** | `/api/growth/overview` | `trend: [{date, query_count, avg_latency_ms, avg_confidence, event_count}]` | 可能为空/无 trend 数组 | 🟡 成长图表空白 |
| **Vanilla chat.js** | `/api/antenna/search` | `{answer: "..."}` | `{results: [], query, source, message}` | 🔴 Web搜索返回空 |
| **Vue3 SystemStatus.vue** | `/api/admin/status` | `{system: {...}, knowledge: {documents, vectors}, api: {...}, users: {todayQueries, online}}` | `{ok: true, uptime_seconds, uptime_hours}` | 🟡 状态面板数据错位 |
| **Vue3 auth store** | `/api/auth/me` | `ApiResponse<UserInfo>` (`{code, message, data: {id, username, role}}`) | 旧格式 `{username, role}` 或 v2 格式 `{status, message, data: {username, role}}` | 🟡 解析失败 |

### 3.3 🟡 后端有但前端未使用的 API

| 后端端点 | 定义位置 | 前端是否使用 |
|---------|---------|------------|
| `POST /api/chat/agent` | chat.py | ❌ 前端从未调用，只用 `/api/chat` |
| `POST /api/auth/register` | auth_routes.py | ❌ 登录页没有注册功能 |
| `GET /api/search-history` | search.py | ❌ 前端从未调用 |
| `GET /api/wiki/search` | wiki.py | ❌ 前端 Wiki 搜索走的是 `/api/search` |
| `GET /api/wiki` | wiki.py | ❌ 只有 Vue3 前端调用了，Vanilla 前端用的是 `/api/wiki/pages` |
| `GET /api/worldtree/*` | worldtree.py | ❌ 前端完全没有 WorldTree 相关页面/代码 |
| `GET /api/v2/status` | v2_routes.py | ❌ 前端没有调用 |
| `GET /api/dashboard` | dashboard.py | ❌ 前端的仪表板走的是 `/api/admin/metrics-summary` |
| `GET /api/evolution/overview` | evolution.py | ❌ 前端没有进化面板 |
| `GET /api/health` | server.py | ❌ 前端未使用（仅用于运维） |
| `GET /api/metrics` | server.py | ❌ 前端未使用（仅用于 Prometheus） |
| `GET /api/mcp/*` (4个端点) | server.py | ❌ 前端未使用（仅用于 MCP 协议） |
| `POST /api/eval/run` | server.py | ❌ 重复路由，已有 `/api/admin/evaluations/run` |
| `GET /api/eval/report` | server.py | ❌ 前端未使用 |
| `GET /api/eval/history` | server.py | ❌ 前端未使用 |
| `GET /api/admin/stats` | admin.py | ❌ 前端用的是 `/api/admin/status` 和 `/api/admin/metrics-summary` |
| `GET /api/admin/server-status` | admin.py | ❌ 前端用的是 `/api/admin/status`（别名） |
| `GET /api/admin/documents` | admin.py | ⚠️ 只有 Vue3 前端使用 |
| `GET /api/admin/evaluations` | admin.py | ⚠️ 只有 Vue3 前端使用 |
| `GET /api/admin/users` | admin.py | ⚠️ 只有 Vue3 前端使用 |
| `POST /api/admin/evaluations/run` | admin.py | ⚠️ 只有 Vue3 前端使用 |
| `/api/symbols/status` | server.py | ⚠️ Vanilla 前端使用，但有 catch 静默失败 |
| `/api/growth/overview` | server.py | ⚠️ Vanilla 前端使用，但有 catch 静默失败 |
| `POST /api/mcp/sag_search/ingest/explain` | server.py | ❌ 仅 MCP 协议使用 |
| `/api/proxy/loader/*` | server.py | ❌ 前端未调用 |
| `/api/ai/*` (ai_tools) | ai_tools/routes.py | ❌ 前端未调用 |
| `/api/analytics/*` | data_analytics/routes.py | ❌ 前端未调用 |
| `/api/tools/*` (doc_tools) | doc_tools/routes.py | ❌ 前端未调用 |
| `/api/dxf/*` | dxf_viewer/api.py | ❌ 前端未调用 |

### 3.4 🔴 关键断裂汇总

| 优先级 | 问题 | 影响范围 |
|-------|------|---------|
| 🔴 P0 | Vue3 前端 `/api/search` 期待 `data.results` 但后端返回 `wiki_results/chunk_results` | Vue3 搜索完全不可用 |
| 🔴 P0 | Vue3 前端 `/api/files/*` 路由不存在 | Vue3 文件管理完全不可用 |
| 🔴 P0 | Wiki 端点全部是空壳（pages, page 都返回空） | Vanilla+Vue3 Wiki 完全空 |
| 🔴 P0 | `/api/services/*` 网关未注册 | 服务管理页 404 |
| 🔴 P0 | Web搜索 `/api/antenna/search` 格式不匹配 + 返回空 | 联网搜索不可用 |
| 🔴 P1 | `DELETE /api/documents/{hash}` 未注册 | 文件删除不可用 |
| 🔴 P1 | Vue3 UserPanel 的 CRUD 路由全部缺失 | 用户管理不可用 |
| 🔴 P1 | Vue3 KnowledgePanel 的 reindex/delete 路由缺失 | 文档管理操作不可用 |
| 🟡 P2 | Vue3 前端期待的 `ApiResponse<T>` 统一包装格式只有 v2 请求才会得到 | Vue3 数据解析失败（部分） |
| 🟡 P2 | 大量后端端点无前端消费者（dead code） | 约 30+ 端点/handler 对前端无用 |
| 🟡 P3 | Token 存储不一致（sessionStorage vs localStorage） | 双前端运行时认证混乱 |

---

## 四、附录：完整后端路由注册清单

### server.py 直接注册的端点

```
GET  /                            → index.html
GET  /login                       → login.html
GET  /admin                       → admin.html
GET  /metrics                     → Prometheus metrics
GET  /api/metrics                 → Prometheus metrics (别名)
GET  /api/health                  → 健康检查
GET  /api/auth/me                 → 当前用户
GET  /api/system/stats            → 系统统计
GET  /api/cache/stats             → 缓存统计
GET  /api/errors/stats            → 错误统计
GET  /api/admin/metrics-summary   → 指标摘要
GET  /api/feature-flags           → 列出 flags
PUT  /api/feature-flags/{name}    → 切换 flag
GET  /api/symbols/status          → 四象状态
GET  /api/growth/overview         → 成长概览
POST /api/mcp                     → MCP JSON-RPC
GET  /api/mcp/tools               → MCP 工具列表
POST /api/mcp/sag_search          → MCP 搜索
POST /api/mcp/sag_ingest          → MCP 入库
POST /api/mcp/sag_explain         → MCP 解释
GET  /api/mcp/sag_status          → MCP 状态
POST /api/eval/run                → 评测运行
GET  /api/eval/report             → 评测报告
GET  /api/eval/history            → 评测历史
GET  /api/proxy/loader/files      → 代理: 文件列表
POST /api/proxy/loader/upload     → 代理: 文件上传
```

### 通过 include_router 注册的模块

| 模块 | 前缀 | 端点 |
|------|------|------|
| auth_routes.py | `/api/auth` | POST /login, POST /register |
| search.py | 无 | GET /api/search, GET /api/search-history |
| chat.py | 无 | POST /api/chat, POST /api/chat/agent |
| documents.py | 无 | GET /api/documents, POST /api/upload |
| graph.py | 无 | GET /api/graph |
| metadata.py | 无 | /api/metadata/* |
| feedback.py | 无 | GET /api/feedback/weekly, POST /api/feedback |
| wiki.py | 无 | GET /api/wiki, /api/wiki/pages, /api/wiki/search, /api/wiki/page/{id} |
| dashboard.py | 无 | GET /api/dashboard |
| admin.py | 无 | GET /api/admin/stats, /status, /server-status, /documents, /evaluations, /users; POST /api/admin/evaluations/run |
| evaluation.py | 无 | GET /api/evaluation/overview |
| evolution.py | 无 | GET /api/evolution/overview |
| worldtree.py | 无 | GET /api/worldtree/stats, /terms, /wiki/tree, /wiki, /entities |
| files_view.py | 无 | GET /api/view/{hash}, /api/download/{hash}, /api/antenna/search |
| v2_routes.py | 无 | GET /api/v2/status |
| ai_tools/routes.py | 无 | POST /api/ai/summarize, /translate, /keywords, /entities, /classify; GET /api/ai/health |
| data_analytics/routes.py | `/api/analytics` | 15 个端点 |
| doc_tools/routes.py | 无 | 10 个端点 |
| dxf_viewer/api.py | 无 | 5 个端点 |

---

## 五、建议修复优先级

### 立即修复 (P0)
1. **Vue3 搜索格式适配** — 在 Search.vue 中将 `data.results` 改为 `data.wiki_results.concat(data.chunk_results)` 或在后端添加 results 字段
2. **Vue3 文件管理路由** — 为 `/api/files` 添加路由或在前端改为 `/api/documents`
3. **Wiki 数据源接入** — 将 `/api/wiki/pages` 和 `/api/wiki/page/{id}` 接入真实数据（shaoyang/wiki_distiller 或 db 加载）
4. **注册服务网关** — 在 server.py 中调用 `register_platform_routes(app)`
5. **文件删除路由** — 在 documents.py 添加 `@router.delete("/api/documents/{file_hash}")`

### 短期修复 (P1)
6. **Vue3 用户/文档 CRUD** — 在 admin.py 中添加 POST/PUT/DELETE 端点
7. **antenna/search 格式统一** — 改为返回 `{answer: ...}` 或前端改为读 `d.results`
8. **评测面板数据接入** — `/api/evaluation/overview` 接入真实评测数据

### 长期优化 (P2)
9. **清理 dead code** — 移除前端未使用的 30+ 后端端点
10. **统一响应格式** — 全部切换到 `{status, message, data}` 格式
11. **统一 Token 存储** — 确定使用 sessionStorage 或 localStorage
12. **API 文档同步** — 修改 `docs/API.md` 反映实际路由状态
