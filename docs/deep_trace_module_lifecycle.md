# 伏羲 v1.50 核心模块生死盘点

> 只覆盖 15 个核心模块（按 loading 顺序），基于静态 import 链 + 运行时调用链追踪。

## 调用链全景 (server.py 启动 → 请求 → 响应)

```
server.py (startup)
├── from src.config import HOST,PORT,VERSION,CORS_ORIGINS,LOADER_URL
├── ├── src.hypothalamus.fuxi → Fuxi().born()
│   ├── ├── Meridian()                    # 经络总线
│   ├── ├── ShaoyangPipeline(self.meridian)    # 四象·少阳
│   ├── ├── TaiyangRetrieval(self.meridian)    # 四象·太阳
│   ├── ├── ShaoyinBrain(self.meridian)        # 四象·少阴
│   ├── ├── TaiyinServer(self.meridian)        # 四象·太阴
│   └── └── Brain(self.meridian)               # 大脑
│
├── app.include_router(chat_router)        # /api/chat
├── app.include_router(search_router)       # /api/search
└── app.include_router(documents_router)    # /api/documents

POST /api/chat
  → chat.py: brain = ShaoyinBrain(meridian)  [每次请求新建]
    → brain.think(query, history)
      → _retrieve() → src.taiyang.retrieval.hybrid_search()
        → TaiyangRetrieval.refine()
          → _bm25_recall / _vector_recall (双路召回)
          → _fuse() (RRF 融合)
          → _rerank() → src.taiyang.rerank.rerank_with_deepseek()
          → [条件] multi_hop_search() → src.taiyang.multi_hop
      → [条件] self_rag → src.shaoyin.smart_self_rag
      → [条件] crag → src.shaoyin.crag_corrector.CRAGCorrector.correct_and_retry()
      → _compose() → src.infra.llm.call_deepseek()
      → [记录] src.growth.growth_recorder.GrowthRecordPoints.record_shaoyin_decision()

GET /api/search
  → search.py: src.taiyang.retrieval.hybrid_search()  [不经 brain/brain, 直接调用]

hypothalamus/brain.py → Brain.think()
  → _search_internal() → meridian.send_and_wait(limbs)
  → _compose_with_llm() → deepseek/ollama/模板 三级降级
  → 不走 shaoyin/brain.py, 不走 taiyang/retrieval 上的 hybrid_search
```

---

## 逐模块判定

### 1. server.py → 启动入口
**🟢 运行层**
`python -m src.server` / `uvicorn src.server:app` 直接执行。
证据：FastAPI app 定义、@app.on_event("startup")、_start_fuxi() 均在 server.py。

### 2. src/config.py
**🟢 运行层**
`from src.config import HOST, PORT, VERSION, CORS_ORIGINS, LOADER_URL` — server.py 第 48 行。
证据：server.py 启动最先 import config；所有模块通过 config 读数据库路径/端口/embedder URL。

### 3. src/api/chat.py → 对话 API
**🟢 运行层**
`app.include_router(chat_router)` — server.py 第 165 行。
证据：`POST /api/chat` 和 `/api/chat/agent` 上线；内部 new ShaoyinBrain + Meridian 走 think()。

### 4. src/api/search.py → 搜索 API
**🟢 运行层**
`app.include_router(search_router)` — server.py 第 162 行。
证据：`GET /api/search` → `src.taiyang.retrieval.hybrid_search()`。

### 5. src/api/documents.py → 文档上传 API
**🟢 运行层**
`app.include_router(documents_router)` — server.py 第 173 行。
证据：`GET /api/documents`, `POST /api/upload` 上线；读 src.db.data_store。

### 6. src/shaoyin/brain.py → 少阴推理 (ShaoyinBrain)
**🟢 运行层**
`chat.py: from src.shaoyin.brain import ShaoyinBrain` → POST /api/chat 每次构建。
证据：chat.py 第 16 行直接 import 并在请求内调用 brain.think()；Fuxi.born() 中也创建 ShaoyinBrain 实例。

### 7. src/shaoyin/agentic_rag_v2.py → Agentic RAG
**🔴 死层**
全仓库无任何 `from src.shaoyin.agentic_rag_v2` 或 `from shaoyin.agentic_rag_v2` import 语句。
证据：chat.py 只调 ShaoyinBrain.think()（走 _retrieve → _compose），未引用 AgenticRAG 类。services/__init__.py 将其标记为「已删除」列表。agents_old/orchestrator.py 仅 comment 提及。

### 8. src/shaoyin/crag_corrector.py → CRAG 纠错
**🟡 条件层**
`shaoyin/brain.py: from src.shaoyin.crag_corrector import CRAGCorrector` → 仅在 Self-RAG 未通过时调用。
证据：brain.py think() L88: `if not reflection_pass: crag = self._get_crag()` → `crag.correct_and_retry()`。
条件：self_rag 存在 && reflection.action != "pass"。若 self_rag 不可用（smart_self_rag import 失败），CRAG 永不触发。

### 9. src/taiyang/retrieval.py → 检索入口 (TaiyangRetrieval + hybrid_search)
**🟢 运行层**
两条独立调用路径均命中：
- chat.py → ShaoyinBrain._retrieve() → hybrid_search()
- search.py → hybrid_search()
- Fuxi.born() 中创建 TaiyangRetrieval 单例
证据：hybrid_search() 是 module-level 函数，走 `get_retrieval()` 获取 Fuxi 启动时生成的 taiyang 单例。

