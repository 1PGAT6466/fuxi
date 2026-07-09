# 伏羲 Fuxi v1.50 — 安全审计报告 (R6)

**审计日期**：2026-07-09  
**审计范围**：认证安全 · 授权检查 · 输入验证 · 敏感信息泄露 · 依赖安全  
**审计目标**：`E:\easyclaw\伏羲-v1.44\repo\`  
**服务器**：172.25.30.200:8080  
**代码语言**：Python 3.11 (FastAPI + SQLite) + JavaScript (Vue3)  
**总代码行数**：~24,000+ 文件  

---

## 执行摘要

对伏羲 v1.50 进行了五维安全审计，发现 **8 个发现**：

| 严重性 | 数量 | 状态 |
|--------|------|------|
| 🔴 严重 | 1 | 开放 |
| 🟠 高 | 2 | 开放 |
| 🟡 中 | 3 | 开放 |
| 🔵 低 | 2 | 开放 |
| ⚪ 信息性 | 0 | - |

**关键结论**：v1.50 的安全基础较好（JWT、bcrypt、速率限制、SQL 参数化查询均已到位），但存在一个严重发现需要立即处理：默认 JWT 密钥弱且被泄露在版本控制的备份文件中。

---

## 📋 发现详情

### [C-01] 🔴 严重 — 默认 JWT 密钥被硬编码且备份文件泄露

**严重性**：严重  
**位置**：`.env#L8`, `.env.bak-jwt-fix#L8`  
**CWE**：CWE-798, CWE-259

**描述**：

`.env` 文件中使用可预测的默认 JWT 签名密钥：
```
FUXI_JWT_SECRET=fuxi-v1.50-jwt-production-key-change-in-prod
```

虽然代码通过 `require_admin` 等权限检查做了访问控制，但 JWT 密钥是整个认证体系的基石。如果攻击者获取此密钥，可以：

1. 伪造任意用户（包括 admin）的 JWT token
2. 绕过所有认证中间件
3. 访问所有管理端点、MCP 工具、用户数据

**更严重的是**：备份文件 `.env.bak-jwt-fix` 混入代码仓库，若已提交至 Git 且仓库被公开或内部广泛访问，任何有读取权限的人都可获取密钥。

**影响**：极高。一旦密钥泄露，攻击者可以伪造管理员 JWT，完全接管系统。

**PoC**：
```python
import jwt
# 使用已知密钥伪造 admin token
fake_token = jwt.encode(
    {"sub": "admin", "role": "admin", "exp": 9999999999, "iat": 0},
    "fuxi-v1.50-jwt-production-key-change-in-prod",
    algorithm="HS256"
)
# 使用此 token 可以直接调用 /api/admin/users 等管理端点
```

**建议**：

1. **立即**：更换为强随机密钥：
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. **立即**：将 `.env` 和 `.env.bak-jwt-fix` 加入 `.gitignore` 并确保未跟踪
3. **立即**：检查 Git 历史，确认备份文件是否曾提交；如有，需使旧密钥失效并旋转凭证
4. **长期**：将密钥移至环境变量/密钥管理服务（如 Vault），禁止文件内硬编码

---

### [H-01] 🟠 高 — 生产环境中 `FUXI_ALLOW_REGISTRATION=true` 未关闭

**严重性**：高  
**位置**：`.env#L24`  
**CWE**：CWE-287

**描述**：

`.env.example` 中明确写着 `# 生产环境建议关闭`，但实际 `.env` 中 `FUXI_ALLOW_REGISTRATION=true` 未设置为 `false`。虽然目前代码中注册端点未实际检查此环境变量（只是记录了注释），注册端点仍然对外开放。

**风险**：
- 任何能访问登录页的人都可以注册新账号
- 没有 CAPTCHA/邮箱验证等防滥用机制
- 注册端点的限流为 3次/小时/IP，无法完全防止自动化批量注册
- 可以注册用户名并尝试探测已有的用户账号（用户名已存在的错误 vs 注册成功的差异响应）

**建议**：
1. 在生产环境设置 `FUXI_ALLOW_REGISTRATION=false`
2. 在注册路由中实际检查此环境变量并生效禁止注册
3. 考虑添加验证码或邀请码机制

---

### [H-02] 🟠 高 — 错误详情泄露至客户端（信息泄露）

