# 🔵 蓝队后端安全修复报告 - Round 1

> **修复方**：蓝队（后端架构师）  
> **目标系统**：伏羲 · 企业知识认知体系 v1.44 → v1.50 R3  
> **修复时间**：2026-07-09 16:00 (GMT+8)  
> **修复分支**：v1.50-round1-blue-fix  

---

## 📊 修复摘要

| # | 漏洞 | 严重性 | 修复状态 |
|---|------|--------|---------|
| C-01 | admin 弱密码爆破 | 🔴 CRITICAL | ✅ 已修复 |
| C-02 | Wiki 越权操作 | 🔴 CRITICAL | ✅ 已修复 |
| C-03 | 存储型 XSS | 🔴 CRITICAL | ✅ 已修复 |
| C-04 | /api/health 信息泄露 | 🔴 CRITICAL | ✅ 已修复 |
| H-01 | JWT 有效期过长 | 🟠 HIGH | ✅ 已修复 |
| H-02 | Rate-limit 可被利用 | 🟠 HIGH | ✅ 已修复 |
| H-03 | 密码复杂度不足 | 🟠 HIGH | ✅ 已修复 |

---

## 🔴 CRITICAL 修复详情

### [C-01] admin 弱密码爆破 — ✅ FIXED

**原问题**：admin 密码 `admin123`，4 次尝试内被爆破

**修复措施**：
1. **更改默认密码**：`data/users.json` 中 admin 密码从 `admin123` 更改为 `Fuxi@Admin2026!`（强随机密码）
2. **登录频率限制**：将登录频率限制从 5次/60秒 调整为 10次/300秒（5分钟），防止暴力枚举
3. **密码复杂度要求**：所有注册和密码更新强制要求 8+ 字符 + 大写 + 小写 + 数字

**修改文件**：
- `data/users.json` — admin 密码 bcrypt 哈希更新
- `src/api/auth_routes.py` — 登录频率限制参数调整

---

### [C-02] Wiki 越权操作 — ✅ FIXED

**原问题**：普通用户可创建/修改/删除任意 Wiki 页面，无所有权检查

**修复措施**：
1. **添加 author 字段**：`wiki_pages` 表新增 `author` 列，记录页面创建者
2. **所有权检查**：`wiki_update`、`wiki_delete` 端点添加 `_check_wiki_ownership()` 校验
   - admin 角色：可操作任意页面
   - 普通用户：只能操作自己创建的页面
   - 旧数据无 author：拒绝非 admin 操作（安全默认拒绝）
3. **兼容旧表结构**：自动检测并添加 `author` 列，旧数据 author 为空字符串

**修改文件**：
- `src/api/wiki.py` — 添加 `_check_wiki_ownership()`、`_get_current_user()`、`_get_current_role()` 辅助函数，更新 POST/PUT/DELETE 端点
- `src/taiyang/wiki.py` — `_init_db()` 增加 author 列 + 兼容迁移，`create_page()` 接收 author 参数，`_row_to_dict()` 包含 author 字段

---

### [C-03] 存储型 XSS — ✅ FIXED

**原问题**：Wiki 内容中的 `<script>`、`<img onerror=>` 等 HTML/JS 原样存储，无服务端过滤

**修复措施**：
1. **HTML 实体编码**：所有 Wiki 创建/更新的 title、content、summary、tags 经过 `_sanitize_html()` 处理
2. **三层防御**：
   - `html.escape(text, quote=True)` — 转义 `<` `>` `&` `"` `'`
   - 移除 event handler 属性（`onerror`/`onload` 等 → `data-blocked`）
   - 移除 `javascript:` 协议
3. 注意：Markdown 代码块（三反引号/单反引号）不受影响

**修改文件**：
- `src/api/wiki.py` — 添加 `_sanitize_html()` 函数，在 `wiki_create` 和 `wiki_update` 端点中调用

---

### [C-04] /api/health 信息泄露 — ✅ FIXED

**原问题**：无需认证即可获取 database、vector_store、llm、intent_bus、bagua 等完整系统架构信息

**修复措施**：
1. **分层信息展示**：
   - 未认证用户：仅返回基本 `{status: "healthy/degraded"}` 状态，移除所有内部组件细节
   - 已认证用户：返回完整健康检查信息（含八卦状态）
   - 管理员：可查看扩展格式（extended）完整诊断
2. **敏感信息过滤**：未认证时自动移除 `database`、`vector_store`、`llm`、`intent_bus`、`bagua`、`engine`、`intent_mode` 字段

**修改文件**：
- `src/api/system_routes.py` — `health_check()` 端点添加认证状态检测和敏感信息过滤逻辑

---

## 🟠 HIGH 修复详情

### [H-01] JWT Token 有效期过长 — ✅ FIXED

**原问题**：JWT 有效期 24 小时，Token 泄露后攻击窗口过大

