# R5 蓝队前端修复报告

> 修复时间：2026-07-09 19:07 GMT+8
> 修复范围：`frontend/` 全栈（js/ 原生 + vue3-migration/ Vue3）
> 提交：`8f0084d` — 伏羲 v1.44: R5 蓝队前端修复 (HTTP统一+错误码+会话历史)

---

## 修复清单

### 🔴 HIGH-1: 双HTTP客户端架构缺陷 → 统一使用 apiClient

**问题**：vue3-migration 中 `auth.ts`、`chat.ts`、`rag.ts`、`TokenManager.ts` 存在原生 `fetch` 调用，绕过了 `apiClient` 的统一拦截器（token 注入、401 自动刷新、统一错误处理）。

**修复方案**：
| 文件 | 修改内容 |
|------|---------|
| `api/auth.ts` | `login()` 改用 `apiClient.post()` 替代原生 fetch |
| `api/auth.ts` | `logout()` 改用 `apiClient.post()` 替代原生 fetch |
| `api/chat.ts` | `sendMessageStream()` 保留 fetch（SSE 流式需要 ReadableStream），但 token 统一从 TokenManager 获取 |
| `api/rag.ts` | `subscribeToSearchTrace()` 保留 fetch（同 SSE 原因），添加注释说明 |
| `utils/TokenManager.ts` | `refreshToken()` 保留 fetch（避免循环调用），但统一错误格式处理 |

**保留 fetch 的原因**：axios 不支持浏览器端 ReadableStream 流式读取，SSE 场景必须用原生 fetch。TokenManager.refreshToken() 保留 fetch 是因为 apiClient 的 401 拦截器依赖它，用 apiClient 会导致无限循环。

---

### 🔴 HIGH-2: 无统一错误码体系 → 定义 ApiError + ErrorCodes

**问题**：前端错误处理散落各处，用 `throw new Error(string)` 传递错误，无法结构化区分错误类型。

**修复方案**：
在 `api-client.js` 中新增：
- `ErrorCodes` 常量对象：定义 10+ 错误码（SUCCESS=0, UNAUTHORIZED=401, FORBIDDEN=403, NOT_FOUND=404, VALIDATION_ERROR=422, RATE_LIMITED=429, SERVER_ERROR=500, NETWORK_ERROR=-2, TIMEOUT=-3, TOKEN_EXPIRED=4011, TOKEN_REFRESH_FAILED=4012）
- `ApiError` 构造函数：继承 Error，携带 `code`、`message`、`detail` 三个字段
- 所有 `api()` 函数的 `throw new Error(...)` 替换为 `throw new ApiError(code, message, detail)`

**前端模块兼容**：ApiError 继承 Error，`e.message` 仍然可用，现有 catch 块无需修改。

---

### 🔴 HIGH-3: 前后端API响应格式不一致 → 统一三格式兼容

**问题**：后端存在三种错误返回格式，前端只处理了部分。

**修复方案**：
在 `api-client.js` 的 `api()` 函数中，统一处理三种格式：
1. `{status: 'error', message: '...'}` — 伏羲标准格式
2. `{detail: '...'}` — FastAPI 默认格式
3. `{code: 非0, message: '...'}` — 通用 code-message 格式

`TokenManager.ts` 的 `refreshToken()` 也同步增加 `{status: 'error'}` 格式处理。

---

### 🔴 HIGH-4: shallowRef 深层属性修改不触发响应

**问题**：`windowManager.ts` 中 `windows` 使用 `shallowRef`，但 `focus()`、`minimize()`、`toggleMaximize()`、`close()`、`move()`、`resize()`、`open()` 等函数直接修改窗口对象的属性（`window.state = ...`），不会触发 Vue 响应式更新。

**修复方案**：所有修改窗口属性的地方，改为创建新对象 + 创建新数组：
```typescript
// 旧：直接修改（不触发响应）
window.state = 'minimized';

// 新：创建新对象（触发响应）
const updated = { ...window, state: 'minimized' as const };
windows.value = [...windows.value.slice(0, idx), updated, ...windows.value.slice(idx + 1)];
```

**修改的函数**（共 9 个）：
- `open()` — singleton 恢复时的状态和数据更新
- `focus()` — state 恢复 + zIndex 更新
- `minimize()` — state 变更
- `toggleMaximize()` — state 切换
- `close()` — state 设置为 closing
- `move()` — position 更新
- `resize()` — size 更新
- `arrangeTiled()` — 批量布局更新
- `arrangeSplit()` — 批量布局更新

