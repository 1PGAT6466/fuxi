# 伏羲 API 文档

**版本**: v1.50
**基础路径**: `http://<host>:8080`
**Swagger UI**: `GET /docs` (自动生成)
**ReDoc**: `GET /redoc` (自动生成)

---

## 认证

### 认证方式

所有需要认证的端点通过 `AuthMiddleware` 处理，需在请求头中携带 JWT Token：

```
Authorization: Bearer <jwt_token>
```

### Token 结构

```json
{
  "sub": "admin",
  "role": "admin",
  "exp": 1735689600,
  "iat": 1735603200
}
```

- `sub`: 用户名
- `role`: 角色（admin / user）
- `exp`: 过期时间（UTC 时间戳，默认 24 小时后过期）
- `iat`: 签发时间

### 白名单端点（无需认证）

| 端点 | 说明 |
|------|------|
| `POST /api/auth/login` | 用户登录 |
| `POST /api/auth/register` | 用户注册 |
| `GET /api/health` | 健康检查 |
| `GET /` | 主页 |
| `GET /login` | 登录页 |
| `GET /static/*` | 静态资源 |

### 登录

```
POST /api/auth/login
```

**请求**:

```json
{
  "username": "admin",
  "password": "fuxi2024"
}
```

**响应** (200):

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "username": "admin",
  "role": "admin"
}
```

**错误响应** (401):

```json
{
  "detail": "用户名或密码错误"
}
```

### 注册

```
POST /api/auth/register
```

**请求**:

```json
{
  "username": "newuser",
  "password": "securepassword"
}
```

**响应** (200):

```json
{
  "ok": true,
  "username": "newuser"
}
```

### 获取当前用户

```
GET /api/auth/me
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "username": "admin",
  "role": "admin"
}
```

---

## 搜索

### 混合搜索

```
GET /api/search?q=<query>&top_k=15&page=1&page_size=8
Authorization: Bearer <token>
```

**参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| q | string | 是 | - | 搜索关键词 |
| top_k | int | 否 | 15 | 返回结果数量 |
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 8 | 每页数量 |

**响应** (200):

```json
{
  "wiki_results": [
    {
      "title": "VPN 连接指南",
      "content": "...",
      "score": 0.92,
      "_source": "wiki"
    }
  ],
  "chunk_results": [
    {
      "file_name": "网络配置手册.pdf",
      "content": "...",
      "score": 0.87,
      "category": "网络",
      "file_hash": "abc123"
    }
  ],
  "query": "VPN 连接",
  "page": 1,
  "page_size": 8,
  "total": 12
}
```

### 搜索历史

```
GET /api/search-history
Authorization: Bearer <token>
```

**响应** (200):

```json
[]
```

---

## AI 对话

### 智能问答

```
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json
```

**请求**:

```json
{
  "query": "如何配置 VPN？",
  "history": [
    {"role": "user", "content": "之前的问题"},
    {"role": "assistant", "content": "之前的回答"}
  ],
  "stream": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 用户问题 |
| history | array | 否 | 对话历史 |
| stream | bool | 否 | 是否流式输出 |

**响应** (200):

```json
{
  "answer": "配置 VPN 的步骤如下：...",
  "sources": [
    {
      "file_name": "VPN配置指南.docx",
      "content": "...",
      "score": 0.91
    }
  ],
  "mode": "shaoyin",
  "confidence": 0.85
}
```

### Agent 模式对话

```
POST /api/chat/agent
Authorization: Bearer <token>
Content-Type: application/json
```

请求和响应格式与 `/api/chat` 相同，Agent 模式支持多轮推理和工具调用。

---

## 文档管理

### 文档列表

```
GET /api/documents?page=1&limit=50
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "files": [
    {
      "file_name": "技术规范v2.pdf",
      "file_hash": "abc123def456",
      "category": "技术",
      "chunk_count": 42
    }
  ],
  "total": 156,
  "page": 1,
  "limit": 50
}
```

### 上传文件

```
POST /api/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**表单字段**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 上传的文件 |
| relative_path | string | 否 | 文件夹上传时的相对路径 |

**支持的文件类型**:

`.txt` `.md` `.csv` `.docx` `.doc` `.xlsx` `.xls` `.pdf` `.pptx` `.ppt` `.cfg` `.log` `.ini` `.conf` `.json` `.xml` `.html` `.htm` `.zip` `.wps` `.dwg` `.dxf` `.stp` `.step` `.igs` `.iges` `.jpg` `.jpeg` `.png` `.gif` `.bmp` `.svg` `.py` `.js` `.ts` `.java` `.c` `.cpp` `.h` `.sh` `.bat` `.ps1` `.yaml` `.yml` `.7z` `.rar` `.tar` `.gz`

**响应** (200):

```json
{
  "status": "ok",
  "file_name": "技术规范v2.pdf",
  "relative_path": "技术规范v2.pdf",
  "chunks": 42,
  "duration_ms": 3200
}
```

**错误响应** (400):

```json
{
  "detail": "不支持的文件类型: .exe"
}
```

### 批量上传

```
POST /api/upload/batch
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**响应** (200):

```json
{
  "results": [
    {"file_name": "doc1.pdf", "status": "ok", "chunks": 15},
    {"file_name": "doc2.exe", "status": "error", "error": "不支持的文件类型: .exe"}
  ],
  "total": 2
}
```

### 删除文档

```
DELETE /api/documents/{file_hash}
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "status": "ok",
  "removed": 42,
  "file_hash": "abc123def456"
}
```

### 导出文档列表

```
GET /api/documents/export
Authorization: Bearer <token>
```

**响应**: CSV 文件下载

```csv
file_name,file_hash,category,chunk_count
技术规范v2.pdf,abc123,技术,42
```

---

## 知识图谱

### 查询图谱

```
GET /api/graph?entity=<keyword>
Authorization: Bearer <token>
```

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| entity | string | 否 | 实体关键词过滤 |

**响应** (200):

```json
{
  "nodes": {
    "VPN": {"type": "technology", "properties": {...}},
    "防火墙": {"type": "device", "properties": {...}}
  },
  "edges": [
    {"source": "VPN", "target": "防火墙", "relation": "连接"}
  ]
}
```

---

## 管理

### 管理统计

```
GET /api/admin/stats
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "ok": true,
  "chunks": 15234,
  "categories": {
    "技术": 5234,
    "办公": 3456,
    "网络": 2345
  }
}
```

### 服务器状态

```
GET /api/admin/server-status
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "ok": true,
  "uptime_seconds": 86400,
  "uptime_hours": 24.0
}
```

### 可观测性指标摘要

```
GET /api/admin/metrics-summary
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "latency": {"p50": 120, "p95": 450, "p99": 1200},
  "error_rate": 0.02,
  "requests_total": 15234
}
```

---

## 四象系统

### 四象状态

```
GET /api/symbols/status
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "shaoyang": {"status": "active", "processed": 15234},
  "taiyang": {"status": "active", "queries": 8923},
  "shaoyin": {"status": "active", "answers": 4521},
  "taiyin": {"status": "active", "requests": 23456}
}
```

### 成长概览

```
GET /api/growth/overview
Authorization: Bearer <token>
```

---

## 评测

### 运行评测

```
POST /api/eval/run
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "status": "ok",
  "report": {
    "accuracy": 0.87,
    "recall": 0.82,
    "f1": 0.84
  }
}
```

### 获取评测报告

```
GET /api/eval/report
Authorization: Bearer <token>
```

### 评测历史

```
GET /api/eval/history
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "history": [
    {"date": "2026-07-02", "accuracy": 0.87, "recall": 0.82},
    {"date": "2026-07-01", "accuracy": 0.85, "recall": 0.80}
  ]
}
```

---

## MCP 协议

### MCP 入口（JSON-RPC 2.0）

```
POST /api/mcp
Authorization: Bearer <token>
Content-Type: application/json
```

**请求**:

```json
{
  "jsonrpc": "2.0",
  "method": "sag_search",
  "params": {"query": "VPN 配置", "top_k": 5},
  "id": 1
}
```

**响应** (200):

```json
{
  "jsonrpc": "2.0",
  "result": {"results": [...]},
  "id": 1
}
```

### MCP 工具列表

```
GET /api/mcp/tools
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "tools": [
    {"name": "sag_search", "description": "搜索知识库"},
    {"name": "sag_ingest", "description": "入库文档"},
    {"name": "sag_explain", "description": "解释查询"},
    {"name": "sag_status", "description": "系统状态"}
  ]
}
```

### MCP 搜索

```
POST /api/mcp/sag_search
Authorization: Bearer <token>
```

**请求**:

```json
{
  "query": "如何配置 VPN",
  "top_k": 10
}
```

### MCP 入库

```
POST /api/mcp/sag_ingest
Authorization: Bearer <token>
```

**请求**:

```json
{
  "file_path": "/path/to/document.pdf",
  "category": "技术"
}
```

---

## Feature Flags

### 获取所有 Flag

```
GET /api/feature-flags
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "flags": {
    "shaoyang_sag_extract": false,
    "taiyang_multi_hop": false,
    "enhanced_pipeline": false
  },
  "defaults": {
    "shaoyang_sag_extract": false,
    "taiyang_multi_hop": false,
    "enhanced_pipeline": false
  }
}
```

### 更新 Flag

```
PUT /api/feature-flags/{name}
Authorization: Bearer <token>
Content-Type: application/json
```

**请求**:

```json
{
  "value": true
}
```

**响应** (200):

```json
{
  "ok": true,
  "flag": "shaoyang_sag_extract",
  "value": true
}
```

**错误响应** (404):

```json
{
  "detail": "未知 flag: unknown_flag"
}
```

---

## 健康检查与监控

### 健康检查（无需认证）

```
GET /api/health
```

**响应** (200):

```json
{
  "status": "ok",
  "version": "1.50",
  "checks": {
    "database": "ok",
    "vector_store": "ok",
    "meridian": "ok"
  }
}
```

### 系统统计

```
GET /api/system/stats
Authorization: Bearer <token>
```

### 缓存统计

```
GET /api/cache/stats
Authorization: Bearer <token>
```

### 错误统计

```
GET /api/errors/stats
Authorization: Bearer <token>
```

### Prometheus 指标（无需认证）

```
GET /metrics
```

返回 Prometheus 格式的文本指标：

```
# HELP fuxi_requests_total Total requests
# TYPE fuxi_requests_total counter
fuxi_requests_total 15234

# HELP fuxi_request_duration_seconds Request duration
# TYPE fuxi_request_duration_seconds histogram
fuxi_request_duration_seconds_bucket{le="0.1"} 12000
```

---

## 反馈

### 提交反馈

```
POST /api/feedback
Authorization: Bearer <token>
Content-Type: application/json
```

**请求**:

```json
{
  "query": "VPN 配置问题",
  "answer": "...",
  "rating": 4,
  "comment": "回答很有帮助"
}
```

**响应** (200):

```json
{
  "ok": true
}
```

### 每周反馈

```
GET /api/feedback/weekly
Authorization: Bearer <token>
```

**响应** (200):

```json
{
  "feedbacks": []
}
```

---

## 代理

### 获取装载机文件列表

```
GET /api/proxy/loader/files
Authorization: Bearer <token>
```

### 上传文件到装载机

```
POST /api/proxy/loader/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

---

## Wiki

### Wiki 页面列表

```
GET /api/wiki/pages
Authorization: Bearer <token>
```

### Wiki 搜索

```
GET /api/wiki/search?q=<query>
Authorization: Bearer <token>
```

### Wiki 页面详情

```
GET /api/wiki/page/{page_id}
Authorization: Bearer <token>
```

---

## 平台服务

### 服务列表

```
GET /api/services/
Authorization: Bearer <token>
```

### 服务详情

```
GET /api/services/{id}
Authorization: Bearer <token>
```

### 启动/停止服务

```
POST /api/services/{id}/start
POST /api/services/{id}/stop
Authorization: Bearer <token>
```

---

## 前端页面

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 主页 | 否 |
| GET | `/login` | 登录页 | 否 |
| GET | `/admin` | 管理面板 | 否 |

---

## 错误码

| 状态码 | 说明 | 常见原因 |
|--------|------|----------|
| 200 | 成功 | - |
| 400 | 请求错误 | 参数缺失、文件类型不支持 |
| 401 | 未认证 | Token 缺失、Token 过期、Token 无效 |
| 404 | 未找到 | 资源不存在、未知 Flag |
| 413 | 文件过大 | 上传文件超过 200MB 限制 |
| 429 | 请求过多 | 超过 60 次/分钟限流 |
| 500 | 服务器错误 | 内部处理异常 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 常见错误示例

**401 - 未登录**:

```json
{
  "detail": "未登录"
}
```

**401 - Token 过期**:

```json
{
  "detail": "Token已过期"
}
```

**400 - 不支持的文件类型**:

```json
{
  "detail": "不支持的文件类型: .exe"
}
```

**404 - 未知 Flag**:

```json
{
  "detail": "未知 flag: unknown_flag"
}
```

---

## 限流

- 默认限流：60 次/分钟/IP
- 限流算法：滑动窗口
- 超限响应：HTTP 429

---

## 附录：curl 示例

### 登录并获取 Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"fuxi2024"}' | jq -r '.token')
```

### 搜索

```bash
curl -s "http://localhost:8080/api/search?q=VPN配置&top_k=5" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 对话

```bash
curl -s -X POST http://localhost:8080/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"如何配置VPN？"}' | jq
```

### 上传文件

```bash
curl -X POST http://localhost:8080/api/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf" | jq
```

### 查看 Prometheus 指标

```bash
curl http://localhost:8080/metrics
```
