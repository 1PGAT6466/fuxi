# 伏羲 v1.50 体系架构

## 术语定义

- **伏羲 = 体系（System of Systems）**：由多个系统组成的完整知识认知体系
- **四象 = 系统（System）**：少阳、太阳、少阴、太阴四大功能系统
- **器官 = 组件（Component）**：系统内的具体功能模块（心、肝、脾、肺、肾...）

## 一、物理拓扑

```
172.25.30.10 (本机/PGAT-CDB004)
  └─ EasyClaw 会话 + 代码备份

172.25.30.16 (装载机/PGAT-CDT004 · Windows 10)
  ├─ local_receiver :8090  — 文件上传接收
  ├─ kb_daemon :8093      — 自动清洗推送守护
  ├─ ocr_daemon           — OCR 后台处理
  ├─ rerank_proxy :8091   — Rerank 代理(SiliconFlow API)
  └─ 存储: F:\公司知识平台\
      ├─ 传入数据\原始文件\
      ├─ 清洗文件\
      ├─ 清洗程序\
      ├─ 知识图谱\
      ├─ 后端\     (v1.50 代码备份)
      └─ 前端\     (v1.50 代码备份)

172.25.30.200 (服务器/PGAT-storge · Ubuntu 22.04 VM)
  ├─ kb-server :8080      — FastAPI 主服务
  ├─ Ollama :11434        — qwen2.5:1.5b 本地推理
  ├─ embedder_server :8081 — BGE-base 文本向量化
  ├─ ChromaDB             — 向量存储
  ├─ MemoryStore          — BM25 全文索引
  └─ 路径: /home/feng-shaoxuan/kb-server/
```

## 二、四象系统架构

### 2.1 少阳·消化系统（知识消化中枢）

负责文档的解析、清洗、分块和知识提取。

```
shaoyang/
├── pipeline.py        # 统一处理管线
├── extractor.py       # SAG式事件/实体提取
├── semantic_chunker.py # 语义分块（替代原 chunker.py）
├── cleaner.py         # 文本清洗
├── parser.py          # 文档解析
└── ingest.py          # 入库管理
```

### 2.2 太阳·筑基系统（精炼排序中枢）

负责检索和排序。通过多路召回、融合、精排，从海量知识中找到最相关内容。

```
taiyang/
├── retrieval.py       # 混合检索管线
├── multi_hop.py       # SAG式多跳检索
├── fusion.py          # RRF融合
├── rerank.py          # 四级降级精排
├── dynamic_alpha.py   # 动态融合权重 (v1.50新增)
├── query_expansion.py # 查询扩展
├── graph.py           # 图谱检索
└── cache.py           # 语义缓存
```

### 2.3 少阴·炼化系统（决策合成中枢）

负责答案生成和质量控制。通过LLM合成答案，并进行事实性校验和质量评估。

```
shaoyin/
├── brain.py           # 决策合成引擎
├── judge_v2.py        # LLM-as-Judge评分 (v1.50新增)
├── fact_check.py      # 事实性校验 (v1.50新增)
├── context_compressor.py # 上下文压缩 (v1.50新增)
├── strategy.py        # 策略选择
├── orchestrator.py    # 编排器
└── resolver.py        # 解析器
```

### 2.4 太阴·显化系统（对外接口中枢）

负责体系对外服务。提供API接口、监控指标、审计日志和安全管理。

```
taiyin/
├── server.py          # 对外接口
├── audit.py           # 审计日志 (v1.50新增)
├── metrics.py         # Prometheus指标 (v1.50新增)
├── security.py        # 安全模块 (v1.50新增)
├── flags.py           # Feature Flag管理
├── monitor.py         # 监控模块
└── mcp_protocol.py    # MCP协议
```

## 三、经络系统

### 3.1 信号总线

经络系统是体系内唯一的通信网络，负责系统和器官间的异步通信和状态同步。

