# 伏羲系统前端 P1 问题修复总结

修复日期：2026-07-09
修复人：前端开发专家

---

## 修复总览

| P1 编号 | 问题描述 | 状态 | 变更文件 |
|---------|---------|------|---------|
| P1-1 | Chart.js 未引入，成长面板无图表 | ✅ 已修复 | index.html |
| P1-2 | files.js 分类按钮 XSS 风险 | ✅ 已修复 | files.js |
| P1-3 | _adminError 跨文件依赖未显式导出 | ✅ 已修复 | utils.js, admin.js |
| P1-4 | graph.js 节点详情缺少 DOMPurify 二次防护 | ✅ 已修复 | graph.js |
| P1-5 | 非流式聊天长时间无反馈 | ✅ 已修复 | chat.js |
| P1-6 | _addHeadingIds 正则替换 Bug | ⏭ 已在之前修复 | wiki.js (之前已修) |
| P1-7 | uploadFiles() 使用裸 fetch 无 token | ✅ 已修复 | files.js |
| P1-8 | loadWikiTree 中 Promise.all 错误处理不全 | ✅ 已修复 | wiki.js |
| P1-9 | Wiki 分类为空时无提示 | ✅ 已修复 | wiki.js |
| P1-10 | 401 handler 可能暴露 DOM 状态不一致 | ✅ 已修复 | api-client.js |
| P1-11 | 移动端快捷按钮溢出 | ✅ 已修复 | app.css |
| P1-12 | 文件夹上传依赖 Chrome API 无 Firefox 回退 | ✅ 已修复 | files.js |
| P1-13 | Token 正则模式过严 | ⏭ 无需修复 | — (正则已足够宽松) |
| P1-14 | 版本号 v1.50 vs v1.44 不一致 | ✅ 已修复 | index.html |
| P1-15 | CSV 导出时间字段可能为空 | ✅ 已修复 | files.js |
| P1-16 | services.js modal 事件监听器泄漏 | ✅ 已修复 | services.js |

**已修复: 14 | 之前已修复: 1 | 无需修复: 1**

---

## 详细变更

### P1-1: Chart.js CDN 引入
- **文件**: `index.html` 第 21 行
- **变更**: 新增 `<script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>`
- **CSP**: 同步更新 `script-src` 添加 `https://cdn.jsdelivr.net`
- **影响**: 成长面板的趋势图现在可以正常渲染

