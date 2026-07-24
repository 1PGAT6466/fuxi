# 伏羲系统架构优化方案

**审议时间**: 2026-07-18  
**审议范围**: 全系统架构（八卦体系 / 数据流 / 检索 / 安全）  
**当前版本**: v1.44（架构文档 v1.50）

---

## 一、架构评估

### 1.1 优点

**① 四象系统分层清晰**  
少阳（消化）→ 太阳（筑基）→ 少阴（炼化）→ 太阴（显化）四层架构符合 RAG 系统的自然数据流。每一层职责单一，理论上可独立扩展。这是架构设计中最值得保留的部分。

**② 检索管线设计严谨**  
L-1 到 L6 的多级检索管线体现了工程深度：QA对快速匹配、语义缓存、HyDE 假设文档、双路召回、RRF 融合、多阶段精排、四级降级 Rerank。对中文 RAG 场景做了针对性优化（jieba 分词、BGE-base-zh、同义词扩展）。

**③ 降级链路完备**  
LLM 调用（MiMo → DeepSeek → 规则兜底）、Rerank（SiliconFlow → 本地 → BM25 → 原始排序）、四级 CircuitBreaker 降级——系统对外部依赖的脆弱性有充分预案。

**④ 自愈体系先行**  
五行器官（心/肝/脾/肺/肾）提供自监控、自修复能力，配合经络信号总线，构建了自治基础。这在同体量系统中罕见。

**⑤ 平台化方向正确**  
v1.50 引入的 Service Registry + Event Bus + API Gateway 平台化思路，为后续扩展（DXF、CAD、ERP 接入）预留了架构空间。

---

### 1.2 缺点

**① 八卦体系过度设计（Over-Engineering）**  
IntentBus + 8 个卦象 + CircuitBreaker + 三级优先级队列 + 反压保护——这套机制的复杂度远超当前业务需求。实际的 RAG 流程只有 5 种意图（SEARCH/DIGEST/REFINE/PRESENT/DONE），绝大多数请求走的是线性流程，八卦调度带来的收益无法覆盖其维护成本和同步阻塞风险。

**② 双路由维护负担**  
v1 ShaoyinBrain 和 v2 乾卦意图循环并行存在，`api/chat.py` 中两套路由逻辑交织。每次修改都需同时验证两条路径，bug 修复容易遗漏。

**③ 存储层碎片化**  
SQLite 文件散落各处：`chunks.db`、`chat_sessions.db`、`conversation_sessions.db`、`memory.db`、`login_rate.db`、`audit.db`、`worldtree.db`、`chroma.sqlite3`——7+ 个独立 SQLite 文件。SQLite 的单写者模型在并发写场景下是硬瓶颈，且 WAL 模式在多文件场景下的锁竞争会放大。

**④ 检索管线无超时保护**  
10+ 阶段管线中，HyDE（~500ms）、Rerank（~1-3s）、LLM 改写（~1-5s）都是潜在的慢操作，但管线层面没有端到端超时。单个阶段的延迟会级联放大，P95 可能超过 10 秒。

**⑤ 假流式 SSE**  
当前 SSE 实现是"先收集完整结果，再分块推送"——不是真正的流式。对用户体验（首 token 延迟）和资源利用（需等待完整生成）都有负面影响。

**⑥ JWT 密钥管理缺陷**  
密钥硬编码或重启失效，没有持久化方案。在生产环境中这是 P0 安全问题。

**⑦ 阻塞式调用混入异步事件循环**  
`time.sleep()` 在 async 函数中直接使用、IntentBus 同步阻塞、部分 I/O 未正确 async 化——这些问题在并发请求时会导致事件循环卡顿，影响所有用户的响应时间。

**⑧ 日志缺乏结构化**  
纯文本日志 + 缺少 trace_id 传播，使得问题排查和性能分析极其困难。当请求经过 10+ 个模块时，无法串联完整链路。

---

## 二、架构优化方案

### 2.1 短期（1-2 周）—— 止血

> **目标**: 修复阻断性问题，不改变架构结构。

#### P0-1: JWT 密钥持久化

**当前问题**: 密钥重启后失效，所有已签发 Token 失效。

**方案**:
```python
# src/auth/jwt_manager.py
import os
import json
from pathlib import Path

KEY_FILE = Path("data/.jwt_key")

def get_or_create_secret() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    secret = os.urandom(32).hex()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(secret)
    os.chmod(KEY_FILE, 0o600)  # 仅 owner 可读
    return secret
```

