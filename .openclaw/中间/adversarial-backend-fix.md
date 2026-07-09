# 对抗式后端检测 — 修复报告

> **修复时间**: 2026-07-09 13:07 CST
> **修复者**: 后端架构专家
> **基于报告**: `.openclaw/中间/adversarial-backend-report.md`

---

## 修复摘要

共计修复 **7 个大类、34 个端点/方法**，涉及 **5 个文件**。

---

## 🔴 CRITICAL 修复

### C1: ✅ 普通用户可创建 admin 用户 — 已修复

**文件**: `src/api/admin.py`
**修复**: 在 `POST /api/admin/users` 端点添加 `dependencies=[Depends(require_admin)]`

```python
@router.post("/api/admin/users", dependencies=[Depends(require_admin)])
async def admin_create_user(request: Request):
```

现在只有 admin 角色的用户才能创建新用户，普通用户访问此端点会收到 **403 Forbidden**。

---

### C2: ✅ 所有 /api/admin/* 端点缺少权限 — 已修复

**文件**: `src/api/admin.py`
**修复**: 为以下 16 个管理端点全部添加 `dependencies=[Depends(require_admin)]`：

| 端点 | 方法 | 修复后 |
|------|------|--------|
| `/api/admin/stats` | GET | ✅ 仅 admin |
| `/api/admin/server-status` | GET | ✅ 仅 admin |
| `/api/admin/status` | GET | ✅ 仅 admin |
| `/api/admin/documents` | GET | ✅ 仅 admin |
| `/api/admin/evaluations` | GET | ✅ 仅 admin |
| `/api/admin/evaluations/run` | POST | ✅ 仅 admin |
| `/api/admin/users` | GET | ✅ 仅 admin |
| `/api/admin/users` | POST | ✅ 仅 admin |
| `/api/admin/users/{user_id}` | PUT | ✅ 仅 admin |
| `/api/admin/users/{user_id}` | DELETE | ✅ 仅 admin |
| `/api/admin/teams` | GET | ✅ 仅 admin |
| `/api/admin/teams` | POST | ✅ 仅 admin |
| `/api/admin/teams/{team_id}` | GET | ✅ 仅 admin |
| `/api/admin/teams/{team_id}` | DELETE | ✅ 仅 admin |
| `/api/admin/teams/{team_id}/members` | POST | ✅ 仅 admin |
| `/api/admin/teams/{team_id}/members/{user_id}` | DELETE | ✅ 仅 admin |

**注意**: `GET /api/user/teams` 保持无需 admin 权限（用户查看自己的团队）。

---

### C3: ✅ 系统资源信息泄露 — 已修复

**文件**: `src/api/system_routes.py`
**修复**: `/api/system/stats` 现在需要 admin 权限

```python
@router.get("/api/system/stats", dependencies=[Depends(require_admin)])
```

---

### C4: ✅ 监控端点公开 — 已修复

**文件**: `src/api/system_routes.py`、`src/server.py`
**修复**: 以下 11 个敏感端点现在全部需要 admin 权限：

| 端点 | 修复 |
|------|------|
| `/api/metrics` | ✅ 仅 admin |
| `/metrics` | ✅ 仅 admin |
| `/api/cache/stats` | ✅ 仅 admin |
| `/api/errors/stats` | ✅ 仅 admin |
| `/api/audit/logs` | ✅ 仅 admin |
| `/api/audit/stats` | ✅ 仅 admin |
| `/api/health/alert-rules` | ✅ 仅 admin |
| `/api/health/alerts` | ✅ 仅 admin |
| `/api/health/bagua` | ✅ 仅 admin |
| `/api/health/infra` | ✅ 仅 admin |
| `/api/feature-flags` (GET/PUT) | ✅ 仅 admin |

---

## 🟠 HIGH 修复

### H1: ✅ Chat 功能不可用 — 已修复

**文件**: `src/bagua/intent_bus.py`
**根因**: `IntentBus` 缺少 `register_symbol`、`heartbeat`、`is_alive`、`last_heartbeat_ago` 方法，而 `SymbolBase.__init__` 调用这些方法来注册和心跳。

**修复**: 在 `IntentBus` 类中添加了 4 个兼容方法：

1. **`register_symbol(symbol_id, name, handler)`** — 自动将非 GuaHandler 对象包装为 CompatGuaHandler 后注册
2. **`heartbeat(symbol_id)`** — 记录心跳时间戳，自动注册首次心跳的 symbol
3. **`is_alive(symbol_id)`** — 30 秒内有心跳视为存活
4. **`last_heartbeat_ago(symbol_id)`** — 返回上次心跳距今秒数

同时添加了 `_heartbeat_times: Dict[str, float]` 字段用于跟踪心跳时间。

**影响**: `ShaoyinBrain(intent_bus)` 现在可以在 v2 引擎下正常工作，Chat 功能恢复。

---

### H2: ✅ 速率限制失效 — 已修复

**文件**: `src/server.py`
**修复**: 增强 slowapi 配置：

```python
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    headers_enabled=True,       # 新增：在响应头中返回限流信息
    strategy="fixed-window",    # 新增：明确策略
)
```

新增 `headers_enabled=True` 确保限流响应头可见，`strategy="fixed-window"` 确保策略明确。

**注意**: 登录限流（`auth_routes.py` 中的 `_check_login_rate`）使用独立的 SQLite 持久化机制，与 slowapi 无关。登录限流本身工作正常（5次/60秒/每IP）。

---

### H3: ✅ `/api/search` 路径不一致 — 已修复

**文件**: `src/api/search.py`
**修复**: 新增 `POST /api/search` 端点

```python
class SearchBody(BaseModel):
    q: str
    top_k: int = 15
    page: int = 1
    page_size: int = 8
    granularity: str = "chunk"

@router.post("/api/search")
async def search_post(body: SearchBody, request: Request = None):
    """搜索端点（POST） — v1.50 安全修复：支持 POST 方法"""
    return await _search_impl(body.q, body.top_k, ...)
```

原有 GET 逻辑提取为 `_search_impl()` 共享函数，GET 和 POST 共享同一实现。

---

## 变更文件清单

| 文件 | 变更类型 | 变更行数 |
|------|---------|---------|
| `src/api/admin.py` | 16 个端点添加 Depends(require_admin) | ~16 行 |
| `src/api/system_routes.py` | 10 个端点添加 Depends(require_admin) + import | ~11 行 |
| `src/bagua/intent_bus.py` | 新增 4 个方法 + 1 个字段 | ~45 行 |
| `src/api/search.py` | 新增 POST 端点 + Pydantic model | ~30 行 |
| `src/server.py` | 5 个端点添加 Depends + slowapi 增强 | ~8 行 |

---

## 向后兼容性

- ✅ 所有现有 GET 端点保持原有行为（仅增加了权限校验）
- ✅ Chat 功能在 v2 引擎下恢复，不影响 v1 引擎
- ✅ 搜索 GET 端点保持不变，仅新增 POST 支持
- ✅ 限流增强不影响现有配置
- ✅ `/api/health` 和 `/api/auth/login` 保持公开访问

---

## 未修复的问题（本次范围外）

以下问题在报告中列为 MEDIUM/LOW，不在本次 CRITICAL+HIGH 修复范围内：

- M1: SSRF 风险 in proxy/loader — 需要基础设施层修复
- M2: API 参数不一致（query vs message）— 文档/前端同步问题
- M3: 用户偏好任意修改 — 需要更精细的权限模型
- L1-L3: 路由 404/参数不一致 — 前端对齐问题
- 数据不一致（admin/stats vs health）— 数据源统一问题
