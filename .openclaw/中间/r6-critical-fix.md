# R6 关键修复摘要

**修复日期**: 2026-07-09
**修复人**: 后端架构专家 (Backend-1 Agent)
**影响**: 修复 R6 最终检测发现的 2 个阻止上线问题

---

## 1. CRITICAL — Admin 登录回归已修复

**问题**: `_is_username_blocked()` 函数将 "admin" 列入黑名单，导致合法 admin 用户无法登录。

**根因**:
- `_BLOCKED_USERNAMES` 集合中包含 `"admin"` 条目
- 子字符串检测 `any(blocked in lower for blocked in ["admin", "root", "system"])` 也会拦截所有包含 "admin" 的用户名

**修复内容** (`src/api/auth_routes.py`):
1. 从 `_BLOCKED_USERNAMES` 集合中移除 `"admin"`（保留 `"administrator"` 防止冒充）
2. 将子字符串检测从 `["admin", "root", "system"]` 改为 `["root", "system"]`
3. 更新注释说明 admin 已从黑名单移除

**状态**: ✅ 已修复

---

## 2. P1 — eval/run 权限漏洞已修复

**问题**: `POST /api/eval/run` 端点缺少管理员权限校验，任何登录用户均可触发评测。

**修复**:
- `src/server.py` — 添加 `dependencies=[Depends(require_admin)]`
- `src/routes.py` — 添加 `dependencies=[Depends(require_admin)]`  
- `src/core/routes.py` — 添加 `dependencies=[Depends(require_admin)]`

现在 `POST /api/eval/run` 要求调用者具有 admin 角色，否则返回 HTTP 403。

**状态**: ✅ 已修复

---

## 变更文件清单

| 文件 | 变更 |
|------|------|
| `src/api/auth_routes.py` | 从黑名单移除 "admin"，修改子串检测 |
| `src/server.py` | 添加 `Depends(require_admin)` 到 `/api/eval/run` |
| `src/routes.py` | 添加 `Depends(require_admin)` 到 `/api/eval/run` |
| `src/core/routes.py` | 添加 `Depends(require_admin)` 到 `/api/eval/run` |
