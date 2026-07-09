# 伏羲系统前端 API 修复报告

> **修复日期**: 2026-07-09  
> **修复范围**: Legacy 前端 (`js/`) + Vue3 迁移版 (`vue3-migration/src/`)  
> **目标**: 删除所有 mock 数据，接入真实后端 API，统一 API 调用路径

---

## 一、删除的 Mock 文件清单（4 个）

| # | 文件路径 | 说明 |
|---|---------|------|
| 1 | `vue3-migration/src/services/ai-tools/mock.ts` | AI 工具集 mock：health/summarize/translate/keywords/entities/classify |
| 2 | `vue3-migration/src/services/data-analytics/mock.ts` | 数据分析 mock：stats/trends/report/storage/export |
| 3 | `vue3-migration/src/services/doc-tools/mock.ts` | 文档工具 mock：convert/merge/split/compress/image-info/text-extract |
| 4 | `vue3-migration/src/services/dxf-viewer/mock.ts` | DXF 查看器 mock：health/files/render（含完整几何假数据） |

---

## 二、删除的硬编码假数据

### 2.1 `MOCK_STREAM_CONTENT` 和 `mockSendMessageStream`

- **文件**: `vue3-migration/src/api/chat.ts`
- **操作**: 完全删除 `MOCK_STREAM_CONTENT` 常量和 `mockSendMessageStream()` 函数
- **影响**: 聊天功能失败时不再显示假文本，而是将错误冒泡给调用层处理

### 2.2 `getMockUnifiedSearch()` 函数

- **文件**: `vue3-migration/src/api/symbols.ts`
- **操作**: 完全删除 `getMockUnifiedSearch()` 函数（含 18 条虚构搜索结果）
- **影响**: 伏羲令搜索失败时不再显示假服务/页面列表

### 2.3 `_wikiCategories` 硬编码分类

- **文件**: `js/wiki.js`
- **操作**: 删除 9 类 80 个硬编码关键词，改为从后端 `GET /api/wiki` 获取 `categories` 字段
- **新增函数**: `_loadWikiCategories()` — 从后端 API 加载分类数据
- **保留**: 图标/颜色映射表 `_CAT_ICON_MAP` / `_CAT_COLOR_MAP` 仅用于视觉呈现，不影响数据分类逻辑
- **降级策略**: 后端返回空时，所有页面归入「未分类」，图标/颜色使用默认值

### 2.4 `_catIcons` / `_catColors` 硬编码

- **文件**: `js/wiki.js`
- **操作**: 改为支持后端 API 返回 `icons`/`colors` 字段，若后端不提供则使用内置映射表
- **新增函数**: `_getCatIcon(cat)` / `_getCatColor(cat)` — 优先使用后端数据，fallback 到内置映射

---

## 三、修改的文件列表

### 3.1 Legacy 前端 (生产版本)

| # | 文件路径 | 修改内容 |
|---|---------|---------|
| 1 | `js/wiki.js` | 删除 `_wikiCategories` 硬编码 → 改为 `_loadWikiCategories()` 从 `/api/wiki` 获取；删除 `_catIcons`/`_catColors` 硬编码 → 改为 `_getCatIcon()`/`_getCatColor()`；`loadWikiTree()` 并行加载分类和页面；`_renderWikiTree()` 分类排序改为动态；`loadWikiPage()` 增加分类预加载 |
| 2 | `js/search.js` | 无需修改（已直接使用后端 API） |

### 3.2 Vue3 迁移版

| # | 文件路径 | 修改内容 |
|---|---------|---------|
| 3 | `vue3-migration/src/api/chat.ts` | 删除 `MOCK_STREAM_CONTENT` 和 `mockSendMessageStream()` |
| 4 | `vue3-migration/src/api/symbols.ts` | 删除 `getMockUnifiedSearch()` 函数及 18 条虚构数据 |
| 5 | `vue3-migration/src/components/search/FuxiLing.vue` | 删除 `getMockUnifiedSearch` 导入和 mock fallback → 搜索失败时显示空结果 |
| 6 | `vue3-migration/src/services/ai-tools/api.ts` | 删除 `mockAiToolsResponse` 导入和 `requestWithFallback()` mock 兜底 → 直接调用后端 API |
| 7 | `vue3-migration/src/services/data-analytics/api.ts` | 删除 `mockAnalyticsResponse` 导入和 `requestWithFallback()` mock 兜底 → 直接调用后端 API |
| 8 | `vue3-migration/src/services/doc-tools/api.ts` | 删除 `mockDocToolsResponse` 导入和 `requestWithFallback()` mock 兜底 → 直接调用后端 API |
| 9 | `vue3-migration/src/services/dxf-viewer/api.ts` | 删除 `mockDxfResponse` 导入和 `requestWithFallback()` mock 兜底 → 直接调用后端 API |

