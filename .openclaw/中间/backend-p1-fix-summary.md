# 伏羲系统后端 P1 修复摘要

**修复日期**: 2026-07-09  
**修复范围**: 所有 14 个 P1 问题  
**修复原则**: 最小改动，不破坏现有功能

---

## ✅ 已修复 (10 个)

### P1-1: 用户密码双格式兼容性陷阱
- **文件**: `src/api/auth_routes.py`
- **修复**: `_verify_password` 移除了旧版 SHA-256(salt:password) 分支，仅保留 bcrypt($2b$) 验证。旧格式密码用户将被提示联系管理员重置。
- **改动**: 删除 `hashlib` 导入，移除 `elif "$" in stored` 分支，添加日志警告。

### P1-2: 登录速率限制基于内存，重启失效
- **文件**: `src/api/auth_routes.py`
- **修复**: `_check_login_rate()` 改为使用 SQLite 持久化存储（`DATA_DIR/login_rate.db`），重启不丢失限制记录。SQLite 异常时自动回退到内存模式。
- **改动**: 新增 `_get_login_rate_db_path()`, `_ensure_login_rate_table()` 辅助函数；`_check_login_rate()` 重写为 SQLite 优先 + 内存回退。
- **额外修复**: `login()` 端点现在实际调用 `_check_login_rate()` 并返回 `unauthorized()` 响应。

### P1-3: 会话/消息存储在内存 dict，重启丢失
- **文件**: `src/api/chat.py`
- **修复**: 新增 SQLite 持久化层（`DATA_DIR/chat_sessions.db`），包含 `sessions` 和 `messages` 两张表。启动时从 SQLite 加载到内存缓存；创建/更新/删除会话时同步持久化；每条消息保存时持久化。
- **改动**: 新增 `_ensure_chat_tables()`, `_save_session_to_db()`, `_save_message_to_db()`, `_delete_session_from_db()`, `_load_sessions_from_db()` 等函数；在 `create_session`, `delete_session`, `chat_send` 中调用持久化；启动时调用 `_load_sessions_from_db()`。

### P1-4: 静态文件挂载安全增强
- **文件**: `src/server.py`
- **修复**: 静态文件挂载优先使用 `frontend/dist/` 构建产物目录；回退到 `frontend/` 根目录时使用 `_SafeStaticFiles` 子类阻止敏感源文件（.vue/.ts/.jsx/.json/lock 等）被访问。
- **改动**: 新增 `_SafeStaticFiles` 内部类，包含 `_BLOCKED_EXTS` 和 `_BLOCKED_NAMES` 黑名单。

### P1-5: SAG Trace SSE 返回占位虚假数据
- **文件**: `src/api/rag.py`
- **修复**: 不再返回虚假占位消息。优先尝试从 `taiyang.sag_pipeline.SagTracer` 获取真实追踪数据；失败时返回明确的"追踪不可用"通知而非伪造数据。
- **改动**: 将硬编码的占位 SSE 消息替换为 `SagTracer` 调用 + 友好通知回退。

### P1-6: Entity-expand 回退时无原因说明
- **文件**: `src/api/rag.py`
- **修复**: 实体扩展失败时明确告知原因。新增知识图谱回退路径；返回结果增加 `source` 字段标明数据来源；失败时返回 `notice` 字段说明是"功能未实现"还是"无匹配结果"。
- **改动**: 在 `ImportError` 分支后新增知识图谱回退逻辑；占位返回改为带 `notice` 字段的结果。

### P1-7: MCP 工具 handler 每次调用动态 __import__
- **文件**: `src/server.py`
- **修复**: 在模块加载时通过 `_init_mcp_handlers()` 一次性预导入所有 24 个 MCP 工具 handler。`_MCP_TOOL_HANDLERS` 变为预加载的 dict，调用时直接使用缓存的处理函数，不再每次执行 `__import__`。
- **改动**: 删除原先的 `MCP_TOOL_HANDLERS = {... 24 个 lambda ...}`，替换为 `_init_mcp_handlers()` 预加载。

### P1-10: 子服务端口冲突风险
- **文件**: `src/services/data_analytics/service.json`, `src/services/doc_tools/service.json`
- **修复**: 为两个子服务的 `service.json` 明确配置端口：data-analytics=8011, doc-tools=8012，host 绑定 127.0.0.1，`standalone=false` 表明默认作为嵌入路由。
- **改动**: 在 `config` 字段新增 `port`, `host`, `standalone` 配置。

### P1-13: 文档可见性权限检查漏洞
- **文件**: `src/api/documents.py`
- **修复**: `update_document_visibility` 中 `doc_owner_id` 确保为 str 类型（处理 None/空值）；向量库 metadata 的 `team_id` 默认值从 `"public"` 改为 `""`（空字符串，避免误设为公共团队）；新增 `JSONResponse` 导入。
- **改动**: 添加类型检查 `if not isinstance(doc_owner_id, str)`, 修改 `team_id or "public"` → `team_id or ""`, 添加 import。

### P1-14: unauthorized() 未被 auth_routes 使用
- **文件**: `src/api/auth_routes.py`
- **修复**: `login()` 端点中的 `raise HTTPException(401, ...)` 全部替换为 `return unauthorized(...)` 统一响应格式。
- **改动**: 登录失败（用户不存在、密码错误、速率限制）三处均使用 `unauthorized()` 返回 JSONResponse。

---

## ✅ 已确认无需修复 (4 个)

### P1-8: save_chunks 被 4 个文件引用但空操作
- **状态**: ✅ 已修复（在审计前版本中已实现）
- **说明**: `src/db/data_store.py` 中的 `save_chunks()` 已有完整实现：通过 MemoryStore 清空+批量写入，包含缓存失效和数据一致性保证。

### P1-9: AI 工具 routes.py 逻辑可能为空
- **状态**: ✅ 无需修复
- **说明**: `src/services/ai_tools/routes.py` 所有 6 个端点（summarize/translate/keywords/entities/classify/health）均有完整 LLM 调用实现，包含鲁棒 JSON 解析、语言代码映射、类型统计等功能。

### P1-11: 艮卦 GenGua 核心实现待确认
- **状态**: ✅ 无需修复
- **说明**: `src/bagua/gen.py` 已完整实现 GuaBase 接口：零结果检测、延迟监控、日志异常分析、内容安全审核（三层 NSFW 检测）、嗅探循环、降级规则、统计报告等。

### P1-12: DELETE/PUT /api/files/{id} 中的 save_chunks 调用无效果
- **状态**: ✅ 与 P1-8 同因，已修复
- **说明**: `save_chunks()` 已有完整实现，调用生效。

---

## 📊 修复统计

| 类别 | 数量 |
|------|------|
| 安全/认证增强 | 3 (P1-1, P1-2, P1-14) |
| 数据持久化 | 2 (P1-2, P1-3) |
| 功能正确性 | 3 (P1-5, P1-6, P1-13) |
| 性能优化 | 1 (P1-7) |
| 部署/配置 | 2 (P1-4, P1-10) |
| 已确认有效 | 4 (P1-8, P1-9, P1-11, P1-12) |

---

*修复工具: EasyClaw backend-1 agent (DeepSeek v4 Pro)*  
*修复方式: 代码编辑 + 配置修改*