**交付物**: 新增 `src/auth/jwt_manager.py`，修改 `server.py` 启动逻辑。

#### P0-2: IntentBus async 化

**当前问题**: `intent_bus.py` 使用 `threading.Lock` + 同步调度，在 FastAPI 异步上下文中阻塞事件循环。

**方案**: 将 `IntentBus.dispatch()` 改为 `async def`，Lock 改为 `asyncio.Lock`，超时用 `asyncio.wait_for()`。这是最小改动量的修复，不做架构重构。

```python
# 核心改动
class IntentBus:
    def __init__(self):
        self._lock = asyncio.Lock()  # 替代 threading.Lock
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    async def dispatch(self, intent: Intent, timeout: float = 5.0) -> IntentResult:
        async with self._lock:
            handler = self._route(intent)
        try:
            return await asyncio.wait_for(handler(intent), timeout=timeout)
        except asyncio.TimeoutError:
            return IntentResult(status=DispatchStatus.TIMEOUT)
```

**交付物**: 修改 `src/bagua/intent_bus.py` + `src/services/intent_bus.py`。

#### P0-3: 检索管线端到端超时

**当前问题**: 无超时保护，单阶段失败导致整体阻塞。

**方案**: 在 `TaiyangRetrieval.refine()` 入口添加端到端超时，每阶段独立超时。

```python
async def refine(self, query: str, timeout: float = 8.0, ...) -> List[Dict]:
    try:
        return await asyncio.wait_for(
            self._refine_inner(query, ...),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"[{trace_id}] 检索管线超时 ({timeout}s)，返回缓存/空结果")
        return self._fallback_result(query)
```

**交付物**: 修改 `src/taiyang/retrieval.py`。

#### P1-1: 语义缓存阈值放宽

**当前问题**: 阈值过严导致缓存命中率极低，缓存形同虚设。

**方案**: 阈值从 0.92 降至 0.85，增加近似匹配缓存（similarity ≥ 0.75 时返回候选但标记为"参考"）。

**交付物**: 修改 `src/services/cache.py` 或 `src/taiyang/cache.py`。

#### P1-2: time.sleep 替换

**当前问题**: async 函数中使用 `time.sleep()` 阻塞事件循环。

**方案**: 全局搜索 `time.sleep` 替换为 `await asyncio.sleep()`，对无法 async 化的场景使用 `asyncio.to_thread()`。

**交付物**: 批量修改，grep 验证。

#### P1-3: v1/v2 路由统一

**当前问题**: 双路由维护成本高，bug 修复需双份验证。

**方案**: 短期内保留双路由但统一入口——在 `api/chat.py` 中抽取公共逻辑为共享函数，两条路由共用。

**交付物**: 重构 `src/api/chat.py`。

#### P1-4: 结构化日志 + trace_id

**当前问题**: 纯文本日志，无链路追踪。

**方案**: 引入 `structlog` 或自建 JSON 日志格式，所有日志携带 `trace_id`。

```python
# src/infra/logging.py 改造
import json
import logging

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
            "module": record.module,
        }, ensure_ascii=False)
```

**交付物**: 修改 `src/core/logging_config.py`，所有 logger 调用点添加 trace_id。

#### P2-1: 路由注册统一

**当前问题**: `server.py`、`core/routes.py`、各模块独立注册，方式不统一。

**方案**: 统一由 `core/routes.py` 管理所有路由注册，`server.py` 只负责生命周期。

---

### 2.2 中期（1-3 月）—— 架构优化

> **目标**: 解决结构性问题，为后续扩展铺路。

#### 2.2.1 存储层迁移：SQLite → PostgreSQL

**决策**: **推荐迁移**，但分阶段。

**理由**:
- 当前 7+ SQLite 文件的维护成本已超过迁移成本
- PostgreSQL 提供：并发写、JSONB（替代 knowledge_graph.json）、全文检索（替代 FTS5）、行级锁、ACID 事务
- SQLite 适合嵌入式/单机原型，不适合并发服务

**迁移路径**:

| 阶段 | 内容 | 周期 |
|------|------|------|
| Phase 1 | `chunks.db` + `chat_sessions.db` + `conversation_sessions.db` 迁移 | 1 周 |
| Phase 2 | `memory.db` + `audit.db` + `login_rate.db` 迁移 | 1 周 |
| Phase 3 | `worldtree.db` + 知识图谱 JSON 迁移 | 1 周 |
| Phase 4 | ChromaDB 保留（向量检索专用），但元数据迁入 PG | 随 ChromaDB 版本升级 |

