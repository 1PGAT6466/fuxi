# 第三轮对抗式检测 — 前端修复摘要

**修复时间**: 2026-07-09  
**修复人**: 前端开发专家 (Subagent)  
**轮次**: Round 3 (R3)

---

## 🟠 R3-1: login.html — Token 格式验证 + api() 封装

**文件**: `login.html`

**问题**:
1. 登录页使用裸 `fetch()` 直接请求，无超时控制、无错误统一处理
2. 存储 token 前未验证格式合法性（可能存入畸形/注入 payload）

**修复**:
- 新增轻量 `_loginFetch()` 封装函数（含 15s 超时 + AbortController + 统一错误处理）
- 新增 `_isValidToken()` 校验函数：正则 `/^[A-Za-z0-9._~+\/=-]+$/` + 长度 < 4096
- 登录成功后先校验 token 格式，不合法则拒绝存储并提示用户
- 页面初始化时也校验已存储 token，非法则清除
- 改用 `.then()/.catch()/.finally()` Promise 链替代 async/await for 循环（代码更扁平、易读）

**影响**: 中等 — 防止不合规 token 进入 sessionStorage，提升登录安全性

---

## 🟡 R3-3: wiki.js — KV_FULL_RE 正则截断修复

**文件**: `js/wiki.js` (第 ~165 行)

**问题**:
```js
// 原正则
var _WIKI_KV_FULL_RE = /<li>\s*<strong>([^<]+)<\/strong>[：:]\s*([^<]*(?:<br>\s*<\/li>|<\/li>))/g;
```
`([^<]*)` 遇到第一个 `<` 即停止，若 value 中包含 `<a>`、`<code>`、`<em>` 等嵌套 HTML 标签会被截断。

**修复**:
```js
// 新正则 — 允许 value 中嵌套 HTML，仅禁止跨越 <li> 边界
var _WIKI_KV_FULL_RE = /<li>\s*<strong>([^<]+)<\/strong>[：:]\s*((?:(?!<li[\s>])[\s\S])*?)<\/li>/g;
```
- 使用 `(?:(?!<li[\s>])[\s\S])*?` 非贪婪匹配，遇到 `<li` 标签（非 `<li>` 闭合）即停止
- 支持 value 中包含任意嵌套 HTML（链接、行内代码、强调等）

**影响**: 中等 — 修复包含富文本 value 的 Wiki Key-Value 卡片渲染截断问题

---

## 🔵 R3-2: chatInput onkeydown 代码风格清理

**文件**: `index.html` + `js/init-app.js`

**问题**:
`index.html` 中 chatInput 使用内联 `onkeydown` 属性，代码写在 HTML 属性值中：
```html
onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat()}"
```
- 代码混在 HTML 属性中，可读性差
- 无 `typeof sendChat === 'function'` 存在性检查

**修复**:
- 移除 index.html 中的内联 `onkeydown` 属性
- 在 `init-app.js` 的 textarea 初始化 IIFE 中添加 `keydown` 事件监听器
- 添加 `sendChat` 函数存在性检查，避免 chat.js 延迟加载时的错误
- 与其他事件监听器集中管理，代码风格统一

**影响**: 低 — 纯代码风格改进，无功能变化

---

## 改动文件清单

| 文件 | 变更类型 | 风险等级 |
|------|---------|---------|
| `login.html` | 重写内联脚本（~60 行） | 中 |
| `js/wiki.js` | 修复 1 个正则表达式 | 低 |
| `index.html` | 移除 1 个内联属性 | 极低 |
| `js/init-app.js` | 新增 5 行事件监听 | 极低 |
