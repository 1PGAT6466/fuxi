# 伏羲 v1.50 — 第三轮审计：API 与架构全维度扫描报告

> **生成日期**：2026-07-06  
> **扫描工具**：自动化静态分析（260+ .py 文件全量解析）  
> **覆盖范围**：10 个维度，89 个 API 端点，251 个模块  
> **严重等级定义**：🔴 严重 | 🟡 中等 | 🟢 轻微 | ℹ️ 信息

---

## 📊 执行摘要

| 维度 | 发现数 | 最高严重度 | 关键发现 |
|------|--------|------------|----------|
| 1. API 响应一致性 | 31 种模式 | 🟡 | **无统一响应格式**，31 种不同结构共存 |
| 2. HTTP 状态码 | 6 种使用 | 🟡 | 缺少 422/403/201/204，错误码使用局限 |
| 3. 认证覆盖 | 21 个端点 | 🔴 | **AuthMiddleware 不验证 token**，只检查存在性 |
| 4. 输入校验 | 35 个端点 | 🟡 | 19 个 POST/PUT 端点无 Pydantic 模型 |
| 5. 分页支持 | 12 个端点 | 🟡 | 10 个列表端点缺少分页 |
| 6. API 版本管理 | 1 个 v2 路由 | 🟢 | v2_routes 几乎空壳，无实际 v1/v2 共存 |
| 7. 架构分层 | 2 处违规 | 🟡 | API 层直接导入 db 层（documents.py, graph.py） |
| 8. 循环导入 | 0 个新增 | 🟢 | 第二轮报告中的 2 组循环未修复 |
| 9. 模块内聚 | 251 个模块 | ℹ️ | 35 个模块全公开（无封装），3 个低内聚 |
| 10. server.py 拆分 | 460 行 | 🟡 | 29 个内联路由 + 5 个服务路由器未注册 |

---

## 维度 1：API 响应一致性 🔍

### 问题概述
代码库中存在 **31 种不同的响应结构模式**，完全缺少统一的响应格式规范。

### 发现的 31 种响应模式
```
Pattern  1: answer, confidence, mode, sources        （对话类）
Pattern  2: categories, chunks, ok                    （管理类）
Pattern  3: content, id, title                         （Wiki类）
Pattern  4: dashboard                                  （单值包裹）
Pattern  5: defaults, flags                           （Feature Flag）
Pattern  6: dependencies, status, service, version    （服务健康检查 - 标准格式）
Pattern  7: description, name, tools                  （MCP 工具列表）
Pattern  8: entities                                   （单值包裹）
Pattern  9: entities, terms, wiki_pages                （WorldTree类）
Pattern 10: error                                      （错误单字段）
Pattern 11: error, files                               （错误详情）
Pattern 12: error, status                              （健康检查错误）
Pattern 13: evolution                                  （单值包裹）
Pattern 14: ezdxf_available, service, status, version  （DXF服务）
Pattern 15: feedbacks                                  （单值包裹）
Pattern 16: files, total                               （文件列表）
Pattern 17: flag, ok, value                            （Flag更新）
Pattern 18: history                                    （单值包裹）
Pattern 19: message, query, results, source            （天线搜索）
Pattern 20: metadata                                   （单值包裹）
Pattern 21: model, status, workers                     
Pattern 22: ok                                         （最小响应）
Pattern 23: ok, uptime_hours, uptime_seconds           （服务器状态）
Pattern 24: original_length, summary, summary_length   （摘要类）
Pattern 25: pages, total                               （Wiki 列表）
Pattern 26: platform_version, service, status, ...     （详细健康检查）
Pattern 27: role, username                             （认证信息）
Pattern 28: search_stats                               （评测类）
Pattern 29: service, status, version                   （服务健康检查 - 简洁格式）
Pattern 30: status                                      （v2状态）
Pattern 31: tree                                       （树形数据）
```

### 问题分析
| 问题 | 说明 | 严重度 |
|------|------|--------|
| **无统一 schema** | 没有定义 `ApiResponse[T]` 或 `BaseResponse` 基类 | 🟡 |
| **混合使用 ok/status** | 部分端点用 `ok`，部分用 `status` | 🟡 |
| **错误格式不统一** | 有的用 `{"error": str}`，有的用 `{"status":"error","error":str}` | 🟡 |
| **单值直接包裹** | `{"dashboard":{}}`, `{"evolution":{}}` 等无元数据 | 🟡 |
| **成功响应无状态标识** | 对话端点返回 `answer/sources` 无法区分成功/失败 | 🟡 |

