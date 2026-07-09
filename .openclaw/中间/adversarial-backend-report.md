# 伏羲系统 对抗式后端检测报告

> **检测时间**: 2026-07-09 13:00 - 13:10
> **服务器**: http://172.25.30.200:8080
> **检测类型**: 全面安全审计 + 功能验证 + 数据真实性 + 边界测试
> **测试端点数**: 100+ 个端点（通过 OpenAPI 发现 141 个路径）
> **总测试用例**: 80+ 个测试场景

---

## 🔴 严重安全漏洞（CRITICAL — 必须立即修复）

### C1: ⚠️ **普通用户可创建 admin 角色用户**（最高严重度）

**漏洞描述**：任何已认证的普通用户（role=user）可以通过 `POST /api/admin/users` 端点创建具有 `role: "admin"` 的新用户，完全绕过权限控制。

**复现步骤**：
```
1. 以普通用户登录获取 token
2. POST /api/admin/users {"username":"hacker","password":"hack123","role":"admin"}
3. 系统返回 200 OK，成功创建 admin 用户
4. 新创建的 admin 用户可以执行所有管理操作
```

**证据**：
- 测试用户 `adv_deep_test`（role: user）成功创建了 `hacker`（role: admin）
- `hacker` 可以登录并访问 `/api/auth/me`，返回 `{"username":"hacker","role":"admin"}`
- `hacker` 可以查看所有用户列表、创建团队等

**影响**：**最高严重度** — 任何注册用户都可以提升为管理员，完全控制系统。

**根因**：`/api/admin/users` 路由缺少 `Depends(require_admin)` 依赖注入，或 `require_admin` 函数检查不生效。

---

### C2: ⚠️ **全部 /api/admin/* 端点缺少权限校验**

**漏洞描述**：以下管理端点均未正确校验用户角色，普通用户可以自由访问：

| 端点 | 状态 | 泄露内容 |
|------|------|---------|
| `GET /api/admin/users` | ⚠️ 公开 | **所有用户列表**（用户名、角色、创建时间） |
| `GET /api/admin/documents` | ⚠️ 公开 | 文档元数据 |
| `GET /api/admin/evaluations` | ⚠️ 公开 | 评测结果 |
| `GET /api/admin/teams` | ⚠️ 公开 | 所有团队及其成员 |
| `GET /api/admin/stats` | ⚠️ 公开 | 系统统计 |
| `GET /api/admin/server-status` | ⚠️ 公开 | 服务器运行状态 |
| `POST /api/admin/evaluations/run` | ⚠️ 公开 | 可触发评测运行 |
| `POST /api/admin/teams` | ⚠️ 公开 | 可创建团队 |

**根因**：这些路由没有使用 `Depends(require_admin)`，或 `require_admin` 函数未正确校验 `request.state.role`。

---

### C3: ⚠️ **系统资源信息泄露**

**漏洞描述**：`GET /api/system/stats` 端点向所有认证用户暴露详细的系统资源信息：

```json
{
  "cpu_percent": 0.0,
  "memory_total_gb": 15.58,
  "memory_used_gb": 1.07,
  "memory_percent": 6.8,
  "disk_total_gb": 97.87,
  "disk_used_gb": 47.39,
  "disk_percent": 51.0,
  "uptime_seconds": 372
}
```

**影响**：攻击者可以利用这些信息规划针对性的资源耗尽攻击。

---

### C4: ⚠️ **敏感监控端点完全暴露**

以下服务监控端点对所有认证用户（包括普通用户）完全开放：

| 端点 | 泄露信息 |
|------|---------|
| `/api/cache/stats` | 缓存命中率、延迟 |
| `/api/errors/stats` | 错误统计、最近错误 |
| `/api/audit/logs` | 审计日志条目 |
| `/api/audit/stats` | 审计统计 |
| `/api/metrics` | 完整 Prometheus 指标（GC、请求数等） |
| `/api/health/alert-rules` | 告警规则配置 |
| `/api/health/alerts` | 当前告警状态 |
| `/api/health/bagua` | 八卦引擎内部状态 |
| `/api/health/infra` | 基础设施组件状态（连接池等） |

---

## 🟠 高危问题（HIGH）

### H1: **IntentBus 错误 — Chat 功能完全不可用**

**问题**：`POST /api/chat` 和 `POST /api/chat/send` 两个端点均返回错误：
```
"处理失败: 'IntentBus' object has no attribute 'register_symbol'"
```

**影响**：核心聊天功能完全不可用。

**根因**：`src/bagua/intent_bus.py` 的 `IntentBus` 类缺少 `register_symbol` 方法，但在某处被调用。

---

### H2: **速率限制失效**

**问题**：
- `/api/health` 端点 100 次连续请求（50秒内）无任何限流
- 配置的 `slowapi` 60/minute 限制未生效
- 登录限流：15 次失败登录后未触发 "频繁" 提示

**影响**：可被用于 DoS 攻击，暴力破解密码。

---

### H3: **API 路径不一致 — /api/search 只能 GET**

**问题**：`POST /api/search` 返回 405 Method Not Allowed，只能使用 `GET /api/search?q=xxx`。

**影响**：前端如果使用 POST 方法调用搜索将失败。

---

## 🟡 中危问题（MEDIUM）

### M1: **SSRF 风险**

`GET /api/proxy/loader/files` 端点尝试连接内部主机 `localhost:8090`，虽然当前报错（连接失败），但如果 loader 服务在运行，可能被利用进行内部网络探测。

### M2: **API 参数不一致 — Chat 需要 'query' 而非 'message'**

文档描述 `POST /api/chat/send` 接受 `{"message": "..."}`，但实际需要 `{"query": "..."}`。

### M3: **用户偏好可被任意修改**

