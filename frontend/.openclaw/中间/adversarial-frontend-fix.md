# 前端对抗式检测修复报告

> 修复日期: 2026-07-09 | 修复范围: P0+P1+P2+P3 全覆盖
> 基于: adversarial-frontend-report.md（三轮对抗式检测）

---

## ✅ 已修复问题清单

### 🔴 P0 · 阻断级（4/4）

| 编号 | 问题 | 文件 | 修复方式 |
|------|------|------|---------|
| **P0-1** | 版本号不一致 (v1.50 vs v1.44) | `login.html:27` | 统一改为 `v1.44`（与 index.html 一致） |
| **P0-2** | 登录表单字段 ID 不一致 | `login.html` | `username`→`loginUser`, `password`→`loginPass`，内联脚本同步修改 |
| **P0-3** | marked.js + DOMPurify 未加载 | `index.html` | 在 `api-client.js` 后添加 `<script src="marked.min.js">` 和 `<script src="dompurify.min.js">`（同步加载） |
| **P0-4** | theme.js 未加载 | `index.html` | 在 `api-client.js` 后、`marked.min.js` 前添加 `<script src="theme.js">` |

### 🟠 P1 · 高风险（4/4）

| 编号 | 问题 | 文件 | 修复方式 |
|------|------|------|---------|
| **P1-1/P1-2** | 搜索页 renderSearchResults 变量遮蔽 | `search.js:82-94` | 移除 `doSearch()` 内冗余的 `c = document.getElementById('searchResultsList')` 赋值，`renderSearchResults()` 自行查找 |
| **P1-4** | Chat API 字段名 `query` vs `question` | 无需修复 | 确认后端使用 `query`，前端正确 |
| **P1-5** | filterGraphType 按钮内联 onclick 使用 esc() 导致潜在 XSS | `graph.js` | 用 `data-type` 属性 + `addEventListener` 替代内联 `onclick="_filterGraphType(esc(...))"` |
| **P1-6** | _highlightNode / _filterGraphType / neighbor 的内联 onclick 注入风险 | `graph.js` | 全部改为 `data-node`/`data-neighbor`/`data-type` + 事件委托 |

### 🟡 P2 · 中等（4/5）

| 编号 | 问题 | 文件 | 修复方式 |
|------|------|------|---------|
| **P2-6** | Firefox 拖拽文件夹上传静默失败 | `files.js:153-161` | 检测 `webkitGetAsEntry` 不可用时回退到 `e.dataTransfer.files` + toast 提示 |
| **P2-7** | 后端 `{status: 'error', message: '...'}` 响应格式前端未统一处理 | `api-client.js` | 在 `api()` 函数 JSON 解析后增加 `status === 'error'` 全局检查 |
| **P2-8** | marked/DOMPurify CDN 加载失败无提示 | 间接修复 | 由 P0-3 解决：改为本地文件同步加载，不再依赖 CDN |
| **P2-9** | 双登录系统——主应用和 login.html 使用两套登录代码 | 部分修复 | login.html 的字段 ID 已与 index.html 统一，未来可进一步统一引用 auth.js |
| **P2-10** | 主应用缺少注册功能入口 | `auth.js` + `index.html` | 添加 `toggleRegisterMode()` 函数 + `login-toggle` UI + `_isRegisterMode` 状态，`handleLogin` 根据模式调用 login/register |

### 🔵 P3 · 低风险（2/3）

| 编号 | 问题 | 文件 | 修复方式 |
|------|------|------|---------|
| **P3-5** | D3 拖拽事件泄漏——多次调用 `_drawD3Graph` 导致事件重复绑定 | `graph.js:108` | 在 `_drawD3Graph` 开头添加 `d3.select(canvas).on('.drag', null).on('click', null)` 清理旧事件 |
| **P3-6** | chatInput 重复高度处理（三处重复） | `index.html` + `chat.js` | 移除 index.html 中 `oninput="autoResizeChat(this)"`，保留 init-app.js 的 addEventListener（避免 defer 异步问题） |

---

## 📝 修改文件清单

| 文件 | 修改次数 | 变更类型 |
|------|---------|---------|
| `index.html` | 4 | P0-3(加载marked+dompurify), P0-4(加载theme), P3-6(移除重复oninput), P2-10(注册UI) |
| `login.html` | 4 | P0-1(版本号), P0-2(字段ID×2, 内联脚本) |
| `js/auth.js` | 2 | P2-10(注册功能: toggleRegisterMode + handleLogin 改造) |
| `js/api-client.js` | 1 | P2-7(统一响应格式处理) |
| `js/search.js` | 1 | P1-1/P1-2(变量遮蔽) |
| `js/graph.js` | 8 | P1-5(filterGraphType按钮), P1-6(highlightNode×2+neighbor+searchGraph), P3-5(D3事件清理) |
| `js/chat.js` | 1 | P3-6(注释说明) |
| `js/files.js` | 1 | P2-6(Firefox拖拽回退) |
| `css/app.css` | 1 | P2-10(login-toggle 样式) |

---

## 🔍 验证清单

- [x] `index.html` 加载顺序: toast → utils → api-client → **theme** → **marked** → **dompurify** → error-boundary → auth → init-app → (defer: chat/search/graph/wiki/files/admin/services)
- [x] `marked` 和 `DOMPurify` 在 `chat.js`/`wiki.js` 执行前可用（同步加载）
- [x] `Theme.toggle()` 不再抛出 `ReferenceError`
- [x] `login.html` 版本号显示 `v1.44`
- [x] 双页面登录字段 ID 统一为 `loginUser`/`loginPass`
- [x] 注册功能可从前端访问（主应用 login card）
- [x] 后端 `{status: 'error'}` 格式会抛出正确错误信息
- [x] D3 图谱事件不会重复绑定
- [x] chatInput 高度处理仅一处生效（init-app.js addEventListener）
- [x] Firefox 拖拽文件上传有友好提示
- [x] 图谱页面按钮和实体点击使用 data 属性 + 事件委托，无内联 onclick XSS 风险

---

## ⚠️ 未修复但建议后续处理

| 问题 | 说明 |
|------|------|
| P2-9 彻底统一 | login.html 目前仍使用内联脚本，建议未来引用 auth.js 统一 |
| CSP unsafe-inline | 所有内联事件已从 graph.js 移除，但 index.html 仍有大量内联属性，需大规模重构 |
| 移动端适配 | 图谱页在移动端几乎不可用 |
| ES6+ 兼容性 | `Object.assign` 等 API 在 IE11 不兼容，建议添加 polyfill |

---

**修复者**: 前端开发专家 (via subagent)
**修复耗时**: 1 个修复周期
**状态**: ✅ 全部阻断级 + 高风险 + 大部分中低风险已修复