### 建议的统一格式
```json
// 成功响应
{
  "status": "success",
  "data": { ... },
  "meta": {
    "timestamp": "2026-07-06T09:00:00Z",
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}

// 错误响应
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "用户名已存在",
    "details": {}
  }
}
```

---

## 维度 2：HTTP 状态码 🔍

### 使用情况统计
| 状态码 | 出现次数 | 用途 | 评价 |
|--------|---------|------|------|
| 400 (Bad Request) | 14 | 参数错误、业务逻辑错误 | ✅ 合理 |
| 401 (Unauthorized) | 7 | 认证失败、token过期 | ⚠️ 有但中间件未正确使用 |
| 404 (Not Found) | 1 | 文件未找到 | ⚠️ 使用极不充分 |
| 413 (Payload Too Large) | 2 | 上传文件过大 | ✅ 合理 |
| 500 (Internal Server) | 8 | 内部处理失败 | ⚠️ 部分场景应使用 503 |
| 502 (Bad Gateway) | 1 | LLM调用失败 | ✅ 恰当 |
| 503 (Service Unavailable) | 9 | 依赖不可用（pypdf等） | ✅ 恰当 |

### 缺少的关键状态码
| 状态码 | 应使用的场景 | 是否使用 |
|--------|-------------|----------|
| 201 (Created) | 资源创建成功（注册、上传、入库） | ❌ 未使用 |
| 204 (No Content) | 删除操作成功 | ❌ 未使用 |
| 403 (Forbidden) | 权限不足（admin/普通用户区分） | ❌ 未使用 |
| 422 (Unprocessable Entity) | Pydantic 自动校验失败 | ❌ FastAPI 应自动返回但未确认 |

### 错误处理反模式（19 个 bare except）
以下文件存在 `except:` 裸捕获（吞噬所有异常）：
```
server.py, category_registry.py, growth/engine.py (2个), 
services/evaluator.py (3个), shaoyin/crag_corrector.py (2个),
shaoyin/smart_self_rag.py (2个), 等共 19 处
```

---

## 维度 3：认证覆盖 🔴 严重

### 关键安全发现：AuthMiddleware 未实际验证 Token

```python
# src/api/auth.py 中的 AuthMiddleware.dispatch()
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ...
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        if not token:
            raise HTTPException(401, "未登录")
        # ⚠️ 检查完 token 存在后直接放行，从未调用 verify_jwt_token()！
        return await call_next(request)
```

**影响**：攻击者只需发送任意 Bearer token（如 `Bearer fake123`）即可通过认证，访问所有受保护端点。

### 白名单端点（完全无需认证）
| 端点 | 说明 |
|------|------|
| `/api/health` | 健康检查（合理） |
| `/api/auth/login` | 登录（合理） |
| `/api/auth/register` | 注册（合理） |
| `/` | 前端入口 |
| `/login` | 登录页 |

### 受 AuthMiddleware 保护但 Token 未验证的端点（21 个）
```
GET  /api/auth/me               PUT  /api/feature-flags/{name}
GET  /api/admin/metrics-summary  POST /api/eval/run
GET  /api/cache/stats            GET  /api/eval/report
GET  /api/errors/stats           GET  /api/eval/history
GET  /api/feature-flags          GET  /api/growth/overview
GET  /api/metrics                GET  /api/symbols/status
GET  /api/system/stats           POST /api/mcp
GET  /api/mcp/tools              POST /api/mcp/sag_search
GET  /api/mcp/sag_status         POST /api/mcp/sag_ingest
GET  /api/proxy/loader/files     POST /api/mcp/sag_explain
POST /api/proxy/loader/upload
```

### 通过 router 注册的端点（14 个 APIRouter）
所有通过 `app.include_router()` 注册的路由同样受 AuthMiddleware 影响，但 token 同样不被验证。

### 静态文件安全问题
```
AuthMiddleware 条件: if path.startswith('/static/'): return await call_next(request)
```
`/static/` 下所有前端源代码无认证即可访问，包括 JS/CSS 等。

### 修复建议
1. **紧急**：在 AuthMiddleware.dispatch() 中调用 `verify_jwt_token(token)` 
2. 为不同端点添加角色检查（admin/普通用户区分）
3. 考虑将 `/static/` 下的敏感 JS 文件加入认证检查

---

## 维度 4：输入校验 🟡

### 有 Pydantic 校验的端点（16 个）✅
```python
# 示例：登录端点
class LoginRequest(BaseModel):
    username: str
    password: str

# AI 工具端点
class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    max_length: int = Field(150, ge=50, le=2000)
```

