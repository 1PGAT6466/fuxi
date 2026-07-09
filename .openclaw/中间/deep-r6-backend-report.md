# 伏羲 v1.50 第六轮（最终轮）深层检测报告 (R6)

> **日期**: 2026-07-09 15:15  
> **服务器**: 172.25.30.200:8080  
> **检测者**: 后端架构师 Agent  
> **结论**: 🔴 **BLOCKED — 1 个 CRITICAL 回归问题：Admin 登录被阻止**

---

## 一、检测概览

| 指标 | 结果 |
|------|------|
| 服务器状态 | ✅ Online (200 OK) |
| 八卦引擎 | ✅ v2 正常，8 卦全部 healthy |
| 总测试端点 | 54 |
| 通过 | 35 |
| 失败 | 7 |
| 跳过 (权限不足) | 12 |
| 有效测试 | 42 |
| 有效通过率 | 83.3% |
| CRITICAL 问题 | 🔴 1 (Admin Login Regression) |
| P1 问题 | 1 (eval/run 权限漏洞) |
| P2 问题 | 2 (错误格式、MCP 方法) |
| R5 修复验证 | ✅ 5/5 全部通过 |

---

## 二、🔴 CRITICAL：Admin 登录回归

### 问题描述

`POST /api/auth/login` 使用 admin 账户返回 **422 错误**：
```
{"detail":[{"type":"value_error","loc":["body","username"],"msg":"Value error, 该用户名不可用，请选择其他用户名","input":"admin","ctx":{"error":{}}}]}
```

### 根因

`src/api/auth_routes.py` 第 24-32 行的 `_is_username_blocked()` 函数：
```python
def _is_username_blocked(username: str) -> bool:
    lower = username.lower().strip()
    if lower in _BLOCKED_USERNAMES:
        return True
    # 检查包含 admin/root 的变形
    if any(blocked in lower for blocked in ["admin", "root", "system"]):
        return True  # ← 这会拦截 "admin" 本身！
    return False
```

该函数被 LoginRequest 的 Pydantic validator 调用（第 130 行），导致 **"admin" 这个用户名在登录时也被拦截**。

### 影响范围

- ❌ Admin 账户完全无法登录
- ❌ 所有 admin-only 端点无法访问
- ❌ 系统管理功能完全瘫痪

### 建议修复

将 `_is_username_blocked()` 仅用于注册（RegisterRequest），不应被 LoginRequest 调用。移除 LoginRequest 中的用户名验证器，或将其改为仅验证格式而不检查黑名单。

```python
# 方案 1: 仅在注册时检查黑名单
# 从 LoginRequest 移除 _is_username_blocked 的 validator
# 保留在 register 函数内部的检查

# 方案 2: 修改 validator 仅在字段被赋值时检查（登录不应该再validate用户名）
```

---

## 三、R5 修复验证

| 端点 | R5 问题 | R6 结果 |
|------|---------|---------|
| `POST /api/mcp/call` health_check | `takes 0 positional arguments` | ✅ 通过 |
| `POST /api/mcp/call` feature_flags_list | `takes 0 positional arguments` | ✅ 通过 |
| `POST /api/mcp/call` graph_stats | `takes 0 positional arguments` | ✅ 通过 |
| `POST /api/mcp/call` wiki_search | `'dict' object has no attribute 'strip'` | ✅ 通过 |
| `POST /api/mcp/call` sag_status | `takes 0 positional arguments` | ✅ 通过 |

**结论**: R5 所有修复均验证通过，无回归。✅

---

## 四、核心 API 端点测试结果

### ✅ 正常工作 (35 个)

