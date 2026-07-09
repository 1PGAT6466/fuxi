# R4: Chat SSE 流式改造摘要

## 改动范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `js/chat.js` | 重写 | 核心 SSE 流式逻辑 |
| `css/chat_redesign.css` | 新增 | 流式输出样式 |

## 架构变更

### 数据流：旧 vs 新

```
旧: sendChat() → api(POST /api/chat/send, stream:false) → 整包 JSON → appendMsg('ai')
新: sendChat() → sendChatSSE() → fetch(POST /api/chat/send, stream:true) → ReadableStream → 逐帧 parse → updateStreamingBubble()
```

### 关键函数变化

| 函数 | 变化 |
|------|------|
| `sendChat()` | 拆分为两个分支：`useWeb` 走旧的非流式路径，普通对话走 `sendChatSSE()` |
| `sendChatSSE()` | **新增** — SSE 流式核心，管理 AbortController、ReadableStream 解析、HTTP 状态码检查、Content-Type 检测 |
| `updateStreamingBubble()` | **新增** — 逐字更新气泡内容，带滚动跟随 |
| `stopStreaming()` | **新增** — 暴露中止接口，可绑定到 UI 按钮 |
| `appendMsg()` | 新增 `loading-stream` 和 `ai-stream` 两种 role 支持 |

## 流式解析协议

后端 SSE 帧格式（预期）：
```
data: {"delta":"文本片段"}
data: {"delta":"更多文本"}
data: {"done":true,"sources":[...]}
```

前端解析器：
- 使用 `resp.body.getReader()` + `TextDecoder('utf-8', {stream: true})` 逐块读取
- 按 `\n` 分行，解析 `data:` 前缀的 JSON
- 最后一行不完整时保留到 buffer 下次处理（防截断）
- 兼容 `[DONE]` 标记（OpenAI 风格）
- JSON 解析失败时回退 buffer，等待下个 chunk 拼接

## 打字机效果

- 渲染节流：`RENDER_INTERVAL = 50ms`（每秒最多 20 帧）
- 流式过程中用 `esc()` 纯文本渲染（避免 Markdown 不完整导致渲染闪烁）
- 流结束后用 `marked.parse()` + `DOMPurify.sanitize()` 完整 Markdown 渲染
- 闪烁光标 `▍` 在流式过程中显示，完成后移除

## 加载状态

| 阶段 | 显示效果 |
|------|---------|
| 请求发送 | `loading-stream` — 跳动的三点动画 |
| 2 秒后无响应 | 渐显「AI 正在生成回复…」进度文字 |
| 收到首个 delta | loading 消失，出现 `ai-stream` 气泡 + `▍` 闪烁光标 |
| 生成完成 | 光标消失，Markdown 完整渲染，sources/trace 完整显示 |

## 错误处理覆盖

| 场景 | 处理方式 |
|------|---------|
| HTTP 401 | 清除认证信息，跳转登录页 |
| HTTP 403 | 显示「🚫 没有权限访问该资源」 |
| HTTP 429 | 显示「⏳ 请求过于频繁，请稍后重试」 |
| HTTP 5xx | 显示「服务器错误 (xxx)，请稍后重试」 |
| 超时 (AbortError) | 显示「⏱️ 请求超时，AI 响应时间较长」 |
| 用户中止 (stopStreaming) | 保留已生成文本 + 标记 `[已中止]` |
| 网络错误 | 显示「🌐 网络连接失败」 |
| JSON 解析失败 | 显示「📡 服务器响应格式异常」 |
| Content-Type 非 SSE | JSON 兜底解析 → 否则报格式异常 |
| 后端返回 error 帧 | 直接抛出 `{error: "xxx"}` 的 message |
| 无输出 | 兜底显示「未能生成回答」 |

## 向后兼容

- Web 搜索模式 (`/api/antenna/search`) 不受影响，仍走旧的 `api()` 路径
- 后端不返回 SSE 而是返回普通 JSON 时，有 Content-Type 检测 + JSON 兜底解析
- 不影响 `quickChat()` / `toggleWebSearch()` 等现有 API
- `appendMsg('ai', ...)` 逻辑保持不变

## 可扩展点

- `_streamSpeed` 变量预留了打字机速度控制入口
- `stopStreaming()` 可绑定到 UI 的「停止生成」按钮
- `.btn-stop-stream` 样式已预定义，等待 HTML 引用

## 修改日期

2026-07-09