### 10. src/taiyang/rerank.py → 精排
**🟡 条件层**
`taiyang/retrieval.py: from src.taiyang.rerank import rerank_with_deepseek` → `_rerank()` 调用。
证据：retrieval.py refine() L81: `reranked = await self._rerank(query, fused)` → `rerank_with_deepseek()`。
条件：需 DEEPSEEK_API_KEY 环境变量非空；无 key 则 fallback 到 embedder_server rerank 端点（同文件 L17 读取），两者都不可用时 `_rerank()` 静默返回原始结果（无本地 TF-IDF 降级）。

### 11. src/taiyang/multi_hop.py → 多跳检索
**🔴 死层**（默认关闭）
`taiyang/retrieval.py: if is_enabled("taiyang_multi_hop"): from src.taiyang.multi_hop import multi_hop_search`
证据：src/taiyin/flags.py 中 `"taiyang_multi_hop": False`。除非管理员显式 enable，否则永不到达。

### 12. src/services/evolver.py → 进化引擎
**🟡 条件层**（通过 auto_classifier 间接调用）
调用链：`src.services/__init__.py` → `auto_classifier.classify_by_vectors` → `auto_classifier.py` → `knowledge_evolver.EntityGraph` → `src.services.evolver.discover_entities/infer_relations/evolve_graph`。
证据：evolver 的 discover_entities/infer_relations/evolve_graph 在 shaoyang/auto_classifier.py 的 `classify_and_annotate()` 方法中被调用（L167-169）。但 auto_classifier 仅在文档摄入（pipeline 中）触发，不在 chat/search 热链路。
此外 `/api/evolution/overview` 路由（evolution.py）返回空 `{}`，不走 evolver。

### 13. src/hypothalamus/brain.py → 大脑 (Brain)
**🟢 运行层**（但独立于 chat 链路）
`hypothalamus/fuxi.py: from src.hypothalamus.brain import Brain` → `Fuxi.born()` 中创建 `Brain(self.meridian)`。
证据：Brain 独立运行在经络信号总线（meridian）上，监听信号。它有自己的 think() 方法（走 limbs 检索 → deepseek/ollama 三级降级），不依赖 shaoyin/brain.py。chat API 链路用的是 ShaoyinBrain，不是这个 Brain。两个"大脑"各自独立。

### 14. src/hypothalamus/meridian.py → 经络总线
**🟢 运行层**
`hypothalamus/fuxi.py` → `Meridian()` → `await self.meridian.start()` 启动 pub/sub 信号总线。
证据：所有四象模块 + 器官均通过 Meridian 收发 Signal；brain.py 的 `_search_internal` 通过 `meridian.send_and_wait(limbs)` 检索；chat.py 也实例化 Meridian() 传给 ShaoyinBrain。

### 15. src/growth/engine.py → 成长引擎 (GrowthEngine)
**🔴 死层**
`GrowthEngine` 类仅在 `src/growth/__init__.py` 和 `src/__init__.py` 中 export，**全仓库无任何 runtime import**。
证据：server.py 不用它；fuxi.py 不用它；chat/search/brain 链路不用它。实际使用的 growth 组件是 `src/growth/growth_recorder.py`（在 shaoyin/brain.py 和 hypothalamus/brain.py 中被调用），与 GrowthEngine 完全无关。GrowthEngine 是一个独立的 Phase 2/3 评估与自动调参框架，但从未被集成到启动或请求链路中。

---

## 总结

| # | 模块 | 判定 | 关键证据 |
|---|------|------|---------|
| 1 | server.py | 🟢 运行层 | FastAPI app 启动入口 |
| 2 | src/config.py | 🟢 运行层 | server.py 第 48 行 import |
| 3 | src/api/chat.py | 🟢 运行层 | app.include_router / POST /api/chat |
| 4 | src/api/search.py | 🟢 运行层 | app.include_router / GET /api/search |
| 5 | src/api/documents.py | 🟢 运行层 | app.include_router / upload+list |
| 6 | src/shaoyin/brain.py | 🟢 运行层 | chat.py 直接调用 brain.think() |
| 7 | src/shaoyin/agentic_rag_v2.py | 🔴 死层 | 0 个 runtime import，services list 标记删除 |
| 8 | src/shaoyin/crag_corrector.py | 🟡 条件层 | Self-RAG 失败时才触发 correct_and_retry |
| 9 | src/taiyang/retrieval.py | 🟢 运行层 | chat+search 双链路均调用 hybrid_search |
| 10 | src/taiyang/rerank.py | 🟡 条件层 | 需 DEEPSEEK_API_KEY 或 rerank proxy |
| 11 | src/taiyang/multi_hop.py | 🔴 死层 | feature flag 默认 False，不进入 |
| 12 | src/services/evolver.py | 🟡 条件层 | 仅文档摄入 auto_classifier 间接调用 |
| 13 | src/hypothalamus/brain.py | 🟢 运行层 | Fuxi.born() 创建，经络总线独立运行 |
| 14 | src/hypothalamus/meridian.py | 🟢 运行层 | 全局 pub/sub 信号总线 |
| 15 | src/growth/engine.py | 🔴 死层 | 有 import 无调用，从未集成到 runtime |

**统计：🟢 运行层 9 个 · 🟡 条件层 4 个 · 🔴 死层 2 个 + agentic_rag_v2**

两个独立"大脑"（hypothalamus/brain.py 与 shaoyin/brain.py）并存——前者走经络总线（meridian→limbs 检索），后者是 chat API 的直接入口。两者互不调用，但共享 Meridian 实例。
