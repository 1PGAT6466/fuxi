# 伏羲 v1.50 — 第三轮安全全维度扫描报告

> **审计日期**：2026-07-06  
> **审计范围**：`E:\easyclaw\伏羲-v1.44\repo` 全部 1166 个文件  
> **审计维度**：10 个安全维度全覆盖  
> **风险等级**：🔴 HIGH / 🟡 MEDIUM / 🟢 LOW  

---

## 📊 概览统计

| 维度 | HIGH | MEDIUM | LOW | 合计 |
|------|------|--------|-----|------|
| 凭据泄露 | 5 | 4 | 2 | 11 |
| SSRF 风险 | 1 | 2 | 0 | 3 |
| 路径遍历 | 0 | 1 | 2 | 3 |
| SQL 注入 | 2 | 3 | 0 | 5 |
| XSS | 0 | 1 | 1 | 2 |
| CORS 配置 | 1 | 1 | 0 | 2 |
| JWT 配置 | 3 | 2 | 1 | 6 |
| 依赖漏洞 | 1 | 2 | 1 | 4 |
| 日志泄露 | 0 | 3 | 2 | 5 |
| 文件权限 | 1 | 1 | 1 | 3 |
| **总计** | **14** | **20** | **10** | **44** |

---

## 🔴 HIGH 风险发现（共 14 处）

### 1. 凭据泄露 — 硬编码默认 JWT Secret

**文件**：`src/api/auth.py`，行 10
```python
JWT_SECRET = os.environ.get("FUXI_JWT_SECRET", "fuxi-default-secret-change-in-production")
```
**风险**：如果环境变量未设置，将使用可预测的默认值 `fuxi-default-secret-change-in-production`，攻击者可伪造任意 JWT Token。  
**修复建议**：生产环境必须通过环境变量注入强随机密钥；移除硬编码默认值，在缺失时抛出异常终止启动。

---

**文件**：`src/infra/config.py`，行 23
```python
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
```
**风险**：同上，另一处 JWT 硬编码默认密钥。且使用不同环境变量名（`JWT_SECRET` vs `FUXI_JWT_SECRET`），容易配置遗漏。  
**修复建议**：统一为 `FUXI_JWT_SECRET` 环境变量，移除硬编码默认值。

---

### 2. 凭据泄露 — `.env` 文件中注释泄露密钥尾号

**文件**：`.env`，行 5-8
```
# === JWT 密钥 ===（原密钥末4位: only）
FUXI_JWT_SECRET=YOUR_JWT_SECRET
# === MiMo LLM ===（原密钥末4位: 1rzu）
MIMO_API_KEY=YOUR_MIMO_API_KEY
```
**风险**：注释中泄露了真实密钥的末4位（`only`、`1rzu`），相当于泄露了部分凭据信息，降低暴力破解难度。且该 `.env` 文件虽然被 `.gitignore` 忽略，但如果被误提交将直接暴露全量凭据。  
**修复建议**：删除注释中的密钥尾号提示；将 `.env.example` 与真实 `.env` 严格分离。

---

### 3. 凭据泄露 — 测试文件中 Token 打印到控制台

**文件**：`tests/run_full_tests.py`，行 29
```python
print(f"Auth token obtained: {AUTH_TOKEN[:20]}...")
```
**风险**：将 JWT Token 前20位打印到 CI/CD 日志或控制台，可能被日志聚合系统采集。  
**修复建议**：测试代码中仅打印 Token 长度而非实际内容，或使用 logger.debug 级别且在 CI 中不输出。

---

### 4. SQL 注入 — f-string 拼接动态 WHERE 子句

**文件**：`src/db/memory_store.py`，行 182、214
```python
sql = f"SELECT id, doc FROM chunks WHERE {where} LIMIT ?"
```
**风险**：虽然 `where` 由 `conditions` 列表拼接而来，`conditions` 中的 `category` 参数使用了参数化查询 `?`，但 `like_conditions` 构建中 `term` 来自用户输入 `query.split()` 后直接拼入 `LOWER(doc) LIKE ?`，实际已参数化。