**方案**: 使用 `deploy/migrate_to_pg.py`（已存在）+ `deploy/schema_pg.sql`（已存在）作为基础，补充数据迁移脚本。

**兼容层**: 抽象 `DataStore` 接口，SQLite/PG 双实现，通过配置切换。

```python
# src/db/data_store.py 改造
class DataStore(Protocol):
    async def get_chunks(self, doc_hash: str) -> List[Dict]: ...
    async def save_session(self, session: SessionData) -> None: ...
    async def get_audit_logs(self, since: datetime) -> List[Dict]: ...

class SQLiteDataStore(DataStore): ...  # 现有实现
class PostgresDataStore(DataStore): ...  # 新实现
```

#### 2.2.2 八卦体系精简

**决策**: **保留四象系统，精简八卦调度**。

**理由**:
- 四象（少阳/太阳/少阴/太阴）的分层是架构核心价值，必须保留
- 8 个卦象 + IntentBus 的调度复杂度对当前业务是过度设计
- 八卦体系的"意图路由"功能可以用更简单的方式实现

**方案**:

| 组件 | 决策 | 理由 |
|------|------|------|
| IntentBus (bagua/) | **简化为 async Router** | 当前 5 种意图不需要三级优先级队列 |
| 乾卦 (qian.py) | **保留，简化为 Orchestrator** | 作为 RAG 流程编排器仍有价值 |
| 坤卦 (kun.py) | **合并入太阴** | 数据存储职责已由太阴覆盖 |
| 震卦 (zhen.py) | **合并入少阳** | 上传处理是消化流程的一部分 |
| 巽卦 (xun.py) | **保留，独立** | 文档搜索是独立能力 |
| 坎卦 (kan.py) | **合并入太阳** | 检索增强已由太阳覆盖 |
| 离卦 (li.py) | **保留，独立** | 通知/告警是独立关注点 |
| 艮卦 (gen.py) | **合并入少阴** | 质量控制是炼化流程的一部分 |
| 兑卦 (dui.py) | **合并入太阴** | 对外表达是显化系统的职责 |

**精简后**: 4 象系统 + 3 独立卦（乾/巽/离），去掉 5 个冗余卦和复杂的 IntentBus 调度。

#### 2.2.3 检索管线优化

**问题**: 10+ 阶段管线复杂度高，部分阶段收益递减。

**方案**:

| 阶段 | 决策 | 理由 |
|------|------|------|
| L-1 QA对匹配 | **保留** | <10ms，几乎零成本 |
| L0 语义缓存 | **保留，阈值放宽** | 缓存命中时省去整个管线 |
| L0 图谱路由 | **选择性启用** | 仅当知识图谱实体 > 1000 时 |
| L1 同义词扩展 | **保留** | 低成本高收益 |
| L1 LLM 改写 | **选择性启用** | 简单查询跳过，复杂查询启用 |
| L1.5 HyDE | **默认关闭，按需启用** | ~500ms 延迟，对长尾查询有帮助 |
| L2 双路召回 | **保留** | 核心检索能力 |
| L3 RRF 融合 | **保留** | 核心融合逻辑 |
| L4 三阶段精排 | **简化为两阶段** | 匹配+MMR 去重，去掉中间分类 |
| L5 Rerank | **保留四级降级** | 已有良好设计 |
| L6 Parent-Child | **选择性启用** | 短文档跳过 |

**Feature Flag 控制**: 每个可选阶段通过 Feature Flag 控制，默认关闭。

#### 2.2.4 真流式 SSE

**当前问题**: 先收集完整结果，再分块推送。

**方案**: 
- LLM 调用改为真正的 streaming（MiMo API 支持 stream=true）
- 前端逐 token 渲染
- 检索阶段先完成，生成阶段实时流式

```python
# api/chat.py 改造
async def chat_stream(request: ChatRequest):
    # 阶段1: 检索（非流式，但有进度推送）
    yield sse_event("status", {"stage": "retrieving"})
    chunks = await retrieval.refine(query, timeout=5.0)
    
    # 阶段2: 生成（真流式）
    yield sse_event("status", {"stage": "generating"})
    async for token in llm.stream_generate(prompt, chunks):
        yield sse_event("token", {"text": token})
    
    yield sse_event("done", {})
```

#### 2.2.5 ChromaDB Client-Server 模式

**当前问题**: 嵌入式 ChromaDB 与 FastAPI 进程绑定，无法独立扩展。