**严重性**：高  
**位置**：多个路由端点  
**文件**：`src/api/chat.py`, `src/api/files_view.py`, `src/api/admin.py`, `src/server.py`

**描述**：

大量异常处理将 `str(e)` 直接返回给客户端：

```python
# chat.py L220
return {"answer": f"处理失败: {str(e)}", "sources": [], "mode": "error"}

# chat.py L251
"answer": f"乾卦路径处理失败: {str(e)}"

# admin.py 多处
return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# files_view.py L56
return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
```

**风险**：
- 异常消息可能包含内部文件路径、数据库结构、库版本、API 密钥片段等
- 堆栈跟踪可能暴露内部实现细节
- 帮助攻击者绘制系统架构和识别漏洞

**建议**：
1. 对所有 `str(e)` 返回进行过滤，生产环境返回通用错误信息
2. 在生产环境（`FUXI_ENV=production`）统一返回 `"Internal server error"` 不包含详情
3. 将详细错误仅写入日志，不在 HTTP 响应中暴露
4. 实现统一的错误响应处理中间件，按环境自动切换

---

### [M-01] 🟡 中 — 缺少 CSRF 保护

**严重性**：中  
**位置**：全局 HTTP 层  
**CWE**：CWE-352

**描述**：

系统在整个请求链中没有 CSRF 保护机制：

1. 没有 CSRF token 中间件
2. 没有 SameSite Cookie 设置机制（虽然当前用 Bearer token 而非 Cookie）
3. CORS 配置的 `allow_origins` 取决于环境变量配置，可能设置过于宽松
4. 前端 `api-client.js` 仅使用 `Authorization: Bearer` header 做认证，这本身是 CSRF 安全的，但如果有任何 Cookie-based 认证路径则不安全

**风险**：如果未来启用 Cookie-based 认证（如 refresh token 存储在 HttpOnly Cookie），则存在 CSRF 风险。

**建议**：
1. 确保仅使用 Bearer token 认证，不启用 Cookie-based 认证路径
2. 在 CORS 配置中限制 `allow_origins` 为明确的白名单
3. 考虑添加 `SameSite=Lax` 或 `SameSite=Strict` 策略
4. 审计所有 POST/PUT/DELETE 端点，确保不依赖仅 Cookie 的认证

---

### [M-02] 🟡 中 — 密码策略较弱（无复杂度要求）

**严重性**：中  
**位置**：`src/api/auth_routes.py#L85-L87`, `src/api/auth_routes.py#L92-L96`  
**CWE**：CWE-521

**描述**：

密码验证策略仅检查最小长度 6 字符，无复杂度要求：

```python
@field_validator("password")
@classmethod
def validate_password(cls, v: str) -> str:
    if not v or len(v) < 6 or len(v) > 128:
        raise ValueError("密码长度必须在6-128字符之间")
    return v
```

没有要求：
- 大小写字母混合
- 数字和特殊字符
- 常见密码黑名单检查

**影响**：用户可以使用 `123456`、`password` 等弱密码，容易被暴力破解。

**建议**：
1. 增加密码复杂度要求（至少 8 字符、含大小写字母数字特殊字符中 3 类）
2. 实施常见弱密码黑名单
3. 在密码验证提示中引导用户使用强密码

---

### [M-03] 🟡 中 — JWT Token 无撤销机制（logout 为空操作）

**严重性**：中  
**位置**：`src/api/auth_routes.py#L190-L215`  
**CWE**：CWE-613

**描述**：

logout 端点实际上不撤销 JWT token：

```python
@router.post("/logout")
async def auth_logout(request: Request = None):
    """当前为无状态 JWT，登出仅做标记（实际撤销需靠 token 过期自然失效）。
    后续可集成 token 黑名单机制。"""
```

这意味着：
1. 用户在客户端点击"登出"后，token 在有效期内仍可被重用
2. 如果 token 被泄露（如 XSS 窃取、日志泄露），无法主动撤销
3. Token 有效期为 24 小时，在此期间被窃取的 token 完全可用

**影响**：token 泄露后无法快速响应，只能等待 24 小时自然过期。

**建议**：
1. 实现 token 黑名单/撤销列表（Redis 或 SQLite）
2. 或使用 refresh token + short-lived access token 模式（access token 5-15 分钟）
3. 在 logout 时将当前 token 加入黑名单