### 无 Pydantic 校验的 POST/PUT 端点（19 个）⚠️
| 端点 | 文件 | 问题 |
|------|------|------|
| `POST /api/mcp` | server.py | 直接用 `request.json()` |
| `POST /api/mcp/sag_search` | server.py | 直接用 `request.json()` |
| `POST /api/mcp/sag_ingest` | server.py | 直接用 `request.json()` |
| `POST /api/mcp/sag_explain` | server.py | 直接用 `request.json()` |
| `POST /api/eval/run` | server.py | 无请求体校验 |
| `PUT /api/feature-flags/{name}` | server.py | 直接用 `request.json()` |
| `POST /api/proxy/loader/upload` | server.py | 透传，无校验 |
| `POST /api/upload` | documents.py | 仅有 File 校验，无元数据校验 |
| `POST /api/feedback` | feedback.py | 无任何参数 |
| `POST /stats` | data_analytics/routes.py | 无 Body model |
| `POST /storage` | data_analytics/routes.py | 无 Body model |
| `POST /convert` | doc_tools/routes.py | 仅有 File+Form 校验 |
| `POST /merge` | doc_tools/routes.py | 仅有 File 校验 |
| `POST /split` | doc_tools/routes.py | 仅有 File+Form 校验 |
| `POST /compress` | doc_tools/routes.py | 仅有 File 校验 |

### 修复建议
- 为所有 POST/PUT 端点创建对应的 Pydantic 模型
- 特别是 `/api/mcp/*` 系列需要通过 JSON-RPC 2.0 标准模型校验

---

## 维度 5：分页支持 🟡

### 有分页的端点（2 个）✅
| 端点 | 参数 |
|------|------|
| `GET /api/search` | `page=1, page_size=8` |
| `GET /api/documents` | `page=1, page_size=50` |

### 缺少分页的列表端点（10 个）⚠️
| 端点 | 说明 |
|------|------|
| `GET /api/mcp/tools` | 工具列表无分页 |
| `GET /api/eval/history` | 评测历史无分页 |
| `GET /api/feature-flags` | Flag 列表无分页 |
| `GET /api/wiki/pages` | Wiki 页面列表无分页 |
| `GET /api/wiki/search` | Wiki 搜索结果无分页 |
| `GET /api/worldtree/entities` | 实体列表无分页 |
| `GET /api/search-history` | 搜索历史无分页 |
| `GET /api/antenna/search` | 天线搜索无分页 |
| `GET /api/graph` | 图谱数据可能很大但无分页 |
| `GET /files` (DXF viewer) | 文件列表无分页 |

### 建议
- 统一使用 `page/page_size` 或 `offset/limit` 参数
- 在所有列表端点返回 `total` 计数
- 创建 `PaginatedResponse` 通用模型

---

## 维度 6：API 版本管理 🟢

### 现状
- **v1 路由**：0 个（所有路由均无版本前缀）
- **v2 路由**：1 个（`GET /api/v2/status`，返回 `{"status":"ok"}`）
- `v2_routes.py` 文件只有 9 行代码，无可用的业务逻辑

### 评价
- v2 实现是**纯占位符**，未实际演进
- 所有路由均使用 `/api/` 前缀，无版本号
- ✅ 不存在 v1/v2 路由冲突问题（v1 不存在）
- ⚠️ 未来 API 演进时无版本管理能力

---

## 维度 7：架构分层违规 🟡

### 分层模型（从上到下）
```
API 层 (src/api/)         ← HTTP 路由
  ↓
Service 层 (src/services/) ← 业务逻辑
  ↓
四象层 (taiyang/shaoyang/) ← 领域逻辑
  ↓
DB 层 (src/db/)           ← 数据访问
  ↓
Core 层 (src/core/)        ← 基础组件
  ↓
Infra 层 (src/infra/)      ← 基础设施
```

### 发现的违规导入（2 处）
| 文件 | 违规导入 | 问题 |
|------|---------|------|
| `api/documents.py` | `from src.db.data_store import load_chunks` | **API 层直接访问 DB 层**，跨 3 层 |
| `api/graph.py` | `from src.db.data_store import load_graph` | **API 层直接访问 DB 层**，跨 3 层 |

### 其他分层问题
| 层级 | 导入目标 | 数量 | 严重度 |
|------|---------|------|--------|
| hypothalamus → services | 直接依赖 | 18 处 | 🟡 器官层不应直接依赖服务层 |
| hypothalamus → core | 直接访问底层 | 4 处 | 🟢 较轻微 |
| pipeline → services | 正常流向 | 3 处 | ✅ 合理 |