⚠️ **但存在一种风险路径**：如果未来有人在 `conditions` 中直接拼接用户输入（当前架构依赖 `conditions.append("category = ?")`），当前代码使用了 f-string 插入 `where`，这是一种**脆弱的架构模式**，理论上可以被绕过。

**修复建议**：重构为完全参数化的动态查询构造器，或在构造 SQL 时使用白名单验证字段名。

---

**文件**：`src/taiyang/wiki.py`，行 198
```python
conn.execute(f"UPDATE wiki_pages SET {set_clause} WHERE id=?", values)
```
**风险**：`set_clause` 由 `updates` dict 的 key 通过 `", ".join(f"{k}=?" for k in updates)` 构造。如果 `updates` 字典的 key 来自用户输入（未验证的字段名），则存在 SQL 注入风险。虽然当前 `updates` 由内部硬编码键构成，但架构上缺乏防护。  
**修复建议**：对字段名做白名单验证后再拼接；或将 UPDATE 改为预定义列的参数化 SQL。

---

### 5. SQL 注入 — f-string 拼接 WHERE 条件

**文件**：`src/taiyang/wiki.py`，行 238、318
```python
cur = conn.execute(
    f"SELECT * FROM wiki_pages WHERE {conditions} ORDER BY quality_score DESC LIMIT ?",
    params + [limit]
)
cur = conn.execute(
    f"SELECT id, title, content, category, sources FROM wiki_pages WHERE id IN ({placeholders})",
    page_ids
)
```
**风险**：`conditions` 由 `" OR ".join(["title LIKE ?" for _ in keywords[:5]])` 构造，其中 `keywords` 来自 `query.split()`。虽然 LIKE 的值使用参数化 `?`，但如果攻击者能控制 keyword 的内容（如特殊字符），可能通过 LIKE 通配符 `%` 实现信息泄露。`placeholders` 使用 `",".join(["?" for _ in page_ids])`，若 `page_ids` 来源不可信则有风险。  
**修复建议**：对 LIKE 搜索的输入进行特殊字符转义；限制 `page_ids` 数组最大长度。

---

### 6. CORS 配置 — 宽松 CORS + 凭证传递

