# 伏羲 v1.50 第五轮深层检测报告 (R5)
> 日期: 2026-07-09 14:47
> 服务器: 172.25.30.200:8080
> 检测者: 后端架构师 Agent

---

## 一、检测概览

| 指标 | 结果 |
|------|------|
| 服务器状态 | ✅ 在线 (200 OK) |
| 八卦引擎 | ✅ v2 正常，15 个卦全部 healthy |
| 核心 API 通过率 | ✅ 18/20 端点正常 |
| JSON 格式统一 | ⚠️ 部分端点未统一 |
| SSE 流式 | ✅ 正常工作 |
| 权限控制 | ✅ 正常 (admin-only 端点正确拦截) |
| 新发现问题 | 🔴 1 个 P1 + 3 个 P2 |

---

## 二、关键 API 端点测试结果

### ✅ 正常工作

| 端点 | 状态 | 响应格式 | 说明 |
|------|------|---------|------|
| GET /api/health | 200 | `{status, checks, bagua, ...}` | 8 卦全部 healthy |
| POST /api/auth/register | 200 | `{ok, username}` | 注册正常 |
| POST /api/auth/login | 200 | `{token, username, role, display_name}` | JWT Token 正常 |
| GET /api/auth/me | 200 | `{username, role}` | 需 Bearer Token |
| GET /api/symbols/status | 200 | `{symbols, health, timestamp}` | 四象状态正常，需认证 |
| GET /api/growth/overview | 200 | `{symbols, summary, timestamp}` | 需认证 |
| POST /api/chat | 200 | `{answer, sources, mode, confidence}` | 旧格式 |
| POST /api/chat?format=v2 | 200 | `{status: "success", data, message}` | ✅ v2 统一格式 |
| POST /api/chat/send (SSE) | 200 | `text/event-stream` | ✅ 逐字符流式输出 |
| GET /api/chat/sessions | 200 | 会话列表 | 需认证 |
| POST /api/rag/search | 200 | `{results, total}` | 旧格式 |
| POST /api/rag/sag-search | 200 | `{results, events, total, granularity}` | 旧格式 |
| GET /api/unified-search | 200 | `{query, matches, total, took_ms}` | 需认证 |
| GET /api/wiki | 200 | `{ok, title, pages, total}` | 41 页 Wiki 内容 |
| GET /api/files | 200 | `{files, total, page, page_size}` | 需认证 |
| GET /api/notifications | 200 | `{notifications, unread_count, ...}` | ✅ 需认证 |
| GET /api/user/preferences | 200 | `{preferences: {theme, ...}}` | ✅ 需认证 |
| GET /api/eval/report | 200 | `{timestamp, metrics, issues}` | 需认证 |
| GET /api/eval/history | 200 | `{history: [...]}` | 需认证 |
| POST /api/mcp/sag_status | 200 | `{status, uptime_seconds}` | 需认证 |

### 🔴 发现问题

| 端点 | 问题 | 严重性 |
|------|------|--------|
| POST /api/mcp/call (health_check) | `takes 0 positional arguments but 1 was given` | P1 |
| POST /api/mcp/call (feature_flags_list) | `takes 0 positional arguments but 1 was given` | P2 |
| POST /api/mcp/call (graph_stats) | `takes 0 positional arguments but 1 was given` | P2 |
| POST /api/mcp/call (wiki_search) | `'dict' object has no attribute 'strip'` | P2 |

---

## 三、JSON 格式统一性分析

### 现状：混用 3 种格式

| 格式 | 示例端点 | 占比 |
|------|---------|------|
| **{status, data, message}** (v2 新格式) | /api/chat?format=v2, /api/audit/logs | ~15% |
| **{ok, ...}** (旧格式) | /api/auth/register, /api/wiki | ~20% |
| **裸数据** (无包装) | /api/chat, /api/health, /api/rag/search | ~65% |

### 前后端对齐分析

前端 TypeScript 类型定义（`frontend/vue3-migration/src/api/`）期望的响应格式：

| 前端期望 | 后端实际 | 对齐 |
|---------|---------|------|
| `{status, message, data: {entries, count}}` (audit.ts) | 兼容多格式 | ⚠️ 需兼容层 |
| `{data: {preferences}}` (user.ts) | `{preferences}` (无 data 包装) | ⚠️ 不一致 |
| `{data: {notifications, unread_count}}` (notifications.ts) | `{notifications, unread_count}` (无 data 包装) | ⚠️ 不一致 |
| `{ok, pages}` (wiki.ts) | `{ok, pages}` | ✅ 一致 |
| `{status, data, message}` (chat.ts v2) | `{status, data, message}` | ✅ 一致 |

---

## 四、SSE 流式测试

### /api/chat/send?stream=true

- 状态码: 200
- Content-Type: `text/event-stream; charset=utf-8`
- 流式模式: 逐字符输出
- SSE 事件类型: `content`, `references`, `done`, `error`
- 结论: ✅ 正常工作

```
data: {"type": "content", "content": "H"}
data: {"type": "content", "content": "i"}
data: {"type": "content", "content": " "}
...
data: {"type": "done"}
```

---

## 五、新引入问题详情

### P1: MCP 工具 handler 签名不一致

`server.py` 中 `_MCP_TOOL_HANDLERS` 预加载的工具函数签名不统一：
- `health_check()`, `feature_flags_list()`, `graph_stats()` 定义为无参函数
- `/api/mcp/call` 调用时总是传入 `args` 参数：`result = handler(args)`
- 导致调用这 3 个工具时报 `takes 0 positional arguments but 1 was given`

**影响范围**: 3/24 个 MCP 工具不可用

**修复建议**: 统一 handler 签名，接受 `args` 参数并在函数内部忽略

### P2: wiki_search handler 参数类型错误

`wiki_search` 的 `args` 参数期望字符串，但 `/api/mcp/call` 传入的是 dict，调用 `.strip()` 时报错。

---

## 六、权限控制验证

| 端点 | 所需权限 | 普通用户 | 结果 |
|------|---------|---------|------|
| /api/mcp/call (audit_logs) | admin | 拒绝 | ✅ |
| /api/mcp/call (dream_cycle_run) | admin | 拒绝 | ✅ |
| /api/mcp/call (health_check) | public | 允许 | ✅ |
| /api/feature-flags | admin | 拒绝 (403) | ✅ |
| /api/system/stats | admin | 拒绝 (403) | ✅ |

---

## 七、总结

### 架构重构影响评估

R4 的架构重构（server.py）**未破坏核心功能**。所有关键 API 端点均可正常响应。server.py 当前为 722 行，结构清晰。

### 待修复清单

1. **[P1]** 修复 `health_check`, `feature_flags_list`, `graph_stats` 3 个 MCP handler 签名（统一接受 `args` 参数）
2. **[P2]** 修复 `wiki_search` handler 的 args 类型处理
3. **[P2]** 前后端数据格式不一致：`user/preferences` 和 `notifications` 前端期望 `{data: {...}}` 包装，后端直接返回裸数据
4. **[P3]** 建议逐步将核心 API 迁移至统一的 `{status, data, message}` v2 格式

### 整体评价

- 服务器稳定运行，八卦体系 15 卦全部健康
- 核心对话、RAG、SSE 流式功能正常
- MCP 工具调用机制发现 3 个功能性 Bug 需修复
- 前后端格式不一致问题已在多轮检测中持续存在，建议制定迁移计划统一
