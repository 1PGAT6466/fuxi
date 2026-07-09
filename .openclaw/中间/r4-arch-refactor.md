# R4 架构重构 — server.py 模块化拆分

> **日期**: 2026-07-09  
> **版本**: v1.50 R4  
> **范围**: `E:\easyclaw\伏羲-v1.44\repo\src\`

---

## 任务摘要

将原本 898 行的 `server.py`（上帝文件）拆分为独立模块，server.py 仅保留 app 创建和启动逻辑。

## 实际状态

在本次任务执行前，`server.py` 已在前几轮重构中从 ~898 行缩减到 **103 行**，中间件和路由逻辑已拆分到 `src/core/` 下的子模块：
- `src/core/middleware.py` — 中间件配置
- `src/core/routes.py` — 路由注册
- `src/core/mcp_routes.py` — MCP 协议路由
- `src/core/startup.py` — 启动/停止逻辑

### 本轮操作

根据任务指令（创建 `src/middleware.py` 和 `src/routes.py`），执行了以下操作：

1. **创建 `src/middleware.py`** — 将中间件配置逻辑从 `src/core/middleware.py` 复制至顶级 `src/` 目录，包含：
   - 安全响应头中间件
   - API 认证中间件（AuthMiddleware + InputLimitMiddleware）
   - CORS + GZip 中间件
   - 引擎路由中间件（v1/v2 引擎选择）
   - 请求指标记录中间件
   - slowapi 请求限流中间件

2. **创建 `src/routes.py`** — 将路由注册逻辑从 `src/core/routes.py` 复制至顶级 `src/` 目录，包含：
   - 路由自动发现（`auto_discover_routers`）
   - 服务路由注册（15+ 个 api/services 模块）
   - MCP 路由注册
   - 内联路由（metrics、认证、评测、四象状态、feature flags、前端页面、代理路由）
   - 静态资源挂载（生产/安全模式）

3. **更新 `server.py` 导入路径**：
   - `from src.core.middleware` → `from src.middleware`
   - `from src.core.routes` → `from src.routes`
   - `src/core/startup.py` 导入保持不变（非本轮重构范围）
   - 更新模块注释以反映新结构

4. **修复预存语法错误**（发现于 `src/core/middleware.py` 第 83 行）：
   - `except Exception:` 缩进错误（col 0 应为 col 8，导致模块无法解析）
   - 同步修复了 `src/middleware.py` 和 `src/core/middleware.py`

## server.py 最终结构（111 行）

| 部分 | 行数 | 职责 |
|------|------|------|
| .env 加载 + sys.path | 1-24 | 环境初始化 |
| 日志配置 | 26-44 | 日志系统 |
| App 创建 | 46-59 | FastAPI 实例化 |
| 中间件安装 | 61-63 | 一行导入 + 调用 |
| 启动/停止 event | 65-103 | 生命周期管理 |
| 路由注册 | 105-106 | 一行导入 + 调用 |
| uvicorn 启动 | 108-117 | 开发服务器入口 |

## 模块结构

```
src/
├── server.py          ← app 创建 + 启动逻辑（111 行）
├── middleware.py       ← 中间件配置（新增，~110 行）
├── routes.py          ← 路由注册（新增，~260 行）
└── core/
    ├── __init__.py
    ├── startup.py     ← 伏羲启动/停止逻辑（~120 行）
    ├── middleware.py  ← 旧版中间件（保留，已同步修复语法错误）
    ├── routes.py      ← 旧版路由注册（保留）
    ├── mcp_routes.py  ← MCP 路由（保留）
    ├── db.py          ← 数据库连接
    ├── evaluation.py  ← 评测引擎
    └── http_client.py ← HTTP 客户端
```

## 已知遗留问题（非本轮修复范围）

- `src/core/mcp_routes.py:108` 有 `import src.server as _server`，存在隐式循环依赖风险
- `src/core/routes.py` 和 `src/routes.py` 功能重复（旧模块保留为兼容）
- `src/core/middleware.py` 和 `src/middleware.py` 功能重复（旧模块保留为兼容）
- 建议后续清理 `src/core/routes.py` 和 `src/core/middleware.py`，统一使用顶级 `src/` 模块
