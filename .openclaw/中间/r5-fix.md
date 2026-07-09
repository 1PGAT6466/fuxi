# 伏羲 v1.50 R5 修复摘要
> 日期: 2026-07-09
> 修复者: 后端架构师 Agent
> 基于: deep-r5-backend-report.md

---

## 修复清单

### 1. ✅ MCP Handler 签名错误（P1/P2）

**问题**: `/api/mcp/call` 调用 handler 时总是传入 `args` 参数 `result = handler(args)`，但 `health_check`、`feature_flags_list`、`graph_stats` 等无参函数不接受参数，报 `takes 0 positional arguments but 1 was given`。

**修复**: 统一所有无参 handler 签名，接受 `args: dict = None` 参数：

| 文件 | 函数 | 修改 |
|------|------|------|
| `src/taiyin/mcp_tools.py` | `health_check` | 签名: `health_check(args: dict = None)` |
| `src/taiyin/mcp_tools.py` | `feature_flags_list` | 签名: `feature_flags_list(args: dict = None)` |
| `src/taiyin/mcp_tools.py` | `graph_stats` | 签名: `graph_stats(args: dict = None)` |
| `src/taiyin/mcp_tools.py` | `sag_status` | 签名: `sag_status(args: dict = None)` |
| `src/taiyin/mcp_tools.py` | `kb_list_documents` | 签名: `kb_list_documents(args: dict = None)` |
| `src/taiyin/mcp_tools.py` | `dream_cycle_run` | 签名: `dream_cycle_run(args: dict = None)` |
| `src/taiyin/mcp_tools.py` | `dream_cycle_report` | 签名: `dream_cycle_report(args: dict = None)` |

---

### 2. ✅ wiki_search 参数类型错误（P2）

**问题**: `wiki_search` 通过 `/api/mcp/call` 调用时 `args` 是 dict，但函数内直接对 `q` 调用 `.strip()`，报 `'dict' object has no attribute 'strip'`。

**修复**: 重写 `wiki_search` 签名接受 `args: dict = None`，内部检测类型：
- 若 `args` 是 dict → 从 `args` 中提取 `q`/`category`/`limit`
- 若 `args` 是字符串 → 直接使用（兼容老调用方式）

**文件**: `src/taiyin/mcp_tools.py`

---

### 3. ✅ user/preferences 和 notifications 返回格式统一

**问题**: 前端 `user.ts` 期望 `{data: {preferences}}`，后端返回 `{preferences}` 无 data 包装。

**修复**:
- `src/api/user_preferences.py` — `GET /preferences` 返回格式改为 `{"status": "ok", "data": {"preferences": prefs}}`
- `src/api/notifications.py` — `GET /api/notifications` 返回格式改为 `{"status": "ok", "data": data}`

---

### 4. ✅ 添加 /api/services/{id}/{action} 端点

**状态**: 该端点已在 R5 检测前添加（`src/api/services.py` 中的 `toggle_service`）。

**修复**: 修复了 `request.state.username` → `getattr(request.state, 'user', 'admin')` 的属性名错误。

**文件**: `src/api/services.py`

---

### 5. ✅ FastAPI 默认错误格式处理

**问题**: FastAPI 默认返回 `{"detail": "..."}`，与系统统一的 `{status: "error", message: "..."}` 格式不一致。

**修复**: 在 `src/server.py` 中添加两个全局异常处理器：
- `global_http_exception_handler` — 处理 Starlette `HTTPException`
- `global_fastapi_exception_handler` — 处理 FastAPI `HTTPException`

转换规则: `{"detail": "xxx"}` → `{"status": "error", "message": "xxx", "status_code": nnn}`

**文件**: `src/server.py`（第 340-372 行附近）

---

## 影响范围

| 文件 | 修改行数 | 风险 |
|------|---------|------|
| `src/taiyin/mcp_tools.py` | ~30 行 | 低 — 仅改签名，不改变逻辑 |
| `src/api/user_preferences.py` | ~5 行 | 低 — 仅改返回格式 |
| `src/api/notifications.py` | ~5 行 | 低 — 仅改返回格式 |
| `src/api/services.py` | ~1 行 | 极低 — 属性名修正 |
| `src/server.py` | ~30 行 | 中 — 全局异常处理器影响所有 HTTP 错误响应 |

## 验证建议

1. 重启服务后测试 `POST /api/mcp/call` 调用 `health_check`、`feature_flags_list`、`graph_stats`、`wiki_search`
2. 验证 `GET /api/user/preferences` 返回 `{status: "ok", data: {preferences: {...}}}`
3. 验证 `GET /api/notifications` 返回 `{status: "ok", data: {...}}`
4. 触发 404/401/403 异常，验证返回格式为 `{status: "error", message: "...", status_code: nnn}`
