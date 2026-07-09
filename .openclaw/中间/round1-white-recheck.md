# ⚪ 白队重新验证报告 - Round 1（补充修复后）

> **裁决方**：白队（系统设计架构师）
> **目标系统**：伏羲 · 企业知识认知体系 v1.44 → v1.50 R3
> **目标地址**：172.25.30.200:8080
> **重检时间**：2026-07-09 16:13~16:25 (GMT+8)
> **重检原因**：蓝队报告完成 C-01（admin 密码）和 C-02（Wiki author BUG）的补充修复，需重新验证
> **结论**：🔴 **二次未通过** — 关键修复未部署到服务器

---

## 📊 最终裁决

| 维度 | 得分 | 满分 | 说明 |
|------|------|------|------|
| **安全性** | 15 | 30 | admin 弱密码未修复 + hacker admin 账户残留 |
| **功能完整性** | 18 | 25 | author BUG 持续存在，用户功能严重受损 |
| **架构健壮性** | 18 | 20 | 设计正确，但部署问题导致实际效果打折 |
| **代码质量** | 12 | 15 | 本地代码质量良好，但未正确部署 |
| **性能** | 10 | 10 | 端点响应正常 |

| **总分** | **73/100** | — | 🔴 **未通过**（阈值 90/100，比首次验证的 80 分更低） |

---

## 🔍 与上次验证的变化对比

| 修复项 | Round 1 首次验证 | 本次重检 | 变化 |
|--------|:---:|:---:|:---:|
| **C-01 admin 密码** | ⚠️ admin123 仍有效 | 🔴 admin123 **仍然有效** | **无变化** |
| **C-02 Wiki author** | ⚠️ 时间戳 BUG | 🔴 时间戳 BUG **仍然存在** | **无变化** |
| **C-03 XSS** | ✅ 已修复 | ✅ 仍有效 | 保持 |
| **C-04 Health 泄露** | ✅ 已修复 | ✅ 仍有效 | 保持 |
| **H-01 JWT 有效期** | ✅ 2 小时 | ✅ 2 小时 | 保持 |
| **H-02 Rate-limit** | ✅ 已调整 | ✅ 有效 | 保持 |
| **H-03 密码复杂度** | ✅ 已修复 | ✅ 有效 | 保持 |
| **hacker admin 账户** | — | 🔴 **新发现** | ⬇️ |

### 📉 得分变化

上次：80/100（4 CRITICAL 中 2 个完全修复、1 个有 BUG、1 个未部署）
本次：73/100（新发现 hacker admin 账户，扣分增加）

---

## 🔴 CRITICAL 逐项详细验证

### [C-01] Admin 密码更新 — ❌ **未部署到服务器**

| 检查项 | 预期 | 实际 | 结论 |
|--------|------|------|------|
| admin/admin123 登录 | ❌ 拒绝 | ✅ **仍然接受** | ❌ |
| admin/Fuxi@Admin2026! 登录 | ✅ 接受 | ❌ 401 | ❌ |
| 本地 data/users.json admin 密码 | bcrypt(Fuxi@Admin2026!) | bcrypt(Fuxi@Admin2026!) | ✅ 本地已更新 |
| .env 配置 | FUXI_ADMIN_DEFAULT_PASSWORD=Fuxi@Admin2026! | 存在 | ✅ 本地配置正确 |

**根因分析**：本地 `data/users.json` 已更新为新密码的 bcrypt 哈希，`.env` 已配置默认密码。但服务器实例使用了**不同的数据目录**或**未重新加载配置文件**。

服务器在 16:13 左右经历了重启（uptime 从 164 秒起跳），但重启后仍使用旧密码，说明：

1. 服务器可能从其他位置加载 `users.json`
2. 或服务器上有独立于本地的用户数据库
3. 或部署流程未将 `data/users.json` 同步到服务器

**影响**：攻击者仍可使用 `admin/admin123` 获取完全的 admin 权限。

---

### [C-02] Wiki Author 字段修复 — ❌ **BUG 持续存在**

| 检查项 | 预期 | 实际 | 结论 |
|--------|------|------|------|
| 创建 Wiki 后 author 字段 | `"weaktest4"`（用户名） | `"2026-07-09 08:15"`（时间戳） | ❌ |
| 普通用户删除自己的 Wiki | ✅ 200 | ❌ 403 | ❌ |
| 普通用户编辑自己的 Wiki | ✅ 200 | ❌ 403 | ❌ |
| 普通用户删除他人的 Wiki | ❌ 403 | ✅ 403 | ✅ |
| 普通用户编辑他人的 Wiki | ❌ 403 | ✅ 403 | ✅ |
| Admin 删除任意 Wiki | ✅ 200 | ✅ 200 | ✅ |

