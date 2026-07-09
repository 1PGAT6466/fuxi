# 第二轮对抗式检测 — 前端修复摘要

> 日期：2026-07-09
> 执行者：前端开发专家（subagent）

## 修复列表

### 🟠 P1: `files.js` deleteFile 内联 onclick 残余 XSS ✅

**问题**：删除按钮使用 `onclick="event.stopPropagation();deleteFile('${fh.replace(/'/g, "\\'")}')"`，
仅做单引号转义，`fh`（file_hash）参数直接拼入 HTML 属性值，存在 XSS 注入面。

**修复**：
- 删除按钮改为 `data-file-hash` 属性 + 事件委托
- 批量选择 checkbox 改为 `data-file-hash` 属性 + `change` 事件委托
- 新增事件委托在 `loadFiles()` 中统一注册：click 处理删除、change 处理批量选择
- HTML 模板值统一使用 `esc()` 写入 `data-file-hash` 属性

**影响文件**：`js/files.js`

---

### 🟡 P2: toggleBatchSelect 内联注入风险 ✅

**问题**：`onchange="toggleBatchSelect('${fh.replace(/'/g, "\\'")}')"`，相同的单引号转义不足问题。

**修复**：
- 与 P1 一同修复，checkbox 改为 `class="batch-checkbox"` + `data-file-hash` 属性
- 事件委托在 grid 上监听 change 事件，读取 `data-file-hash` 调用 `toggleBatchSelect(hash)`

**影响文件**：`js/files.js`

---

### 🟡 P2: deleteFile/batchDelete 绕过 `api()` 封装 ✅

**问题**：`deleteFile()` 和 `batchDelete()` 使用裸 `fetch()` + 手动添加 Authorization header，
绕过 `api()` 的 token 刷新、401 自动跳转登录、缓存管理、超时重试等统一机制。

**修复**：
- `deleteFile()` 改为 `await api('/api/documents/' + hash, { method: 'DELETE' })`
- `batchDelete()` 改为逐条 `await api(..., { method: 'DELETE' })`
- 移除手动 token 获取和 header 拼接代码

**影响文件**：`js/files.js`

---

### 🔵 P3: admin 面板数值强转不够安全 ✅

**问题**：`loadOverview()` 和 `loadEval()` 中大量 `(d.xxx||0).toFixed(1)` 调用，
当后端返回非数值类型（如字符串 `"N/A"`）时，`Number("N/A")` 产生 `NaN`，`.toFixed()` 崩溃。

**修复**：
- 在 `utils.js` 新增 `safeNum(val, def)` 安全数值转换函数
- `admin.js` 中所有数值展示点全部替换为 `safeNum()` 调用
- 涉及 `chunks`、`latency_p50_ms`、`error_rate`、`uptime_hours`、`total_searches`、
  `avg_results`、`avg_latency_ms`、`zero_result_rate`、`p50_latency_ms`、`test_cases_count`、
  `cache_hit_rate` 等字段

**影响文件**：`js/utils.js`（新增 safeNum）、`js/admin.js`（17 处调用点替换）

---

### 🔵 P3: login.css 版本注释改为 v1.44 ✅

**问题**：`login.css` 注释 `/* 伏羲登录页样式 v1.50 */` 误标为 v1.50。

**修复**：改为 `/* 伏羲登录页样式 v1.44 */`

**影响文件**：`css/login.css`

---

### 🔵 P3: Wiki 全局正则性能优化 ✅

**问题**：`_structureContent()` 中 4 个正则表达式为局部匿名字面量，
每次函数调用都重新编译正则对象。大篇幅 Wiki 页面可能触发大量 `.replace()` 操作导致用户可感知的延迟。

**修复**：
- 将 4 个正则提取为文件级常量：`_WIKI_ACTION_PATTERN`、`_WIKI_KV_FULL_RE`、
  `_WIKI_KV_NESTED_RE`、`_WIKI_KV_EMPTY_RE`、`_WIKI_LI_RE`、`_WIKI_ACTION_ITEM_RE`
- 新增 `_WIKI_MAX_REPLACEMENTS = 50` 限制每次 regex replace 的最大触发次数，防止恶意大内容导致浏览器卡顿
- 每个 replace/regex exec 前重置 `lastIndex = 0`，因为全局正则在函数间共享

**影响文件**：`js/wiki.js`

---

## 验证确认

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| files.js 内联 onclick 含用户数据 | 2 处 | 0 处 ✅ |
| files.js 裸 fetch 调用 | 2 处 | 0 处 ✅ |
| admin.js 不安全 toFixed | 约 12 处 | 0 处 ✅ |
| utils.js safeNum 函数 | 不存在 | 已添加 ✅ |
| login.css 版本注释 | v1.50 | v1.44 ✅ |
| wiki.js 内联正则（每次编译） | 4 个 | 0 个 ✅ |