---

## 四、API 路径修正清单

### 4.1 已确认后端兼容的路径（无需修改）

经与后端 API 审计报告交叉验证，以下被视为"不匹配"的路径事实上有后端别名/多路由支持：

| 功能 | Legacy 路径 | Vue3 路径 | 后端状态 |
|------|-----------|----------|---------|
| 聊天对话 | `POST /api/chat` | `POST /api/chat/send` | ✅ 两端点均实现 (chat.py #16, #21) |
| 聊天会话 | 无 | `GET/POST/DELETE /api/chat/sessions` | ✅ 已实现 (chat.py) |
| 知识搜索 | `GET /api/search` | `POST /api/rag/search` | ✅ 两端点均实现 |
| Wiki 列表 | `GET /api/wiki/pages` | `GET /api/wiki` | ✅ 两端点均实现 (wiki.py) |
| Wiki 单页 | `GET /api/wiki/page/<id>` | `GET /api/wiki/<id>` | ✅ 两端点均实现 (路径别名) |
| 文件列表 | `GET /api/documents` | `GET /api/files` | ✅ 两端点均实现 (files_alias.py) |
| 文件上传 | `POST /api/upload` | `POST /api/files/upload` | ✅ 两端点均实现 |
| 文件删除 | `DELETE /api/documents/<hash>` | `DELETE /api/files/<id>` | ✅ 两端点均实现 |
| 联网搜索 | `POST /api/antenna/search` | `GET /api/antenna/search` | ✅ 两端点均实现 (GET+POST) |

### 4.2 新发现的缺失端点

| 端点 | 前端使用位置 | 后端状态 | 处理方案 |
|------|------------|---------|---------|
| `GET /api/wiki/categories` | `js/wiki.js` `_loadWikiCategories()` | ❌ 未实现 | 改为从 `GET /api/wiki` 获取 `categories` 字段 |

---

## 五、状态处理规范

所有 API 调用统一遵循以下状态处理原则：

| 状态 | 前端行为 |
|------|---------|
| **加载中** | 显示 loading 动画（省略号/旋转） |
| **成功（有数据）** | 正常渲染数据 |
| **成功（空数据）** | 显示"暂无数据" + 引导操作（如"上传文档后系统会自动生成"） |
| **失败** | 显示错误信息 + 错误原因，不显示任何兜底假数据 |
| **API 不存在** | 显示"功能开发中"（由 API 返回的 HTTP 错误自然触发） |

---

## 六、API_BASE 配置

- **Legacy 前端**: 使用相对路径（`/api/...`），与后端同源部署，无需额外配置
- **Vue3 迁移版**: 
  - `apiClient` (`api/index.ts`) 使用 `baseURL: ''` + vite proxy
  - 开发环境通过 `VITE_API_TARGET` 环境变量配置代理目标（默认 `http://localhost:8080`）
  - 生产环境通过 vite proxy 或 nginx 反向代理转发 `/api` 请求
  - 各微服务模块（ai/dxf/analytics/tools）有独立 `API_BASE` 常量，始终指向正确的 API 路径

---

## 七、未修改的文件（说明）

以下文件根据「Legacy 版本保持不变」原则未修改：

| 文件 | 原因 |
|------|------|
| `js/api-client.js` | 通用 API 客户端，无 mock 逻辑 |
| `js/chat.js` | 直接调用后端 API，无 mock |
| `js/search.js` | 直接调用 `/api/search`，无 mock |
| `js/graph.js` | 直接调用 `/api/graph`，无 mock |
| `js/files.js` | 直接调用后端 API，无 mock |
| `js/admin.js` | 直接调用后端 API，无 mock |
| `js/services.js` | 直接调用 `/api/services`，无 mock |
| `admin/js/admin-worldtree-v20.js` | 独立管理面板，Legacy 版本 |

---

## 八、对后端的要求

为确保前端功能正常运行，建议后端实现以下内容：

1. **`GET /api/wiki` 返回 `categories` 数组**（已有能力，`wiki.py` #30 已提取）— 建议扩展为 `[{name, keywords[]}]` 格式以提供分类关键词匹配能力
2. **AI 工具服务** (`/api/ai/*`) — 后端已实现但前端之前仅 mock，现在前端将直接调用
3. **数据分析服务** (`/api/analytics/*`) — 同上
4. **文档工具服务** (`/api/tools/*`) — 同上
5. **DXF 查看器服务** (`/api/dxf/*`) — 同上

---

*修复完成。所有前端 API 调用现已接入真实后端，零 mock 数据残留。*