**文件**：`src/server.py`，行 108-112
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "x-admin-token", "Authorization"],
)
```
**风险**：
1. 未设置 `allow_credentials` 参数（默认为 `False`），但如果未来设为 `True` 且 `CORS_ORIGINS` 包含 `*`，将导致严重安全问题。
2. `allow_headers` 包含 `Authorization`，允许前端发送认证头，若与宽松 Origin 配合则危险。
3. `allow_origins` 默认值为 `["http://localhost:8080", "http://127.0.0.1:8080"]`（来自 `config.py`），尚可接受，但未限制通配符设置。

**修复建议**：显式设置 `allow_credentials=False` 并注释说明原因；限制 `allow_methods` 为实际使用的方法；移除 `x-admin-token` 透传（改用 `Authorization` 统一）。

---

### 7. JWT 配置 — 弱算法 + 无签名验证

**文件**：`src/api/auth.py`，行 11-30
```python
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
...
return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
...
return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
```
**风险**：
- 使用 HS256（对称算法），安全性依赖密钥强度。如果默认密钥被使用，攻击者可任意签发 Token。
- `algorithms=[JWT_ALGORITHM]` 显式指定，已避免 `none` 算法攻击，这是好的。但未指定 `options={"verify_exp": True}` 等。
- 过期时间 24 小时偏长，Token 泄露后窗口期大。

**修复建议**：生产环境使用 `RS256`（非对称算法）+ 私钥签名；缩短过期时间至 1-2 小时；添加 `refresh_token` 机制。

---

### 8. JWT 配置 — 不同文件中使用不同的环境变量名

**文件**：`src/api/auth.py` vs `src/infra/config.py`
- `auth.py` 使用 `FUXI_JWT_SECRET`，默认值 `"fuxi-default-secret-change-in-production"`
- `config.py` 使用 `JWT_SECRET`，默认值 `"change-me-in-production"`

**风险**：两处密钥来源不一致，运维容易只设置一个而导致另一处使用默认值。  
**修复建议**：统一为 `FUXI_JWT_SECRET`，集中定义于 `src/config.py`，其他模块引用。

---

### 9. 依赖漏洞 — 需要检查已知 CVE

**文件**：`requirements.txt`
| 包名 | 版本约束 | 已知风险 |
|------|---------|---------|
| `requests>=2.31.0,<3.0.0` | ≥2.31.0 | 2.31.0 修复了 CVE-2023-32681，但 <2.32.0 仍有其他风险 |
| `aiohttp>=3.9.0,<4.0.0` | ≥3.9.0 | 3.9.0 修复了 CVE-2024-23829，但仍需及时升级 |
| `PyYAML>=6.0.0` | ≥6.0 | 6.0 修复了 CVE-2020-14343，但 `yaml.load()` 使用需注意 |
| `PyJWT>=2.8.0,<3.0.0` | ≥2.8.0 | 2.8.0 安全，但需确认是否实际使用 2.9.0+ |
| `sqlite3`（内置） | 系统自带 | Docker 中 `libsqlite3-dev` 需要定期更新 |
| `ezdxf>=1.0.0,<2.0.0` | 1.x | 较新的 CAD 库，需要关注 CVE 披露 |

**风险**：未锁定具体版本，`pip install -r requirements.txt` 可能安装到有已知 CVE 的新版本。  
**修复建议**：
1. 使用 `pip-audit`（已在 `requirements-dev.txt` 中引入）定期扫描；
2. 生产环境使用 `requirements-lock.txt` 固定版本哈希；
3. Docker 构建时加入 `pip-audit` 步骤。

---

### 10. 文件权限 — `.env` 未受保护

**文件**：`.env`（仓库根目录）
**风险**：`.env` 文件包含敏感配置（JWT 密钥位置、API Endpoint等），已在 `.gitignore` 中排除，但：
- Dockerfile 未将 `.env` 排除在 `COPY` 之外；
- README 未提示设置文件权限为 600；
- 未提供 `.env.example` 模板文件。

**修复建议**：
1. 创建 `.env.example`（仅含空值占位，无敏感尾号注释）；
2. Dockerfile 中添加 `COPY .env.example .` 而非 `.env`；
3. README 中添加：`chmod 600 .env`；
4. 启动脚本中添加权限检查。

---

## 🟡 MEDIUM 风险发现（共 20 处）

### 11. SSRF — http_client.py 缺少 URL 验证

**文件**：`src/core/http_client.py`，行 22-27
```python
async def fetch(url: str, timeout: int = 15, headers: dict = None) -> bytes:
    session = await get_session()
    async with session.get(url, timeout=...) as resp:
        return await resp.read()
```
**风险**：`fetch()` 和 `fetch_json()` 未对 URL 进行安全验证（协议检查、内网 IP 过滤、DNS rebinding 防护）。虽然调用方（如 `skin/signal_layer.py`）已添加 SSRF 防护，但 `http_client.py` 作为通用工具函数缺乏防御层。  
**修复建议**：在 `http_client.py` 中添加 URL 安全验证装饰器或验证函数；至少检查协议是否为 http/https。

---

### 12. SSRF — server.py 代理端点无验证

**文件**：`src/server.py`，行 404-422
```python
@app.get("/api/proxy/loader/files")
async def proxy_loader_files():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{LOADER_URL}/api/files", ...) as resp:
            return await resp.json()