### 未注册的服务模块（重要发现）
以下服务定义了完整的路由和生命周期管理，但 **从未在 server.py 中注册**：
| 服务模块 | 路由数量 | 状态 |
|---------|---------|------|
| `services/ai_tools/routes.py` | 6 个端点 | ❌ 未注册 |
| `services/data_analytics/routes.py` | 15 个端点 | ❌ 未注册 |
| `services/doc_tools/routes.py` | 10 个端点 | ❌ 未注册 |
| `services/dxf_viewer/api.py` | 5 个端点 | ❌ 未注册 |
| `api/files_view.py` | 3 个端点 | ❌ router 创建但未 include |
| `fuxi_platform/gateway.py` | 多个 | ❌ 整个 fuxi_platform 未集成 |

这些服务是"僵尸代码"——实现了但客户端无法访问。

---

## 维度 8：循环导入 🔍

### 第二轮报告中已知的循环（未修复）
| 循环组 | 链路 | 状态 |
|--------|------|------|
| 第 1 组 | `taiyang.multi_hop ↔ taiyang.retrieval` | ⚠️ 未修复 |
| 第 2 组 | `server ↔ taiyin.mcp_tools`, `server ↔ taiyin.growth_api` | ⚠️ 未修复 |

### 本轮扫描新增循环
**无新增循环**。全量导入图分析表明，两轮报告中已知的 2 组循环是全部风险点。

### 风险评估
- 当前循环依赖 **尚未导致启动失败**（延迟导入 + try/except 包裹）
- 但在 Python 3.11+ 的严格模式下可能导致 `ImportError`
- 如果未来修改导入顺序，可能触发实际故障

---

## 维度 9：模块内聚度分析 ℹ️

### 统计数据
| 指标 | 数值 |
|------|------|
| 总 Python 模块数 | 251 |
| 平均符号数/模块 | ~4.5 |
| 全公开模块（100% public） | 35 个 |
| 低内聚模块（≤30% public） | 3 个 |

### 高内聚（全公开）模块 TOP 10
这些模块的所有函数/类都是公开的，缺乏内部实现封装：
| 模块 | 公开 | 私有 | 问题 |
|------|------|------|------|
| `category_registry` | 8 | 0 | 🔴 无内部封装 |
| `core.db` | 7 | 0 | 数据库工具全公开 |
| `core.evaluation` | 7 | 0 | 评测逻辑全公开 |
| `core.__init__` | 12 | 0 | Re-export 合理 |
| `pipeline.unified` | 10 | 0 | 管道函数全公开 |
| `services.feature_flags` | 5 | 0 | Flag 管理全公开 |
| `services.learner` | 6 | 0 | 学习逻辑全公开 |

### 低内聚模块（应重构）
| 模块 | 公开 | 私有 | 内聚度 | 说明 |
|------|------|------|--------|------|
| `services/retrieval` | 2 | 5 | 0.29 | 大部分是内部实现 |
| `taiyin/growth_api` | 2 | 5 | 0.29 | 内部辅助函数过多 |
| `services/dxf_viewer/parser` | 1 | 10 | 0.09 | 几乎全是内部实现 |

### 按目录的模块分布
| 目录 | 文件数 | 说明 |
|------|--------|------|
| hypothalamus | 82 | 最大的目录（器官层，4层子目录结构） |
| services | 48 | 第二大（含 4 个子服务） |
| infra | 26 | 基础设施 |
| taiyang | 24 | 太阳层（检索） |
| shaoyin | 19 | 少阴层（推理） |
| api | 17 | API 路由 |
| shaoyang | 16 | 少阳层（消化） |
| taiyin | 11 | 太阴层（接口） |

---

## 维度 10：server.py 拆分分析 🟡

### 当前状态
| 指标 | 数值 |
|------|------|
| server.py 总行数 | 460 行 |
| 内联 @app 路由 | 29 个 |
| `app.include_router()` 调用 | 14 个 |
| 路由中间件 | 3 个（Auth + InputLimit + Metrics） |

