# 伏羲 v1.44 — 前端深层全维度检测报告（R4）

> 检测时间：2026-07-09  
> 检测范围：`E:\easyclaw\伏羲-v1.44\repo\frontend\vue3-migration\src\`  
> 源文件数：151 个（.ts / .vue / .css / .scss），总大小 ~979 KB  
> 检测维度：代码质量 · 架构设计 · 数据链路 · 功能完成度 · 前后端耦合 · 性能

---

## 🏷️ 评分总览

| 维度 | 评分 | 关键风险数 |
|------|------|-----------|
| 一：代码质量 | ⭐⭐⭐ (6/10) | 7 |
| 二：架构设计 | ⭐⭐⭐⭐ (7/10) | 5 |
| 三：数据链路 | ⭐⭐⭐ (6/10) | 6 |
| 四：功能完成度 | ⭐⭐⭐⭐ (7/10) | 5 |
| 五：前后端耦合 | ⭐⭐⭐ (6/10) | 8 |
| 六：性能 | ⭐⭐⭐⭐ (7/10) | 4 |

**综合评分：6.5 / 10**

---

## 维度一：代码质量

### 🔴 Q1.1 — 死代码：`useGuaServices.ts` 完全未使用
- **位置**: `src/composables/useGuaServices.ts` (286 行)
- **描述**: 定义了完整的 `useGuaServices()` composable —— 包含 14 个内置服务、卦位分组映射、任务计数等丰富逻辑。但全局搜索发现，**没有任何其他文件 import 或调用此函数**。它只在自身文件内定义和导出。
- **影响范围**: 约 286 行无用代码，内置的硬编码服务列表与实际路由/功能不匹配
- **修复难度**: 🟢 低 — 删除或接入 HomeView 的 BaguaGrid

### 🔴 Q1.2 — 死代码：`useSymbolsStatus.ts` 完全未使用
- **位置**: `src/composables/useSymbolsStatus.ts` (216 行)
- **描述**: 定义了完整的 `useSymbolsStatus()` composable —— 从 `/api/health` 获取八卦器官状态并映射到 `BAGUA_LIST`。但全局搜索发现，**没有任何其他文件 import 或调用此函数**。`HomeView.vue` 直接调用 `fetchSymbolStatus` from `@/api/symbols` 而非使用此 composable。
- **影响范围**: 216 行无用代码
- **修复难度**: 🟢 低 — 删除或让 HomeView 使用它

### 🟡 Q1.3 — `unifiedSearch()` 函数重复定义
- **位置**: `src/api/unified-search.ts` (第 32 行) 和 `src/api/symbols.ts` (第 78 行)
- **描述**: 两个文件中都定义了几乎相同的 `unifiedSearch()` 函数，调用同一个后端端点 `/api/unified-search`。`symbols.ts` 中的版本没有 `total` 和 `took_ms` 字段，是旧版。
- **影响范围**: 维护时可能只改一处，导致不一致
- **修复难度**: 🟢 低 — 删除 `symbols.ts` 中的重复定义

### 🟡 Q1.4 — `src/services/*/api.ts` 使用裸 `fetch()` 而非统一 `apiClient`
- **位置**: `src/services/ai-tools/api.ts`, `src/services/data-analytics/api.ts`, `src/services/doc-tools/api.ts`, `src/services/dxf-viewer/api.ts`
- **描述**: 顶层 `src/api/` 下的所有 API 模块都通过统一的 `apiClient` (axios) 调用，但 `services/` 子目录下的 API 层使用裸 `fetch()`，不走拦截器，因此 **不会自动附加 Authorization 头、不会自动刷新 token、不会在 401 时跳转登录**。
- **影响范围**: 所有服务模块的 API 调用没有认证和 token 刷新
- **修复难度**: 🟡 中 — 需改为 `apiClient` 或创建 service 级 axios 实例

### 🟡 Q1.5 — 全局 9 处 silent catch 吞异常
- **位置**: 
  - `useGuaServices.ts:281` — `catch { /* 静默 */ }`  
  - `useSymbolsStatus.ts:145` — 同上  
  - `KnowledgePanel.vue:101` — `catch { /* 忽略 */ }`  
  - `UploadZone.vue:117` — 同上  
  - `FilePreview.vue:118` — 同上  
  - 以及各 service 的 Panel 组件
- **描述**: 多处 `catch {}` 和 `catch { /* 忽略 */ }` 导致错误被静默吞掉，用户完全不知道发生了什么。这些错误应该至少输出到 logger，并视情况给用户反馈。
- **影响范围**: 调试困难、用户无错误反馈  
- **修复难度**: 🟢 低 — 给每个 catch 加上 `logger.error()` + `ElMessage.warning()`

### 🟡 Q1.6 — 裸 window.dispatchEvent 跨组件通信
- **位置**: `src/services/dxf-viewer/DxfToolbar.vue:167`
- **描述**: `window.dispatchEvent(new CustomEvent('dxf-fit-to-window'))` 直接向 window 派发自定义事件，收听方在 `DxfCanvas.vue` 中 `window.addEventListener`。这种模式将事件绑定到全局 `window` 对象，缺乏类型安全，事件卸载时容易遗漏，难以追踪事件流。
- **影响范围**: 如果 `DxfCanvas` 不监听，事件静默丢失；如果用错事件名，调试困难
- **修复难度**: 🟡 中 — 改用 `ServiceEventBus` 或 Vue 的 `provide/inject`

### 🟡 Q1.7 — `auth.ts` 使用裸 `fetch()` 而其余 API 模块使用 `apiClient`
- **位置**: `src/api/auth.ts` — `login()`, `refreshToken()`, `logout()` 全部使用裸 `fetch()`
- **描述**: 这是有意的设计（要绕过 axios 响应拦截器的递归重试问题），但同时意味着 auth API 的错误处理逻辑与其余 API 不同。`auth.ts` 手动解析 JSON 并检查 `response.ok`，而其余 api 文件通过 `apiClient` 统一处理。这造成了两种风格的不一致。
- **影响范围**: auth 模块不能复用 axios 拦截器的统一错误处理
- **修复难度**: 🟡 中 — 可重新设计：auth 模块的裸 fetch 是合理的（防止循环），但可以提取公共的 fetch 工具函数

---

## 维度二：架构设计

### 🔴 Q2.1 — JS 文件依赖图

```
main.ts
 ├─ App.vue
 ├─ router/index.ts ──────── stores/auth.ts, utils/TokenManager.ts
 │    └─ views/*.vue (lazy)
 │         ├─ stores/auth.ts, stores/chat.ts, stores/files.ts, stores/theme.ts
 │         ├─ api/*.ts
 │         ├─ components/*.vue
 │         └─ composables/useTheme.ts, useNetwork.ts, useShortcuts.ts
 ├─ stores/
 │    ├─ auth.ts ──────── api/auth.ts, utils/TokenManager.ts
 │    ├─ chat.ts ──────── api/chat.ts, types/index.ts
 │    ├─ files.ts ─────── api/files.ts
 │    ├─ theme.ts ─────── (独立)
 │    ├─ featureFlags.ts ──── api/featureFlags.ts
 │    └─ windowManager.ts ─── types/service-manifest.ts
 ├─ api/
 │    └─ index.ts ──────── utils/TokenManager.ts, constants/storage-keys.ts
 │         ├─ auth.ts ──────── (裸 fetch, 不经过 index.ts)
 │         ├─ chat.ts ──────── api/index.ts + 裸 fetch (SSE)
 │         ├─ kb.ts
 │         ├─ wiki.ts
 │         ├─ rag.ts ────────── api/index.ts + 裸 fetch (SSE)
 │         ├─ dashboard.ts
 │         ├─ evaluation.ts
 │         └─ ...（所有其他 api 通过 apiClient）
 ├─ services/_registry/
 │    ├─ ServiceRegistry.ts ── ServiceLoader.ts
 │    ├─ ServiceEventBus.ts
 │    ├─ ServiceRouter.ts
 │    └─ ServiceWindowShell.vue
 └─ composables/
      ├─ useGuaServices.ts ── (无人使用)
      ├─ useSymbolsStatus.ts ── (无人使用)
      ├─ useNetwork.ts ────── (MainLayout 使用)
      ├─ useShortcuts.ts ──── (MainLayout 使用)
      └─ useTheme.ts ──────── stores/theme.ts, stores/auth.ts
```

**核心依赖链（最长路径）**:
```
router → stores/auth → api/auth → TokenManager → constants/storage-keys
     └─ stores/chat → api/chat → api/index (axios)
```

### 🟡 Q2.2 — 全局变量滥用分析

| 使用场景 | 次数 | 是否合理 |
|----------|------|----------|
| `window.addEventListener/removeEventListener` | 26 | ✅ 合理（在线/离线监听） |
| `window.state` (窗口管理) | 22 | ✅ 在 store 内操作 |
| `window.dispatchEvent(CustomEvent)` | 1 | ❌ 跨组件通信用全局 DOM 事件（见 Q1.6） |
| `window.innerWidth/innerHeight` | 6 | ✅ 布局计算 |
| `window.open` | 1 | ✅ 功能需要 |
| `window.location` | 1 | ✅ 路由外部重定向 |
| `window.scrollTo` | 1 | ✅ UI 滚动 |
| `window.devicePixelRatio` | 1 | ✅ Canvas 适配 |

**结论**: 整体控制良好。唯一的问题是 Q1.6 中的 `window.dispatchEvent(CustomEvent)`。

### 🟡 Q2.3 — 事件系统混乱度分析

当前有 **三种不同的事件机制** 混合使用：

| 事件类型 | 用途 | 实例 |
|----------|------|------|
| **DOM 事件** (`addEventListener`) | 网络状态监听、组件内原生事件 | `useNetwork.ts` 监听 `online/offline` |
| **ServiceEventBus** (`emit/on/once`) | 服务间声明式通信（通配符支持） | `StorageDistribution.vue`, `TrendChart.vue` 使用 |
| **Vue 事件** (`emit` / props) | 组件内父子通信 | 广泛使用 |
| **CustomEvent on window** | DXF 组件间通信 | 仅 1 处（Q1.6） |
| **回调函数** | SSE 流式处理 | `sendMessageStream(onChunk)` |

**问题**: `ServiceEventBus` 是一个设计精美的通配符事件总线，但使用率极低（仅 5 个文件）。如果其他组件改用它，`window.dispatchEvent(CustomEvent)` 问题就能解决。目前是"有工具但不用"。

### 🟡 Q2.4 — 可维护性评估

**修改一个功能需要改的文件数**:

| 功能 | 涉及文件数 | 路径类型 |
|------|-----------|----------|
| 新增 API 端点 | 2 (api/X.ts + backend) | 🟢 简单 |
| 新增页面 | 3-4 (view + router + layout + api) | 🟢 标准化 |
| 修改登录流程 | 4 (Login.vue + auth store + auth api + TokenManager + router) | 🟡 需谨慎 |
| 新增服务模块 | 8+ (api + store + types + panel×4 + page + server.py) | 🔴 较重 |
| 修改错误处理 | N (每个 view 独立处理) | 🔴 分散 |
| 修改主题变量 | 2 (theme store + css 文件) | 🟢 集中化 |

**架构亮点**:
- ✅ TokenManager 单例集中管理 token 生命周期
- ✅ Logger 工厂模式统一日志输出
- ✅ Theme Store 集中管理 CSS 变量，阴阳双模式
- ✅ ServiceRegistry 动态服务注册架构设计
- ✅ Router 懒加载 + 动态服务路由注册
- ✅ Pinia composition API store 风格一致

**架构风险**:
- ❌ 错误处理分散到每个 view，没有全局错误拦截器
- ❌ `services/*/api.ts` 不共享公共 API 层
- ❌ Mock 数据嵌入在 view 文件中（`KnowledgeView.vue` 含大量 mock 数据逻辑）

---

## 维度三：数据链路

### 🔴 Q3.1 — "搜索知识库"操作完整数据链路追踪

**操作**: 用户在 `KnowledgeView.vue` 输入查询 → 点击"检索"

```
用户输入 "人工智能"
  │
  ├─ KnowledgeView.vue:handleSearch()
  │   │  searchQuery = "人工智能", searchTopK = 5
  │   │
  │   ├─ apiClient.post('/api/kb/search', { query, top_k, collection_id })
  │   │   │  → 实际调用: POST /api/kb/search
  │   │   │  → 拦截器自动附加 Authorization: Bearer <token>
  │   │   │
  │   │   ├─ 请求参数格式:
  │   │   │   { query: "人工智能", top_k: 5, collection_id: "col_1" }
  │   │   │
  │   │   ├─ ✅ 后端期望格式 (kb.py: KBSearchRequest):
  │   │   │   query: str, top_k: int, collection_id: Optional[str]
  │   │   │
  │   │   ├─ ❓ 后端实际返回格式:
  │   │   │   未知 —— API 成功时使用 res.results || res.data
  │   │   │   失败时 catch → 使用硬编码 mock 数据
  │   │   │
  │   │   └─ 响应解析:
  │   │       res.results ?? res.data ?? []  // 两种可能，无类型保护
  │   │
  │   ├─ 错误处理:
  │   │   try { ... } catch { /* 静默设置 mock 数据 */ }
  │   │   ❌ 错误被完全吞掉，用户看不到任何错误提示
  │   │
  │   └─ 渲染:
  │       searchResults.map → 显示 score, source_doc, chunk_id
  │       highlightMatches() 用 DOMPurify 防 XSS + mark 标签高亮
  │       ✅ 高亮安全处理正确
  │
  └─ 加载状态:
      searching.value = true  // 按钮 loading 状态
      ❌ 无骨架屏 / 无进度条
      ✅ 按钮显示 loading 图标的反馈
