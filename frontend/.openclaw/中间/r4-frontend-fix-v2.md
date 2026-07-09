# R4 前端修复报告 v2

> 修复时间：2026-07-09 · 修 3 项，不改其他

---

## 1. API 路径统一

| 文件 | 行号 | 旧路径 | 新路径 | 说明 |
|------|------|--------|--------|------|
| `js/chat.js` | 47 | `/api/chat` | `/api/chat/send` | 对齐后端路由 `/api/chat/send` |
| `vue3-migration/src/views/KnowledgeView.vue` | 405 | `/api/kb/documents` | `/api/documents` | 对齐后端路由 `GET /api/documents` |
| `vue3-migration/src/views/KnowledgeView.vue` | 438 | `/api/kb/documents?collection_id=` | `/api/documents?collection_id=` | 分集合获取 |
| `vue3-migration/src/views/KnowledgeView.vue` | 477 | `/api/kb/documents/{id}/chunks` | `/api/documents/{id}/chunks` | 分块查询 |
| `vue3-migration/src/views/KnowledgeView.vue` | 498 | `/api/kb/search` | `/api/documents/search` | 检索测试 |
| `vue3-migration/src/views/KnowledgeView.vue` | 566 | `/api/kb/documents/{id}` (DELETE) | `/api/documents/{id}` (DELETE) | 删除文档 |
| `vue3-migration/src/views/KnowledgeView.vue` | 393 | `/api/kb/documents` (上传) | `/api/documents` (上传) | 上传端点 |
| `vue3-migration/src/api/kb.ts` | 4-5 | `/api/kb/search`, `/api/kb/documents` | `/api/documents/search`, `/api/documents` | API 封装同步 |

### 已验证正确的路径
- ✅ `/api/auth/login` — `js/auth.js` line 57
- ✅ `/api/auth/register` — `js/auth.js` line 57
- ✅ `/api/auth/me` — `js/init-app.js` line 76
- ✅ `/api/documents` — `js/files.js` line 82 (GET list), line 55/68 (DELETE)
- ✅ `/api/upload` — `js/files.js` line 244

---

## 2. 删除死代码

### 已删除的函数

| 文件 | 函数名 | 原因 |
|------|--------|------|
| `js/utils.js` | `debounce()` | 定义但零引用（所有 `.js` / `.html` 中均无调用） |
| `js/utils.js` | `throttle()` | 同上 |
| `js/utils.js` | `sanitizeInput()` | 同上 |
| `js/chat.js` | `autoResizeChat()` | 高度逻辑已由 `init-app.js` 统一处理，注释已注明「P3-6 fix」，无外部调用 |
| `js/error-boundary.js` | `safeFetch()` | 被 `api-client.js` 的 `__fetchWithTimeout` 替代，注释已注明「如需删除死代码...」 |
| `js/error-boundary.js` | `showLoading()` | `@unused` 注释标注，无调用 |
| `js/error-boundary.js` | `showError()` | `@unused` 注释标注，无调用 |

### 确认无 mock 文件
- `vue3-migration/src/` 中 zero mock/fake/stub 文件匹配
- `vue3-migration/src/api/*.ts` 中无 mock/fake/stub 字面量

---

## 3. KnowledgeView 接入真实 API

### 3.1 mock 数据替换
- **`totalSizeText`** — 原来 `collections.length * 1024 * 1024 * 15`（硬编码 ~15MB/集合），改为 `documents.reduce((sum, d) => sum + (d.size || 0), 0)`（真实文档大小累加）

### 3.2 API 端点迁移
- 全量 `/api/kb/*` → `/api/documents*`，详情见上表（共 8 处修改）
- `GET /api/documents` — 获取文档列表
- `DELETE /api/documents/{id}` — 删除文档
- `POST /api/documents/search` — 检索测试
- 上传端点统一为 `/api/documents`

---

## 影响范围总结
- **修改文件**：5 个 (`js/chat.js`, `js/utils.js`, `js/error-boundary.js`, `vue3-migration/src/views/KnowledgeView.vue`, `vue3-migration/src/api/kb.ts`)
- **API 路径修正**：8 处
- **死代码删除**：7 个函数
- **Mock 数据替换**：1 处 (`totalSizeText`)
- **破坏性**：低 — 所有修改均对齐已有后端路由 `GET /api/documents`, `/api/chat/send`