**方案**: 
- 短期：保持嵌入式，但添加连接池和重试
- 中期：ChromaDB Server 模式（Docker 部署），FastAPI 通过 HTTP Client 连接

```yaml
# docker-compose.yml 新增
chromadb:
  image: chromadb/chroma:latest
  ports:
    - "8000:8000"
  volumes:
    - ./data/chromadb:/chroma/chroma
```

---

### 2.3 长期（3-6 月）—— 平台化

> **目标**: 从单一 RAG 系统演进为知识平台。

#### 2.3.1 微服务拆分

当系统负载和团队规模增长后，考虑按四象系统拆分微服务：

```
┌─────────────────┐
│  API Gateway     │  ← 统一入口，认证，限流
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
 少阳服务    太阳服务    少阴服务    太阴服务
 (消化)     (检索)     (炼化)     (显化)
    │         │          │          │
    └────┬────┴──────────┴──────────┘
         ▼
    PostgreSQL + ChromaDB + Redis
```

**前提条件**:
- 日均请求量 > 10 万
- 团队 ≥ 3 人
- 需要独立扩缩容

#### 2.3.2 消息队列引入

**场景**: 文档入库（异步处理）、事件通知、跨服务通信。

**选型**: 
- 轻量级：Redis Streams（已有 Redis 则复用）
- 标准级：RabbitMQ（适合企业内网部署）
- 不推荐 Kafka（对当前规模过重）

#### 2.3.3 OAuth2 / OIDC

**场景**: 企业级用户管理，对接 AD/LDAP。

**方案**: 引入 Keycloak 或 Casdoor 作为身份提供者，伏羲系统作为 OAuth2 Client。

#### 2.3.4 Prompt Injection ML 防御

**当前问题**: 基于规则的检测覆盖不全。

**方案**: 
- 短期：扩充规则库（正则 + 关键词黑名单）
- 长期：引入专用 ML 模型（如 OpenAI Moderation API 或自训练分类器）

---

## 三、技术选型建议

### 3.1 数据库

| 组件 | 当前 | 推荐 | 理由 |
|------|------|------|------|
| 主数据库 | SQLite (7+ 文件) | **PostgreSQL 15+** | 并发写、JSONB、全文检索、成熟生态 |
| 向量库 | ChromaDB 嵌入式 | **ChromaDB Server** 或 **pgvector** | ChromaDB Server 独立扩展；pgvector 如需统一 |
| 缓存 | 内存 dict | **Redis 7+** | 跨进程共享、过期策略、Pub/Sub |
| 知识图谱 | JSON 文件 | **PostgreSQL JSONB** 或 **Neo4j** | JSONB 适合中等规模；Neo4j 适合复杂图查询 |

### 3.2 消息队列

| 场景 | 推荐 | 理由 |
|------|------|------|
| 文档异步入库 | Redis Streams | 轻量，已有 Redis 则零成本 |
| 服务间事件 | RabbitMQ | 企业内网友好，管理界面成熟 |
| 实时通知 | WebSocket + Redis Pub/Sub | 已有 WebSocket 基础 |

### 3.3 缓存

| 层级 | 当前 | 推荐 |
|------|------|------|
| L1 进程内 | dict | 保留，用于热点 QA 对 |
| L2 分布式 | 暴力搜索 | **Redis + 语义哈希索引** |
| L3 语义缓存 | ChromaDB | 保留，阈值放宽至 0.85 |

### 3.4 认证

| 方案 | 适用场景 | 推荐 |
|------|----------|------|
| JWT (当前) | 单服务、内网 | 短期保留，修复密钥管理 |
| JWT + Refresh Token | 中等规模 | 中期升级 |
| OAuth2 / OIDC | 企业级、多服务 | 长期引入 |

### 3.5 日志与监控

| 组件 | 当前 | 推荐 |
|------|------|------|
| 日志 | 纯文本文件 | **structlog + JSON** + trace_id |
| 指标 | Prometheus (已接入) | 保留 |
| 链路追踪 | 无 | **OpenTelemetry** 或自建 trace_id |
| 日志聚合 | 文件轮转 | **Loki** 或 **ELK**（长期） |

---

## 四、迁移路径

### 4.1 Phase 0: 准备（第 1 周）

- [ ] 创建 `develop` 分支，所有改动在此分支进行
- [ ] 建立基准性能测试（P50/P95 延迟、缓存命中率、错误率）
- [ ] 补充关键路径的集成测试（chat、search、ingest）
- [ ] 备份所有 SQLite 文件

### 4.2 Phase 1: 止血（第 1-2 周）

