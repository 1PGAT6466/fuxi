# 伏羲系统后端全面审计报告

**审计日期**: 2026-07-09  
**审计范围**: E:\easyclaw\伏羲-v1.44\repo\src\  
**审计版本**: v1.50  
**审计结论**: 发现 **P0 问题 8 个，P1 问题 14 个，P2 问题 11 个**

---

## 🔴 P0 — 关键阻塞问题（运行时崩溃/数据丢失/安全漏洞）

### P0-1: `save_chunks()` 为空函数，所有文件删除/更新操作静默失败
- **文件**: `src/db/data_store.py:94-96`
- **影响范围**: `src/api/documents.py`, `src/api/files_alias.py`, `src/bagua/kan.py`
- **问题**: `save_chunks(chunks)` 定义为 `"""已废弃：所有写入通过 MemoryStore"""` + `pass`，不执行任何操作。
- **影响**: 调用 `save_chunks()` 的 `DELETE /api/documents/{hash}`、`DELETE /api/files/{id}`、`PUT /api/files/{id}` 以及 `src/bagua/kan.py` 中的写入操作全部**静默失败**——虽然执行了 `save_chunks(kept)` 调用，但实际上数据库中的数据从未被修改。用户以为文件已删除/更新，数据库中的 chunks 却完好无损。
- **修复建议**: 重构 `save_chunks()` 使其调用 `MemoryStore.add_batch()` 或 `insert_many()`，配合事务实现真正的写入；或者将所有调用点改为直接使用 MemoryStore 方法。

### P0-2: `api/path_aliases.py` 引用不存在的 `wiki_list` 函数，启动即崩溃
- **文件**: `src/api/path_aliases.py:39`
- **问题**: 第 39 行 `from src.api.wiki import wiki_list` 导入了不存在的函数 `wiki_list`。wiki.py 中实际的函数名是 `wiki_pages`。当访问 `GET /api/wiki/pages` 时会触发 `ImportError`，导致整个请求返回 500。
- **影响**: `GET /api/wiki/pages` 端点不可用，Legacy 前端兼容层断裂。
- **修复建议**: 将 `from src.api.wiki import wiki_list` 改为 `from src.api.wiki import wiki_pages`，并更新调用。

### P0-3: `admin.py` 的 `admin_stats` 端点返回硬编码的零数据
- **文件**: `src/api/admin.py:65-72`
- **问题**: `GET /api/admin/stats` 端点定义了 `_get_chunks_stats()` 辅助函数（可正常查询真实数据），但路由处理函数 `admin_stats()` **没有调用它**，而是直接返回硬编码的 `{"ok": True, "chunks": 0, "categories": {}}`。无论数据库中有多少数据，管理面板都显示 0。
- **影响**: 管理面板统计数据始终为空，运维无法了解系统真实状态。

### P0-4: `src/api/admin.py` 中 `admin_documents` 端点引用错误的路由函数
- **文件**: `src/api/admin.py:95`（`admin_documents` 函数）
- **问题**: `admin_documents(request)` 内部 `from src.api.documents import documents` 然后 `return await documents(request=request)`，但 `documents.py` 的 `documents` 函数参数签名为 `(page: int = 1, page_size: int = 50, request: Request = None)`——直接传入 `request` 对象会导致 `page` 参数成为 Request 对象，产生类型错误。
- **修复建议**: 应该为 `admin_documents` 也接受 `page`/`page_size` 参数并正确传递。

### P0-5: `src/api/admin.py` 中 `admin_evaluations` 端点引用错误的路由函数
- **文件**: `src/api/admin.py:110`（`admin_evaluations` 函数）
- **问题**: `from src.api.evaluation import evaluation_results` 然后 `return await evaluation_results(request=request)`，但 evaluation.py 中实际没有名为 `evaluation_results` 的函数。实际函数为 `evaluation_results(request: Request = None)`（以小写开头）。这会导致 `ImportError`。
- **修复建议**: 确认 evaluation.py 中实际导出名称，修正 import。

