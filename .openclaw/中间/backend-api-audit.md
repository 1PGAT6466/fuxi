# 伏羲系统后端 API 完整审计报告

> **审计日期**: 2026-07-09  
> **系统版本**: 伏羲 v1.50  
> **审计范围**: `src/api/` + `src/server.py` + `src/services/*/routes.py`  
> **工作目录**: `E:\easyclaw\伏羲-v1.44\repo\`  
> **状态**: 第一阶段摸底，不改代码

---

## 一、认证模块 (Auth)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 1 | POST | `/api/auth/login` | 用户登录，签发JWT | `{username, password}` (JSON) | `{token, username, role, display_name}` | 否 (白名单) | ✅ Vue3 auth.ts / auth.js | auth_routes.py |
| 2 | POST | `/api/auth/register` | 用户注册 | `{username, password}` (JSON) | `{ok, username}` | 否 (白名单) | ❌ 前端未调用 | auth_routes.py |
| 3 | POST | `/api/auth/refresh` | JWT Token 刷新 | `{token?}` + Header `Authorization: Bearer <token>` | `{token, username, role}` | 是 (token验证) | ✅ Vue3 auth.ts | auth_routes.py |
| 4 | POST | `/api/auth/logout` | 用户登出（无状态JWT，占位） | 无（从Header取token） | `{ok, message}` | 是 | ✅ Vue3 auth.ts | auth_routes.py |
| 5 | GET | `/api/auth/me` | 获取当前用户信息 | 无（从AuthMiddleware注入） | `{username, role}` | 是 | ✅ init-app.js | server.py |

---

## 二、知识库模块 (KB / Documents)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 6 | GET | `/api/documents` | 文档列表（从chunks聚合） | `?page=1&page_size=50` | `{files, total, page, page_size}` | 是 | ✅ files.js | documents.py |
| 7 | GET | `/api/files` | 文档列表别名（前端Files.vue） | `?page=1&page_size=50` | `{files, total, page, page_size}` | 是 | ✅ files.ts | files_alias.py |
| 8 | POST | `/api/upload` | 文件上传（通过少阳管道消化） | `multipart/form-data: file` | `{status, file_name, chunks, duration_ms}` | 是 | ✅ files.js | documents.py |
| 9 | POST | `/api/files/upload` | 文件上传别名 | `multipart/form-data: file` | `{status, file_name, chunks, duration_ms}` | 是 | ✅ files.ts | files_alias.py |
| 10 | DELETE | `/api/documents/{file_hash}` | 删除文档（chunks+向量+物理文件） | Path: file_hash | `{status, file_name, chunks_removed}` | 是 | ✅ files.js | documents.py |
| 11 | DELETE | `/api/files/{file_id}` | 删除文件别名 | Path: file_id | `{status, message, chunks_removed}` | 是 | ✅ files.ts | files_alias.py |
| 12 | PUT | `/api/files/{file_id}` | 更新文件元数据 | `{file_name?, category?, tags?}` | `{ok, chunks_updated}` | 是 | ❌ 前端未调用 | files_alias.py |
| 13 | PUT | `/api/documents/{doc_id}/visibility` | 修改文档可见性 | `{visibility, team_id?}` (JSON) | `{status, doc_id, visibility}` | 是 | ❌ 前端未调用 | documents.py |
| 14 | POST | `/api/kb/search` | 知识库语义搜索 | `{query, top_k, mode}` (JSON) | `{results, total}` | 是 | ✅ kb.ts | kb.py |
| 15 | GET | `/api/kb/documents` | 知识库文档列表（聚合视图） | 无 | `{documents, total}` | 是 | ✅ kb.ts | kb.py |

---

## 三、对话模块 (Chat)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 16 | POST | `/api/chat` | AI对话（v1/v2双引擎） | `{query, history[], stream?, granularity?}` + `?engine=v1\|v2` | `{answer, sources, mode, confidence}` | 是 | ✅ chat.js | chat.py |
| 17 | POST | `/api/chat/agent` | Agent对话端点（同chat） | `{query, history[]}` (JSON) | `{answer, sources, mode, confidence}` | 是 | ❌ 前端未调用 | chat.py |
| 18 | GET | `/api/chat/sessions` | 获取会话列表 | 无（从token取user） | `{sessions[], total}` | 是 | ✅ chat.ts | chat.py |
| 19 | POST | `/api/chat/sessions` | 创建新会话 | `{title?}` (JSON) | `{id, title, created_at, message_count}` | 是 | ✅ chat.ts | chat.py |
| 20 | DELETE | `/api/chat/sessions/{session_id}` | 删除会话 | Path: session_id | `{ok, message}` | 是 | ✅ chat.ts | chat.py |
| 21 | POST | `/api/chat/send` | 发送消息（支持SSE流式） | `{session_id?, query, history[], stream?, granularity?}` | JSON 或 SSE流 | 是 | ✅ chat.ts | chat.py |
| 22 | GET | `/api/chat/sessions/{session_id}/messages` | 获取会话历史消息 | Path: session_id | `{session_id, messages[], total}` | 是 | ❌ 前端未直接调用 | chat.py |

---

## 四、八卦子系统 (Bagua / Health)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 23 | GET | `/api/health` | 健康检查（支持legacy/v2/extended格式） | `?format=legacy\|v2\|extended` | `{status, checks, bagua, engine}` | 否 (白名单) | ✅ dashboard.ts / symbols.ts | system_routes.py |
| 24 | GET | `/api/health/bagua` | 八卦级健康检查 | 无 | `{status, message, data}` | 是 | ❌ 前端未调用 | system_routes.py |
| 25 | GET | `/api/health/infra` | 基础设施健康检查 | 无 | `{status, message, data}` | 是 | ❌ 前端未调用 | system_routes.py |
| 26 | GET | `/api/health/alerts` | 告警规则评估 | 无 | `{status, message, data: {alerts, count}}` | 是 | ❌ 前端未调用 | system_routes.py |
| 27 | GET | `/api/health/alert-rules` | 告警规则列表 | 无 | `{status, message, data: {rules}}` | 是 | ❌ 前端未调用 | system_routes.py |
| 28 | GET | `/api/v2/status` | v2八卦体系状态 | 无 | `{status: "ok"}` | 否 (白名单) | ❌ 前端未调用 | v2_routes.py |
| 29 | GET | `/api/symbols/status` | 四象状态 | 无 | `{symbols, summary}` | 是 | ✅ admin.js | server.py |

---

## 五、Wiki 模块

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 30 | GET | `/api/wiki` | Wiki首页/目录 | 无 | `{ok, title, pages[], total, categories}` | 是 | ✅ wiki.ts | wiki.py |
| 31 | GET | `/api/wiki/pages` | Wiki页面列表 | `?category=&limit=50` | `{pages, total}` | 是 | ✅ wiki.js | wiki.py |
| 32 | GET | `/api/wiki/search` | Wiki全文搜索 | `?q=` | `{pages, total}` | 是 | ❌ 前端未直接调用 | wiki.py |
| 33 | GET | `/api/wiki/page/{page_id}` | Wiki页面详情 | Path: page_id | `{id, title, content, linked_pages[], ...}` | 是 | ✅ wiki.js | wiki.py |
| 34 | GET | `/api/wiki/{page_id:path}` | Wiki页面详情（路径别名） | Path: page_id | `{id, title, content, linked_pages[], ...}` | 是 | ✅ wiki.ts | wiki.py |
| 35 | POST | `/api/wiki` | 创建Wiki页面 | `{title, content, category?, tags?, sources?}` | `{ok, page, message}` | 是 | ✅ wiki.ts | wiki.py |
| 36 | PUT | `/api/wiki/{page_id}` | 更新Wiki页面 | `{content?, summary?, quality_score?}` | `{ok, page, message}` | 是 | ✅ wiki.ts | wiki.py |
| 37 | DELETE | `/api/wiki/{page_id}` | 删除Wiki页面 | Path: page_id | `{ok, message}` | 是 | ❌ 前端未调用 | wiki.py |

---

## 六、评测模块 (Evaluation)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 38 | GET | `/api/evaluation/overview` | 评测概览（占位/空） | 无 | `{search_stats, rag_eval, test_cases_count}` | 是 | ✅ evaluation.ts / admin.js | evaluation.py |
| 39 | GET | `/api/evaluation/datasets` | 评测数据集列表 | 无 | `{datasets}` | 是 | ✅ evaluation.ts | evaluation.py |
| 40 | GET | `/api/evaluation/tasks` | 评测任务列表 | 无 | `{tasks}` | 是 | ✅ evaluation.ts | evaluation.py |
| 41 | GET | `/api/evaluation/results` | 评测结果列表 | 无 | `{results, latest_report}` | 是 | ✅ evaluation.ts | evaluation.py |
| 42 | POST | `/api/evaluation` | 创建/触发评测任务 | 无必需参数 | `{ok, result}` | 是 | ✅ evaluation.ts | evaluation.py |
| 43 | POST | `/api/eval/run` | 运行每日评测（eval_automation） | 无 | `{ok, results}` | 是 | ✅ evaluation.ts | server.py |
| 44 | GET | `/api/eval/report` | 获取最新评测报告 | 无 | 报告JSON | 是 | ✅ evaluation.ts | server.py |
| 45 | GET | `/api/eval/history` | 获取评测历史 | 无 | `{history[]}` | 是 | ✅ evaluation.ts | server.py |

---

## 七、进化/反馈模块 (Evolution / Feedback)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 46 | GET | `/api/evolution/overview` | 进化概览（占位/空） | 无 | `{evolution: {}}` | 是 | ✅ evolution.ts | evolution.py |
| 47 | POST | `/api/evolution/dream-cycle/run` | 手动触发Dream Cycle消化循环 | 无 | `{ok, report}` | 是 | ❌ 前端未调用 | evolution.py |
| 48 | GET | `/api/evolution/dream-cycle/report` | 获取最新Dream Cycle日报 | 无 | `{ok, has_report, report, metadata}` | 是 | ❌ 前端未调用 | evolution.py |
| 49 | GET | `/api/evolution/dream-cycle/history` | Dream Cycle日报历史 | `?limit=30` | `{ok, total, history[]}` | 是 | ❌ 前端未调用 | evolution.py |
| 50 | GET | `/api/feedback/weekly` | 每周反馈汇总（占位/空） | 无 | `{feedbacks: []}` | 是 | ✅ feedback.ts / admin.js | feedback.py |
| 51 | POST | `/api/feedback` | 提交反馈（占位） | `{content, rating?, category?}` | `{ok}` | 是 | ✅ feedback.ts | feedback.py |

---

## 八、Feature Flags 模块

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 52 | GET | `/api/feature-flags` | 获取所有Feature Flag状态 | 无 | `{flags, defaults}` | 是 | ✅ featureFlags.ts / admin.js | server.py |
| 53 | GET | `/api/feature-flags/{name}` | 获取单个Feature Flag | Path: name | `{flag, value, default}` | 是 | ❌ 前端未调用 | server.py |
| 54 | PUT | `/api/feature-flags/{name}` | 更新Feature Flag | `{value: bool}` (JSON) | `{ok, flag, value}` | 是 | ✅ featureFlags.ts / admin.js | server.py |
| 55 | WS | `/api/feature-flags/ws` | Feature Flag变更实时WebSocket推送 | WebSocket连接 | 推送 `snapshot` / `flag_changed` 事件 | 否 | ✅ featureFlagsStore | feature_flags_ws.py |

---

## 九、文件管理模块 (View / Download)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 56 | GET | `/api/view/{file_hash}` | 查看文档（按file_hash查找） | Path: file_hash | FileResponse（直接返回文件） | 是 (安全降级到匿名) | ✅ files.js | files_view.py |
| 57 | GET | `/api/download/{file_hash}` | 下载文档 | Path: file_hash | FileResponse（Content-Disposition附件） | 是 (安全降级到匿名) | ✅ files.js | files_view.py |
| 58 | GET/POST | `/api/antenna/search` | 天线搜索（Web搜索代理） | `?q=` | `{results, query, source, message}` | 是 | ✅ chat.ts | files_view.py |
| 59 | GET | `/api/files/{file_id}/download` | 文件下载别名 | Path: file_id | FileResponse | 是 | ✅ files.ts | files_alias.py |

---

## 十、搜索模块 (Search / RAG)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 60 | GET | `/api/search` | 统一搜索（混合检索+Wiki） | `?q=&top_k=15&page=1&page_size=8&granularity=chunk` | `{wiki_results, chunk_results, results, query, total}` | 是 | ✅ search.js / unified-search.ts | search.py |
| 61 | GET | `/api/search-history` | 搜索历史（占位/空） | 无 | `[]` | 是 | ❌ 前端未调用 | search.py |
| 62 | POST | `/api/rag/search` | RAG chunk粒度检索 | `{query, top_k, mode, score_threshold}` | `{results, total}` | 是 | ✅ rag.ts | rag.py |
| 63 | POST | `/api/rag/sag-search` | SAG Event粒度检索 | `{query, top_k, granularity, score_threshold}` | `{results, events, total, granularity}` | 是 | ✅ rag.ts | rag.py |
| 64 | POST | `/api/rag/sag-trace` | SAG检索追踪（SSE流式） | `{session_id}` | SSE流 `{type, stage, message}` | 是 | ✅ rag.ts | rag.py |
| 65 | GET | `/api/rag/entity-expand` | 实体向量扩展 | `?entity_name=` | `{entity_name, expanded_entities[], total}` | 是 | ✅ rag.ts | rag.py |

---

## 十一、知识图谱模块 (Graph)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 66 | GET | `/api/graph` | 知识图谱查询 | `?entity=` | `{nodes, edges}` | 是 | ✅ graph.js | graph.py |
| 67 | GET | `/api/graph/auto-edges` | 查询自动提取的图谱边 | `?doc_id=&source=&target=&edge_type=&min_confidence=&limit=` | `{total, limit, edges[]}` | 是 | ❌ 前端未调用 | graph.py |
| 68 | GET | `/api/graph/stats` | 知识图谱统计 | 无 | `{nodes_count, edges_count, edge_type_distribution, ...}` | 是 | ❌ 前端未调用 | graph.py |
| 69 | POST | `/api/graph/rebuild-auto` | 重建指定文档的自动图谱 | `?doc_id=` | `{ok, entity_count, edge_count}` | 是 | ❌ 前端未调用 | graph.py |

---

## 十二、管理面板 (Admin)

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 70 | GET | `/api/admin/stats` | 管理统计（占位/空） | 无 | `{ok, chunks, categories}` | 是 | ❌ 前端未调用 | admin.py |
| 71 | GET | `/api/admin/server-status` | 服务器状态（uptime） | 无 | `{ok, uptime_seconds, uptime_hours}` | 是 | ❌ 前端未调用 | admin.py |
| 72 | GET | `/api/admin/status` | 服务器状态别名 | 无 | `{ok, uptime_seconds, uptime_hours}` | 是 | ❌ 前端未调用 | admin.py |
| 73 | GET | `/api/admin/documents` | 管理面板：文档统计 | 无 | `{ok, documents: {total_chunks, unique_files, categories}}` | 是 | ❌ 前端未调用 | admin.py |
| 74 | GET | `/api/admin/evaluations` | 管理面板：评测列表 | 无 | `{ok, evaluations, latest_report}` | 是 | ❌ 前端未调用 | admin.py |
| 75 | POST | `/api/admin/evaluations/run` | 管理面板：触发评测 | 无 | `{ok, result}` | 是 | ❌ 前端未调用 | admin.py |
| 76 | GET | `/api/admin/users` | 用户列表 | 无 | `{ok, users[], total}` | 是 (admin) | ✅ admin.ts | admin.py |
| 77 | POST | `/api/admin/users` | 创建用户 | `{username, password, display_name?, role?}` | `{ok, username, role, display_name}` | 是 (admin) | ✅ admin.ts | admin.py |
| 78 | PUT | `/api/admin/users/{user_id}` | 更新用户 | `{display_name?, role?, password?}` | `{ok, username}` | 是 (admin) | ✅ admin.ts | admin.py |
| 79 | DELETE | `/api/admin/users/{user_id}` | 删除用户 | Path: user_id | `{ok, message}` | 是 (admin) | ✅ admin.ts | admin.py |
| 80 | GET | `/api/admin/teams` | 团队列表 | 无 | `{ok, teams[], total}` | 是 (admin) | ❌ 前端未调用 | admin.py |
| 81 | POST | `/api/admin/teams` | 创建团队 | `{team_id, name, description?, member_ids[]?}` | `{ok, team}` | 是 (admin) | ❌ 前端未调用 | admin.py |
| 82 | GET | `/api/admin/teams/{team_id}` | 团队详情 | Path: team_id | `{ok, team}` | 是 (admin) | ❌ 前端未调用 | admin.py |
| 83 | DELETE | `/api/admin/teams/{team_id}` | 删除团队 | Path: team_id | `{ok, message}` | 是 (admin) | ❌ 前端未调用 | admin.py |
| 84 | POST | `/api/admin/teams/{team_id}/members` | 添加团队成员 | `{user_id}` | `{ok, team, message}` | 是 (admin) | ❌ 前端未调用 | admin.py |
| 85 | DELETE | `/api/admin/teams/{team_id}/members/{user_id}` | 移除团队成员 | Path: team_id, user_id | `{ok, team, message}` | 是 (admin) | ❌ 前端未调用 | admin.py |
| 86 | GET | `/api/user/teams` | 当前用户所属团队列表 | 无 | `{ok, teams[], user_id}` | 是 | ❌ 前端未调用 | admin.py |
| 87 | GET | `/api/admin/metrics-summary` | 管理员指标摘要（延迟P50/P95/P99+错误率） | 无 | 指标JSON | 是 (admin) | ✅ dashboard.ts / admin.js | server.py |

---

## 十三、通知中心 / 用户偏好 / 统一搜索

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 88 | GET | `/api/notifications` | 通知列表（占位/空） | `?page=1&page_size=20&unread_only=false` | `{notifications, unread_count, total}` | 是 | ✅ notifications.ts | notifications.py |
| 89 | PUT | `/api/notifications/{notification_id}/read` | 标记通知已读（占位） | Path: notification_id | `{ok, id, read}` | 是 | ✅ notifications.ts | notifications.py |
| 90 | PUT | `/api/notifications/read-all` | 标记全部已读（占位） | 无 | `{ok, read_all}` | 是 | ✅ notifications.ts | notifications.py |
| 91 | GET | `/api/user/preferences` | 获取用户偏好（占位） | 无 | `{preferences: {theme, language, ...}}` | 是 | ✅ user.ts | user_preferences.py |
| 92 | PUT | `/api/user/preferences` | 更新用户偏好（占位） | `{theme?, language?, ...}` | `{preferences, ok}` | 是 | ✅ user.ts | user_preferences.py |
| 93 | GET | `/api/unified-search` | 伏羲令统一搜索（占位/空） | `?q=` | `{query, matches, total, took_ms}` | 是 | ✅ symbols.ts / unified-search.ts | unified_search.py |

---

## 十四、系统/监控/审计

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 94 | GET | `/api/system/stats` | 系统资源统计 | 无 | `{cpu, memory, disk, ...}` | 是 | ❌ 前端未调用 | system_routes.py |
| 95 | GET | `/api/cache/stats` | 缓存命中率统计 | 无 | 缓存JSON | 是 | ❌ 前端未调用 | system_routes.py |
| 96 | GET | `/api/errors/stats` | 错误追踪统计 | 无 | 错误JSON | 是 | ❌ 前端未调用 | system_routes.py |
| 97 | GET | `/api/audit/logs` | 审计日志查询 | `?user=&action=&days=1&limit=100` | `{status, message, data: {entries, count}}` | 是 | ✅ audit.ts | system_routes.py |
| 98 | GET | `/api/audit/stats` | 审计日志统计 | `?days=7` | `{status, message, data}` | 是 | ✅ audit.ts | system_routes.py |
| 99 | GET | `/api/metrics` | Prometheus指标端点 | 无 | text/plain | 是 | ❌ 前端未直接调用 | server.py |
| 100 | GET | `/metrics` | Prometheus指标（直接暴露） | 无 | text/plain | 否 (白名单) | ❌ 前端未直接调用 | server.py |

---

## 十五、MCP 协议接口

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 101 | POST | `/api/mcp` | MCP JSON-RPC 2.0入口 | `{method, params, id}` | JSON-RPC Response | 是 | ❌ 前端未调用 | server.py |
| 102 | GET | `/api/mcp/tools` | 列出所有MCP工具 | 无 | `{tools: [{name, description}]}` | 是 | ❌ 前端未调用 | server.py |
| 103 | POST | `/api/mcp/sag_search` | MCP: 搜索知识库 | `{query, top_k}` | 搜索结果 | 是 | ❌ 前端未调用 | server.py |
| 104 | POST | `/api/mcp/sag_ingest` | MCP: 入库文档 | `{file_path, category}` | 入库结果 | 是 | ❌ 前端未调用 | server.py |
| 105 | POST | `/api/mcp/sag_explain` | MCP: 解释查询 | `{query}` | 解释结果 | 是 | ❌ 前端未调用 | server.py |
| 106 | GET | `/api/mcp/sag_status` | MCP: 系统状态 | 无 | 状态JSON | 是 | ❌ 前端未调用 | server.py |
| 107 | POST | `/api/mcp/call` | MCP通用工具调用（24个工具） | `{tool, args}` | `{ok, tool, result}` | 是 | ❌ 前端未调用 | server.py |

---

## 十六、合成/服务清单/仪表板/其他

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 108 | POST | `/api/synthesis/cross-entity` | 跨实体合成查询 | `{query, entity_names?, top_k?, include_graph?, mode?}` | `{query, synthesized_text, entity_groups, sources}` | 是 | ❌ 前端未调用 | synthesis.py |
| 109 | GET | `/api/synthesis/health` | Synthesis模块健康检查 | 无 | `{status, module, stats}` | 是 | ❌ 前端未调用 | synthesis.py |
| 110 | GET | `/api/services` | 服务聚合清单 | 无 | `{status, message, data: {services, total}}` | 是 | ✅ services.js | services.py |
| 111 | GET | `/api/services/{service_id}` | 单个服务详情 | Path: service_id | `{status, data}` | 是 | ✅ services.js | services.py |
| 112 | GET | `/api/dashboard` | 仪表板数据（占位/空） | 无 | `{dashboard: {}}` | 是 | ✅ dashboard.ts | dashboard.py |
| 113 | GET | `/api/metadata` | 元数据（占位/空） | 无 | `{metadata: []}` | 是 | ❌ 前端未调用 | metadata.py |
| 114 | GET | `/api/growth/overview` | 成长概览（四象指标） | 无 | `{symbols, summary, timestamp}` | 是 | ✅ growth.ts / admin.js | server.py |
| 115 | GET | `/api/proxy/loader/files` | 代理：获取装载机文件列表 | 无 | 装载机文件JSON | 是 | ❌ 前端未调用 | server.py |
| 116 | POST | `/api/proxy/loader/upload` | 代理：上传文件到装载机 | multipart/form-data | 上传结果JSON | 是 | ❌ 前端未调用 | server.py |

---

## 十七、WorldTree 模块

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 117 | GET | `/api/worldtree/stats` | WorldTree统计（占位/空） | 无 | `{wiki_pages, entities, terms}` | 是 | ❌ 前端未调用 | worldtree.py |
| 118 | GET | `/api/worldtree/terms` | 实体/术语列表 | `?limit=2000` | `{ok, terms[], total}` | 是 | ❌ 前端未调用 | worldtree.py |
| 119 | GET | `/api/worldtree/wiki/tree` | Wiki树（占位/空） | 无 | `{tree: []}` | 是 | ❌ 前端未调用 | worldtree.py |
| 120 | GET | `/api/worldtree/wiki` | Wiki树别名 | 无 | `{tree: []}` | 是 | ❌ 前端未调用 | worldtree.py |
| 121 | GET | `/api/worldtree/entities` | 实体列表（占位/空） | 无 | `{entities: []}` | 是 | ❌ 前端未调用 | worldtree.py |
| 122 | GET | `/api/worldtree/wiki/{page_id}` | WorldTree Wiki页面详情 | Path: page_id | `{ok, page}` | 是 | ❌ 前端未调用 | worldtree.py |
| 123 | GET | `/api/worldtree/entity/{entity_id}/wiki` | 实体关联Wiki页面 | Path: entity_id | `{entity_id, wiki_pages[], total}` | 是 | ❌ 前端未调用 | worldtree.py |
| 124 | GET | `/api/worldtree/relations` | WorldTree关系图数据 | `?entity_id=或?entity_name=` | `{relations[], total}` | 是 | ❌ 前端未调用 | worldtree.py |

---

## 十八、AI工具/数据分析/文档工具/DXF看图（僵尸服务）

| # | HTTP 方法 | 路径 | 功能描述 | 请求参数 | 响应格式 | 需认证 | 前端使用 | 文件来源 |
|---|-----------|------|---------|---------|---------|--------|---------|---------|
| 125 | GET | `/api/ai/health` | AI工具服务健康检查 | 无 | `{status, service, version}` | 是 | ❌ 前端未调用 | services/ai_tools/routes.py |
| 126 | POST | `/api/ai/summarize` | 文本摘要 | `{text, max_length?}` | `{summary, original_length, summary_length}` | 是 | ❌ 前端未调用 | services/ai_tools/routes.py |
| 127 | POST | `/api/ai/translate` | 文本翻译 | `{text, source_lang?, target_lang?}` | `{translation, source_lang, target_lang}` | 是 | ❌ 前端未调用 | services/ai_tools/routes.py |
| 128 | POST | `/api/ai/keywords` | 关键词提取 | `{text}` | `{keywords, count}` | 是 | ❌ 前端未调用 | services/ai_tools/routes.py |
| 129 | POST | `/api/ai/entities` | 实体识别 | `{text}` | `{entities, count, type_counts}` | 是 | ❌ 前端未调用 | services/ai_tools/routes.py |
| 130 | POST | `/api/ai/classify` | 文本分类 | `{text, categories?}` | `{category, confidence, reason}` | 是 | ❌ 前端未调用 | services/ai_tools/routes.py |
| 131 | GET/POST等 | `/api/analytics/*` | 数据分析服务（stats/trends/report/storage/export/health） | 多种 | JSON | 是 | ❌ 前端未调用 | services/data_analytics/routes.py |
| 132 | GET/POST等 | `/api/tools/*` | 文档工具服务（convert/merge/split/compress/image-info/compress-image/text-extract/health） | 多种 | JSON | 是 | ❌ 前端未调用 | services/doc_tools/routes.py |
| 133 | POST | `/api/dxf/upload` | 上传DXF/CAD文件 | multipart/form-data: file | `{status, hash, filename, entity_count}` | 是 | ❌ 前端未调用 | services/dxf_viewer/api.py |
| 134 | GET | `/api/dxf/files` | DXF文件列表 | 无 | `{files[], total}` | 是 | ❌ 前端未调用 | services/dxf_viewer/api.py |
| 135 | GET | `/api/dxf/view/{hash}` | 查看DXF渲染数据 | Path: hash | 渲染数据JSON | 是 | ❌ 前端未调用 | services/dxf_viewer/api.py |
| 136 | GET | `/api/dxf/download/{hash}` | 下载DXF文件 | Path: hash | FileResponse | 是 | ❌ 前端未调用 | services/dxf_viewer/api.py |
| 137 | GET | `/api/dxf/health` | DXF看图服务健康检查 | 无 | `{status, service, ezdxf_available}` | 是 | ❌ 前端未调用 | services/dxf_viewer/api.py |

---

## 十九、页面路由（非API）

| # | HTTP 方法 | 路径 | 功能描述 | 文件来源 |
|---|-----------|------|---------|---------|
| - | GET | `/` | 前端首页 (index.html) | server.py |
| - | GET | `/login` | 登录页 (login.html) | server.py |
| - | GET | `/admin` | 管理面板 (index.html) | server.py |
| - | GET | `/docs` | FastAPI Swagger 文档 | server.py |
| - | GET | `/redoc` | FastAPI ReDoc 文档 | server.py |
| - | GET | `/static/*` | 静态资源（Vue3构建产物） | server.py |

---

# 前端-后端 API 对照分析

## 一、✅ 前端调用 & 后端实现 匹配

以下模块 API 前后端完全匹配，运行正常：

| 模块 | 前端调用 | 后端实现 | 状态 |
|------|---------|---------|------|
| 认证 | `/api/auth/{login,refresh,logout,me}` | auth_routes.py + server.py | ✅ 正常 |
| 知识库 | `/api/kb/{search,documents}` / `/api/rag/*` | kb.py + rag.py | ✅ 正常 |
| 对话 | `/api/chat/{sessions,send}` / SSE流式 | chat.py | ✅ 正常 |
| Wiki | `/api/wiki` CRUD | wiki.py | ✅ 正常 |
| 评测 | `/api/evaluation/*` / `/api/eval/*` | evaluation.py + server.py | ✅ 正常 |
| 进化 | `/api/evolution/overview` | evolution.py | ✅ 正常 |
| 反馈 | `/api/feedback` / `/api/feedback/weekly` | feedback.py | ✅ 正常（占位实现） |
| Feature Flags | `/api/feature-flags` + WebSocket | server.py + feature_flags_ws.py | ✅ 正常 |
| 文件管理 | `/api/files` / `/api/view` / `/api/download` | files_alias.py + files_view.py + documents.py | ✅ 正常 |
| 搜索 | `/api/search` | search.py | ✅ 正常 |
| 知识图谱 | `/api/graph` | graph.py | ✅ 正常 |
| 管理面板 | `/api/admin/{users,metrics-summary}` | admin.py + server.py | ✅ 正常 |
| 仪表板 | `/api/dashboard` / `/api/health` | dashboard.py + system_routes.py | ✅ 正常 |
| 通知中心 | `/api/notifications` | notifications.py | ✅ 正常（占位实现） |
| 用户偏好 | `/api/user/preferences` | user_preferences.py | ✅ 正常（占位实现） |
| 统一搜索 | `/api/unified-search` | unified_search.py | ✅ 正常（占位实现） |
| 四象/成长 | `/api/symbols/status` / `/api/growth/overview` | server.py | ✅ 正常 |
| 审计日志 | `/api/audit/{logs,stats}` | system_routes.py | ✅ 正常 |
| 服务清单 | `/api/services` | services.py | ✅ 正常 |

## 二、🔴 前端调用路径与后端不匹配

以下为前端调用但路径与后端实现不一致的问题：

| 前端文件 | 调用路径 | 后端实际路径 | 差异 | 影响 |
|---------|---------|-------------|------|------|
| files.ts | `GET /api/files` | ✅ files_alias.py 提供 `/api/files` | 已通过别名解决 | 低 |
| files.ts | `POST /api/files/upload` | ✅ files_alias.py 提供 | 已通过别名解决 | 低 |
| files.ts | `DELETE /api/files/{id}` | ✅ files_alias.py 提供 | 已通过别名解决 | 低 |
| files.ts | `GET /api/files/{id}/download` | ✅ files_alias.py 提供 | 已通过别名解决 | 低 |
| wiki.ts | `GET /api/wiki/{id}` | ✅ wiki.py 通过 `/{page_id:path}` 提供 | 路径别名实现 | 低 |
| evaluation.ts | `GET /api/evaluation/datasets` | ✅ evaluation.py 提供 | 正常 | - |
| evaluation.ts | `GET /api/evaluation/tasks` | ✅ evaluation.py 提供 | 正常 | - |
| evaluation.ts | `GET /api/evaluation/results` | ✅ evaluation.py 提供 | 正常 | - |

## 三、⚫ 后端有但前端未调用的 API（冗余/僵尸端点）

以下端点后端已实现，但前端（Vue3+旧JS）均未调用：

| 级别 | 端点 | 说明 |
|------|------|------|
| 僵尸服务 | `/api/ai/*` (6端点) | AI工具服务：summarize/translate/keywords/entities/classify/health |
| 僵尸服务 | `/api/analytics/*` (15端点) | 数据分析服务：stats/trends/report/storage/export/health |
| 僵尸服务 | `/api/tools/*` (10端点) | 文档工具服务：convert/merge/split/compress/*/health |
| 僵尸服务 | `/api/dxf/*` (5端点) | DXF看图服务：upload/files/view/download/health |
| 待对接 | `/api/auth/register` | 用户注册，前端无注册页面 |
| 待对接 | `/api/chat/agent` | Agent对话端点 |
| 待对接 | `/api/chat/sessions/{id}/messages` | 会话历史消息查询 |
| 待对接 | `/api/evolution/dream-cycle/*` (3端点) | Dream Cycle运行/日报/历史 |
| 待对接 | `/api/graph/auto-edges` | 自动图谱边查询 |
| 待对接 | `/api/graph/stats` | 图谱统计 |
| 待对接 | `/api/graph/rebuild-auto` | 图谱重建 |
| 待对接 | `/api/synthesis/cross-entity` | 跨实体合成 |
| 待对接 | `/api/synthesis/health` | 合成健康检查 |
| 待对接 | `/api/documents/{id}/visibility` | 文档可见性 |
| 待对接 | `/api/admin/teams/*` (6端点) | 团队管理CRUD |
| 待对接 | `/api/user/teams` | 用户团队列表 |
| 待对接 | `/api/health/{bagua,infra,alerts,alert-rules}` (4端点) | 八卦/基础设施详细健康 |
| 待对接 | `/api/worldtree/*` (8端点) | WorldTree模块 |
| 待对接 | `/api/mcp/*` (7端点) | MCP协议接口 |
| 待对接 | `/api/files/{id}` (PUT) | 文件元数据更新 |
| 待对接 | `/api/wiki/search` | Wiki全文搜索 |
| 待对接 | `/api/wiki/{id}` (DELETE) | Wiki页面删除 |
| 待对接 | `/api/system/stats` | 系统资源统计 |
| 待对接 | `/api/cache/stats` | 缓存统计 |
| 待对接 | `/api/errors/stats` | 错误统计 |
| 占位实现 | `/api/notifications` | 通知中心（返回空列表） |
| 占位实现 | `/api/user/preferences` | 用户偏好（返回默认值） |
| 占位实现 | `/api/unified-search` | 伏羲令（返回空匹配） |
| 占位实现 | `/api/feedback` / `/api/feedback/weekly` | 反馈（返回空数据） |
| 占位实现 | `/api/dashboard` | 仪表板（返回空对象） |
| 占位实现 | `/api/metadata` | 元数据（返回空数组） |

