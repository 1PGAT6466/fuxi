# 伏羲系统前端 API 调用审计报告

> **生成时间**: 2026-07-09  
> **审计范围**: `E:\easyclaw\伏羲-v1.44\repo\frontend\`  
> **覆盖文件**: `js/*.js` (legacy) + `vue3-migration/src/api/*.ts` (Vue3 迁移版) + admin 面板  
> **审计方法**: 扫描所有 `fetch()/api()` 调用、axios 封装调用、mock 数据定义  
> **阶段**: 第一阶段 — 只摸底，不改代码

---

## 一、总体概览

### 1.1 前端版本架构

| 层 | 技术栈 | 说明 |
|---|---|---|
| **Legacy 前端** (主) | 原生 JS + fetch | `index.html` 直接加载 `js/*.js`，当前生产版本 |
| **Vue3 迁移版** | Vue3 + TypeScript + Axios | `vue3-migration/src/`，功能更丰富，部分端点未实现 |
| **Admin 面板** | 原生 JS + fetch | `admin/js/admin-worldtree-v20.js`，独立管理界面 |

### 1.2 统计汇总

| 指标 | Legacy 前端 | Vue3 迁移版 | Admin 面板 | 合计 |
|---|---|---|---|---|
| **API 调用端点（去重）** | 20 | 35+ | 14 | ~45+ |
| **Mock 数据源** | 0 | 5 个文件 | 0 | 5 |
| **硬编码假数据** | 1 (wiki 分类) | 大量 mock 文件 | 0 | 多处 |

---

## 二、Legacy 前端 API 调用明细（生产版本）

### 2.1 核心 API 客户端

**文件**: `js/api-client.js`  
**封装函数**: `api(url, opt)` — 统一封装了 Token 管理、缓存、超时、重试

关键行为：
- GET 请求自动缓存 30 秒
- 超时 15 秒，自动重试 2 次（仅 5xx）
- 自动添加 `Authorization: Bearer <token>` 头
- 401 自动清除 auth 并跳转登录页
- 403 弹出 "没有权限" toast

---

### 2.2 登录/认证

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 1 | `/api/auth/login` | POST | `js/auth.js` | `{username, password}` | `{token, username, role, display_name}` | 用户点击登录按钮 | ✅ |
| 2 | `/api/auth/me` | GET | `js/init-app.js` | 无（依赖 token） | `{username}` | 页面初始化时（有 token 时） | ✅ |

**登录流程**:
1. 用户输入用户名 + 密码，选择 user/admin 角色
2. 调用 `POST /api/auth/login`，成功后存入 `sessionStorage`
3. 检查角色是否匹配，不匹配则报错
4. 初始化时调用 `GET /api/auth/me` 验证 token 有效性
5. Token 非法则清空 auth 并显示登录页

---

### 2.3 对话/聊天页面

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 3 | `/api/chat` | POST | `js/chat.js` `sendChat()` | `{query, history, stream: false}` | `{answer, sources[], trace}` | 用户发送消息 | ✅ |
| 4 | `/api/antenna/search` | POST | `js/chat.js` `sendChat()` | `{query}` | `{answer, results[]}` | 用户开启"联网搜索"后发消息 | ✅ |

**聊天流程**:
1. 用户输入消息 → `sendChat()` 
2. 如果启用联网搜索 (`_webSearchEnabled=true`) → `POST /api/antenna/search`
3. 否则 → `POST /api/chat`
4. 响应渲染为 Markdown，显示引用来源卡片（含查看/下载链接）
5. 支持 SAG 追踪面板 (`trace.steps`)

**附加 URL（非 API 调用，是直接链接）**:
- `/api/view/<file_hash>` — 查看原文（`target="_blank"` 链接）
- `/api/download/<file_hash>` — 下载文件（`<a>` 链接）

---

### 2.4 知识搜索页面

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 5 | `/api/search` | GET | `js/search.js` `doSearch()` | `?q=<query>&page_size=20` | `{wiki_results[], chunk_results[]}` | 用户输入搜索词 | ✅ |

搜索流程：
1. 调用 `GET /api/search?q=xxx&page_size=20`
2. 返回 `wiki_results`（Wiki 页面）和 `chunk_results`（文档块）
3. 前端合并为统一搜索结果列表
4. 支持按标签分 tab 展示：全部/文档/问答/数据

---

### 2.5 知识图谱页面

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 6 | `/api/graph` | GET | `js/graph.js` `loadGraph()` | 无 | `{nodes: {name: {type, ...}}, edges: [{from, to, relation}]}` | 切换到图谱页面时 | ✅ |
| 7 | `/api/graph` | GET | `js/graph.js` `_filterGraphType()` | 无（客户端过滤） | 同上 | 用户点击类型过滤按钮 | ✅ |
| 8 | `/api/graph` | GET | `js/graph.js` `searchGraph()` | `?entity=<name>` | 同上（按实体过滤） | 用户搜索实体时 | ✅ |

图谱流程：
1. 页面切换时 → `loadGraph()` → 获取全部节点和边
2. D3.js 力导向图渲染
3. 类型过滤通过再次请求全部数据后客户端过滤
4. 实体搜索传递 `?entity=` 参数

---

### 2.6 Wiki 知识页面

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 9 | `/api/wiki/pages` | GET | `js/wiki.js` `loadWikiTree()` | 无 | `{pages: [{id, title, content, summary}]}` | 切换到 Wiki 页面时 | ✅ |
| 10 | `/api/wiki/page/<id>` | GET | `js/wiki.js` `loadWikiPage(id)` | 无 | `{id, title, content, summary}` | 用户点击某个 Wiki 页面 | ✅ |

Wiki 流程：
1. 切换页面 → `loadWikiTree()` → 获取所有 Wiki 页面
2. 前端通过 `_classifyWikiPage()` 按关键词分类到 9 个预设类别
3. 分类数据 (`_wikiCategories`) 是**硬编码在前端的假数据**
4. 点击页面 → `loadWikiPage(id)` → 获取页面内容
5. 内容渲染为 Markdown，提取 TOC 目录
6. 智能结构化将 `【xxx】：描述` 转为卡片表格

---

### 2.7 文件管理页面

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 11 | `/api/documents` | GET | `js/files.js` `loadFiles()` | 无 | `{files: [{file_hash, file_name, category, created_at}]}` | 切换到文件管理页面 | ✅ |
| 12 | `/api/upload` | POST | `js/files.js` `uploadFiles()` | `FormData{file, relative_path}` | (ok) | 用户拖拽/选择文件上传 | ✅ |
| 13 | `/api/documents/<hash>` | DELETE | `js/files.js` 内联 `fetch()` | 无 | (ok) | 用户点击删除按钮 | ✅ |
| 14 | `/api/view/<hash>` | GET | 直接 `<a>` 链接 | 无 | HTML 页面 | 用户点击"查看" | ✅ |
| 15 | `/api/download/<hash>` | GET | 直接 `<a>` 链接 | 无 | 文件下载 | 用户点击"下载" | ✅ |

文件管理流程：
1. 加载文件列表，按类别分组显示
2. 支持批量选择、批量删除（并发 fetch DELETE）
3. 拖拽上传（支持递归文件夹遍历 `webkitGetAsEntry`）
4. 支持 CSV 导出（前端生成，无需 API）
5. 查看/下载通过直接链接（非 API 调用的 JSON 格式）

---

### 2.8 管理面板

#### 2.8.1 系统概览

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 16 | `/api/admin/metrics-summary` | GET | `js/admin.js` `loadOverview()` | 无 | `{chunks, latency_p50_ms, error_rate, uptime_hours, latency_p95_ms, latency_p99_ms, cache_hit_rate}` | 切换到概览页面 | ✅ |

#### 2.8.2 评测报告

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 17 | `/api/evaluation/overview` | GET | `js/admin.js` `loadEval()` | 无 | `{search_stats: {total_searches, avg_results, avg_latency_ms, zero_result_rate, p50_latency_ms}, rag_eval: {available, test_cases, hint}, test_cases_count, generated_at}` | 切换到评测页面 | ✅ |

#### 2.8.3 Feature Flags

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 18 | `/api/feature-flags` | GET | `js/admin.js` `loadFlags()` | 无 | `{flags: {name: value}, defaults: {name: value}}` | 切换到 Flags 页面 | ✅ |
| 19 | `/api/feature-flags/<name>` | PUT | `js/admin.js` `toggleFlag()` | `{value: true/false}` | (ok) | 用户切换开关 | ✅ |

#### 2.8.4 用户反馈

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 20 | `/api/feedback/weekly` | GET | `js/admin.js` `loadFeedback()` | 无 | `[{timestamp, query, rating, feedback}]` 或 `{feedbacks: [...]}` | 切换到反馈页面 | ⚠️ 注1 |

> 注1: 前端尝试兼容多种响应格式：数组、`{feedbacks}`, `{items}`, `{feedback_list}`, `{message}` — 说明后端响应格式可能不统一。

#### 2.8.5 系统状态（四象+器官）

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 21 | `/api/symbols/status` | GET | `js/admin.js` `loadSymbols()` | 无 | `{symbols: {shaoyang:{alive,status}, ...}, organs: {organId:{alive,emoji,name}, ...}}` | 切换到系统状态页面 | ⚠️ 注2 |

> 注2: 此端点调用使用了 try-catch 静默失败，可能后端不稳定或尚未完全实现。

#### 2.8.6 成长面板

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 22 | `/api/growth/overview` | GET | `js/admin.js` `loadGrowth()` | 无 | `{symbols: {shaoyang:{metrics,event_count}, ...}, total_events, phase, trend: [{date,query_count,...}]}` | 切换到成长面板页面 | ⚠️ 注3 |

> 注3: 使用 try-catch 静默失败 `overview = {}`，趋势图降级显示"数据将自动积累"。

#### 2.8.7 服务管理

| # | URL | 方法 | 调用位置 | 请求参数 | 期望响应 | 调用时机 | 状态 |
|---|---|---|---|---|---|---|---|
| 23 | `/api/services` | GET | `js/services.js` `loadServices()` | 无 | `[{id, name, status, service_type, version, api_prefix, description, registered_at, ...}]` | 切换到服务管理页面 | ✅ |
| 24 | `/api/services/<id>` | GET | `js/services.js` `showServiceDetail()` | 无 | `{id, name, version, service_type, status, api_prefix, description, capabilities[], ...}` | 用户点击"详情" | ✅ |
| 25 | `/api/services/<id>/start` | POST | `js/services.js` `toggleService()` | 无 | (ok) | 用户点击"启动" | ✅ |
| 26 | `/api/services/<id>/stop` | POST | `js/services.js` `toggleService()` | 无 | (ok) | 用户点击"停止" | ✅ |

---

## 三、Vue3 迁移版前端 API 调用明细

### 3.1 认证 API (`vue3-migration/src/api/auth.ts`)

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| A1 | `/api/auth/login` | POST | 登录（比 legacy 多传 `role` 字段，响应格式不同） | ⚠️ 注4 |
| A2 | `/api/auth/refresh` | POST | Token 刷新 | ✅ |
| A3 | `/api/auth/logout` | POST | 退出登录 | ✅ |

> 注4: Legacy 版 `auth.js` 调用 `POST /api/auth/login` 传 `{username, password}`，Vue3 版 `auth.ts` 多传了 `role` 字段。后端可能不处理或不返回 `role` 字段 — 这可能是路径不匹配。

### 3.2 Chat API (`vue3-migration/src/api/chat.ts`)

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| C1 | `/api/chat/sessions` | GET | 获取会话列表 | ⚠️ 注5 |
| C2 | `/api/chat/sessions` | POST | 创建会话 | ⚠️ 注5 |
| C3 | `/api/chat/sessions/<id>` | DELETE | 删除会话 | ⚠️ 注5 |
| C4 | `/api/chat/send` | POST | 发送消息（转为模拟流式输出） | ❌ 注6 |
| C5 | `/api/antenna/search` | GET | 天线联网搜索 | ⚠️ 注7 |
| C6 | mock | - | `MOCK_STREAM_CONTENT` 硬编码兜底文本 | 🆕 |

> 注5: Legacy 版没有会话管理（`/api/chat` 直接对话），Vue3 版新增了会话管理端点。需确认后端是否已实现 `/api/chat/sessions`。  
> 注6: `POST /api/chat/send` 与 Legacy 的 `POST /api/chat` 完全不同 — 路径不同、参数不同（`{query} vs {query, session_id, ...}`）。后端可能只有 `/api/chat` 而没有 `/api/chat/send`。  
> 注7: Legacy 用 `POST /api/antenna/search`，Vue3 用 `GET /api/antenna/search?q=xxx` — HTTP 方法不同。

### 3.3 搜索 API (`vue3-migration/src/api/rag.ts`)

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| R1 | `/api/rag/search` | POST | 传统 RAG 检索 | ⚠️ 注8 |
| R2 | `/api/rag/sag-search` | POST | SAG Event 粒度检索 | ❌ 注9 |
| R3 | `/api/rag/entity-expand` | GET | 实体向量扩展 | ❌ 注9 |
| R4 | `/api/rag/sag-trace` | POST | SAG 检索追踪 SSE 流 | ❌ 注9 |

> 注8: Legacy 用 `GET /api/search?q=xxx`，Vue3 用 `POST /api/rag/search` — 路径和方法都不同。  
> 注9: 这些是新增的高级功能端点，Legacy 版完全不使用。需要确认后端是否实现。

### 3.4 统一搜索 API

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| U1 | `/api/search` | GET | 传统搜索（与 legacy 一致） | ✅ |
| U2 | `/api/unified-search` | GET | 伏羲令统一搜索 | ❌ 注10 |

> 注10: `/api/unified-search` 是新增端点，Legacy 未使用。需要确认后端是否实现。

### 3.5 Wiki API (`vue3-migration/src/api/wiki.ts`)

| # | URL | 方法 | 说明 | Legacy 对应 | 状态 |
|---|---|---|---|---|---|
| W1 | `/api/wiki` | GET | 获取 Wiki 页面列表 | `/api/wiki/pages` | ⚠️ 注11 |
| W2 | `/api/wiki/<id>` | GET | 获取单个 Wiki 页面 | `/api/wiki/page/<id>` | ⚠️ 注11 |
| W3 | `/api/wiki` | POST | 创建 Wiki 页面 | 无 | 🆕 |
| W4 | `/api/wiki/<id>` | PUT | 更新 Wiki 页面 | 无 | 🆕 |

> 注11: Legacy 用 `/api/wiki/pages` 和 `/api/wiki/page/<id>`（有 `pages`/`page` 前缀），Vue3 用 `/api/wiki` 和 `/api/wiki/<id>`（RESTful 风格）。这是典型的 API 版本差异，可能不兼容。

### 3.6 文件 API (`vue3-migration/src/api/files.ts`)

| # | URL | 方法 | 说明 | Legacy 对应 | 状态 |
|---|---|---|---|---|---|
| F1 | `/api/files` | GET | 获取文件列表 | `/api/documents` | ⚠️ 注12 |
| F2 | `/api/files/upload` | POST | 上传文件 | `/api/upload` | ⚠️ 注12 |
| F3 | `/api/files/<id>` | DELETE | 删除文件 | `/api/documents/<hash>` | ⚠️ 注12 |
| F4 | `/api/files/<id>/download` | GET | 下载文件 | `/api/download/<hash>` | ⚠️ 注12 |

> 注12: Legacy 用 `/api/documents`, `/api/upload`, `/api/download`, `/api/view` — Vue3 用 RESTful 风格 `/api/files/...`。路径完全不兼容。

### 3.7 管理 API

| # | URL | 方法 | 说明 | Legacy 对应 | 状态 |
|---|---|---|---|---|---|
| AD1 | `/api/admin/metrics-summary` | GET | 管理员指标 | 相同 | ✅ |
| AD2 | `/api/admin/users` | GET | 用户列表 | 无 | 🆕 |
| AD3 | `/api/admin/users` | POST | 创建用户 | 无 | 🆕 |
| AD4 | `/api/admin/users/<id>` | PUT | 更新用户 | 无 | 🆕 |
| AD5 | `/api/admin/users/<id>` | DELETE | 删除用户 | 无 | 🆕 |
| AD6 | `/api/health` | GET | 健康检查 | 无 | 🆕 注13 |
| AD7 | `/api/dashboard` | GET | 仪表板 | 无 | 🆕 |

> 注13: Admin 面板的 `admin-worldtree-v20.js` 也调用了 `/api/health`。

### 3.8 评测/进化 API

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| E1 | `/api/evaluation/overview` | GET | 评测概览（与 legacy 一致） | ✅ |
| E2 | `/api/evaluation/datasets` | GET | 评测数据集（后端暂无，注释写 501） | ❌ |
| E3 | `/api/evaluation` | POST | 创建评测 | ❌ |
| E4 | `/api/evaluation/tasks` | GET | 评测任务列表 | ❌ |
| E5 | `/api/evaluation/results` | GET | 评测结果 | ❌ |
| E6 | `/api/eval/run` | POST | 运行评测 | ❌ |
| E7 | `/api/eval/report` | GET | 评测报告 | ❌ |
| E8 | `/api/eval/history` | GET | 评测历史 | ❌ |
| EV1 | `/api/evolution/overview` | GET | 进化概览 | ❌ |
| EV2 | `/api/evolution/overview` | GET | (废弃别名，同 EV1) | ❌ |

### 3.9 反馈/审计/用户 API

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| FB1 | `/api/feedback/weekly` | GET | 每周反馈（与 legacy 一致） | ✅ |
| FB2 | `/api/feedback` | POST | 提交反馈 | ✅ |
| AU1 | `/api/audit/logs` | GET | 审计日志 | ❌ |
| AU2 | `/api/audit/stats` | GET | 审计统计 | ❌ |
| UP1 | `/api/user/preferences` | GET | 用户偏好 | ❌ |
| UP2 | `/api/user/preferences` | PUT | 更新用户偏好 | ❌ |

### 3.10 KB 知识库 API (`vue3-migration/src/api/kb.ts`)

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| KB1 | `/api/kb/search` | POST | 知识库搜索 | ❌ |
| KB2 | `/api/kb/documents` | GET | 知识库文档列表 | ❌ |

---

## 四、Admin 面板独立 API 调用

**文件**: `admin/js/admin-worldtree-v20.js`

| # | URL | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| WT1 | `/api/worldtree/wiki/tree` | GET | Wiki 四级树 | ❌ 注14 |
| WT2 | `/api/worldtree/wiki/<id>` | GET | 单个 Wiki 页面详情 | ❌ |
| WT3 | `/api/worldtree/entities` | GET | 知识图谱实体列表 | ❌ |
| WT4 | `/api/worldtree/relations?entity_id=<id>` | GET | 实体关联关系 | ❌ |
| WT5 | `/api/worldtree/entity/<id>/wiki` | GET | 实体关联的 Wiki 页面 | ❌ |
| WT6 | `/api/worldtree/stats` | GET | 世界树统计信息 | ❌ |
| WT7 | `/api/worldtree/terms?limit=2000` | GET | 术语库 | ❌ |
| WT8 | `/api/documents?limit=500` | GET | 文档列表（管理视图） | ✅ |
| WT9 | `/api/documents?page=1&limit=500` | GET | 文档分页 | ✅ |
| WT10 | `/api/documents/<hash>` | GET | 文档详情 | ✅ |
| WT11 | `/api/files` | GET | 文件列表（备用） | ⚠️ 注12 |
| WT12 | `/api/upload` | POST | 上传文件 | ✅ |
| WT13 | `/api/health` | GET | 健康检查（多处调用） | ✅ |
| WT14 | `/api/admin/server-status` | GET | 服务器状态 | ❌ |
| WT15 | `/api/evaluation/overview?days=7` | GET | 评测概览（7天） | ✅ |
| WT16 | `/api/evolution/overview?days=30` | GET | 进化概览（30天） | ❌ |

> 注14: `/api/worldtree/*` 系列是新体系，所有端点以 `worldtree` 为前缀，从 `worldtree.db` 读取。这些完全独立于 Legacy 和 Vue3 版本的 API。需确认后端是否实现。

---

## 五、微服务 API 调用

### 5.1 AI 工具集 (`/api/ai/*`)

| # | URL | 方法 | Mock 兜底 | 状态 |
|---|---|---|---|---|
| AI1 | `/api/ai/health` | GET | ✅ | 🆕 |
| AI2 | `/api/ai/summarize` | POST | ✅ | 🆕 |
| AI3 | `/api/ai/translate` | POST | ✅ | 🆕 |
| AI4 | `/api/ai/keywords` | POST | ✅ | 🆕 |
| AI5 | `/api/ai/entities` | POST | ✅ | 🆕 |
| AI6 | `/api/ai/classify` | POST | ✅ | 🆕 |

### 5.2 文档工具集 (`/api/tools/*`)

| # | URL | 方法 | Mock 兜底 | 状态 |
|---|---|---|---|---|
| DT1 | `/api/tools/health` | GET | ✅ | 🆕 |
| DT2 | `/api/tools/convert` | POST | ✅ | 🆕 |
| DT3 | `/api/tools/merge` | POST | ✅ | 🆕 |
| DT4 | `/api/tools/split` | POST | ✅ | 🆕 |
| DT5 | `/api/tools/compress` | POST | ✅ | 🆕 |
| DT6 | `/api/tools/image-info` | POST | ✅ | 🆕 |
| DT7 | `/api/tools/text-extract` | POST | ✅ | 🆕 |

### 5.3 数据分析 (`/api/analytics/*`)

| # | URL | 方法 | Mock 兜底 | 状态 |
|---|---|---|---|---|
| DA1 | `/api/analytics/health` | GET | ✅ | 🆕 |
| DA2 | `/api/analytics/stats` | GET | ✅ | 🆕 |
| DA3 | `/api/analytics/trends?period=` | GET | ✅ | 🆕 |
| DA4 | `/api/analytics/report` | POST | ✅ | 🆕 |
| DA5 | `/api/analytics/storage` | GET | ✅ | 🆕 |
| DA6 | `/api/analytics/export` | POST | ✅ | 🆕 |

### 5.4 DXF 查看器 (`/api/dxf/*`)

| # | URL | 方法 | Mock 兜底 | 状态 |
|---|---|---|---|---|
| DXF1 | `/api/dxf/health` | GET | ✅ | 🆕 |
| DXF2 | `/api/dxf/files` | GET | ✅ | 🆕 |
| DXF3 | `/api/dxf/files/upload` | POST | ✅ | 🆕 |
| DXF4 | `/api/dxf/files/<hash>/render` | GET | ✅ | 🆕 |
| DXF5 | `/api/dxf/files/<hash>/download` | GET | ❌ (返回 null) | 🆕 |

---

## 六、硬编码 Mock 数据汇总

### 6.1 完全硬编码的假数据

| 文件 | 变量/函数 | 内容 | 影响范围 |
|---|---|---|---|
| `js/wiki.js` | `_wikiCategories` | 9 个分类 × 每组 5-10 个关键词，共 ~80 个关键词 | Wiki 分类逻辑完全在前端 |
| `js/wiki.js` | `_catIcons` / `_catColors` | 每个分类的图标和颜色 | Wiki 视觉呈现 |
| `vue3-migration/src/api/chat.ts` | `MOCK_STREAM_CONTENT` | 硬编码的兜底回复文本 | Vue3 聊天当 API 失败时 |
| `vue3-migration/src/api/symbols.ts` | `getMockUnifiedSearch()` | 18 条假搜索结果 | 伏羲令搜索兜底 |

### 6.2 Mock 文件（API 不可用时的降级方案）

| 文件 | 函数 | 覆盖端点 |
|---|---|---|
| `vue3-migration/src/services/ai-tools/mock.ts` | `mockAiToolsResponse` | `/api/ai/health, summarize, translate, keywords, entities, classify` |
| `vue3-migration/src/services/doc-tools/mock.ts` | `mockDocToolsResponse` | `/api/tools/convert, merge, split, compress, image-info, text-extract` |
| `vue3-migration/src/services/data-analytics/mock.ts` | `mockAnalyticsResponse` | `/api/analytics/stats, trends, report, storage, export` |
| `vue3-migration/src/services/dxf-viewer/mock.ts` | `mockDxfResponse` | `/api/dxf/files, render` — 含完整几何数据（矩形、圆、线、文字） |

### 6.3 前端逻辑中的数据生成

| 文件 | 函数 | 说明 |
|---|---|---|
| `js/files.js` | `exportCSV()` | 前端从 `_filesData` 生成 CSV，不调用 API |
| `js/admin.js` | `loadGrowth()` 中的趋势图 | 使用前端 Chart.js，数据来自 `/api/growth/overview` |
| `js/wiki.js` | `_classifyWikiPage()` | 基于前端硬编码关键词表进行文本分类 |
| `js/wiki.js` | `_extractToc()` / `_addHeadingIds()` | 前端从 Markdown 提取 TOC 并修改 DOM |

---

## 七、路径不匹配汇总（⚠️ 标记）

以下是在 Legacy 和 Vue3 版本之间使用不同 URL 路径调用同一后端功能的冲突情况：

| 功能 | Legacy URL | Vue3 URL | 建议 |
|---|---|---|---|
| 聊天对话 | `POST /api/chat` | `POST /api/chat/send` | 统一为 `/api/chat` |
| 聊天会话 | 无 | `GET/POST/DELETE /api/chat/sessions[/*]` | 需后端实现 |
| 知识搜索 | `GET /api/search?q=` | `POST /api/rag/search` | 统一保留 `/api/search` |
| Wiki 列表 | `GET /api/wiki/pages` | `GET /api/wiki` | 统一为 RESTful `/api/wiki` |
| Wiki 单页 | `GET /api/wiki/page/<id>` | `GET /api/wiki/<id>` | 统一为 RESTful `/api/wiki/<id>` |
| 文件列表 | `GET /api/documents` | `GET /api/files` | 统一选一个 |
| 文件上传 | `POST /api/upload` | `POST /api/files/upload` | 统一选一个 |
| 文件删除 | `DELETE /api/documents/<hash>` | `DELETE /api/files/<id>` | 统一选一个 |
| 文件下载 | `GET /api/download/<hash>` | `GET /api/files/<id>/download` | 统一选一个 |
| 联网搜索 | `POST /api/antenna/search` | `GET /api/antenna/search?q=` | 统一方法 |
| 登录参数 | `{username, password}` | `{username, password, role}` | 后端需兼容 |

---

## 八、端点状态总览

### 8.1 ✅ 确认可用（前后端匹配）

| # | 端点 | 用途 | 来源 |
|---|---|---|---|
| 1 | `POST /api/auth/login` | 登录 | legacy + vue3 |
| 2 | `GET /api/auth/me` | 验证 token | legacy |
| 3 | `POST /api/auth/refresh` | 刷新 token | vue3 |
| 4 | `POST /api/auth/logout` | 退出登录 | vue3 |
| 5 | `POST /api/chat` | 对话 | legacy |
| 6 | `POST /api/antenna/search` | 联网搜索 | legacy |
| 7 | `GET /api/search` | 知识搜索 | legacy + vue3 |
| 8 | `GET /api/graph` | 知识图谱 | legacy |
| 9 | `GET /api/wiki/pages` | Wiki 列表 | legacy |
| 10 | `GET /api/wiki/page/<id>` | Wiki 单页 | legacy |
| 11 | `GET /api/documents` | 文件列表 | legacy + admin |
| 12 | `POST /api/upload` | 文件上传 | legacy + admin |
| 13 | `DELETE /api/documents/<hash>` | 文件删除 | legacy |
| 14 | `GET /api/view/<hash>` | 查看原文 | legacy |
| 15 | `GET /api/download/<hash>` | 文件下载 | legacy |
| 16 | `GET /api/admin/metrics-summary` | 管理员指标 | legacy + vue3 |
| 17 | `GET /api/evaluation/overview` | 评测概览 | legacy + vue3 |
| 18 | `GET/PUT /api/feature-flags[/*]` | Feature Flags | legacy + vue3 |
| 19 | `GET /api/feedback/weekly` | 反馈汇总 | legacy + vue3 |
| 20 | `GET /api/symbols/status` | 四象状态 | legacy |
| 21 | `GET /api/growth/overview` | 成长面板 | legacy + vue3 |
| 22 | `GET/POST /api/services[/*]` | 服务管理 | legacy |
| 23 | `GET /api/health` | 健康检查 | admin + vue3 |
| 24 | `POST /api/feedback` | 提交反馈 | vue3 |

### 8.2 ❌ 前端调用但后端可能不存在

| # | 端点 | 用途 | 来源 |
|---|---|---|---|
| 1 | `POST /api/chat/send` | 对话发送 | vue3 |
| 2 | `GET/POST/DELETE /api/chat/sessions[/*]` | 会话管理 | vue3 |
| 3 | `POST /api/rag/search` | RAG 检索 | vue3 |
| 4 | `POST /api/rag/sag-search` | SAG 检索 | vue3 |
| 5 | `GET /api/rag/entity-expand` | 实体扩展 | vue3 |
| 6 | `POST /api/rag/sag-trace` | SAG 追踪 SSE | vue3 |
| 7 | `GET /api/unified-search` | 统一搜索 | vue3 |
| 8 | `GET /api/evaluation/datasets` | 评测数据集 | vue3 |
| 9 | `POST /api/evaluation` | 创建评测 | vue3 |
| 10 | `GET /api/evaluation/tasks` | 评测任务 | vue3 |
| 11 | `GET /api/evaluation/results` | 评测结果 | vue3 |
| 12 | `POST /api/eval/run` | 运行评测 | vue3 |
| 13 | `GET /api/eval/report` | 评测报告 | vue3 |
| 14 | `GET /api/eval/history` | 评测历史 | vue3 |
| 15 | `GET /api/evolution/overview` | 进化概览 | vue3 + admin |
| 16 | `GET /api/audit/logs` | 审计日志 | vue3 |
| 17 | `GET /api/audit/stats` | 审计统计 | vue3 |
| 18 | `GET/PUT /api/user/preferences` | 用户偏好 | vue3 |
| 19 | `POST /api/kb/search` | 知识库搜索 | vue3 |
| 20 | `GET /api/kb/documents` | 知识库文档 | vue3 |
| 21 | `GET /api/worldtree/wiki/tree` | WorldTree Wiki树 | admin |
| 22 | `GET /api/worldtree/wiki/<id>` | WorldTree Wiki详情 | admin |
| 23 | `GET /api/worldtree/entities` | WorldTree 实体 | admin |
| 24 | `GET /api/worldtree/relations` | WorldTree 关系 | admin |
| 25 | `GET /api/worldtree/entity/<id>/wiki` | WorldTree 关联Wiki | admin |
| 26 | `GET /api/worldtree/stats` | WorldTree 统计 | admin |
| 27 | `GET /api/worldtree/terms` | WorldTree 术语 | admin |
| 28 | `GET /api/admin/server-status` | 服务器状态 | admin |
| 29 | `GET /api/dashboard` | 仪表板 | vue3 |
| 30 | `GET /api/admin/users` | 用户列表 | vue3 |
| 31 | `POST /api/admin/users` | 创建用户 | vue3 |
| 32 | `PUT /api/admin/users/<id>` | 更新用户 | vue3 |
| 33 | `DELETE /api/admin/users/<id>` | 删除用户 | vue3 |

### 8.3 🆕 微服务 API（前端有完整 mock 降级方案）

| # | 端点 | 来源 |
|---|---|---|
| 1 | `/api/ai/health, summarize, translate, keywords, entities, classify` | ai-tools service |
| 2 | `/api/tools/health, convert, merge, split, compress, image-info, text-extract` | doc-tools service |
| 3 | `/api/analytics/health, stats, trends, report, storage, export` | data-analytics service |
| 4 | `/api/dxf/health, files, files/upload, files/<id>/render, files/<id>/download` | dxf-viewer service |

以上 4 个微服务端点组，每个都有完整的 mock 兜底方案，在 `vue3-migration/src/services/*/mock.ts` 中实现。

### 8.4 ⚠️ 路径不匹配需统一

| # | 功能 | Legacy 端点 | Vue3 端点 | 建议 |
|---|---|---|---|---|
| 1 | 聊天对话 | `POST /api/chat` | `POST /api/chat/send` | 统一为 `/api/chat` |
| 2 | 聊天会话 | 无 | `GET/POST/DELETE /api/chat/sessions` | 后端需实现 |
| 3 | 知识搜索 | `GET /api/search` | `POST /api/rag/search` | 统一用 `/api/search` |
| 4 | Wiki 列表 | `/api/wiki/pages` | `/api/wiki` | 统一 RESTful |
| 5 | Wiki 单页 | `/api/wiki/page/<id>` | `/api/wiki/<id>` | 统一 RESTful |
| 6 | 文件列表 | `/api/documents` | `/api/files` | 统一选一个 |
| 7 | 文件上传 | `/api/upload` | `/api/files/upload` | 统一选一个 |
| 8 | 文件删除 | `/api/documents/<hash>` | `/api/files/<id>` | 统一选一个 |
| 9 | 联网搜索 | `POST /api/antenna/search` | `GET /api/antenna/search` | 统一方法 |

---

## 九、关键发现与风险

### 9.1 🔴 高风险问题

1. **双版本路径分裂**：Legacy 生产版和 Vue3 迁移版使用了不同 API 路径（如 `/api/documents` vs `/api/files`），迁移时需更新所有路径或保持后端同时兼容。

2. **Vue3 版调用大量未实现端点**：`/api/chat/send`, `/api/rag/*`, `/api/worldtree/*`, `/api/eval/*` 等约 30+ 个端点可能后端不存在。Vue3 前端虽有 mock 降级，但部署到生产时可能导致功能缺失。

3. **Wiki 分类完全依赖前端硬编码**：`_wikiCategories` 包含 9 类约 80 个关键词的硬编码映射表，后端可能不知道这些分类逻辑，导致前后端分类不一致。

4. **认证参数不一致**：Legacy 版登录不传 `role` 字段，Vue3 版传了。如果后端不处理 `role`，可能被忽略或报错。

### 9.2 🟡 中风险问题

1. **文件管理端点命名混乱**：存在三套：`/api/documents`, `/api/files`, `/api/upload`, `/api/download`, `/api/view` — 非 RESTful，不利于维护。

2. **HTTP 方法混用**：同一个 `/api/antenna/search`，Legacy 用 POST，Vue3 用 GET。

3. **响应格式不统一**：`/api/feedback/weekly` 前端做了 5 种格式兼容（数组、`{feedbacks}`, `{items}`, `{feedback_list}`, `{message}`），说明后端响应格式可能不稳定。

4. **Symbols/Status 端点不稳定**：`loadSymbols()` 使用了静默的 try-catch，可能后端 `/api/symbols/status` 偶发故障。

### 9.3 🟢 低风险问题

1. **admin-worldtree-v20.js 是独立管理面板**：使用了完全不同的 `/api/worldtree/*` 命名空间，与主前端系统正交，不冲突。

2. **微服务 mock 覆盖完整**：4 个微服务 (AI/Tools/Analytics/DXF) 都有完整的 mock 实现，API 不可用时不影响前端 UI 展示。

---

## 十、建议

1. **立即行动**：以 Legacy 生产版端点为准，更新 Vue3 版 API 路径使之一致
2. **短期**：与后端团队确认 `/api/chat/send`, `/api/rag/*`, `/api/worldtree/*` 的实现状态
3. **中期**：统一文件管理 API 为 RESTful 风格（如 `/api/files`，支持 CRUD）
4. **长期**：将 Wiki 分类逻辑移至后端，用数据库管理分类而非前端硬编码

---

*审计完成。如需查看具体代码行，请参考原始源文件。*