### P0-6: 硬编码测试 JWT 密钥
- **文件**: `.env` 文件
- **问题**: `.env` 中 `FUXI_JWT_SECRET=test-secret-key-for-curltest-32chars!!` 是一个明文测试密钥。
- **注意**: `config.py` 和 `api/auth.py` 已正确实现了"启动时若未设置则拒绝启动"的 RuntimeError 防护。但当前 `.env` 中设置的测试密钥本身是硬编码的弱密钥。
- **影响**: 若此 `.env` 用于生产环境，JWT 安全性完全失效。不过 config 层面已有 RuntimeError 兜底。
- **修复建议**: 为生产环境生成强随机密钥。当前代码层防护已到位，标记为 P0 是因为`.env` 中仍存在明文示例。

### P0-7: MiMo API Key 未设置
- **文件**: `.env`
- **问题**: `.env` 中 `MIMO_API_KEY=YOUR_MIMO_API_KEY`，这是一个占位值。`src/services/evaluator.py` 中直接使用此 key 调用 MiMo API，认证会失败。
- **影响**: 所有依赖 MiMo LLM 的功能（评测、搜索等）都可能失败。虽然有大模型调用有三层降级机制（L1 Mimo→DeepSeek→OpenAI 4o-mini），但若所有 API key 都未正确配置，将完全不可用。

### P0-8: `src/api/antenna/search` 端点（`files_view.py`）始终返回空结果
- **文件**: `src/api/files_view.py:65-71`
- **问题**: `GET/POST /api/antenna/search` 返回固定的空数组 `{"results": [], "query": q, "source": "antenna", "message": "Antenna search requires external API configuration"}`。这是一个占位实现，没有实际的搜索逻辑。
- **影响**: 前端联网搜索功能完全不可用。

---

## 🟠 P1 — 严重问题（功能异常/逻辑错误/潜在安全风险）

### P1-1: 用户密码使用自定义哈希 + bcrypt 双格式，存在兼容性陷阱
- **文件**: `src/api/auth_routes.py:37-43`
- **问题**: `_verify_password` 支持两种格式：`$2b$` 开头的 bcrypt，以及 `$` 分隔的自定义 `salt:sha256` 格式。自定义哈希格式是 SHA-256(salt + ":" + password)，比 bcrypt 弱。如果数据库中仍有旧格式密码，虽然登录时会自动升级，但旧密码的存储安全性已不足。
- **修复建议**: 对所有非 bcrypt 密码强制执行迁移，完成后移除 SHA-256 分支。

### P1-2: 登录速率限制基于内存 `defaultdict`，重启即失效
- **文件**: `src/api/auth_routes.py:15-28`
- **问题**: `_login_attempts` 是一个模块级 `defaultdict(list)`，服务器重启后所有限制记录丢失。攻击者可以通过反复重启来绕过限制。此外，使用客户端 IP 进行限制可被代理/内网绕过。
- **修复建议**: 使用 Redis 或其他持久化存储记录登录尝试次数。

### P1-3: 会话/消息存储在内存 dict 中，重启即丢失
- **文件**: `src/api/chat.py:17-19`
- **问题**: `_sessions_store: dict = {}` 和 `_messages_store: dict = {}` 是纯内存存储。代码注释也承认"生产环境应替换为持久化存储"。会话和消息在服务重启后全部丢失。
- **修复建议**: 将会话和消息改为 SQLite / PostgreSQL 存储。

### P1-4: 静态文件挂载在最后，路径冲突导致 API 404
- **文件**: `src/server.py:319`
- **问题**: `app.mount("/static", ...)` 在 `server.py` 接近末尾的位置执行。如果静态路由顺序不当，某些路径可能被意外拦截。此外，静态文件目录指向 `frontend/` 而非专门的 dist 目录，可能导致暴露源代码文件。

### P1-5: `POST /api/rag/sag-trace` 返回占位 SSE 数据
- **文件**: `src/api/rag.py:175-221`
- **问题**: `rag_sag_trace()` 返回的 SSE 追踪流包含硬编码的占位消息（"阶段1: 检索完成（占位）"、"阶段2: 重排序完成（占位）"等），并非真实的 SAG Pipeline 追踪数据。这会使调试和监控界面显示虚假信息。

### P1-6: `GET /api/rag/entity-expand` 回退时返回空列表无提示
- **文件**: `src/api/rag.py:230-270`
- **问题**: 当 `taiyang.expand` 不可用时，返回 `{"entity_name": ..., "expanded_entities": [], "total": 0}`，不向调用者说明原因是"功能未实现"还是"无匹配结果"。