## 四、🔵 前端需要但后端缺失的 API

以下为前端设计需要的端点，但后端尚未实现或仅占位：

| 优先级 | 端点 | 前端需求 | 当前状态 | 建议 |
|--------|------|---------|---------|------|
| 🔴 P0 | `/api/notifications` | 通知中心功能 | 占位（返回空列表） | 需实现通知持久化存储 |
| 🔴 P0 | `/api/user/preferences` | 用户偏好设置 | 占位（返回默认值） | 需实现用户偏好持久化 |
| 🔴 P0 | `/api/unified-search` | 伏羲令全局搜索 | 占位（返回空匹配） | 需实现跨服务搜索聚合 |
| 🟡 P1 | `/api/dashboard` | 仪表板数据 | 占位（返回空对象） | 需接入真实统计数据 |
| 🟡 P1 | `/api/feedback` | 用户反馈功能 | 占位（空操作） | 需实现反馈持久化 |
| 🟡 P1 | `/api/admin/teams` | 团队管理（Company Brain） | 后端基本就绪但前端未对接 | 前端需实现UI |
| 🟠 P2 | `/api/ai/*` | AI工具箱 | 后端已实现，无前端 | 前端需添加UI入口 |
| 🟠 P2 | `/api/analytics/*` | 数据分析 | 后端已注册，前端未对接 | 前端需添加看板 |
| 🟠 P2 | `/api/dxf/*` | DXF看图 | 后端已实现，无前端入口 | 前端需添加CAD浏览器 |
| 🟠 P2 | `/api/synthesis/cross-entity` | 跨实体合成 | 后端已实现，无前端 | 前端需添加合成查询UI |
| 🟢 P3 | `/api/evolution/dream-cycle/*` | Dream Cycle 控制面板 | 后端已实现，仅cron使用 | 前端可添加手动触发UI |
| 🟢 P3 | `/api/graph/auto-edges` + stats | 图谱探索 | 后端已实现，无前端 | 前端可添加图谱可视化 |
| 🟢 P3 | `/api/worldtree/*` | 实体知识树 | 后端基本实现 | 前端可添加WorldTree浏览器 |