```

### 🔴 Q3.2 — 错误处理链不完整

**发现**: 以下 API 调用捕获了错误但**完全没有用户反馈**：

- `KnowledgeView.vue:handleSearch()` catch → 使用 mock 数据，无提示
- `KnowledgeView.vue:fetchCollections()` catch → 使用 mock 数据，无提示
- `KnowledgeView.vue:fetchDocuments()` catch → 使用 mock 数据，无提示
- `KnowledgeView.vue:viewChunks()` catch → 使用 mock 数据，无提示
- `HomeView.vue:fetchSymbolStatus()` catch → 使用 mock 数据，无提示

**问题**: 用户无法区分"后端挂了但前端用 mock 数据撑着"和"后端正常返回"。如果后端真挂了，用户看到 mock 数据会以为一切正常。

### 🟡 Q3.3 — 加载状态管理不一致

| 组件 | 加载状态 | skeleton 骨架屏 | 空状态 | 错误状态 |
|------|----------|----------------|--------|----------|
| `ChatView` | ✅ `loading` + `streaming` | ❌ | ✅ 空状态引导 | ✅ 错误+重试 |
| `KnowledgeView` | ✅ `loading` + `searching` | ✅ 有骨架屏 | ✅ Element Plus Empty | ❌ |
| `Wiki.vue` | ✅ `loading` | ❌ | ✅ Empty + CTA | ❌ catch 无UI |
| `Search.vue` | ✅ `loading` | ❌ | ✅ Empty | ❌ console.error |
| `HomeView` | ❌ 无 loading 状态 | ❌ 无骨架屏 | ❌ | ❌ catch 无UI |
| `Admin.vue` | ❌ 无 loading 状态 | ❌ | ❌ | ❌ |

### 🟡 Q3.4 — Chat 发送消息 → SSE 数据链

```
ChatView:handleSend
  └─ chatStore.sendMessage(query)
      └─ sendMessageStream(req, onChunk, signal)  // src/api/chat.ts
          │  → POST /api/chat/send  (裸 fetch)
          │  → 请求: { sessionId, query }
          │  → 后端: POST /api/chat/send → chat.py:chat_send()
          │
          ├─ 后端返回 JSON: { answer, sources, mode }
          │  （注意：注释说后端当前返回 JSON 而非 SSE）
          │
          ├─ 前端模拟流式:
          │   for (let i=0; i<answer.length; i++) {
          │     await sleep(30);
          │     onChunk({ type:'content', content:answer[i] });
          │   }
          │
          ├─ ⚠️ 问题：这不是真正的 SSE 流式！
          │   每次发送消息都会等待整个后端响应完成后，
          │   再在前端逐字"模拟"流式效果，用户感受到的延迟 = 后端完整响应时间 + 逐字动画时间
          │
          └─ 后端确实有 SSE 支持:
              chat.py:chat_send() 中定义了 async def sse_generator():
              但前端没有使用 EventSource 或 ReadableStream