**根因分析**：
- 本地代码库（`src/api/wiki.py` + `src/taiyang/wiki.py` + `src/bagua/kun.py`）**已正确实现** author 字段
- `_check_wiki_ownership()` 权限校验逻辑正确：非 admin 用户只能操作 author 匹配的页面
- 但服务器运行的是旧代码，`author` 列仍存储为时间戳 `"2026-07-09 08:15"` 而非用户名 `"weaktest4"`
- 这导致 `owner == current_user` 比较永远为 `False`
- **结果**：防御了越权攻击（正确），但同时也剥夺了用户操作自己内容的权利（错误）

**本地代码正确性验证**：
- `src/taiyang/wiki.py` L164-169：INSERT 语句 12 个列，author 在正确位置
- `src/api/wiki.py` L222：`author = _get_current_user(request) if request else "anonymous"`
- `src/api/auth.py` L127-128：中间件正确设置 `request.state.user = payload.get("sub", "unknown")`
- 本地 `data/worldtree.db` 表结构包含 `author` 列（索引 11）

---

### [C-03] 存储型 XSS — ✅ 修复持续有效

三层防御全部生效：

| 测试载荷 | 结果 | 
|----------|------|
| `<script>alert(1)</script>` → `&lt;script&gt;alert(1)&lt;/script&gt;` | ✅ 实体编码 |
| `<img src=x onerror=alert(1)>` → `data-blocked=alert(1)` | ✅ event handler 替换 |
| `javascript:void(0)` → `blocked:void(0)` | ✅ 协议移除 |

---

### [C-04] /api/health 信息泄露 — ✅ 修复持续有效

| 请求方式 | 返回 | 结论 |
|----------|------|------|
| 未认证 | `{"status":"healthy","checks":{},"timestamp":...}` | ✅ 无敏感字段 |
| 用户认证 | 同上（checks 为空） | ✅ 分层正确 |

---

## 🟠 HIGH 修复验证

| # | 修复项 | 状态 | 详情 |
|---|--------|:----:|------|
| H-01 | JWT 有效期 2 小时 | ✅ | iat: 16:14, exp: 18:14, TTL=7200s |
| H-02 | Rate-limit 调整 10次/10分钟 | ✅ | 第 11 次注册触发 429 |
| H-03 | 密码复杂度要求 | ✅ | 短密码/无大写/无数字均被拒绝 |

---

## 🔴 新发现

### [C-05] 残留高危账户：hacker（角色：admin）

**发现详情**：
- 通过 `/api/admin/users` 端点发现存在用户 `hacker`，其 `role` 字段为 `admin`
- 这是之前对抗式测试中红队注册的账户
- **未被清理**，服务器上仍然存在

| 用户列表中的 admin 账户 | | |
|---|---|---|
| `admin` | `display_name="管理员"` | 合法管理员 |
| `hacker` | `display_name="hacker"` | ⚠️ 残留测试账户 |

**影响**：
- 如果 `hacker` 账户的密码较弱或被破解，攻击者拥有**完全管理员权限**
- 该账户的存在对系统构成**额外的攻击面**（潜在弱密码入口点）

**建议**：立即删除 `hacker` 账户或降级其角色为 `user`

---

## 📋 攻击链重新评估

```
原攻击链：
弱密码爆破(admin/admin123) → 获取admin JWT → 越权操作Wiki → XSS存储

Round 1 修复后状态：
1. admin 密码      → 🔴 admin123 仍然有效（修复未部署）
   → 攻击链第 1 步仍然可执行
2. 越权操作 Wiki   → ⚠️ 越权被阻断，但用户自身权利也被剥夺
   → 防御部分生效但功能受损
3. XSS 存储        → ✅ 被阻断
4. /api/health     → ✅ 被阻断
5. hacker 账户     → 🔴 额外的 admin 级攻击入口
```

---

## 📊 本地代码 vs 服务器运行代码

| 修复内容 | 本地代码 | 服务器实际 | 差距 |
|----------|:---:|:---:|:---:|
| admin 密码更新（users.json） | ✅ | ❌ | 未部署 |
| _check_wiki_ownership() | ✅ | ✅ | 已部署 |
| _sanitize_html() | ✅ | ✅ | 已部署 |
| author 参数传递 | ✅ | ❌ | 旧代码仍写入时间戳 |
| Health 信息过滤 | ✅ | ✅ | 已部署 |
| JWT 2 小时 | ✅ | ✅ | 已部署 |
| 密码复杂度 | ✅ | ✅ | 已部署 |
| Rate-limit 调整 | ✅ | ✅ | 已部署 |

