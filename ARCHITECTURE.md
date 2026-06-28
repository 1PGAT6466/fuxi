
# 宝利根知识库 v10.0 系统架构

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
      ├─ 后端\     (v10.0 代码备份)
      └─ 前端\     (v10.0 代码备份)

172.25.30.200 (服务器/PGAT-storge · Ubuntu 22.04 VM)
  ├─ kb-server :8080      — FastAPI 主服务
  ├─ Ollama :11434        — qwen2.5:1.5b 本地推理
  ├─ embedder_server :8081 — BGE-base 文本向量化
  ├─ ChromaDB             — 向量存储 (4,985 vectors)
  ├─ MemoryStore          — BM25 全文索引 (9,937 chunks)
  └─ 路径: /home/feng-shaoxuan/kb-server/
```

## 二、数据流

```
上传:  用户 → 主平台 → local_receiver:8090
         → kb_daemon 监听 → 清洗 → POST /api/ingest-batch
         → 服务器 MemoryStore → 自动向量化 → 图谱进化

检索:  用户 Query → /api/search
         → query_router(意图路由) → graph_router(图谱分类锁定)
         → BM25 + 向量双路 → RRF 融合 → 精排(匹配/分类/MMR)
         → Rerank(装载机:8091→SiliconFlow) → Sentence Window
         → Top-K 结果

AI对话: /api/chat → 混合检索 → 图谱上下文注入
         → Ollama 流式生成 → 答案 + 引用来源

评估:   /api/admin/eval/run
         → Hit@K/MRR/NDCG/ContextPrecision/Faithfulness

反馈:   👍/👎 → feedback_log → 术语权重调整 → 周画像更新
```

## 三、代码结构 (服务器)

```
/home/feng-shaoxuan/kb-server/
├── server.py              # 主入口 (81行)
├── config.py              # 全局配置
├── data_store.py          # 数据读写工具
├── memory_store.py        # BM25 全文检索(FTS5)
├── vector_store.py        # ChromaDB 向量存储
├── ingest.py              # 文本提取/清洗/分块(pdfplumber+PyPDF2)
├── classify.py            # 17类文档分类器
├── query_router.py        # 意图路由
├── feedback_learner.py    # 反馈学习闭环
├── knowledge_evolver.py   # 图谱进化
├── embedder_server.py     # 向量嵌入服务(独立进程)
│
├── routers/               # API 路由层
│   ├── search.py          # /api/search
│   ├── chat.py            # /api/chat
│   ├── documents.py       # /api/documents + raw-store + ingest-batch
│   ├── graph.py           # /api/graph
│   ├── admin.py           # / /admin /api/health + 管理API
│   └── feedback.py        # /api/feedback + 用户偏好
│
├── services/              # 业务逻辑层
│   ├── retrieval.py       # 混合检索全链路
│   ├── rerank.py          # Rerank 精排(代理 → SiliconFlow)
│   ├── llm.py             # LLM 调用(Ollama/MIMO)
│   ├── embed.py           # 向量嵌入
│   ├── eval.py            # 四层评估指标
│   └── graph_router.py    # 图谱驱动检索路由
│
└── static/                # 前端
    ├── index.html         # 主平台(搜索+AI问答)
    └── admin/
        ├── index.html     # 管理面板(9个tab)
        └── graph.html     # 知识图谱(知书阁)
```

## 四、API 清单 (58 个端点)

### 搜索
- GET  /api/search            — 混合检索
- GET  /api/search-history    — 搜索历史
- GET  /api/images/{name}     — 图片服务

### AI 对话
- POST /api/chat              — 智能问答(流式/非流式)
- POST /api/chat/agent        — Agentic RAG

### 文档管理
- GET  /api/documents         — 文档列表(分页)
- GET  /api/documents/{hash}  — 文档详情
- DEL  /api/documents/{hash}  — 删除文档
- GET  /api/view/{hash}       — 原文查阅
- POST /api/raw-store         — 上传代理
- POST /api/ingest-batch      — 批量入库
- POST /api/reindex           — 全量重建索引
- POST /api/reset             — 清空数据

### 知识图谱
- GET  /api/graph             — 实体查询/BFS路径
- GET  /api/graph/path        — 最短路径
- GET  /api/graph/nodes       — 节点列表
- POST /api/graph/build       — 重建图谱

### 管理面板
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

### 评估 (v10.0新增)
- GET  /api/admin/eval/run     — 运行评估
- GET  /api/admin/eval/dataset — 评测集(GET/POST)
- GET  /api/admin/eval/results — 历史结果

### 反馈与用户
- POST /api/feedback           — 用户反馈
- POST /api/feedback/v2        — 增强反馈
- POST /api/behavior           — 行为日志
- GET  /api/user/preferences   — 用户偏好(GET/POST)
- GET  /api/task/{id}          — 任务状态
- GET  /api/tools              — 工具列表
- GET  /api/tools/check        — 工具状态检查
- GET  /api/faq                — FAQ列表

## 五、数据库

| 存储 | 引擎 | 数据量 | 用途 |
|------|------|--------|------|
| MemoryStore | SQLite FTS5 + JSON | 9,937 chunks | BM25 全文检索 |
| ChromaDB | SQLite + HNSW | 4,985 vectors | 语义向量检索 |
| knowledge_graph.json | JSON | 249 entities, 2,932 edges | 知识图谱 |
| chunks.json | JSON | 53MB | 原始 chunk 数据 |
| feedback_log.jsonl | JSONL | — | 反馈日志 |

## 六、关键技术栈

| 组件 | 选型 | 版本 |
|------|------|------|
| Web框架 | FastAPI | — |
| 本地模型 | Ollama qwen2.5:1.5b | — |
| Embedding | BGE-base-zh-v1.5 | :8081 |
| 向量库 | ChromaDB | — |
| 关键词检索 | jieba + BM25 | — |
| Rerank | SiliconFlow Qwen3-Reranker-8B | 代理 via :8091 |
| 文档解析 | pdfplumber + PyPDF2 | 双轨 |
| 前端 | 原生 HTML/CSS/JS | 无框架依赖 |