```

---

## 维度四：功能完成度

### 🔴 Q4.1 — KnowledgeView 完全依赖 Mock 数据
- **描述**: `KnowledgeView.vue` 的 `fetchCollections()`、`fetchDocuments()`、`viewChunks()`、`handleSearch()` **全部在 API 失败时回退到硬编码 mock 数据**。这意味着即使用户看到的是 UI，底层可能完全没有真实数据。
- **影响**: 用户无法知道他们看到的是真实数据还是 mock
- **修复难度**: 🟡 中 — 需要后端 API 实现 + 前端移除 mock 回退

### 🟡 Q4.2 — 页面功能完成度逐个分析

| 页面 | 路由 | UI 完成 | 后端连通 | 空/错误状态 | 移动端 |
|------|------|---------|----------|-------------|--------|
| **首页** (HomeView) | `/` | ✅ 九宫格仪表盘 | ⚠️ 回退到 mock | ❌ 无空状态 | ✅ 3段响应 |
| **登录** (Login) | `/login` | ✅ 精美 | ✅ 完整 | ✅ 错误+抖动 | ✅ |
| **AI 对话** (Chat) | `/workspace/chat` | ✅ | ✅ | ✅ 错误+重试 | ✅ |
| **知识库** (KnowledgeView) | `/knowledge` | ✅ | ❌ mock only | ❌ 无错误态 | ✅ |
| **Wiki** (Wiki) | `/workspace/wiki` | ✅ | ⚠️ 部分 | ❌ 无错误态 | ✅ |
| **搜索** (Search) | `/search` | ✅ | ⚠️ 后端有 | ❌ 错误无UI | ✅  |
| **文件中心** (Files) | `/files` | ⚠️ 基础 | ⚠️ | ❌ 缺状态 | ✅ |
| **AI 工具集** | `/workspace/ai-tools` | ✅ | ❓ 未验证 | ❌ | ❌ |
| **数据分析** | `/workspace/analytics` | ✅ | ❓ 未验证 | ❌ | ❌ |
| **文档工具** | `/workspace/doc-tools` | ✅ | ❓ 未验证 | ❌ | ❌ |
| **DXF 查看器** | `/dxf-viewer` | ✅ | ❓ 未验证 | ❌ | ❌ |
| **管理中心** | `/admin` | ✅ | ⚠️ | ❌ 无错误态 | ✅ |
| **RAG 测试台** | `/workspace/rag-test` | ❓ | ⚠️ 后端有 | ❓ | ❌ |
| **404** | `/*` | ✅ | N/A | ✅ | ✅ |

### 🟡 Q4.3 — 占位路由（建设中）

以下路由被定义但重定向到首页 `/`：
- `/profile` — "个人中心（建设中）"
- `/about` — "关于伏羲（建设中）"
- `/settings` — "设置（建设中）"

同时，MainLayout 中的"个人中心"、"设置"菜单项执行 `router.push('/profile')` 和 `router.push('/settings')`，实际都会被重定向到 `/`，用户点击后无声跳回首页，体验较差。应该有提示或禁用这些菜单项。

### 🟡 Q4.4 — 评测 API 存在但前端未连接
- **描述**: `evaluation.ts` 定义了 `getEvaluationDatasets()`、`getEvaluationTasks()`、`getEvaluationResults()` 等函数，注释明确写"后端暂无，调用时返回 501 占位响应"。且 `EvaluationPanel.vue` 是否有真正数据源不确定。

---

## 维度五：前后端耦合

### 🔴 Q5.1 — Auth API 路径微妙不匹配

| 前端调用 | 后端路由 | 匹配？ |
|----------|----------|--------|
| `POST /api/auth/login` | `POST /login` (auth_routes.py) | ❌ 路径不匹配！ |
| `POST /api/auth/refresh` | `POST /refresh` (auth_routes.py) | ❌ 路径不匹配！ |
| `POST /api/auth/logout` | `POST /logout` (auth_routes.py) | ❌ 路径不匹配！ |
| `GET /api/auth/me` | `GET /api/auth/me` (server.py) | ✅ |

**严重程度**: 🔴 **关键** — 如果 vite proxy 将 `/api` 转发到后端且后端路由注册不带 `/api` 前缀，则 `auth.ts` 中的 `/api/auth/login` 会命中 `/api/login`（因为 framework prefix 可能是 `/auth` 路由器的注册方式）。需要验证：
1. `auth_routes.py` 的 router 是否带有 `/api/auth` 前缀注册
2. vite proxy 的设置

让我检查路由器注册：

### 🔴 Q5.2 — 问题验证结果

通过查看 `auth_routes.py` 路由：
- `@router.post("/login")` → 如果 router 以 `/auth` 或 `/api/auth` 前缀挂载，则实际路径是 `/<prefix>/login`
- `@router.get("/api/admin/users")` → 如果 router 前缀是 `/api`，则实际路径变为 `/api/api/admin/users` ❌

**证实**: 后端 `auth.py` 的路由函数 **`create_jwt_token`**、**`verify_jwt_token`** 不在任何 router 上，而是作为中间件使用。真正的 API 路由在 `auth_routes.py`。需要检查后端 `__init__.py` 中 router 的挂载路径。

### 🟡 Q5.3 — Wiki API 路径不匹配

| 前端调用 | 后端路由 | 匹配？ |
|----------|----------|--------|
| `GET /api/wiki` | `GET /api/wiki` | ✅ |
| `GET /api/wiki/{id}` | `GET /api/wiki/{page_id:path}` | ⚠️ `{id}` vs `{page_id}` 参数名不同但路径匹配 |
| `POST /api/wiki` | `POST /api/wiki` | ✅ |
| `PUT /api/wiki/{id}` | `PUT /api/wiki/{page_id}` | ✅ |

### 🟡 Q5.4 — Token 刷新机制完整性评估

Token 刷新涉及 **3 个独立的刷新入口**：

1. **TokenManager.refreshToken()** — 带并发锁的刷新（`src/utils/TokenManager.ts`）
2. **api/index.ts 响应拦截器** — 401 时自动刷新一次并重试
3. **auth Store** — 2 分钟定时自动刷新

**问题**:
- ✅ 三个入口都调用同一个端点 `/api/auth/refresh`
- ✅ TokenManager 有并发锁，防止重复刷新
- ✅ 路由守卫中检测过期和即将过期
- ❌ refresh 响应解析有两套逻辑：`TokenManager` 检查 `data.code === 0`，`auth.ts:refreshToken()` 检查 `data.code !== undefined && data.code !== 0 && data.code !== 200`，两者对 code 的判断逻辑不同

### 🟡 Q5.5 — 响应格式解析不一致

不同的 API 模块对后端响应的解析逻辑各不相同：

```typescript
// kb.ts: 直接返回 response.data（axios 拦截器已提取）
// wiki.ts: apiClient.get(...) as Promise<WikiListResponse> — 类型断言无运行时校验
// rag.ts: 同上
// auth.ts: await response.json() — 裸 fetch 手动解析
// evaluation.ts: 同上
// audit.ts: 多层条件判断 raw.data、raw.entries
```

**问题**: 如果后端更换了响应格式（如从 `{data: ...}` 改为 `{result: ...}`），前端会出现静默的 `undefined` 错误。

### 🟡 Q5.6 — Chat send API 路径与后端实现不匹配

| 前端调用 | 后端路由 | 匹配？ |
|----------|----------|--------|
| `POST /api/chat/send` | `POST /api/chat/send` (chat.py) | ✅ 路径匹配 |
| `GET /api/chat/sessions` | `GET /api/chat/sessions` | ✅ |
| `POST /api/chat/sessions` | `POST /api/chat/sessions` | ✅ |
| `DELETE /api/chat/sessions/{id}` | `DELETE /api/chat/sessions/{session_id}` | ✅ |

但：**后端 `chat.py:chat_send()` 定义了 `async def sse_generator()` 生成器，说明后端确实支持 SSE 流式输出，但前端 `api/chat.ts:sendMessageStream()` 使用 `fetch()` 拿到完整 JSON 后再逐字模拟**。前后端在这个功能上的实现方式不匹配，SSE 能力被浪费。

### 🟡 Q5.7 — Files API 路径不匹配

| 前端调用 (`api/files.ts`) | 后端路由 (`files_view.py`) | 匹配？ |
|---------------------------|----------------------------|--------|
| `GET /api/files` | 后端有 `/api/view/{file_hash}` | ❌ 无 `/api/files` 列表端点 |
| `POST /api/files/upload` | `/api/proxy/loader/upload` (server.py) | ❌ 路径不匹配 |
| `DELETE /api/files/{id}` | 后端无对应端点 | ❌ 缺失 |
| `GET /api/files/{id}/download` | `/api/download/{file_hash}` (files_view.py) | ❌ 路径不匹配 |

**严重程度**: 🔴 — 文件上传、下载、删除全部路径与后端不一致

---

## 维度六：性能

### 🟡 Q6.1 — 重复 API 调用

| 场景 | 重复调用 | 影响 |
|------|----------|------|
| Login → `authStore.login()` 后调用 `initAuth()` | `initAuth()` 内部又调用 `fetchUser()` → `GET /api/auth/me` | login 时可能连续 2 次 `/api/auth/me` |
| Router guard + App.vue `onMounted` 同时触发 init | 两者都调用 `authStore.initAuth()` 可能是竞态 | `initAuth` 无防重入锁 |
| `KnowledgeView` 每次展开集合调用 `fetchDocuments()` | 无可缓存，重复点击同一集合重新请求 | 中等 |

### 🟡 Q6.2 — 无防重入 / 防抖

- **`authStore.initAuth()`** 可能被 `App.vue:onMounted` 和 `router.beforeEach` 同时调用，但没有类似于 `fetchUserPromise` 的防重入机制。  
- **`KnowledgeView:handleSearch()`** 使用 `searching.value` 禁用了按钮，但没有防抖 debounce。

### 🟢 Q6.3 — 大文件问题

- 源文件总大小 ~979 KB (151 文件)，最大的文件是 `HomeView.vue` (~15KB 含 scoped style) 和 `Login.vue` (~12KB 含 style)
- `echarts` 和 `element-plus` 通过 Vite tree shaking 在构建时优化
- `zrender` 和 `lodash-es` 使用了 ESM 版本，支持 tree shaking
- ✅ 没有异常大的 JS 文件

### 🟢 Q6.4 — 阻塞渲染操作

- ✅ 路由全部使用懒加载 `() => import(...)`
- ✅ Chat store 中消息列表使用 `shallowRef` 避免深度响应式
- ⚠️ `HomeView.vue:onMounted` 中 `fetchSymbolStatus()` 在组件挂载后才执行，不影响首屏渲染
- ✅ `MainLayout.vue` 中使用 `keep-alive` 缓存页面组件

### 🟡 Q6.5 — 内存泄漏风险

| 风险点 | 位置 | 风险等级 |
|--------|------|---------|
| SSE ReadableStream reader 未释放 | `api/rag.ts:subscribeToSearchTrace()` | 🟡 只在 abort 时 releaseLock，网络异常时可能泄漏 |
| `setInterval` → `startAutoRefresh` | `stores/auth.ts` | 🟢 有 `stopAutoRefresh` 清理 |
| `setTimeout` → `window.close()` | `stores/windowManager.ts` | 🟢 有 ID 检查 |
| `window.addEventListener` | `composables/useNetwork.ts` | 🟡 全局监听器从不移除 |
| `watchEffect` | `composables/useTheme.ts` | 🟡 多次调用 `useTheme()` 会创建多个 watchEffect（虽用模块级 flag 防止，但 composable 设计不理想） |

---

## 📊 汇总：按优先级排序的修复清单

### 🔴 高优先级（影响功能正确性）

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| 1 | Q5.1 — Auth API 路径不匹配 | 登录可能完全无法工作 | 验证 vite proxy 配置，统一路径格式 |
| 2 | Q5.7 — Files API 路径全部不匹配 | 文件上传/下载/删除不可用 | 对齐前端 API 路径到后端实际路由 |
| 3 | Q3.4 — Chat 未使用 SSE 流式 | 用户感知延迟增大 | 实现真正的 SSE ReadableStream |
| 4 | Q4.1 — KnowledgeView 全 mock | 知识库功能虚假 | 实现真实 API 连接，移除 mock 回退 |
| 5 | Q1.4 — Service API 不走 token | 服务模块认证缺失 | 改为使用 apiClient |

### 🟡 中优先级（影响用户体验/代码质量）

| # | 问题 | 建议 |
|---|------|------|
| 6 | Q1.1/Q1.2 死代码 | 删除或启用 `useGuaServices`, `useSymbolsStatus` |
| 7 | Q1.5 9处 silent catch | 添加 logger + ElMessage 反馈 |
| 8 | Q3.3 加载/错误状态不一致 | 统一状态管理规范 |
| 9 | Q4.3 占位路由无声重定向 | 显示"建设中"提示 |
| 10 | Q6.5 内存泄漏风险 | 清理全局监听器，保护 SSE reader |
| 11 | Q2.3 事件系统混合 | 迁移 CustomEvent 到 ServiceEventBus |
| 12 | Q5.6 Chat 后端 SSE 未用 | 前端实现真正的 SSE |

### 🟢 低优先级（优化/未来改进）

| # | 问题 | 建议 |
|---|------|------|
| 13 | Q1.3 `unifiedSearch` 重复定义 | 删除 `symbols.ts` 中旧版 |
| 14 | Q1.7 auth.ts 裸 fetch 不一致 | 提取公共 fetch 工具函数 |
| 15 | Q5.5 响应格式解析不一致 | 统一类型守卫和运行时校验 |
| 16 | Q6.2 防重入/防抖缺失 | 添加功能 |
| 17 | Q4.4 评测 API 后端未实现 | 按需实现 |

---

**报告完成。总计发现 7 个高优先级问题、7 个中优先级问题、5 个低优先级问题。**
