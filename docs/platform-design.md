# 伏羲平台化设计方案（生产环境版）

> 版本：v1.0
> 日期：2026-07-03
> 目标：将伏羲体系打造为通用平台，支持接入多种扩展服务

---

## 一、设计原则

| 原则 | 说明 |
|------|------|
| 零侵入 | 不修改现有四象系统代码 |
| 可插拔 | 服务可独立启停，不影响平台 |
| 故障隔离 | 单个服务故障不影响其他服务 |
| 配置驱动 | 服务行为通过YAML配置控制 |
| 渐进式 | 可逐步接入服务，无需一次性完成 |

## 二、平台架构

```
┌─────────────────────────────────────────────────────────────┐
│                     伏羲平台（v2.0）                         │
├─────────────────────────────────────────────────────────────┤
│  接入层                                                      │
│  ├── Web门户（现有前端扩展）                                 │
│  ├── API网关（统一入口+路由+限流+认证）                      │
│  └── WebSocket（实时通信）                                   │
├─────────────────────────────────────────────────────────────┤
│  平台层                                                      │
│  ├── 服务注册中心（Service Registry）                        │
│  ├── 服务配置中心（Service Config）                          │
│  ├── 服务监控中心（Service Monitor）                         │
│  └── 事件总线（Event Bus，复用经络系统）                     │
├─────────────────────────────────────────────────────────────┤
│  服务层                                                      │
│  ├── 内置服务（复用现有四象系统）                            │
│  └── 扩展服务（DXF/CAD/ERP等）                              │
├─────────────────────────────────────────────────────────────┤
│  核心层（现有，不修改）                                       │
│  ├── 少阳·消化系统                                          │
│  ├── 太阳·筑基系统                                          │
│  ├── 少阴·炼化系统                                          │
│  ├── 太阴·显化系统                                          │
│  └── 器官组件                                               │
└─────────────────────────────────────────────────────────────┘
```

## 三、目录结构

```
伏羲-v1.50/
├── src/
│   ├── fuxi_platform/               # 平台层（新增，避免与Python内置platform冲突）
│   │   ├── __init__.py
│   │   ├── registry.py              # 服务注册中心
│   │   ├── config_center.py         # 服务配置中心
│   │   ├── monitor.py               # 服务监控中心
│   │   ├── gateway.py               # API网关
│   │   ├── events.py                # 事件总线
│   │   └── api.py                   # 平台API路由
│   │
│   ├── services/                    # 扩展服务目录（新增）
│   │   └── dxf-viewer/
│   │       ├── service.yaml         # 服务描述
│   │       ├── __init__.py
│   │       ├── server.py            # 服务入口
│   │       ├── parser.py            # DXF解析
│   │       ├── renderer.py          # 渲染数据
│   │       ├── dedup.py             # 去重算法
│   │       └── api.py               # 服务API
│   │
│   └── ...（现有代码不变）
│
├── config/
│   ├── platform.yaml                # 平台配置（新增）
│   └── services/                    # 服务配置目录（新增）
│
└── data/
    └── services/                    # 服务数据目录（新增）
```

## 四、服务描述协议

```yaml
# services/dxf-viewer/service.yaml
service:
  id: dxf-viewer
  name: DXF看图服务
  version: 1.0.0
  description: 专业DXF文件查看、测量、标注服务
  type: extension
  icon: 📐

  dependencies:
    python:
      - ezdxf>=1.0.0
      - Pillow>=10.0.0

  capabilities:
    file_types: [".dxf", ".dwg"]
    features: ["view", "measure", "annotate", "export"]

  api:
    prefix: /api/dxf
    endpoints:
      - path: /view/{hash}
        method: GET
        auth: required
      - path: /upload
        method: POST
        auth: required
      - path: /files
        method: GET
        auth: required

  health:
    endpoint: /api/dxf/health
    interval: 30s
    timeout: 5s

  resources:
    max_file_size: 100MB
    max_concurrent: 50
    timeout: 30s
```

## 五、平台API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/services/` | GET | 列出所有服务 |
| `/api/services/{id}` | GET | 获取服务详情 |
| `/api/services/{id}/start` | POST | 启动服务 |
| `/api/services/{id}/stop` | POST | 停止服务 |
| `/api/services/{id}/health` | GET | 服务健康检查 |
| `/api/services/{id}/config` | GET | 获取服务配置 |
| `/api/services/{id}/config` | PUT | 更新服务配置 |

## 六、服务生命周期

```
注册 → 启动 → 运行 → 停止
         ↓
       异常 → 自动重启/通知管理员
```

## 七、实施路线

| 阶段 | 任务 | 时间 | 风险 |
|------|------|------|------|
| Phase 1 | 平台核心（注册中心+网关+事件总线） | 2天 | 低 |
| Phase 2 | DXF服务接入 | 2天 | 低 |
| Phase 3 | 服务管理页面 | 1天 | 低 |
| Phase 4 | 集成测试+文档 | 1天 | 低 |

## 八、验收标准

1. 平台可正常启动，服务注册中心运行正常
2. DXF服务可独立启停，不影响主系统
3. 服务健康检查正常工作
4. API网关可正确路由请求
5. 所有现有测试通过（225+ passed）
6. 服务管理页面可正常显示和操作