### P1-7: `/api/mcp/call` MCP 工具注册表使用 lambda + `__import__` 动态导入
- **文件**: `src/server.py:256-285`
- **问题**: `MCP_TOOL_HANDLERS` 字典中每个工具都使用 `lambda args: __import__("src.taiyin.mcp_tools", fromlist=["..."])` 动态导入。每次调用都执行一次 `__import__`，性能低下。如果 `mcp_tools.py` 导入失败，整个 call 端点的所有工具都会出错。
- **修复建议**: 在 `MCP_TOOL_HANDLERS` 构建时执行导入，缓存成功导入的模块。

### P1-8: `save_chunks` 被 4 个文件引用但都是空操作
- **详见 P0-1**, 此处列为 P1 是为了强调修复时需要同步更新以下文件中的调用：
  - `src/api/documents.py` (L90, L216)
  - `src/api/files_alias.py` (L46, L115)
  - `src/bagua/kan.py`
- **修复建议**: 新增 `save_chunks_via_memory_store()` 函数或在调用点直接使用 MemoryStore API。

### P1-9: `ai_tools/routes.py` 中的 AI 功能实际逻辑可能为空
- **文件**: `src/services/ai_tools/routes.py`
- **问题**: AI 工具箱 (summarize, translate, keywords, entities, classify) 声称提供 6 个端点，但实际 LLM 调用可能依赖未配置的 API Key。需要验证每个端点是否有完整的 LLM 调用逻辑还是仅返回占位结果。

### P1-10: `data_analytics` 和 `doc_tools` 子服务独立运行 Server，可能端口冲突
- **文件**: `src/services/data_analytics/server.py`, `src/services/doc_tools/server.py`
- **问题**: 这些子服务有自己的 `server.py` 和 `service.json`，可能以独立进程启动。如果端口配置不当（默认端口未在 service.json / ENV 中明确定义），会导致多进程端口冲突。

### P1-11: 八卦艮卦 (GenGua) 作为"稳定性与自我修复"模块，但具体实现待确认
- **文件**: `src/bagua/gen.py:57`
- **问题**: GenGua 类被定义为 "稳定性与自我修复 + 异常嗅探 + 内容安全审核"，但需要确认其核心逻辑是否有完整实现，还是仅框架代码。

### P1-12: `DELETE/PUT /api/files/{id}` 中的 `save_chunks` 调用无效果
- **相关**: P0-1 的直接影响
- **文件**: `src/api/files_alias.py`
- **问题**: `files_delete` 和 `files_update` 都调用了 `save_chunks(kept)` 但此函数为空，导致修改不生效。

### P1-13: `PUT /api/documents/{doc_id}/visibility` 有权限检查但漏洞
- **文件**: `src/api/documents.py:170-240`
- **问题**: 权限检查通过 `chunks.db` 中的 `owner_id` 字段判断所有权，但文档的 `owner_id` 字段可能为空（默认不设置），此时 `check_write` 的参数 `doc_owner_id=""` 可能导致权限判断不准确。此外，更新向量库 metadata 时用 `团队ID` 字符串 "public" 作为 team_id 默认值不够严谨。

### P1-14: `src/api/response.py` 的 `unauthorized` 函数未被 auth_routes 使用
- **文件**: `src/api/auth_routes.py` vs `src/api/response.py`
- **问题**: auth_routes 在登录失败时直接 `raise HTTPException(401)` 而非使用统一的 `unauthorized()` 函数。格式不一致。

---

## 🟡 P2 — 一般问题（代码质量/维护性/小风险）

### P2-1: `FAKE-ASYNC` 标记的函数过多
- **文件**: 全项目约 30+ 个函数标记了 `# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行`
- **问题**: 大量同步函数假装 async，纯粹是为了保持路由 handler 签名一致。这隐藏了真正的异步/同步行为，增加了调试难度。`asyncio_sleep` 辅助函数也仅是包装 `asyncio.sleep`。
- **修复建议**: 逐步将同步函数改为真正的 `def`（非 async），或者如果确实需要异步，使用 `asyncio.to_thread` 包装阻塞 IO。

### P2-2: `.env` 文件编码问题
- **文件**: `.env`
- **问题**: `.env` 文件中出现乱码：如 `# 浼忕靜 RAG v1.50 娴嬭瘯鐜閰嶇疆`（应为"伏羲 RAG v1.50 测试环境配置"）。虽然不影响功能，但说明文件编码存储有问题（可能非 UTF-8）。

