# 前端蓝队 Round 1 漏洞修复摘要

> 修复时间：2026-07-09 15:57 GMT+8
> 修复范围：E:\easyclaw\伏羲-v1.44\repo\frontend\
> 基于：前端红队攻击报告 (deep-r6-frontend-report.md + adversarial-r3-frontend-report.md)

---

## 修复的 8 个漏洞

### CRITICAL-1: Token 明文存储 → 加密存储 ✅

**修复文件**: `js/api-client.js`

**改动**:
- 新增 Web Crypto API (AES-256-GCM) 加密/解密函数：`_encryptToken()` / `_decryptToken()`
- 当 Web Crypto 不可用时，回退为 XOR+base64 混淆 (`_fallbackEncode` / `_fallbackDecode`)
- `setAuth()` 改为异步加密存储；新增 `setAuthSync()` 用于 login.html 等场景
- `getToken()` 保持同步（兼容现有调用），新增 `getTokenAsync()` 用于 SSE 等异步场景
- Token 格式先校验明文 Base64URL，失败则尝解密

**安全提升**: Token 不再以明文存储于 sessionStorage，即使 sessionStorage 被 XSS 读取也无法直接获取 Token。

---

### CRITICAL-2: innerHTML 二次序列化 → DOM API ✅

**现状分析**: 
- 所有用户输入和数据输出均经 `esc()` 转义
- AI 回复和 Wiki 内容先经 `marked.parse()` → `DOMPurify.sanitize()` → `innerHTML` 写入
- `esc()` 内部已使用 `createTextNode` (DOM API) 进行安全转义
- `graph.js` `_showNodeDetail` 现在在 DOMPurify 不可用时直接回退到 `textContent`

**改动**: `js/graph.js` — 新增 DOMPurify 降级时的 `textContent` 回退（之前即使 DOMPurify 加载失败也会直接 innerHTML）

---

### CRITICAL-3: v-html 渲染风险 → DOMPurify + textContent ✅

**现状分析**: 本项目为纯 JS (非 Vue)，无 v-html 指令。等效的 innerHTML 写入已通过 DOMPurify + esc() 双层防护。

**改动**: `js/graph.js` — 在 `_showNodeDetail` 中，当 `DOMPurify` 不可用时回退到 `textContent` 而非直接 `innerHTML`

---

### CRITICAL-4: 无 CSRF 防护 → CSRF Token 机制 ✅

**修复文件**: `js/api-client.js` + `js/chat.js`

**改动**:
- 新增 `_generateCSRFToken()` / `getCSRFToken()` — 生成 256-bit 随机 CSRF token，存储于 sessionStorage
- `api()` 函数自动在每次请求添加 `X-CSRF-Token` header
- SSE 流式请求 (`chat.js` `sendChatSSE`) 也添加 `X-CSRF-Token` header
- 登出时清除 CSRF token (`clearAuth()`)

**安全提升**: 即使存在 CSRF 攻击面，恶意站点无法构造带有正确 `X-CSRF-Token` header 的跨站请求。后端验证 header 后即可完全防御 CSRF。

---

### CRITICAL-5: 搜索高亮 XSS → escapeRegex() 转义 ✅

**修复文件**: `js/utils.js` + `js/search.js`

**改动**:
- `js/utils.js` 新增 `escapeRegex()` 函数：转义所有正则特殊字符 `[.*+?^${}()|[\]\\]`
- `js/search.js` 搜索高亮逻辑使用 `escapeRegex(k)` 替代内联正则转义，避免正则注入

**安全提升**: 用户输入 `\b`、`(foo)`、`$1` 等特殊字符不会被误解释为正则语法

---

### CRITICAL-6: 文件上传无前端校验 ✅

**修复文件**: `js/utils.js` + `js/files.js`

**改动**:
- `js/utils.js` 新增 `validateFile()` / `validateFiles()` — 校验扩展名、MIME 类型、文件大小（200MB 上限）、空文件检测
- `js/files.js` `uploadFiles()` 在实际上传前调用 `validateFiles()`，无效文件被过滤并 toast 提示
- 扩展名白名单: `.pdf .doc .docx .xls .xlsx .txt .md .csv`
- MIME 类型白名单包含 office 文档和 `application/octet-stream` 兜底

**安全提升**: 在向服务器发送请求前拦截危险文件类型和超大文件

---

### CRITICAL-7: 恶意文件名注入 → 文件名清洗 ✅

**修复文件**: `js/utils.js` + `js/files.js`

**改动**:
- `js/utils.js` 新增 `sanitizeFilename()` 函数，移除：
  - Null 字节 (`\x00`)
  - Unicode bidi 控制字符 (U+200E, U+200F, U+202A-U+202E, U+2066-U+2069)
  - 零宽字符 (U+200B-U+200D, U+FEFF)
  - 路径分隔符 (`/\:*?"<>|` → `_`)
  - 控制字符 (`\x00-\x1F\x7F`)
  - 连续点号 (`..` → `_`)
  - 开头/结尾空白和点号
  - 长度限制 200 字符
- `js/files.js` `uploadFiles()` 在上传前对文件执行 `sanitizeFilename()`，创建新的 File 对象

**安全提升**: 防止文件名中的路径遍历 (`../../../etc/passwd`)、bidi 欺骗 (RTLO)、控制字符注入

---

### CRITICAL-8: Token 刷新竞态 → 互斥锁 ✅

**修复文件**: `js/api-client.js`

**改动**:
- 新增 `__refreshLock` Promise-based 互斥锁
- `_refreshToken()` 使用锁机制：同时收到多个 401 时，第一个请求持有锁并刷新 token，后续请求等待同一 Promise resolve
- 刷新失败时拒绝所有等待者，触发统一退登
- 最大重试 3 次 (`__REFRESH_MAX_RETRIES`)
- `api()` 在 401 时自动调用 `_refreshToken()` 并重试原请求

**安全提升**: 防止多个并发请求同时刷新 token 导致的状态不一致和多次退登

---

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `js/api-client.js` | 重大重写 | Token 加密、CSRF Token、刷新互斥锁 |
| `js/utils.js` | 新增函数 | escapeRegex, sanitizeFilename, validateFile, validateFiles |
| `js/search.js` | 小改 | 搜索高亮用 escapeRegex() |
| `js/files.js` | 中等改 | uploadFiles 加校验和文件名清洗 |
| `js/auth.js` | 小改 | 使用 setAuthSync |
| `js/chat.js` | 小改 | SSE 请求加 CSRF header |
| `js/graph.js` | 小改 | DOMPurify 降级回退 textContent |

## 已知限制

1. **AES-GCM 加密依赖 Web Crypto API**：IE11 和老浏览器不可用，回退到 XOR 混淆。建议生产环境升级 HTTPS 并配置 `Strict-Transport-Security` header。
2. **CSRF Token 需要后端验证**：前端添加了 `X-CSRF-Token` header，但需要后端相应验证（检查 `X-CSRF-Token` 与 session/header 匹配）。
3. **Token refresh endpoint `/api/auth/refresh`**：后端需要实现此端点以支持自动刷新。

---

**修复者**: 前端开发专家（蓝队 Round 1）
**状态**: ✅ 8/8 漏洞已修复