### P1-2: 分类按钮 XSS 风险修复
- **文件**: `js/files.js` 分类按钮渲染
- **变更**: 将 `onclick` 中的字符串拼接改为 `data-cat` 属性 + `esc()` 转义
- **原代码**: `onclick="window._renderFiles('` + c.replace(/'/g,"\\'") + `')"`
- **新代码**: `data-cat="` + esc(c) + `" onclick="window._renderFiles(this.dataset.cat)"`
- **影响**: 防止分类名包含特殊字符时的注入风险

### P1-3: _adminError 迁移到 utils.js
- **文件**: `js/utils.js` (新增), `js/admin.js` (移除重复定义)
- **变更**: 将 `_adminError(containerId, msg)` 从 admin.js 移到 utils.js 作为全局工具函数
- **理由**: utils.js 在 admin.js 和 services.js 之前同步加载，消除隐式依赖
- **影响**: 服务管理与管理面板共享同一个错误显示函数，不再依赖脚本加载顺序

### P1-4: graph.js 节点详情安全加固
- **文件**: `js/graph.js` `_showNodeDetail()` 函数
- **变更**:
  1. 关联实体列表改用 `data-neighbor` 属性传递，避免内联 onclick 拼接
  2. 最终 HTML 输出增加 `DOMPurify.sanitize()` 二次清洗
- **影响**: 与 chat.js 保持一致的安全防护层

### P1-5: 聊天非流式模式用户体验优化
- **文件**: `js/chat.js` `sendChat()` 函数
- **变更**:
  1. 增加 3 秒后显示"正在思考，请耐心等待..."的进度提示
  2. 请求超时时间从默认 15s 提升到 30s
  3. 超时错误消息中文化（"请求超时，请稍后重试"）
  4. 401 错误消息中文化（"登录已过期，请重新登录"）
- **影响**: 长回答请求时用户不会看到无反馈的 loading 状态

### P1-7: uploadFiles 使用统一 api() 封装
- **文件**: `js/files.js` `uploadFiles()` 函数
- **变更**: 将 `fetch('/api/upload', { headers: { 'Authorization': 'Bearer ' + getToken() } })` 改为 `api('/api/upload', { method: 'POST', body: fd })`
- **理由**: `api()` 自动处理 token 注入、401 跳转登录、5xx 重试等逻辑
- **影响**: 上传失败时有更好的错误处理和自动重试

### P1-8: loadWikiTree 错误处理增强
- **文件**: `js/wiki.js` `loadWikiTree()` 函数
- **变更**:
  1. 分类加载和页面列表分别用 `.catch()` 捕获，避免 Promise.all 过早 reject
  2. 分类加载失败时返回空对象 `{}`，页面列表加载失败时返回 `{ pages: [] }`
  3. 错误页增加"重试"按钮
- **影响**: Wiki 页面部分功能可用（如仅分类接口故障时页面列表仍可加载）

### P1-9: Wiki 无分类提示
- **文件**: `js/wiki.js` `_renderWikiTree()` 函数
- **变更**: 当所有页面归入「未分类」时，显示提示信息：
  "分类关键词尚未配置，所有页面归入「未分类」。可在后端 /api/wiki 接口返回 categories 字段来启用自动分类。"
- **影响**: 用户和管理员清楚知道为什么没有分类

### P1-10: 401 处理器防御性写法
- **文件**: `js/api-client.js` 401 响应处理
- **变更**: `showLogin()` 调用包裹在 try/catch 中，异常时直接操作 DOM
- **影响**: 即使 `showLogin()` 异常也不影响后续 throw

### P1-11: 移动端快捷按钮适配
- **文件**: `css/app.css`
- **变更**: 新增 `@media(max-width:420px)` 查询，快捷按钮改为纵向排列、居中显示
- **影响**: 在 375px 宽度的手机上按钮不再横向溢出

### P1-12: 文件夹拖拽上传 Firefox 兼容
- **文件**: `js/files.js` `traverseDropItems()` 函数
- **变更**: 检测 `webkitGetAsEntry` 是否可用，不可用时返回空数组，让调用方回退到普通文件上传
- **影响**: Firefox 中拖拽文件夹不再静默失败

### P1-14: 版本号统一
- **文件**: `index.html` 底部版本提示
- **变更**: `v1.50` → `v1.44`
- **影响**: 与项目目录名 `伏羲-v1.44` 一致

### P1-15: CSV 导出时间字段增强
- **文件**: `js/files.js` `exportCSV()` 函数
- **变更**: 时间字段fallback顺序：`created_at || upload_time || uploaded_at || created || date || '未知'`
- **影响**: 兼容更多后端时间字段命名

### P1-16: Modal 事件监听器泄漏修复
- **文件**: `js/services.js`
- **变更**:
  1. 新增 `closeServiceModal()` 和 `_serviceModalEscHandler()` 全局函数
  2. 关闭按钮从内联匿名函数改为调用 `closeServiceModal()`
  3. 每次打开 modal 前先 `removeEventListener` 清理旧 listener
- **影响**: 多次打开服务详情弹窗不会累积 keydown 事件监听器

---

## 未修复项说明

### P1-6: _addHeadingIds 正则 Bug
- **状态**: 之前已修复
- **说明**: 当前代码已使用 counter-based 方法，逐个匹配 heading 标签，不再有 `replaced` 标志位导致的"只替换第一个"问题

### P1-13: Token 正则模式
- **状态**: 无需修复
- **说明**: 当前正则 `/^[A-Za-z0-9._~+\/=-]+$/` 覆盖了标准 JWT base64url 字符集，不会拒绝合法的 JWT token

---

## 向后兼容性

所有修改均遵循最小改动原则：
- 不改变任何公开的 API 签名
- 不改变任何 DOM 结构的 id/class 命名
- CSS 修改仅增加媒体查询，不覆盖现有样式
- JavaScript 函数签名和调用方式不变