### 内联路由列表（应拆分到独立 router 文件）
```
健康检查/监控:
  GET  /api/health, /api/metrics, /metrics
  GET  /api/system/stats, /api/cache/stats, /api/errors/stats
  GET  /api/admin/metrics-summary

认证:
  GET  /api/auth/me

MCP 协议（5 个端点）:
  POST /api/mcp, /api/mcp/sag_search, /api/mcp/sag_ingest
  POST /api/mcp/sag_explain, GET /api/mcp/sag_status, /api/mcp/tools

评测（3 个端点）:
  POST /api/eval/run, GET /api/eval/report, /api/eval/history

四象/成长:
  GET /api/symbols/status, /api/growth/overview

Feature Flags:
  GET /api/feature-flags, PUT /api/feature-flags/{name}

代理:
  GET /api/proxy/loader/files, POST /api/proxy/loader/upload

前端页面:
  GET /, /login, /admin
```

### 拆分建议
| 建议 | 优先级 |
|------|--------|
| 将 MCP 5 个端点移到 `api/mcp.py` | 🟡 高 |
| 将健康/监控端点移到 `api/monitoring.py` | 🟡 高 |
| 将评测端点移到 `api/evaluation.py` | 🟢 中 |
| 将四象/成长端点移到 `api/growth.py` | 🟢 中 |
| 将代理端点移到 `api/proxy.py` | 🟢 中 |
| 统一前端页面处理 | 🟢 中 |
| 注册 5 个僵尸服务路由（ai_tools, data_analytics, doc_tools, dxf_viewer, files_view） | 🟡 高 |
| 移除或完成 `fuxi_platform` 集成 | 🟢 低 |

### 僵尸服务注册（关键缺失）
以下服务路由需要添加到 server.py：
```python
# 缺失的注册
from src.services.ai_tools.routes import router as ai_tools_router
from src.services.data_analytics.routes import router as analytics_router
from src.services.doc_tools.routes import router as doc_tools_router
from src.services.dxf_viewer.api import router as dxf_viewer_router
from src.api.files_view import router as files_view_router

app.include_router(ai_tools_router)      # 6 endpoints at /api/ai/*
app.include_router(analytics_router)     # 15 endpoints at /api/analytics/*
app.include_router(doc_tools_router)     # 10 endpoints at /api/tools/*
app.include_router(dxf_viewer_router)    # 5 endpoints at /api/dxf/*
app.include_router(files_view_router)    # 3 endpoints at /api/view/*, /api/download/*, /api/antenna/*
```

---

## 📋 汇总与优先级建议

### 🔴 紧急修复（安全相关）
| # | 问题 | 维度 | 影响 |
|---|------|------|------|
| 1 | AuthMiddleware 不验证 token | 3 | **所有 API 无实际认证保护** |
| 2 | 静态资源 `/static/` 无认证 | 3 | 前端源代码暴露 |

### 🟡 高优先级（功能完整性）
| # | 问题 | 维度 |
|---|------|------|
| 3 | 注册 5 个僵尸服务路由 | 7/10 |
| 4 | 统一 API 响应格式 | 1 |
| 5 | 修复 API 层直接导入 DB 层 | 7 |
| 6 | 为 POST/PUT 端点添加 Pydantic 校验 | 4 |
| 7 | 修复循环导入（2 组） | 8 |
| 8 | 为列表端点添加分页 | 5 |

### 🟢 中优先级（架构改进）
| # | 问题 | 维度 |
|---|------|------|
| 9 | 拆分 server.py 内联路由 | 10 |
| 10 | 添加统一错误处理中间件 | 2 |
| 11 | 实现 API 版本管理体系 | 6 |
| 12 | 重构低内聚模块 | 9 |

### ℹ️ 低优先级（技术债务）
| # | 问题 | 维度 |
|---|------|------|
| 13 | 清理 19 处 bare except | 2 |
| 14 | 为高内聚模块添加 `__all__` 和私有化 | 9 |
| 15 | 移除或完成 `fuxi_platform` 集成 | 7 |

---

## 📎 附录

### A. 扫描脚本
- `_scan_api_arch.py` — 全维度扫描主脚本
- `_scan_auth_detail.py` — 认证覆盖详细分析
- `_scan_responses.py` — 响应格式分析
- `_scan_status.py` — HTTP 状态码分析

### B. 仓库文件统计
```
总 Python 源文件: 260+
总代码行数: 约 25,000+
总 API 端点: 89（已注册）+ 39（未注册僵尸服务）
总路由文件: 17 个（api/ 目录）
服务层路由: 4 个（ai_tools, data_analytics, doc_tools, dxf_viewer）
```

### C. 端点完整清单
参见 `docs/API.md` 中的接口文档。

---

> **报告版本**: v1.0 | **下次审计建议**: 修复上述 8 个高优先级问题后进行第四轮回归审计