```python
# 信号类型
class SignalType(Enum):
    HEARTBEAT = "heartbeat"      # 心跳信号
    ALERT = "alert"              # 告警信号
    DATA = "data"                # 数据信号
    COMMAND = "command"          # 命令信号

# 信号优先级
class Priority(Enum):
    CRITICAL = 0                 # 紧急
    HIGH = 1                     # 高
    NORMAL = 2                   # 普通
    LOW = 3                      # 低
```

### 3.2 系统和器官注册

每个系统和器官在启动时注册到经络系统，并订阅感兴趣的信号类型。

```python
class Organ:
    def __init__(self, name: str):
        self.name = name
        self.meridian = get_meridian()
        self.meridian.register(self)
    
    def on_signal(self, signal: Signal):
        """处理接收到的信号"""
        pass
    
    def emit(self, signal_type: SignalType, payload: dict):
        """发送信号到经络"""
        self.meridian.emit(Signal(
            signal_type=signal_type,
            source=self.name,
            payload=payload
        ))
```

## 四、数据流

### 4.1 文档入库流程

```
用户上传 → local_receiver:8090
  → kb_daemon 监听
  → 少阳·消化系统处理
    → parser.py 解析
    → cleaner.py 清洗
    → semantic_chunker.py 分块
    → extractor.py 提取
  → MemoryStore 存储
  → ChromaDB 向量化
  → 知识图谱更新
```

### 4.2 检索流程

```
用户查询 → /api/search
  → 大脑·brain 意图识别
  → 少阴·炼化系统 查询规划
  → 太阳·筑基系统 检索
    → L-1: QA对匹配
    → L0: 语义缓存+图谱路由
    → L1: 同义词+LLM改写
    → L1.5: HyDE
    → L2: BM25+向量双路
    → L3: RRF融合+动态alpha
    → L4: 三阶段精排
    → L5: Rerank四级降级
    → L6: Parent-Child+Sentence Window
  → Top-K 结果
```

### 4.3 对话流程

```
用户提问 → /api/chat
  → 大脑·brain 意图识别
  → 少阴·炼化系统 编排
    → 检索相关知识
    → 上下文压缩
    → LLM生成答案
    → 事实性校验
    → 质量评分
  → 太阴·显化系统 返回响应
  → 审计日志记录
```

## 五、API清单 (60+ 端点)

### 5.1 搜索

- GET  /api/search            — 混合检索
- GET  /api/search-history    — 搜索历史
- GET  /api/images/{name}     — 图片服务

### 5.2 AI 对话

- POST /api/chat              — 智能问答(流式/非流式)
- POST /api/chat/agent        — Agentic RAG

### 5.3 文档管理

- GET  /api/documents         — 文档列表(分页)
- GET  /api/documents/{hash}  — 文档详情
- DEL  /api/documents/{hash}  — 删除文档
- GET  /api/view/{hash}       — 原文查阅
- POST /api/raw-store         — 上传代理
- POST /api/ingest-batch      — 批量入库
- POST /api/reindex           — 全量重建索引
- POST /api/reset             — 清空数据

### 5.4 知识图谱

- GET  /api/graph             — 实体查询/BFS路径
- GET  /api/graph/path        — 最短路径
- GET  /api/graph/nodes       — 节点列表
- POST /api/graph/build       — 重建图谱

### 5.5 管理面板