`PUT /api/user/preferences` 端点允许修改任意偏好值，包括 `default_engine` 等系统级设置。

---

## ⚪ 低危问题（LOW）

### L1: **路由 404 — /api/evaluation/reports**

`GET /api/evaluation/reports` 返回 404，正确路径为 `GET /api/eval/report`。

### L2: **/api/antenna/search POST 参数不一致**

`POST /api/antenna/search` 期望 `q` 字段而非 `query`，导致 400 错误。

---

## ✅ 安全性验证通过项

| 检测项 | 结果 |
|--------|------|
| JWT 签名验证 | ✅ 拒绝 alg=none 攻击 |
| JWT 密钥强度 | ✅ 未使用弱密钥 |
| JWT 过期验证 | ✅ 过期 token 被拒绝 |
| 密码哈希 | ✅ 使用 bcrypt |
| SQL 注入防护 | ✅ 搜索参数安全转义 |
| XSS 注入防护 | ✅ 用户名中的 script 标签被拒绝 |
| 安全响应头 | ✅ X-Content-Type-Options, X-Frame-Options, HSTS 等均正确 |
| 静态文件保护 | ✅ `.env` 等敏感文件不可通过 /static/ 访问 |
| 路径遍历防护 | ✅ `/../etc/passwd` 等均被拦截 |
| IDOR（基础） | ✅ 删除不存在的会话/文档返回 404 |
| 空 body 处理 | ✅ 返回 422 |
| null 值处理 | ✅ 返回 422 并提示应为字符串 |
| 超长输入 | ✅ 500KB 消息被拒绝（4000字符限制） |
| 输入验证 (Pydantic) | ✅ 缺失字段返回 422 |
| bcrypt 密码迁移 | ✅ 旧版 SHA-256 格式被拒绝 |

---

## 📊 数据真实性验证

| 数据源 | 值 | 真实性 |
|--------|-----|--------|
| health → database.chunk_count | 503 | ✅ 非 mock |
| documents → 文件数 | 37 | ✅ 与 health 一致 |
| documents → 总 chunks | 503 | ✅ 交叉验证通过 |
| health → vector_store.vector_count | 0 | ⚠️ 向量存储为空 |
| health → has_seed_data | false | ✅ 确认为真实数据 |
| 八卦引擎 → guas | 8/8 healthy | ✅ 15注册 |
| admin/stats → chunks | 0 | ❌ **与 health 不一致** |

**请注意**: `GET /api/admin/stats` 返回 `chunks=0`，但 `/api/health` 返回 `chunk_count=503`，数据不一致。这可能是因为 admin/stats 读取了不同的数据源。

---

## 🔧 修复建议（按优先级）

### P0（立即）

1. **为所有 /api/admin/* 端点添加 `Depends(require_admin)`**
   ```python
   # 在每个 admin 路由上添加
   @router.get("/api/admin/users", dependencies=[Depends(require_admin)])
   ```

2. **修复 POST /api/admin/users 的角色校验**
   - 要么禁止用户设置自己的 role
   - 要么仅允许 admin 用户创建 admin 角色的用户

3. **为系统监控端点添加认证和授权**
   - `/api/system/stats` → 仅 admin
   - `/api/cache/stats` → 仅 admin
   - `/api/errors/stats` → 仅 admin
   - `/api/audit/*` → 仅 admin
   - `/api/health/alert-rules` → 仅 admin
   - `/api/health/alerts` → 仅 admin
   - `/api/health/bagua` → 仅 admin
   - `/api/health/infra` → 仅 admin
   - `/api/metrics` → 仅 admin

### P1（24小时内）

4. **修复 IntentBus.register_symbol 缺失**
   - 在 `src/bagua/intent_bus.py` 中添加 `register_symbol` 方法
   - 或移除对不存在方法的调用

5. **修复速率限制**
   - 检查 `slowapi` 配置是否正确应用到 `/api/health`
   - 修复登录限流逻辑

6. **修复数据不一致**
   - 统一 `/api/admin/stats` 和 `/api/health` 的数据源

### P2（本周内）

7. **统一 API 参数命名**
   - 统一 chat 端点的参数（query vs message）
   - 统一 antenna/search 的参数（q vs query）

8. **添加 SSRF 防护**
   - 限制 proxy/loader 端点的目标地址白名单
   - 添加连接超时和错误处理

9. **修复 /api/evaluation/reports 路由**
   - 添加别名或重定向到 `/api/eval/report`

---

## 📈 性能数据

| 指标 | 值 |
|------|-----|
| 平均 API 响应时间 | ~5ms（不含 Chat AI 调用） |
| Health 端点 | 15ms |
| OpenAPI spec 加载 | 145ms |
| 50并发 Health | 全部成功 |
| 20并发 Login | 全部成功 |
| 数据库查询 | 实时（SQLite 本地） |

---

## 🔍 检测覆盖率

| 类别 | 测试项 | 覆盖 |
|------|--------|------|
| 认证 | login/register/refresh/logout/me | ✅ 完整 |
| Token | 有效/无效/过期/空/alg=none/JWT伪造 | ✅ 完整 |
| 数据端点 | documents/files/wiki/eval | ✅ 完整 |
| 搜索 | search/unified-search/antenna/kb | ✅ 完整 |
| Chat | chat/send/sessions/agent | ✅ 完整 |
| Admin | users/teams/documents/evaluations/stats | ✅ 完整 |
| 系统 | health/metrics/cache/errors/audit | ✅ 完整 |
| 安全 | SQLi/XSS/PathTraversal/JWT/IDOR/SSRF | ✅ 完整 |
| 边界 | 超长/空/null/并发 | ✅ 完整 |

---

> **报告生成**: 2026-07-09 13:10 CST | 对抗式后端检测 v6