---

# 安全审计摘要

## 认证机制
- ✅ JWT Token 签名与验证（HMAC-SHA256）
- ✅ AuthMiddleware 全局拦截 `/api/` 请求
- ✅ 白名单路径（login/register/health/docs/static）
- ✅ v1.50 修复：AuthMiddleware 实际验证 Token（此前仅提取未验证）
- ✅ Token 刷新机制（POST /api/auth/refresh）
- ✅ 管理员角色校验（require_admin 依赖注入）
- ⚠️ 无 Token 黑名单/吊销机制（登出仅前端清除）
- ⚠️ 文件查看/下载有安全降级到 anonymous 的逻辑

## 安全响应头
- ✅ X-Content-Type-Options: nosniff
- ✅ X-Frame-Options: DENY
- ✅ Strict-Transport-Security
- ✅ X-XSS-Protection
- ✅ Referrer-Policy

## 限流
- ✅ slowapi 全局速率限制（60/分钟）
- ✅ 登录频率限制（5次/分钟/IP）

## 已知风险
- ⚠️ CWE-306: `/api/system/stats` 已从白名单移除
- ⚠️ 用户密码在注册期间以明文传输（未在中间件层强制HTTPS）
- ⚠️ 旧密码格式 `$salt$hash` (SHA-256) 与 bcrypt 混用（有自动升级逻辑）

---

# 统计汇总

| 类别 | 数量 |
|------|------|
| **后端 API 端点总数** | **137** |
| 前端使用中（Vue3 + 旧JS） | 65 |
| 后端有但前端未调用 | 72 |
| 占位实现（返回空数据） | 12 |
| 僵尸服务端点（完整实现但无前端） | 36 |
| 需认证端点 | ~125 |
| 白名单（免认证）端点 | 8 |
| WebSocket 端点 | 1 |
| SSE 流式端点 | 2 |

---

# 改进建议（第二阶段）

1. **补全占位实现**：通知中心、用户偏好、统一搜索、仪表板、反馈系统需实现真实的持久化逻辑
2. **激活僵尸服务**：AI工具箱、数据分析、DXF看图、文档工具需添加前端UI入口
3. **清理冗余端点**：WorldTree 八个端点如无使用计划可考虑标记 deprecated
4. **安全加固**：实现 Token 黑名单、加强输入验证、添加 CORS 白名单细化
5. **API 版本化**：建议统一响应格式为 v2 标准格式（`{status, message, data}`），逐步废弃旧格式
6. **文档生成**：FastAPI 已自带 OpenAPI/Swagger，建议利用 `/docs` 和 `/redoc` 自动生成接口文档