- GET  /                       — 主平台首页
- GET  /admin                  — 管理面板首页
- GET  /api/health             — 健康检查
- GET  /api/stats              — 统计信息
- GET  /api/admin/stats        — 管理统计
- GET  /api/admin/server-status— 服务器状态
- GET  /api/admin/upload-trend — 上传趋势
- GET  /api/admin/recent-activities — 最近活动
- GET  /api/admin/ai-search-logs   — 搜索日志
- GET  /api/admin/search-analytics — 搜索分析
- GET  /api/admin/hot-queries  — 热门搜索
- GET  /api/admin/tools        — 工具管理(GET/POST)
- GET  /api/admin/faq          — FAQ管理(GET/POST)
- GET  /api/admin/terms        — 术语管理(GET/POST)
- GET  /api/admin/feedbacks    — 反馈统计
- GET  /api/admin/config       — 配置管理
- GET  /api/admin/config/history — 配置历史
- POST /api/admin/config/rollback — 配置回滚
- POST /api/admin/deploy-frontend — 前端部署
- POST /api/admin/rebuild-vectors — 重建向量索引
- GET  /api/admin/knowledge-graph — 图谱统计
- GET  /api/admin/export/documents — 导出文档CSV
- GET  /api/admin/export/search-logs — 导出搜索日志

### 5.6 评测

- GET  /api/admin/eval/run     — 运行评估
- GET  /api/admin/eval/dataset — 评测集(GET/POST)
- GET  /api/admin/eval/results — 历史结果

### 5.7 反馈与用户

- POST /api/feedback           — 用户反馈
- POST /api/feedback/v2        — 增强反馈
- POST /api/behavior           — 行为日志
- GET  /api/user/preferences   — 用户偏好(GET/POST)
- GET  /api/task/{id}          — 任务状态
- GET  /api/tools              — 工具列表
- GET  /api/tools/check        — 工具状态检查
- GET  /api/faq                — FAQ列表

### 5.8 MCP协议 (v1.50增强)

- GET  /api/mcp/tools          — MCP工具列表
- POST /api/mcp                — MCP调用

### 5.9 四象系统状态

- GET  /api/symbols/status     — 四象系统状态
- GET  /api/growth/overview    — 成长概览

### 5.10 Feature Flags

- GET  /api/feature-flags      — 获取Flags
- PUT  /api/feature-flags/{name} — 更新Flag

### 5.11 审计与监控 (v1.50新增)

- GET  /api/audit/logs         — 审计日志
- GET  /metrics                — Prometheus指标

## 六、数据库

| 存储 | 引擎 | 数据量 | 用途 |
|------|------|--------|------|
| chunks.db | SQLite FTS5 | — | BM25 全文检索 |
| ChromaDB | SQLite + HNSW | — | 语义向量检索 |
| knowledge_graph.json | JSON | — | 知识图谱 |
| feedback_log.jsonl | JSONL | — | 反馈日志 |

## 七、技术栈

| 组件 | 选型 | 版本 |
|------|------|------|
| Web框架 | FastAPI | — |
| LLM | MiMo 2.5 Pro | v1.50 |
| 本地模型 | Ollama qwen2.5:1.5b | — |
| Embedding | BGE-base-zh-v1.5 | :8081 |
| 向量库 | ChromaDB | — |
| 关键词检索 | jieba + BM25 | — |
| Rerank | SiliconFlow Qwen3-Reranker-8B | 代理 via :8091 |
| 文档解析 | pdfplumber + PyPDF2 | 双轨 |
| 认证 | PyJWT | v1.50升级 |
| 前端 | 原生 HTML/CSS/JS | 无框架依赖 |

## 八、v1.50 新增模块

### 8.1 审计日志 (taiyin/audit.py)

记录所有关键操作，支持安全审计和问题追踪。

### 8.2 Prometheus指标 (taiyin/metrics.py)

暴露体系指标，支持Prometheus监控集成。

### 8.3 安全模块 (taiyin/security.py)

敏感信息脱敏、输入验证、安全防护。

### 8.4 动态融合权重 (taiyang/dynamic_alpha.py)

根据查询特征动态调整BM25和向量检索的权重。

### 8.5 LLM-as-Judge (shaoyin/judge_v2.py)

使用LLM进行答案质量评分。

### 8.6 事实性校验 (shaoyin/fact_check.py)

校验生成答案的事实准确性。

### 8.7 上下文压缩 (shaoyin/context_compressor.py)

压缩检索到的上下文，提高LLM处理效率。