**关键观察**：wiki.py 中的 `_check_wiki_ownership()` 和 `_sanitize_html()` 已部署，但 author 参数的正确传递未部署。这暗示服务器运行的是**混合版本**——部分新代码 + 部分旧代码。可能是：
1. 部署时只更新了部分文件
2. wiki engine 层（taiyang/wiki.py）没有被更新
3. 或服务器直接修改了旧代码，而非从本地代码库部署

---

## ✅ 本地代码正确性证明

```python
# src/taiyang/wiki.py L164-169 — INSERT with author column
conn.execute(
    """INSERT OR REPLACE INTO wiki_pages 
       (id, title, category, tags, summary, content, sources, version, quality_score, author, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (page_id, title, category, json.dumps(tags or []), 
     summary, content, json.dumps(sources or []), 
     1, 0.7, author, now, now)   # <-- author 在第 10 个 ? 位置
)

# src/api/wiki.py L222 — Author 来源正确
author = _get_current_user(request) if request else "anonymous"

# src/api/auth.py L127-128 — 中间件正确注入
request.state.user = payload.get("sub", "unknown")
```

列顺序：`id(0), title(1), category(2), tags(3), summary(4), content(5), sources(6), version(7), quality_score(8), author(9), created_at(10), updated_at(11)`

参数顺序完全匹配 ✅

---

## 🏆 最终评分明细

```
安全性 (30%)：
  C-01 admin 密码未部署: -8
  C-02 author BUG 持续: -5
  C-05 hacker admin 账户: -2
  C-03 XSS 修复有效: 0
  C-04 Health 修复有效: 0
  H-01/02/03 修复有效: 0
  === 15/30

功能完整性 (25%)：
  登录/注册: 正常 0
  Wiki CRUD (admin): 正常 0
  Wiki CRUD (user): 严重受损（无法管理自己的页面）-5
  其他核心功能: 正常 -2
  === 18/25

架构健壮性 (20%)：
  代码设计正确: 0
  部署问题导致实际效果打折: -2
  === 18/20

代码质量 (15%)：
  本地代码质量良好: 0
  部署/版本管理混乱: -3
  === 12/15

性能 (10%)：
  所有端点响应正常: 0
  === 10/10

总分 = 15 + 18 + 18 + 12 + 10 = 73/100
```

---

## 🚨 必须修复才能通过的清单

### Critical（必须修复，总分 < 90/100 且存在 CRITICAL）

1. **[C-01] admin 密码部署** — 将 `data/users.json` 和 `.env` 更新部署到服务器运行实例
   - 确保 `admin/Fuxi@Admin2026!` 可以登录
   - 确保 `admin/admin123` 被拒绝

2. **[C-02] Wiki author 字段部署** — 将 `src/taiyang/wiki.py` 和 `src/bagua/kun.py` 的 author 列支持部署到服务器
   - 确保创建 Wiki 时 author 存储的是用户名，而非时间戳
   - 确保普通用户能管理自己创建的 Wiki 页面

3. **[C-05] 清理 hacker 账户** — 删除 `hacker` 用户或至少降级为 `user` 角色

### 建议改进

4. **统一部署流程** — 建立明确的部署清单，确保所有修改文件同步到服务器
5. **版本校验端点** — 在 `/api/health` 或 `/api/admin/server-status` 中添加代码版本/Git commit hash，便于验证部署状态
6. **测试账户清理机制** — 添加定期或启动时的测试账户清理

---

## 📎 附录：测试汇总

```
测试项目                                      结果
─────────────────────────────────────────────────────
C-01  admin/admin123 登录                     🔴 仍接受
C-01  admin/Fuxi@Admin2026! 登录             🔴 401
C-02  Wiki author 字段                        🔴 时间戳
C-02  用户删除自己的 Wiki                      🔴 403 (BUG)
C-02  用户编辑自己的 Wiki                      🔴 403 (BUG)
C-02  用户删除他人的 Wiki                      🟢 403 (正确)
C-02  用户编辑他人的 Wiki                      🟢 403 (正确)
C-03  HTML 实体编码                            🟢 生效
C-03  event handler 阻止                       🟢 生效
C-03  javascript: 协议移除                     🟢 生效
C-04  Health 未认证返回                        🟢 仅基本状态
C-05  hacker admin 账户                        🔴 残留
H-01  JWT 有效期 2 小时                        🟢 生效
H-02  Rate-limit 注册 10次/10分钟              🟢 生效
H-03  密码复杂度要求                            🟢 生效
─────────────────────────────────────────────────────
通过: 10 项  |  失败: 5 项  |  新发现: 1 项
```

---

*报告生成时间：2026-07-09 16:25 (GMT+8)*
*白队裁判：系统设计架构师*
*最终结论：🔴 未通过 — 关键修复未部署到服务器，总分 73/100（低于 90/100 阈值）*