**`chat.ts` 已正确处理**：`handleStreamChunk()` 中已使用展开运算符创建新对象（`messages.value[aiIndex] = { ...messages.value[aiIndex], content: ... }`），无需修改。

---

### 🔴 HIGH-5: 会话历史缺失 → 实现历史消息加载

**问题**：`chat.ts` store 的 `switchSession()` 函数有 TODO 注释「从后端加载该会话的历史消息」，切换会话时直接清空消息。

**修复方案**：
1. `api/chat.ts` 新增 `fetchSessionMessages(sessionId)` 函数，调用 `GET /api/chat/sessions/{id}/messages`
2. `stores/chat.ts` 的 `switchSession()` 改为先调用 `fetchSessionMessages()` 加载历史
3. 静默降级：如果后端未实现该接口，catch 中返回空数组，不阻塞用户操作

---

### 🟡 MEDIUM-6: token 管理逻辑分散 → 统一到 TokenManager

**问题**：vue3-migration 中 token 读写分散在 `auth.ts`、`chat.ts`、`rag.ts`、`TokenManager.ts`、`api/index.ts` 五处。

**修复方案**：
- `api/index.ts`（apiClient）的请求拦截器已统一使用 `TokenManager.getToken()` 注入 token ✅
- `auth.ts` 的 `login()` 改用 `apiClient.post()`，token 由拦截器统一处理 ✅
- `chat.ts` 的 `sendMessageStream()` 改为动态 import TokenManager 获取 token ✅
- `rag.ts` 的 `subscribeToSearchTrace()` 已使用 `TokenManager.getToken()` ✅
- `TokenManager.ts` 的 `refreshToken()` 是唯一刷新入口 ✅

**token 管理统一路径**：
```
读取：TokenManager.getToken() → apiClient 拦截器自动注入
写入：TokenManager.setToken() → login() 成功后调用
清除：TokenManager.clearToken() → logout() / 401 刷新失败
刷新：TokenManager.refreshToken() → apiClient 401 拦截器自动调用
```

---

### 🟡 MEDIUM-7: 硬编码 mock 数据 → 移除或标记为开发环境

**问题**：`CompressPanel.vue` 和 `ConvertPanel.vue` 中 `downloadFile()` 函数硬编码了 Mock 模式提示文字。

**修复方案**：
- `CompressPanel.vue`：改为 `import.meta.env.DEV` 判断，开发环境显示模拟提示，生产环境触发真实下载
- `ConvertPanel.vue`：同上处理

**DxfViewerPage.vue** 的 `connectionStatus = 'mock'` 保留：这是 API 连接失败时的降级状态显示，不是硬编码 mock 数据。

---

## 修改文件汇总

| # | 文件 | 修改类型 | 对应问题 |
|---|------|---------|---------|
| 1 | `js/api-client.js` | 新增 ErrorCodes + ApiError + 统一错误处理 | HIGH-2, HIGH-3 |
| 2 | `vue3-migration/src/api/auth.ts` | fetch → apiClient | HIGH-1, MEDIUM-6 |
| 3 | `vue3-migration/src/api/chat.ts` | 新增 fetchSessionMessages + token 统一 | HIGH-1, HIGH-5, MEDIUM-6 |
| 4 | `vue3-migration/src/api/rag.ts` | 添加注释说明 SSE 保留 fetch 原因 | HIGH-1 |
| 5 | `vue3-migration/src/stores/chat.ts` | switchSession 加载历史消息 | HIGH-5 |
| 6 | `vue3-migration/src/stores/windowManager.ts` | shallowRef 响应式修复（9 个函数） | HIGH-4 |
| 7 | `vue3-migration/src/utils/TokenManager.ts` | 统一错误格式处理 | HIGH-3, MEDIUM-6 |
| 8 | `vue3-migration/src/services/doc-tools/CompressPanel.vue` | mock → DEV 环境标记 | MEDIUM-7 |
| 9 | `vue3-migration/src/services/doc-tools/ConvertPanel.vue` | mock → DEV 环境标记 | MEDIUM-7 |

**总计**：9 个文件，+202 行，-106 行

---

## 验证要点

1. **apiClient 错误码**：`api()` 函数抛出的错误现在是 `ApiError` 实例，包含 `.code`、`.message`、`.detail`，现有 `catch(e) { e.message }` 代码兼容
2. **shallowRef 响应式**：windowManager 所有状态变更都创建新对象+新数组，Vue 能正确追踪
3. **会话历史**：`fetchSessionMessages()` 静默降级，后端未实现时返回空数组不报错
4. **Mock 标记**：生产环境 `import.meta.env.DEV` 为 false，不会显示 mock 提示