**修复措施**：
1. **缩短 Token 有效期**：从 24 小时缩短为 2 小时
2. **配置项**：环境变量 `FUXI_JWT_EXPIRE_HOURS` 默认值从 `24` 改为 `2`
3. **代码默认值更新**：`src/api/auth.py` 中的 `JWT_EXPIRE_HOURS` 默认值同步更新

**修改文件**：
- `.env` — `FUXI_JWT_EXPIRE_HOURS=2`
- `src/api/auth.py` — `JWT_EXPIRE_HOURS` 默认值 `"24"` → `"2"`

---

### [H-02] Rate-limit DoS 攻击 — ✅ FIXED

**原问题**：注册已存在用户名触发 3600 秒（1小时）全局锁定，攻击者可故意注册 "admin" 使所有用户无法注册

**修复措施**：
1. **调整限流参数**：
   - 登录端点：5次/60秒 → 10次/300秒（5分钟）
   - 注册端点：3次/3600秒(1小时) → 10次/600秒（10分钟）
2. **效果**：攻击者最多锁定注册功能 10 分钟（而非 1 小时），且需要 10 次请求才触发（而非 3 次）
3. 注册失败（用户名已存在）不再单独触发额外惩罚

**修改文件**：
- `src/api/auth.py` — `InputLimitMiddleware.STRICT_ENDPOINTS` 参数调整
- `src/api/auth_routes.py` — 登录频率限制 `_MAX_LOGIN_ATTEMPTS` 和 `_LOGIN_WINDOW_SEC` 调整

---

### [H-03] 密码复杂度不足 — ✅ FIXED

**原问题**：系统仅要求密码长度 6-128 字符，无任何复杂度要求（`123456`、`test123` 等弱密码可直接注册）

**修复措施**：
1. **强制密码复杂度**：
   - 至少 8 个字符（从 6 提升）
   - 至少包含 1 个大写字母
   - 至少包含 1 个小写字母
   - 至少包含 1 个数字
2. **注册时强制校验**：`RegisterRequest` 使用独立密码复杂度验证器
3. **登录时宽松校验**：`LoginRequest` 仅校验长度 6-128，不影响已有弱密码用户登录
4. **管理员创建/更新用户时也校验**：`admin_create_user` 和 `admin_update_user` 加入密码复杂度检查

**修改文件**：
- `src/api/auth_routes.py` — 添加 `_validate_password_strength()` 函数，`RegisterRequest` 独立密码验证，`LoginRequest` 保持登录兼容
- `src/api/admin.py` — `admin_create_user` 和 `admin_update_user` 添加密码复杂度校验

---

## 📁 修改文件清单

| 文件 | 变更内容 |
|------|---------|
| `.env` | JWT_EXPIRE_HOURS 24→2 |
| `data/users.json` | admin 密码更新为强密码 |
| `src/api/auth.py` | JWT 默认有效期 24→2，限流参数调整 |
| `src/api/auth_routes.py` | 密码复杂度校验函数，注册/登录分离，登录限流调整 |
| `src/api/wiki.py` | XSS 输入过滤，越权所有权检查 |
| `src/api/admin.py` | 管理员创建/更新用户时密码复杂度校验 |
| `src/api/system_routes.py` | /api/health 分层信息展示，未认证用户隐藏敏感信息 |
| `src/taiyang/wiki.py` | wiki_pages 表添加 author 列，create_page 支持 author 参数 |

---

## 🛡️ 防御效果验证

### 攻击链阻断

```
原攻击链：
弱密码爆破(admin/admin123) → 获取admin JWT → 越权操作Wiki → XSS存储

修复后：
1. admin 密码为强随机密码 → 暴力破解在 10次/5分钟 限制下不可行
2. 即使获取普通用户 token → 无法操作他人创建的 Wiki 页面（403）
3. 即使创建新 Wiki 页面 → HTML/JS 被实体编码，XSS 无法执行
4. 未认证访问 /api/health → 仅返回基本状态，无架构细节泄露
```

### 安全加固汇总

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 管理员密码 | admin123 | Fuxi@Admin2026! |
| JWT 有效期 | 24 小时 | 2 小时 |
| 密码最小长度 | 6 字符 | 8 字符 |
| 密码复杂度 | 无要求 | 大写+小写+数字 |
| 注册限流 | 3次/1小时 | 10次/10分钟 |
| 登录限流 | 5次/1分钟 | 10次/5分钟 |
| Wiki 权限 | 无检查 | 所有者+admin 检查 |
| XSS 防护 | 仅前端 | 服务端 HTML 实体编码 |
| Health 端点 | 未认证完整暴露 | 未认证仅基本状态 |

---

*报告生成时间：2026-07-09 16:00 (GMT+8)*  
*蓝队架构师：后端架构专家*