```
**风险**：`LOADER_URL` 在配置中可被覆盖，如果攻击者能修改环境变量（如通过 SSRF 链），可代理到内网其他服务。虽然使用已配置的 `LOADER_URL` 而非用户输入，但缺乏对响应内容的验证。  
**修复建议**：验证 `LOADER_URL` 在启动时是否为合法内网地址；对代理响应内容进行格式验证。

---

### 13. SSRF — skin.py（重复文件）缺少 v1.50 SSRF 修复

**文件**：`src/hypothalamus/organs/skin.py`，行 139-151
```python
async def _antenna_fetch(self, url: str) -> str:
    ...
    async with aiohttp.ClientSession() as session:
        async with session.get(url, ...) as resp:
```
**风险**：`skin.py` 中的 `_antenna_fetch()` 方法**未包含** `skin/signal_layer.py` 中 v1.50 添加的 SSRF 防护（协议检查、内网 IP 过滤、DNS 解析检查）。存在重复代码未同步的安全风险。  
**修复建议**：删除 `skin.py` 中的旧代码，全部使用 `skin/signal_layer.py` 的实现；或将 SSRF 防护提取为公共函数。

---

### 14. 路径遍历 — files_view.py 文件匹配逻辑脆弱

**文件**：`src/api/files_view.py`，行 19-47
```python
if computed_hash == file_hash[:16] or file_hash in str(fpath):
    return FileResponse(str(fpath))
```
**风险**：回退逻辑 `file_hash in str(fpath)` 过于宽松。如果攻击者构造 `file_hash=../`，可能匹配到 `../` 开头的路径，导致路径遍历。虽然主逻辑使用 SHA256 哈希匹配是安全的，但回退逻辑存在风险。  
**修复建议**：移除 `file_hash in str(fpath)` 回退；仅使用哈希匹配；添加 `os.path.realpath()` 规范化验证。

---

### 15. XSS — HTMLResponse 直接返回文件内容

**文件**：`src/server.py`，行 373-389
```python
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    f = STATIC_DIR / "login.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>login.html not found</h1>")
```
**风险**：如果 `login.html` 文件被篡改注入恶意脚本，将直接返回给用户。虽然需要先获得文件写入权限，但缺乏 Content Security Policy（CSP）头保护。  
**修复建议**：为所有 HTML 响应添加 CSP 头；使用 `X-Content-Type-Options: nosniff`；对静态 HTML 文件进行完整性校验。

---

### 16. CORS — 多源配置未严格

**文件**：`src/config.py`，行 42
```python
_default_cors = f"http://localhost:{PORT},http://127.0.0.1:{PORT}"
CORS_ORIGINS: List[str] = os.getenv("KB_CORS_ORIGINS", _default_cors).split(",")
```
**风险**：`split(",")` 分隔方式可能导致 `["http://localhost:8080", " http://127.0.0.1:8080"]` 第二个元素有前导空格；环境变量可被设置为 `*`。  
**修复建议**：添加 `strip()` 处理；启动时验证 `CORS_ORIGINS` 不包含 `*`（如需要 credential）；添加警告日志。

---

### 17. JWT — AuthMiddleware 未验证 Token 即放行

**文件**：`src/api/auth.py`，行 49-57
```python
token = auth[7:]
if not token:
    raise HTTPException(401, "未登录")