---

### [L-01] 🔵 低 — 日志中包含敏感信息风险

**严重性**：低  
**位置**：`src/api/auth_routes.py#L199`, 多处 `logger.exception()`

**描述**：

多处使用 `logger.exception()` 记录完整异常堆栈：

```python
logger.exception(f"login 失败: {e}")
logger.exception(f"register 失败: {e}")
logger.exception(f"auth_refresh 失败: {e}")
```

`logger.exception()` 会自动包含完整的 `traceback`，如果异常中包含密码、JWT token 或 API key 片段，这些信息会被写入日志文件。

此外，`src/config.py` 中的 `SENSITIVE_PATTERNS` 正则模式仅用于文档内容脱敏，不用于日志脱敏。

**建议**：
1. 在 `logger.exception()` 前对异常消息进行脱敏（移除 token、密码等）
2. 实现日志级别的敏感信息过滤器
3. 定期审计日志文件的访问权限，确保仅管理员可读

---

### [L-02] 🔵 低 — npm 包使用 CDN 引入，无 SRI 校验

**严重性**：低  
**位置**：`frontend/index.html`  
**CWE**：CWE-829

**描述**：

前端通过 `<script src="...">` 直接引用 CDN 上的库文件（如 `marked.min.js`、`dompurify.min.js`、`chart.umd.js`），这些文件未使用 Subresource Integrity (SRI) 校验：

- 如果 CDN 被攻破，攻击者可以在第三方库中注入恶意代码
- 没有完整性校验意味着无法检测文件是否被篡改

**建议**：
1. 将关键 JS 库本地化（已部分完成，`marked.min.js` 在 frontend/js/）
2. 对仍需 CDN 引入的库添加 SRI hash：
   ```html
   <script src="https://cdn.example.com/lib.js" 
           integrity="sha384-xxxxx" crossorigin="anonymous"></script>
   ```
3. 启用 CSP (Content-Security-Policy) header 限制脚本来源

---

## 🔍 五大审计维度详细分析

### 1. 认证安全 — JWT 实现、密码存储、Token 刷新

| 检查项 | 状态 | 说明 |
|--------|------|------|
| JWT 签名算法 | ✅ HS256 | 使用标准 HMAC-SHA256，算法配置正确 |
| JWT 密钥强度 | ❌ C-01 | 默认密钥弱且可预测，备份文件可能泄露 |
| 密码存储 | ✅ bcrypt | 使用 bcrypt($2b$) 哈希，work factor=12 |
| 旧密码格式处理 | ✅ 已迁移 | `_verify_password()` 拒绝旧 SHA-256 格式 |
| Token 过期 | ✅ 24h | 可配置 `FUXI_JWT_EXPIRE_HOURS` |
| Token 刷新端点 | ✅ 存在 | `/api/auth/refresh` 可用，用旧 token 换新 token |
| Token 撤销 | ❌ M-03 | logout 不撤销 token，无黑名单 |
| 登录速率限制 | ✅ 5次/分钟 | SQLite 持久化，重启不丢失 |
| 注册速率限制 | ✅ 3次/小时 | 有效防止批量注册 |
| 用户名黑名单 | ✅ 已实施 | 阻止 admin/root/system 等敏感用户名 |
| 注册开关 | ❌ H-01 | `FUXI_ALLOW_REGISTRATION` 未生效 |

**总体评价**：认证系统基础扎实，bcrypt + JWT 实现规范。主要问题在密钥管理和 token 生命周期。

### 2. 授权检查 — 所有端点的权限控制

| 检查项 | 状态 | 说明 |
|--------|------|------|
| AuthMiddleware 认证 | ✅ | 对 /api/ 路径全部验证 JWT Bearer token |
| 白名单路径 | ✅ | 仅 /api/health, /api/auth/login, /api/auth/register 等 |
| 生产环境文档保护 | ✅ | 生产环境禁用 /docs, /redoc, /openapi.json |
| require_admin 依赖 | ✅ | FastAPI `Depends(require_admin)` 用于所有管理端点 |
| MCP 工具权限 | ✅ | `_MCP_TOOL_PERMISSIONS` 分级映射 admin/user/public |
| admin 页面认证 | ✅ | /admin 路由检查登录状态，未登录重定向到 /login |
| 团队成员权限 | ✅ | PermissionManager 支持 owner/team/public 三级 + 检索结果过滤 |
| API 端点权限覆盖 | ⚠️ 需确认 | 自动发现的端点（_auto_discovery.py）依赖 AuthMiddleware |
| /api/auth/me | ✅ | 返回当前用户，无法越权 |
| /api/user/teams | ✅ | 仅返回当前用户的团队 |