| 端点 | 状态码 | 格式 | 备注 |
|------|--------|------|------|
| `GET /api/health` | 200 | `{status, checks, bagua}` | 8卦全部 healthy |
| `GET /` | 200 | HTML | 主页正常 |
| `GET /login` | 200 | HTML | 登录页正常 |
| `GET /docs` | 401 | — | ✅ 受保护 (生产环境) |
| `GET /openapi.json` | 401 | — | ✅ 受保护 (生产环境) |
| `GET /api/auth/me` | 200 | `{username, role}` | 通过 |
| `GET /api/search` | 200 | `{results, ...}` | 通过 |
| `GET /api/search-history` | 200 | `[]` | 通过 |
| `GET /api/unified-search` | 200 | `{query, matches, total}` | 通过 |
| `POST /api/chat` | 200 | `{answer, sources}` | 通过 |
| `POST /api/chat?format=v2` | 200 | **`{status, data, message}`** | ✅ v2 格式 |
| `POST /api/chat/agent` | 200 | `{answer, ...}` | 通过 |
| `GET /api/chat/sessions` | 200 | 会话列表 | 通过 |
| `POST /api/chat/send (SSE)` | 200 | `text/event-stream` | ✅ SSE 流式正常 |
| `POST /api/rag/search` | 200 | `{results, total}` | 通过 |
| `POST /api/rag/sag-search` | 200 | `{results}` | 通过 |
| `GET /api/documents` | 200 | `{files, total}` | 通过 |
| `GET /api/wiki/pages` | 200 | `{pages, total}` | 41 页 49KB 内容 |
| `GET /api/wiki/search` | 200 | {title, content} | 通过 |
| `GET /api/graph` | 200 | `{nodes, edges}` | 通过 |
| `GET /api/symbols/status` | 200 | `{symbols, health}` | 通过 |
| `GET /api/growth/overview` | 200 | `{symbols, summary}` | 通过 |
| `GET /api/notifications` | 200 | **`{status, data}`** | ✅ v2 格式 |
| `GET /api/user/preferences` | 200 | **`{status, data}`** | ✅ v2 格式 |
| `GET /api/eval/report` | 200 | `{metrics, issues}` | 通过 |
| `GET /api/eval/history` | 200 | `{history}` | 通过 |
| `GET /api/feedback/weekly` | 200 | 反馈列表 | 通过 |
| `POST /api/feedback` | 200 | 提交成功 | 通过 |
| `POST /api/mcp/sag_search` | 200 | `{results}` | 通过 |
| `POST /api/mcp/call` × 5 | 200 | `{ok, tool, result}` | ✅ R5 全部修复 |
| `PUT /api/feature-flags` (user) | 403 | **v2 error format** | ✅ 权限正确拒绝 |
| `GET /api/nonexistent` | 404 | **v2 error format** | ✅ 全局异常处理 |

### ❌ 失败 (7 个)

| 端点 | 期望 | 实际 | 问题 | 严重性 |
|------|------|------|------|--------|
| `POST /api/auth/login` (nonexist) | 401 | 422 | Pydantic validation blocks before auth check | P2 |
| `POST /api/auth/login` (admin) | 200 | 422 | 🔴 **Admin login BLOCKED** | **CRITICAL** |
| `GET /api/documents/export` | 200 | 405 | Method not allowed (需要 POST?) | P2 |
| `POST /api/mcp/sag_status` | 200 | 405 | Method not allowed | P2 |
| `GET /api/search` (bad token) | 401 | 401 | 旧格式 `{detail}` 而非 v2 error | P2 |
| `GET /api/search` (no auth) | 401 | 401 | 旧格式 `{detail}` 而非 v2 error | P2 |
| `POST /api/eval/run` (user) | 403 | 200 | 🔴 **权限漏洞！user 可以触发 eval run** | **P1** |

### ⏭️ 跳过 (12 个 — 权限不足)

这些端点需要 admin 角色，当前使用 user 角色测试（403）：
- `/api/admin/stats`, `/api/admin/server-status`, `/api/admin/metrics-summary`
- `/api/feature-flags` (GET), `/api/system/stats`, `/api/cache/stats`, `/api/errors/stats`
- `/api/mcp/tools`, `/api/services/`, `/metrics`

**注意**: 由于 admin 登录已被破坏，这些端点无法以 admin 身份测试。

---

## 五、JSON 格式统一性分析

### 当前状态

| 格式 | 端点 | 占比 |
|------|------|------|
| **v2** `{status, data, message}` | /api/chat?format=v2, /api/notifications, /api/user/preferences | ~15% |
| **v2 error** `{status:error, message, status_code}` | 404, 403 | ✅ 全局异常处理生效 |
| **legacy** `{detail}` | 401 响应 | ❌ AuthMiddleware 未迁移 |
| **旧格式** | 其他大部分端点 | ~75% |

### ⚠️ 401 错误仍未统一

`AuthMiddleware` 返回的 401 响应仍使用 `{detail: "未登录"}` 格式：
```python
return JSONResponse(
    status_code=401,
    content={"detail": "未登录"}  # ← 应为 {"status": "error", "message": "未登录"}
)
```