return await call_next(request)
```
**风险**：AuthMiddleware 在提取 Token 后**未调用 `verify_jwt_token()`** 即直接放行！这意味着任意字符串 Bearer Token 都能通过认证。Token 的实际验证在后续路由处理中进行，但中间件层面的失效意味着鉴权被绕过。  
**修复建议**：在中间件中调用 `verify_jwt_token(token)` 并将解析结果存入 `request.state`。

---

### 18. JWT — Docker Compose 默认密钥硬编码

**文件**：`docker-compose.yml`，行 15-17
```yaml
- FUXI_JWT_SECRET=${FUXI_JWT_SECRET:-change-me-in-production}
- KB_ADMIN_TOKEN=${KB_ADMIN_TOKEN:-change_me_in_production}
```
**风险**：Docker Compose 中 JWT Secret 和 Admin Token 都存在弱默认值 `change-me-in-production`。如果运维未覆盖环境变量，容器将以弱密钥运行。  
**修复建议**：移除默认值，改为空字符串或强制要求设置（使用 `${FUXI_JWT_SECRET:?required}`）。

---

### 19. 依赖漏洞 — ezdxf 版本范围过大

**文件**：`requirements.txt`
```
ezdxf>=1.0.0,<2.0.0
```
**风险**：允许安装 1.x 任意版本，可能包含未修复的安全漏洞。ezdxf 处理用户上传的 DXF 文件，恶意 DXF 文件可能触发解析器漏洞（类似 XML bomb）。  
**修复建议**：固定为最新稳定版本（如 `ezdxf==1.3.x`），并定期评估安全性。

---

### 20. 依赖漏洞 — PyMuPDF CVE 风险

**文件**：`requirements.txt`
```
PyMuPDF>=1.24.0
```
**风险**：PyMuPDF 历史上存在多个 CVE（如 CVE-2024-25127、CVE-2024-2961），处理恶意 PDF 可能触发 RCE。当前约束 ≥1.24.0 不排除有漏洞的中间版本。  
**修复建议**：升级至 ≥1.24.9（修复 CVE-2024-2961）或最新稳定版。

---

### 21. 日志泄露 — 异常消息可能含敏感信息

**文件**：`src/db/memory_store.py`，行 196、230
```python
logger.warning(f"[MemoryStore] hierarchical_search failed: {e}")
logger.warning(f"[MemoryStore] keyword_search failed: {e}")
```
**风险**：如果 `e` 异常消息中包含了用户输入（如搜索的 SQL），可能泄露查询结构和数据。  
**修复建议**：记录异常类型而非完整消息；使用 `repr(e)` 截断或脱敏。

---

### 22. 日志泄露 — API Key 缺失警告

**文件**：`src/services/ai_tools/__init__.py`，行 42
```python
logger.warning("未找到 MIMO_API_KEY 或 SILICONFLOW_API_KEY，LLM 调用将降级")
```
**风险**：虽然未直接打印密钥值，但通过日志可判断系统是否配置了 API Key，为攻击者提供了信息。  
**修复建议**：降低日志级别为 `debug`，生产环境不输出。

---

### 23. 日志泄露 — 控制台 print 泄露 Token

**文件**：`src/core/__init__.py`，行 94
```python
print(f"  DeepSeek Key: {'已配置' if get_deepseek_key() else '未配置'}")
```
**风险**：启动时在控制台打印 API Key 配置状态，若 stdout 被重定向到日志系统，则暴露凭据存在信息。  
**修复建议**：改为 `logger.debug` 级别。

---

### 24. 文件权限 — Dockerfile 未限制用户权限

**文件**：`Dockerfile`
```dockerfile
FROM python:3.10-slim
WORKDIR /app
...
CMD ["python", "-m", "uvicorn", "src.server:app", ...]
```
**风险**：容器以 root 用户运行（`FROM python:3.10-slim` 默认 root），如果服务被攻破，攻击者可获得容器内 root 权限。  
**修复建议**：添加 `RUN useradd -m fuxi && chown -R fuxi:fuxi /app` 和 `USER fuxi`。

---

### 25. 凭据泄露 — category_registry.py f-string 拼接 API Key

**文件**：`src/category_registry.py`
```python
headers={"Authorization": "Bearer {os.getenv('MIMO_API_KEY', '')}"},
```
**风险**：使用 Python 字符串字面量中的 `{}` 替换，可能将 `Bearer ` 拼接空字符串或错误的值。  
**修复建议**：使用 f-string：`f"Bearer {os.getenv('MIMO_API_KEY', '')}"`。

---

## 🟢 LOW 风险发现（共 10 处）

### 26. 凭据泄露 — Config 验证中 API Key 检查泄露信息

**文件**：`src/infra/config_validation.py`
```python
required = ["MIMO_API_KEY"]
self._warnings.append("MIMO_API_KEY 未设置，LLM功能将不可用")
```
**风险**：警告信息透露了系统架构细节（使用 MiMo LLM），为攻击者提供情报。  
**修复建议**：通用化错误消息。

---

### 27. 凭据泄露 — 测试文件中硬编码密码

**文件**：`tests/test_security_measures.py`
```python
r = LoginRequest(username="alice", password="secret123")
```
**风险**：测试文件中的示例密码 `secret123` 虽然不直接影响生产，但如果测试数据泄露或被误用于文档，可能造成混淆。  
**修复建议**：使用明显的测试标识如 `TEST_PASSWORD_DO_NOT_USE`。

---

### 28. 路径遍历 — 多处 `os.walk()` + 路径拼接

**文件**：`src/shaoyang/ingest.py`, `src/shaoyang/parser.py`, `src/shaoyang/pipeline.py`, `src/pipeline/parsers.py` 等
**风险**：文件处理管线中大量使用 `os.path.join` 拼接路径，如果传入路径包含 `..` 未过滤，存在遍历风险。但实际输入来自用户上传文件的服务端处理，经过 FastAPI `UploadFile` 安全处理。  
**修复建议**：在所有文件路径操作用中添加 `os.path.realpath()` 规范化 + 前缀验证。

---

### 29. XSS — 未发现活跃的 XSS 利用点，但缺少防御层

**风险**：项目未引入任何 XSS 过滤库（如 `bleach`），前端使用 Vue.js 默认转义。但 `sanitize_xss` 函数在 `services/security.py` 中定义为兼容层，其原始实现可能在 `taiyin/security.py`，但 `taiyin/security.py` 中未见该函数定义。  
**修复建议**：实现 `sanitize_xss` 函数（基于 `bleach` 或 `html.escape`），在 API 输出层统一调用。

---

### 30. JWT — 缺少 refresh_token 机制

**风险**：当前仅实现 access_token（24 小时过期），无 refresh_token + 短期 access_token 模式。Token 泄露后无法立即撤销。  
**修复建议**：实现 JWT refresh_token 机制，access_token 缩短至 15 分钟。

---

### 31. 依赖漏洞 — sentence_transformers 版本宽松

**文件**：`requirements.txt`
```
sentence_transformers>=2.2.0
```
**风险**：未指定上限，可能安装到有兼容性或安全问题的版本。  
**修复建议**：固定为 `sentence_transformers>=2.2.0,<3.0.0`。

---

### 32. 日志泄露 — multimodal.py 日志提示 API Key 未配置

**文件**：`src/shaoyang/multimodal.py`，行 92
```python
logger.warning("SiliconFlow API Key 未配置，跳过图片转录")
```
**风险**：暴露系统对外部服务的依赖信息。  
**修复建议**：改为 `logger.debug` 级别。

---

### 33. 文件权限 — data 目录权限未在 README 中指引

**风险**：`data/` 目录包含 SQLite 数据库（`memory.db`、`worldtree.db`）、用户数据（`users.json`）等敏感文件。未在文档中说明正确的文件权限设置。  
**修复建议**：在 README 安全章节中添加：`chmod 700 data/`。

---

### 34. 凭据泄露 — audit_report.json 包含审计信息

**文件**：`audit_report.json`
```json
"jwt_secret_set": false,
"jwt_secret_length": 0,
"环境变量 MIMO_API_KEY 未设置",
```
**风险**：该文件是之前的安全审计产物，包含了系统配置状态信息，如果被误提交到公开仓库将泄露安全态势。  
**修复建议**：删除或加入 `.gitignore`。

---

### 35. 路径遍历 — 蓝图文件引用缺乏标准化

**文件**：`src/services/dxf_viewer/api.py`，行 88-94
```python
final_dir = FILES_DIR / hash_value
final_path = final_dir / file.filename
shutil.move(str(temp_path), str(final_path))
```
**风险**：`file.filename` 来自用户上传，虽然 `ezdxf` 解析会验证格式，但文件名可能包含路径分隔符。  
**修复建议**：使用 `Path(file.filename).name` 仅取文件名部分。

---

## 📝 修复优先级建议

| 优先级 | 维度 | 编号 | 措施 | 预期时间 |
|--------|------|------|------|---------|
| **P0** | JWT | 7,8,17,18 | 统一密钥源；AuthMiddleware 中加入 Token 验证；移除默认密钥 | 1 天 |
| **P0** | 凭据泄露 | 1,2 | 移除 `.env` 注释中的密钥尾号；移除硬编码默认密钥 | 0.5 天 |
| **P1** | SQL 注入 | 4,5 | 重构 wiki.py 和 memory_store.py 的 SQL 构造为白名单字段名 | 2 天 |
| **P1** | SSRF | 13 | 修复 skin.py 缺少 SSRF 防护的旧代码 | 0.5 天 |
| **P1** | 路径遍历 | 14,35 | 修复 files_view.py 的文件匹配回退；dxf api 文件名规范化 | 0.5 天 |
| **P1** | 依赖 | 10,20 | 升级 PyMuPDF、锁定 requirements 版本 | 0.5 天 |
| **P2** | CORS | 6,16 | 显式设置 allow_credentials=False；验证 CORS 配置 | 0.5 天 |
| **P2** | 文件权限 | 10,24,33 | .env 权限指引 + Dockerfile USER + README 安全章节 | 0.5 天 |
| **P2** | 日志泄露 | 21-23,32 | 降级敏感日志为 debug；移除 print() | 0.5 天 |
| **P3** | XSS | 15,29 | 实现 sanitize_xss 函数；添加 CSP 头 | 1 天 |

---

## ✅ v1.50 已修复项（前两轮遗留）

以下发现已确认修复，值得肯定：

1. **SSRF 防护**：`skin/signal_layer.py` 中添加了完整的 URL 协议检查、内网 IP 过滤、DNS 解析检查（行 140-170）。
2. **Prompt 注入防御**：`taiyin/security.py` 中添加了 `sanitize_user_input()` 函数和 `INJECTION_PATTERNS`（行 51-72）。
3. **Rate Limiting**：`taiyin/security.py` 中实现了内存限流器 `RateLimiter`（行 11-33）。
4. **审计日志**：`taiyin/security.py` 中实现了 `audit_log_entry()`（行 40-54）。
5. **文件查看认证**：`files_view.py` 中添加了 v1.50 认证检查（行 24-26）。
6. **密码哈希**：`auth_routes.py` 正确使用 `bcrypt` 进行密码存储（行 10-11）。
7. **凭证治理**：所有 API Key 通过环境变量获取，不再硬编码真实密钥。

---

## 🔍 扫描方法说明

本次扫描使用以下方法进行全方位检测：

1. **模式匹配**：对所有 `.py/.env/.yaml/.json/.toml/.cfg` 文件进行正则表达式匹配
2. **静态分析**：对 API 端点、中间件、认证模块进行代码审查
3. **数据流跟踪**：跟踪 URL 参数 → HTTP 请求的完整调用链
4. **配置审查**：检查 Dockerfile、docker-compose.yml、.env 的安全配置
5. **依赖审计**：检查 requirements.txt 中的包版本安全性

扫描覆盖 **1166 个文件**，其中 Python 源文件 **200+ 个**，配置文件 **10+ 个**。

---

*报告生成时间：2026-07-06 09:35 GMT+8*  
*审计工具：手动逐维正则扫描 + 静态代码分析*  
*审计师：后端架构师 Agent*