```
Week 1:
  ├── JWT 密钥持久化 (P0-1)
  ├── IntentBus async 化 (P0-2)
  ├── 检索管线超时 (P0-3)
  └── time.sleep 替换 (P1-2)

Week 2:
  ├── 语义缓存阈值 (P1-1)
  ├── v1/v2 路由统一 (P1-3)
  ├── 结构化日志 (P1-4)
  └── 路由注册统一 (P2-1)
```

**验收标准**: 
- JWT 密钥重启后不变
- 并发 10 请求无事件循环阻塞
- 检索管线 P95 < 8 秒
- 所有日志包含 trace_id

### 4.3 Phase 2: 存储迁移（第 3-6 周）

```
Week 3-4: PostgreSQL 部署 + schema 设计 + 兼容层
Week 5:   chunks + sessions 迁移
Week 6:   audit + login_rate + worldtree 迁移
```

**迁移策略**: 
1. 双写阶段（新数据同时写 SQLite + PG）
2. 读切阶段（读从 PG，写仍双写）
3. 切换阶段（完全切到 PG，SQLite 只读备份）
4. 清理阶段（确认稳定后删除 SQLite）

### 4.4 Phase 3: 检索优化（第 7-10 周）

```
Week 7-8: 检索管线简化 + Feature Flag 控制
Week 9:   真流式 SSE 实现
Week 10:  性能基准对比 + 调优
```

### 4.5 Phase 4: 八卦精简（第 11-14 周）

```
Week 11-12: 卦合并（坤→太阴，震→少阳，坎→太阳，艮→少阴，兑→太阴）
Week 13:    IntentBus 简化为 async Router
Week 14:    集成测试 + 回归测试
```

### 4.6 Phase 5: 平台化（第 15-24 周）

```
Week 15-18: Redis 引入 + 语义缓存优化
Week 19-20: ChromaDB Server 迁移
Week 21-22: OAuth2 集成
Week 23-24: OpenTelemetry 链路追踪
```

---

## 五、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| PG 迁移数据丢失 | 低 | 高 | 双写阶段 + SQLite 只读备份 + 回滚脚本 |
| 八卦精简引入回归 | 中 | 中 | 精简前补充集成测试，逐卦合并验证 |
| 流式 SSE 前端兼容 | 中 | 低 | 前端同时支持流式和非流式模式 |
| ChromaDB Server 性能 | 低 | 中 | 嵌入式模式作为 fallback |
| 团队不熟悉 PG | 中 | 中 | 选择标准 SQL 操作，避免高级特性 |

---

## 六、架构目标全景

```
                        ┌─────────────────┐
                        │   API Gateway    │
                        │  (认证/限流/路由) │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        ┌──────────┐     ┌──────────┐      ┌──────────┐
        │ 少阳·消化 │     │ 太阳·检索 │      │ 少阴·炼化 │
        │ (文档处理) │     │ (混合检索) │      │ (LLM合成) │
        └─────┬────┘     └─────┬────┘      └─────┬────┘
              │                │                  │
              └────────────────┼──────────────────┘
                               ▼
                        ┌──────────────┐
                        │  太阴·显化    │
                        │  (API/监控)   │
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │PostgreSQL│    │ ChromaDB │    │  Redis   │
        │ (主存储)  │    │ (向量库)  │    │ (缓存)   │
        └──────────┘    └──────────┘    └──────────┘
```

**核心原则**:
1. **四象分层是架构灵魂**，必须保留
2. **八卦调度是实现细节**，可以简化
3. **存储统一是基础设施**，必须迁移
4. **流式交互是用户体验**，必须实现
5. **可观测性是运维生命线**，必须补齐

---

## 七、总结

伏羲系统当前架构的核心价值在于**四象分层**和**多级检索管线**，这是值得长期保留的。主要问题集中在**存储碎片化**、**同步阻塞**和**过度设计的八卦调度**。

**优先级排序**:
1. 🔴 **立即修**: JWT 密钥、IntentBus async、检索超时（阻断性）
2. 🟡 **尽快做**: 结构化日志、SSE 流式、缓存阈值（影响体验）
3. 🟢 **规划做**: PG 迁移、八卦精简、平台化（架构优化）

**一个关键判断**: 如果系统预期日均请求 < 1 万、团队 < 2 人，当前架构加上短期止血修复即可满足需求。只有当规模增长到日均 10 万+ 或团队扩展时，中长期方案才值得投入。

---

*报告结束。以上方案基于对伏羲系统源码、架构文档、已有审计报告的综合分析。*
