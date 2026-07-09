# R5 前端修复摘要

> 修复时间：2026-07-09 14:53 GMT+8
> 基于报告：`.openclaw/中间/deep-r5-frontend-report.md`
> 修复人：前端开发专家（subagent）

---

## 修复 1：FastAPI 默认错误格式 `{detail: "..."}` 统一解包

**文件**：`js/api-client.js`

**问题**：当后端以 FastAPI 默认格式 `{detail: "error message"}` 返回错误（如 HTTPException 抛出的 422/404），api-client 没有提取 `detail` 字段，导致前端收到原始 JSON 对象而非错误消息。

**修改**：
1. **`!r.ok` 路径**（HTTP 状态码 4xx/5xx）：在抛出通用消息前，先尝试解析响应体 JSON，若包含 `detail` 或 `status === 'error'` + `message`，抛出具名错误。
2. **`r.ok` 路径**（HTTP 200 但内容为错误）：在现有的 `status === 'error'` 检查后，增加对 `data.detail` 的兜底处理，仅在 `data.status !== 'success'` 时触发，避免误杀包含 `detail` 字段的正常 `error()` 响应。

```javascript
// 修改前 (r.ok 路径)
if (data && data.status === 'error' && data.message) {
  throw new Error(data.message);
}

// 修改后
if (data && data.status === 'error' && data.message) {
  throw new Error(data.message);
}
// R5: FastAPI 默认错误格式 {detail: "..."} 兜底（非 success 响应才处理）
if (data && data.detail && typeof data.detail === 'string' && data.status !== 'success') {
  throw new Error(data.detail);
}
```

```javascript
// 修改前 (!r.ok 路径)
if (!r.ok) throw new Error('请求失败: ' + r.status);

// 修改后
if (!r.ok) {
  var errData = null;
  try { errData = await r.json(); } catch(_) { errData = null; }
  if (errData && errData.detail) {
    throw new Error(errData.detail);
  }
  if (errData && errData.status === 'error' && errData.message) {
    throw new Error(errData.message);
  }
  throw new Error('请求失败: ' + r.status);
}
```

---

## 修复 2：services.js start/stop 按钮 — 调用路径与数据格式修复

**涉及文件**：
- 前端 `js/services.js`
- 后端 `src/api/services.py`

**问题 A — 后端缺少 start/stop 端点**：
前端 `toggleService()` 调用 `POST /api/services/{id}/start` 和 `POST /api/services/{id}/stop`，但后端仅有 `GET /` 和 `GET /{service_id}` 两个端点，导致 404 错误。

**修复**：在 `services.py` 中新增 `POST /{service_id}/{action}` 端点：

```python
@router.post("/{service_id}/{action}", dependencies=[Depends(require_admin)])
async def toggle_service(service_id: str, action: str, request: Request):
    if action not in ("start", "stop"):
        return error(f"不支持的操作: {action}", status_code=400, detail="仅支持 start 和 stop")
    # 查找并更新服务状态
    svc["status"] = "running" if action == "start" else "stopped"
    return success({...})
```

**问题 B — 前后端状态值不一致**：
- 后端使用 `"up"` / `"degraded"` / `"unknown"` 表示服务状态
- 前端只识别 `s.status === 'running'`，导致所有服务显示为「已停止」

**修复**：统一处理多种状态值：
- `'running'` 或 `'up'` → 运行中（绿色）
- `'stopped'` → 已停止（红色）
- 其他值 → 显示原始值（橙色）

```javascript
// 修改前
var isRunning = s.status === 'running';

// 修改后
var isRunning = s.status === 'running' || s.status === 'up';
var isStopped = s.status === 'stopped';
var statusColor = isRunning ? '#34c759' : (isStopped ? '#ff3b30' : '#ff9500');
```

**问题 C — loadServices() 数据解包错误**：
后端返回 `{status: 'success', data: {services: [...], total: N}}`，api-client 统一解包后将 `data.services` 展开到顶层，但 `loadServices()` 直接将整个响应对象当作数组处理：
```javascript
var list = await api('/api/services');
if (!Array.isArray(list)) list = [];  // ← 丢弃了所有数据！
```

**修复**：正确提取 services 数组：
```javascript
var raw = await api('/api/services');
var list = Array.isArray(raw) ? raw : (raw.services || raw.data && raw.data.services || []);
```

**问题 D — showServiceDetail() 状态值同样不一致**：
同步修复 `showServiceDetail()` 中的状态判断逻辑。

---

## 修改文件清单

| 文件 | 变更类型 | 内容 |
|---|---|---|
| `frontend/js/api-client.js` | 修改 | FastAPI `{detail}` 错误解包（`!r.ok` + `r.ok` 两处） |
| `frontend/js/services.js` | 修改 | 数据解包修复、状态值统一、detail 状态统一 |
| `src/api/services.py` | 新增端点 | `POST /{service_id}/{action}` start/stop 端点 |

---

## 连带修复的隐藏问题

除 R5 报告明确指出的两个问题外，在修复过程中发现并修复了以下连带问题：

1. **loadServices() 数据完全丢失**：统一解包后 JSON 响应不为数组，原代码无条件替换为空数组。
2. **服务状态全显示「已停止」**：后端 `"up"` 状态前端不识别。
3. **详情弹窗状态颜色错误**：与卡片列表状态判断不一致。