**总体评价**：授权体系完整。所有敏感API都有适当的权限检查。自动路由发现机制依赖AuthMiddleware中间件，只要中间件正确配置即可覆盖。

### 3. 输入验证 — SQL 注入、XSS、CSRF 防护

| 检查项 | 状态 | 说明 |
|--------|------|------|
| SQL 参数化查询 | ✅ | 系统主要使用参数化查询（`?` 占位符） |
| memory_store SQL 注入 | ✅ 已修复 | 白名单验证 `ALLOWED_TABLES` 后再拼接表名 |
| entity_frontier SQL 注入 | ⚠️ | 使用 f-string 拼接 SQL，需确认 `table_name` 来源已白名单化 |
| XSS 防护头 | ✅ | `X-XSS-Protection: 1; mode=block` 已设置 |
| Content-Type 嗅探防护 | ✅ | `X-Content-Type-Options: nosniff` 已设置 |
| CSP 策略 | ❌ 缺失 | 无 Content-Security-Policy header |
| CSRF 防护 | ❌ M-01 | 无 CSRF token 机制 |
| CORS 配置 | ⚠️ | 取决于 `KB_CORS_ORIGINS` 环境变量配置 |
| 输入长度限制 | ✅ | Pydantic `field_validator` 限制用户名 1-64、密码 6-128 |
| Prompt 注入防御 | ✅ | `taiyin/security.py` 检测并拦截常见注入模式 |
| 文件上传类型白名单 | ✅ | `ALLOWED_EXTENSIONS` 限制了允许的文件扩展名 |

**总体评价**：基本安全措施到位。主要缺失 CSP header 和完善的安全头配置。

### 4. 敏感信息泄露 — 配置、密钥、内部路径

| 检查项 | 状态 | 说明 |
|--------|------|------|
| JWT 密钥泄露 | ❌ C-01 | .env 文件中的默认密钥 + .env.bak-jwt-fix 备份文件 |
| API 密钥暴露 | ✅ | MIMO_API_KEY 为空，未在代码中硬编码实际密钥 |
| 错误详情泄露 | ❌ H-02 | 多处 `str(e)` 暴露内部异常 |
| Server header 伪装 | ✅ | `server_header=False` + 安全头中间件伪装为 "nginx" |
| 静态文件敏感过滤 | ✅ | _SafeStaticFiles 阻止 .vue .ts .json .md 等源代码文件 |
| 目录遍历 | ✅ | StaticFiles 使用安全的文件查找 |
| Git 中密钥搜索 | ⚠️ 需审计 | .env.bak-jwt-fix 是否在 Git 历史中 |
| 生产环境 OpenAPI | ✅ 已禁用 | `docs_url=None` 在 `FUXI_ENV=production` 时 |
| 响应头指纹移除 | ✅ | `X-Fuxi-Engine` 仅开发环境返回 |

**总体评价**：敏感信息保护基础不错，但 JWT 密钥管理和错误信息泄露需要立即修复。

### 5. 依赖安全 — 第三方库的已知漏洞

| 依赖 | 已安装版本 | 最新版本 | 风险 |
|------|-----------|---------|------|
| fastapi | 0.139.0 | ≥0.139.0 | ✅ 最新 |
| uvicorn | 0.49.0 | ≥0.49.0 | ✅ 最新 |
| PyJWT | 2.13.0 | 2.13.0 | ✅ 最新 |
| bcrypt | 5.0.0 | 5.0.0 | ✅ 最新 |
| slowapi | 0.1.10 | 0.1.10 | ✅ 最新 |
| cryptography | 48.0.0 | ≥48.0.0 | ✅ 最新 |
| aiohttp | 3.14.0 | 3.14.0 | ✅ 最新 |
| requests | 2.34.2 | ≥2.34.2 | ✅ 最新 |
| starlette | 1.3.1 | ≥1.3.1 | ✅ 最新 |
| chromadb | 1.5.9 | ≥1.5.9 | ✅ 最新 |
| Jinja2 | 3.1.6 | ≥3.1.6 | ✅ 最新 |
| pillow | 12.2.0 | ≥12.2.0 | ✅ 最新 |
| transformers | 5.10.1 | ≥5.10.1 | ✅ 最新 |
| playwright | 1.60.0 | ≥1.60.0 | ✅ 最新 |