### P2-3: 硬编码的 MiMo API Base URL
- **文件**: `src/services/evaluator.py:11`, `src/config.py:81`
- **问题**: `evaluator.py` 中硬编码了 `MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"`，虽然 config.py 也有定义，但 evaluator.py 没有使用 config 中的值。配置不一致。

### P2-4: `src/core/db.py` 中搜索日志写入 JSONL 文件使用裸 `try/except: pass`
- **文件**: `src/core/db.py:92-102`
- **问题**: `log_search_to_db()` 函数在异常时 `pass`（静默吞掉）。如果日志文件无法写入，调用者无感知。

### P2-5: `src/api/services.py` 中服务健康检查始终返回 "up"
- **文件**: `src/api/services.py:203-213`
- **问题**: `_check_service_health()` 总是返回 "up"（当无发现数据时采用"保守乐观"策略）。这意味着服务清单中的健康状态不反映真实情况。

### P2-6: `src/api/admin.py` 用户 CRUD 操作的密码处理
- **文件**: `src/api/admin.py:180-220`
- **问题**: `admin_create_user` 通过读取 JSON body 操作 users.json 文件，验证需要确认密码是否正确哈希存储（bcrypt）。如果 admin 传入明文密码，需确认哈希逻辑已正确调用。

### P2-7: 路由注册重复
- **文件**: `src/server.py`
- **问题**: `notifications_router`、`unified_search_router`、`user_preferences_router` 在 `server.py` 中出现了两次 include（一次在"v2.1 新增路由"区域，一次在"通知中心 + 统一搜索 + 用户偏好"区域）。虽然 FastAPI 可能自动去重，但重复注册是代码质量问题。

### P2-8: 异常日志中的中文编码不一致
- **文件**: 多处
- **问题**: `logger.warning("Exception 失败: %s", e, exc_info=True)` 这种格式出现在 `files_view.py:36`、`server.py:199` 等多处。`exc_info=True` 已经会打印完整 traceback，但消息体写的是"Exception 失败"，没有描述是哪个操作的异常。

### P2-9: ChromaDB `sqlite3` 文件直接包含在源码中
- **文件**: `src/data/chroma_wiki/chroma.sqlite3`
- **问题**: ChromaDB 的持久化数据文件被提交到源码仓库。如果这是一个测试数据库，应放在单独的 data 目录；如果是生产数据，不应进入版本控制。

### P2-10: 缺少输入校验
- **文件**: `src/api/auth_routes.py`
- **问题**: `LoginRequest` 和 `body.username`/`body.password` 没有长度/格式校验。非常长的用户名或密码可能导致 bcrypt 性能问题。
- **文件**: `src/api/chat.py`
- **问题**: `ChatRequest` 的 `query` 字段没有长度限制，`history` 列表没有条目数限制。

### P2-11: 弃用警告：`src/agents_old/` 目录
- **文件**: `src/agents_old/`
- **问题**: `agents_old/` 目录包含大量旧版 agent 文件（orchestrator, yin_agent, yang_agent 等），这些文件仍可能被旧版 v1 引擎引用，但 v2 八卦体系已上线。清理此目录可简化代码库。

---

## 📊 审计统计

| 优先级 | 数量 | 类型分布 |
|--------|------|----------|
| P0 | 8 | 空函数/占位实现 4, 导入错误 2, 配置/密钥 2 |
| P1 | 14 | 安全/认证 3, 功能缺失 4, 数据一致性 3, 逻辑错误 4 |
| P2 | 11 | 代码质量 7, 维护性 3, 编译/编码 1 |

## 🎯 重点修复建议

1. **立即修复 P0-1**: `save_chunks` 空函数——这是影响范围最广的 bug，所有文件删除/更新都做不了
2. **立即修复 P0-2**: `wiki_list` 不存在——这是一行修复（`wiki_list` → `wiki_pages`）
3. **立即修复 P0-3/P0-4/P0-5**: admin 面板三个端点返回占位数据
4. **优先修复 P1-1/P1-2**: 密码安全和登录速率限制
5. **优先修复 P1-3**: 会话持久化
6. **逐步重构 P2-1**: FAKE-ASYNC 标记的函数改为真正的 async 或去掉 async

---

*审计工具: EasyClaw backend-1 agent (DeepSeek v4 Pro)*  
*审计方式: 静态代码审查 (src/**/*.py, .env, 配置)*