### ✅ 全局异常处理器验证

- **404 测试**: ✅ 返回 `{status: "error", message: "Not Found", status_code: 404}` 
- **403 测试**: ✅ 返回 `{status: "error", message: "需要管理员权限", ...}`
- **401 测试**: ❌ 仍返回 `{detail: "未登录"}` — AuthMiddleware 绕过了全局异常处理器

---

## 六、🔴 P1 权限漏洞：`POST /api/eval/run`

### 问题

普通用户（role=user）可以成功调用 `POST /api/eval/run`，返回 200，而预期应返回 403。

### 影响

评测模块可能消耗大量资源（LLM 调用、数据处理），普通用户不应能触发评测运行。这是一个权限控制缺失问题。

### 建议

在 `src/api/eval.py` 的路由中添加 `dependencies=[Depends(require_admin)]`。

---

## 七、SSE 流式测试

| 端点 | 状态码 | Content-Type | 结果 |
|------|--------|--------------|------|
| `POST /api/chat/send` (stream=true) | 200 | `text/event-stream; charset=utf-8` | ✅ 正常 |

SSE 流式输出验证通过，逐字符传输正常工作。

---

## 八、回归问题检查

| 检查项 | 结果 |
|--------|------|
| 服务是否在运行 | ✅ 是 |
| 八卦引擎 | ✅ v2 正常，8卦 healthy |
| 核心对话 / RAG | ✅ 正常 |
| SSE 流式 | ✅ 正常 |
| 前端 HTML 页面 | ✅ 正常 |
| Admin 登录 | 🔴 **回归！** 被 `_is_username_blocked` 阻止 |
| MCP Tools 签名修复 | ✅ 无回归 |
| user/preferences v2 格式 | ✅ 正常 |
| notifications v2 格式 | ✅ 正常 |
| 全局异常处理 (404/403) | ✅ 正常 |
| 全局异常处理 (401) | ❌ AuthMiddleware 绕过 |

---

## 九、问题修复优先级

| 优先级 | 问题 | 影响 | 建议修复 |
|--------|------|------|---------|
| **🔴 CRITICAL** | Admin 登录被 `_is_username_blocked` 阻止 | 系统管理完全瘫痪 | 从 LoginRequest 移除 `_is_username_blocked` validator |
| **🔴 P1** | `POST /api/eval/run` 权限漏洞 | user 可触发评测 | 添加 `Depends(require_admin)` |
| **🟡 P2** | 401 仍使用旧 `{detail}` 格式 | 前后端格式不一致 | 迁移 AuthMiddleware 到 v2 error 格式 |
| **🟡 P2** | `GET /api/documents/export` 返回 405 | 导出功能不可用 | 检查路由方法 |
| **🟡 P2** | `POST /api/mcp/sag_status` 返回 405 | MCP 状态查询不可用 | 检查路由方法 |
| **🟡 P2** | LoginRequest 422 错误误导用户 | 用户体验差，区分不了注册/登录限制 | 修改 validator 仅注册时生效 |

---

## 十、整体评价

### 架构层面

- ✅ 服务架构稳定，核心功能（对话、搜索、RAG、SSE）全部正常
- ✅ 八卦引擎 v2 全部卦象 healthy
- ✅ R5 的 MCP handler 修复全部通过验证
- ✅ v2 格式的 user/preferences 和 notifications 修复生效
- ✅ 全局异常处理 404/403 返回 v2 格式
- 🔴 **1 个 CRITICAL 回归**: admin 登录被破坏
- 🔴 **1 个 P1 权限漏洞**: eval/run 未限制 admin

### 上线评估

**不可上线。** 必须先修复以下 CRITICAL/P1 问题：

1. **CRITICAL**: `_is_username_blocked()` 阻止 admin 登录 — 这是一个 v1.50 R2 安全修复引入的回归
2. **P1**: `POST /api/eval/run` 缺少 admin 权限检查

修复这两个问题后，预计有效通过率可从 83.3% 提升至 > 95%，系统可达到上线标准。

---

## 附录：测试数据

- 测试脚本: `.openclaw/中间/r6_test_v3.py`
- JSON 结果: `.openclaw/中间/r6_test_results.json`
- 总用例数: 54 (覆盖 40+ 个唯一端点)
- 测试方式: Python urllib + 速率控制 (0.6s/请求)