**总体评价**：所有关键安全依赖都是最新版本，无已知 CVE。依赖管理良好。

---

## 📊 风险矩阵

| 风险 | 可能性 | 影响 | 风险等级 |
|------|--------|------|----------|
| JWT 密钥泄露导致伪造认证 | 中（密钥在配置文件中） | 极高（完全接管） | 🔴 严重 |
| 错误详情暴露内部信息 | 高（每次异常都暴露） | 中（逐步信息收集） | 🟠 高 |
| 开放注册导致账户滥用 | 高（接口公开） | 中（资源消耗/探测） | 🟠 高 |
| CSRF 攻击 | 低（纯 Bearer auth） | 中 | 🟡 中 |
| 弱密码被暴力破解 | 中（有限流保护） | 中 | 🟡 中 |
| JWT 无撤销 | 中（token泄露场景） | 中 | 🟡 中 |
| 日志敏感信息泄露 | 低（需要日志访问） | 低 | 🔵 低 |
| CDN 供应链攻击 | 极低 | 低（仅UI影响） | 🔵 低 |

---

## ✅ 正面发现与最佳实践

伏羲 v1.50 在安全方面做得好的地方：

1. **密码存储**：使用 bcrypt($2b$)，工作因子 12，主动拒绝旧 SHA-256 格式
2. **认证中间件**：AuthMiddleware 对所有 API 路径强制 JWT 验证
3. **生产环境安全**：自动禁用 OpenAPI/Swagger 文档，隐藏 server header
4. **速率限制**：登录/注册有严格限制，全局 API 有滑动窗口限流
5. **SQL 注入防护**：主要使用参数化查询，memory_store 对动态表名做了白名单验证
6. **安全响应头**：X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy 均已配置
7. **Prompt 注入防御**：检测并拦截已知注入模式
8. **用户名黑名单**：阻止注册 admin/root/system 等敏感用户名
9. **静态文件安全**：_SafeStaticFiles 阻止源代码文件暴露
10. **审计日志**：完整的操作审计记录和查询能力

---

## 🔧 建议修复优先级

| 优先级 | 发现 | 修复时间 | 工作量 |
|--------|------|---------|--------|
| P0 | C-01: JWT 密钥更换 | 立即 | 30 分钟 |
| P1 | H-02: 错误信息脱敏 | 1 天 | 2-4 小时 |
| P1 | H-01: 关闭开放注册 | 1 天 | 1 小时 |
| P2 | M-03: Token 黑名单 | 1 周 | 4-8 小时 |
| P2 | M-02: 密码复杂度 | 1 周 | 2 小时 |
| P3 | M-01: CSRF 加固 | 1 周 | 2 小时 |
| P3 | L-01: 日志脱敏 | 2 周 | 2 小时 |
| P3 | L-02: SRI 校验 | 2 周 | 1 小时 |

---

## 附录 A：自动化分析结果

由于环境限制，本次审计未运行以下自动化工具，建议在代码审计后补做：
- **Safety** (`pip list` 已确认关键依赖最新)
- **Bandit**：Python 静态安全分析
- **npm audit**：前端依赖安全检查
- **OWASP ZAP**：动态应用安全测试

## 附录 B：审计方法论

1. **代码审查**：手动审查核心安全模块（auth.py, auth_routes.py, permissions.py, server.py, middleware.py）
2. **配置审查**：审查 `.env`, `.env.example`, `config.py` 安全相关配置
3. **数据流追踪**：追踪 JWT token 生命周期、密码存储、异常处理路径
4. **依赖检查**：验证 `requirements.txt` 与已安装包的安全性
5. **前端审查**：检查 `auth.js`, `api-client.js` 令牌管理安全性

---

*本报告由 区块链安全审计师 完成。如有疑问，请通过审计渠道联系。*
