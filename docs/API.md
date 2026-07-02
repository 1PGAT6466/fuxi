# 伏羲 RAG 4.0 API 文档

## 基础信息

- 基础URL: `http://localhost:8080`
- 认证: Bearer Token (JWT)
- 格式: JSON

## 核心API

### 对话

```
POST /api/chat
Content-Type: application/json

{
  "query": "PA66的拉伸强度是多少",
  "history": [],
  "stream": false
}

Response:
{
  "answer": "PA66的拉伸强度...",
  "confidence": 0.85,
  "sources": [...],
  "trace_id": "abc123"
}
```

### 搜索

```
GET /api/search?q=PA66&page_size=20

Response:
{
  "chunk_results": [...],
  "wiki_results": [...],
  "total": 10
}
```

### 入库

```
POST /api/upload
Content-Type: multipart/form-data

file: <文件>
category: "技术文档"

Response:
{
  "success": true,
  "chunks": 10,
  "events": 5,
  "entities": 15
}
```

## MCP协议

### 工具列表

```
GET /api/mcp/tools

Response:
{
  "tools": [
    {"name": "sag_search", "description": "搜索伏羲知识库"},
    {"name": "sag_ingest", "description": "入库文档"},
    {"name": "sag_explain", "description": "解释查询"},
    {"name": "sag_status", "description": "系统状态"}
  ]
}
```

### MCP调用

```
POST /api/mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "sag_search",
    "arguments": {"query": "PA66", "top_k": 5}
  }
}
```

## 四象状态

### 系统状态

```
GET /api/symbols/status

Response:
{
  "symbols": {
    "shaoyang": {"alive": true, "status": "idle", "metrics": {...}},
    "taiyang": {"alive": true, "status": "idle", "metrics": {...}},
    "shaoyin": {"alive": true, "status": "idle", "metrics": {...}},
    "taiyin": {"alive": true, "status": "idle", "metrics": {...}}
  }
}
```

### 成长概览

```
GET /api/growth/overview

Response:
{
  "symbols": {...},
  "total_events": 100,
  "phase": "Phase 1",
  "trend": [...]
}
```

## 评测API

### 运行评测

```
POST /api/eval/run

Response:
{
  "timestamp": 1234567890,
  "date": "2026-07-02",
  "metrics": {...},
  "degradation": {...},
  "recommendations": [...]
}
```

### 评测报告

```
GET /api/eval/report

Response:
{
  "timestamp": 1234567890,
  "metrics": {...},
  "issues": [],
  "recommendations": [...]
}
```

## Feature Flags

### 获取Flags

```
GET /api/feature-flags

Response:
{
  "flags": {
    "shaoyang_sag_extract": false,
    "taiyang_multi_hop": false,
    "taiyang_seed_score": false,
    "enhanced_pipeline": false
  }
}
```

### 更新Flag

```
PUT /api/feature-flags/{name}
Content-Type: application/json

{
  "value": true
}
```

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 未找到 |
| 500 | 服务器错误 |
