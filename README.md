# 伏羲 Fuxi — 企业知识认知系统

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.43-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="python">
  <img src="https://img.shields.io/badge/framework-FastAPI-orange" alt="framework">
  <img src="https://img.shields.io/badge/license-Proprietary-red" alt="license">
</p>

> **伏羲**——以中医脏腑隐喻构建的企业知识认知中枢，经络为信号总线，器官为功能模块，八卦为 UI 架构。

---

## 🏗️ 架构总览

```
src/
├── server.py                  ← FastAPI 入口
├── config.py                  ← 统一配置（环境变量优先）
├── hypothalamus/              ← 下丘脑·生命体核心
│   ├── fuxi.py                ← 生命体启动器（13 器官 + 五行平衡）
│   ├── brain.py               ← 大脑（多意图本能 + 三级降级 + 自我纠错）
│   ├── meridian.py            ← 经络（全身唯一信号总线）
│   ├── organs/                ← 13 个器官 Agent
│   └── balance/               ← 五行平衡 + 天干调度 + 经络流注
├── agents/                    ← 太极·阴阳 Agent 框架
│   ├── yin_agent.py           ← 阴·校验层（规则 + LLM 双层校验）
│   ├── yang_agent.py          ← 阳·执行层（MiMo FC + 多步推理）
│   └── orchestrator.py        ← 调度 Agent
├── services/                  ← 核心服务（30+ 模块）
│   ├── retrieval.py           ← 混合检索 L-1→L6 六层管线
│   ├── rerank.py              ← 四级降级 Rerank
│   ├── graph_router.py        ← 知识图谱路由
│   ├── wiki.py                ← LLM-Wiki 引擎
│   └── ...                    ← 更多服务
├── api/                       ← API 路由（20+ 端点）
├── db/                        ← 数据存储层
├── pipeline/                  ← 周天大阵统一管线
└── 中宫--胃/                  ← 装载机·清洗模块（独立部署）
```

## 🔍 检索管线

```
L-1: QA对匹配 → L0: 语义缓存+图谱路由 → L1: 同义词+LLM改写 →
L1.5: HyDE → L2: BM25+向量双路 → L3: RRF融合+动态alpha →
L4: 三阶段精排 → L5: Rerank四级降级 → L6: Parent-Child+Sentence Window
```

五路并行召回：BM25 + 向量 + HyDE + Wiki + 表格视图

## 🧠 Agent 框架

| Agent | 职责 | 模型 |
|-------|------|------|
| 🧠 Brain | 多意图识别 + 三级降级 + 自我纠错 | MiMo 2.5 |
| ☯️ Yin | 规则校验 + LLM 幻觉检测 | MiMo 2.5 Turbo |
| ☯️ Yang | FC 工具调用 + 多步推理 | MiMo 2.5 Pro |
| 🔄 Orchestrator | Plan→Execute→Reflect 调度 | - |

## 🚀 快速开始

### 环境要求

- Python 3.10+
- ChromaDB
- embedder_server (BGE-small-zh-v1.5)

### 安装

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置 API Key 等
```

### 启动

```bash
python -m src.server
# 或
uvicorn src.server:app --host 0.0.0.0 --port 8080
```

访问 `http://localhost:8080` 进入前端界面。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `KB_PORT` | API 端口 | `8080` |
| `KB_EMBEDDER_URL` | Embedder 服务地址 | `http://localhost:8081` |
| `MIMO_API_KEY` | MiMo API Key | - |
| `MIMO_BASE_URL` | MiMo API 地址 | `https://token-plan-cn.xiaomimimo.com/v1` |
| `MIMO_MODEL` | MiMo 模型名 | `mimo-v2.5` |
| `KB_ADMIN_TOKEN` | 管理员 Token | - |
| `LOADER_URL` | 装载机地址 | `http://localhost:8090` |

## 📡 API 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | AI 对话（流式/非流式） |
| `/api/search` | POST | 混合检索 |
| `/api/documents/*` | GET/POST | 文档管理 |
| `/api/wiki/*` | GET/POST | LLM-Wiki |
| `/api/graph/*` | GET/POST | 知识图谱 |
| `/api/health` | GET | 健康检查 |
| `/api/evaluation/*` | GET | 评测仪表板 |
| `/api/pipeline/*` | POST | 周天大阵统一管线 |
| `/docs` | GET | Swagger 文档 |

## 🧪 测试

```bash
pytest tests/ -v
```

## 📁 项目结构

```
├── src/           # 源代码
├── frontend/      # 前端页面（SPA）
├── tests/         # 单元测试
├── scripts/       # 工具脚本
├── data/          # 数据目录（.gitignore）
├── config/        # 配置文件
└── docs/          # 文档
```

## 📄 License

Proprietary — © PGA Technology
