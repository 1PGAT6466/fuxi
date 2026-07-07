# 伏羲 v1.50 设计文档

## 1. 系统概述

伏羲是一个企业知识认知系统，采用中医五行脏腑隐喻的"生命体"架构。系统将知识处理流程映射为人体的消化、循环、决策和表达过程，通过经络系统实现模块间的信号传递。

### 1.1 设计理念

- **生命体隐喻**: 将企业知识系统比作一个有机生命体
- **四象架构**: 少阳(消化)、太阳(筑基)、少阴(炼化)、太阴(显化)
- **经络通信**: 模块间通过信号总线进行异步通信
- **五行平衡**: 通过器官系统实现自我监控和自愈

### 1.2 核心目标

1. **知识消化**: 自动解析、清洗、分块和提取知识
2. **精准检索**: 多路召回、融合、精排，找到最相关内容
3. **智能决策**: LLM驱动的答案生成和质量控制
4. **稳定服务**: 高可用、可监控、可审计的对外接口

## 2. 架构设计

### 2.1 四象模块

```
┌─────────────────────────────────────────────────────────────┐
│                      太阴·taiyin                            │
│                    (对外接口中枢)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   server    │ │   audit     │ │   metrics   │           │
│  │   API路由   │ │   审计日志  │ │   指标暴露  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 请求
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      少阴·shaoyin                           │
│                    (决策合成中枢)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   brain     │ │   judge_v2  │ │  fact_check │           │
│  │   决策引擎  │ │   质量评分  │ │  事实校验   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 检索结果
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      太阳·taiyang                           │
│                    (精炼排序中枢)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  retrieval  │ │   fusion    │ │   rerank    │           │
│  │  混合检索   │ │   RRF融合   │ │   精排      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 原始文档
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      少阳·shaoyang                          │
│                    (知识消化中枢)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  pipeline   │ │  extractor  │ │   chunker   │           │
│  │  处理管线   │ │  知识提取   │ │   分块      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 经络系统

经络系统是模块间的信号总线，负责异步通信和状态同步。

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

### 2.3 器官系统

五行器官实现系统的自我监控和自愈能力：

| 器官 | 功能 | 职责 |
|------|------|------|
| 心 | 核心监控 | 服务健康检查、自愈 |
| 肝 | 免疫解毒 | 免疫记忆、异常检测 |
| 脾 | 存储泵血 | 数据存储、营养供给 |
| 肺 | 自主呼吸 | 文件监控、变化检测 |
| 肾 | 精炼排泄 | 数据精炼、废物清理 |

## 3. 检索管线设计

### 3.1 多级检索架构

```
Query
  │
  ▼
L-1: QA对匹配 ──────────────────────────────────────┐
  │ (命中率: ~5%, 延迟: <10ms)                       │
  ▼                                                  │
L0: 语义缓存 + 图谱路由 ────────────────────────────┤
  │ (缓存命中: ~15%, 延迟: <50ms)                    │
  ▼                                                  │
L1: 同义词扩展 + LLM改写 ───────────────────────────┤
  │ (扩展率: ~30%)                                   │
  ▼                                                  │
L1.5: HyDE假设文档 ─────────────────────────────────┤
  │ (生成延迟: ~500ms)                               │
  ▼                                                  │
L2: BM25 + 向量双路召回 ────────────────────────────┤
  │ (召回率: ~85%)                                   │
  ▼                                                  │
L3: RRF融合 + 动态alpha ────────────────────────────┤
  │ (融合精度: ~90%)                                 │
  ▼                                                  │
L4: 三阶段精排 ─────────────────────────────────────┤
  │ (匹配→分类→MMR去重)                              │
  ▼                                                  │
L5: Rerank四级降级 ─────────────────────────────────┤
  │ (SiliconFlow→本地→BM25→原始)                     │
  ▼                                                  │
L6: Parent-Child + Sentence Window ──────────────────┘
  │
  ▼
Top-K Results
```

### 3.2 动态融合权重

系统根据查询特征动态调整BM25和向量检索的权重：

```python
def calculate_alpha(query: str, context: dict) -> float:
    """
    alpha ∈ [0.3, 0.7]
    - 技术术语多 → 偏向BM25 (alpha↓)
    - 语义模糊 → 偏向向量 (alpha↑)
    - 有图谱匹配 → 偏向BM25 (alpha↓)
    """
    base_alpha = 0.5
    # 术语密度调整
    term_density = count_technical_terms(query) / len(query)
    if term_density > 0.3:
        base_alpha -= 0.15
    # 语义模糊度调整
    if is_semantic_ambiguous(query):
        base_alpha += 0.1
    return clamp(base_alpha, 0.3, 0.7)
```

## 4. v1.50 新增特性

### 4.1 MiMo 2.5 Pro 集成

升级LLM调用链，支持小米MiMo 2.5 Pro模型：

```python
# 配置
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.mimo.ai/v1")
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
MIMO_TIMEOUT = int(os.getenv("MIMO_TIMEOUT", "60"))

# 调用链
MiMo 2.5 Pro → Ollama qwen2.5:1.5b → 规则兜底
```

### 4.2 JWT认证升级

从自定义SHA256实现升级为标准PyJWT：

```python
# 旧实现 (v1.44)
def create_token(user_id: str) -> str:
    payload = {"user_id": user_id, "exp": expire}
    signature = hmac.new(SECRET, payload, sha256)
    return base64(payload) + "." + signature

# 新实现 (v1.50)
import jwt

def create_token(user_id: str) -> str:
    payload = {"user_id": user_id, "exp": expire}
    return jwt.encode(payload, SECRET, algorithm="HS256")
```

### 4.3 审计日志

新增审计日志模块，记录所有关键操作：

```python
class AuditLogger:
    def log(self, action: str, user: str, resource: str, detail: dict):
        """记录审计事件"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user": user,
            "resource": resource,
            "detail": detail
        }
        self._write(event)
```

### 4.4 Prometheus指标

新增Prometheus指标暴露，支持系统监控：

```python
# 暴露端点
GET /metrics

# 指标类型
- fuxi_requests_total (Counter)
- fuxi_request_duration_seconds (Histogram)
- fuxi_search_results_count (Histogram)
- fuxi_llm_calls_total (Counter)
- fuxi_cache_hits_total (Counter)
```

### 4.5 安全模块

新增安全模块，支持敏感信息脱敏和输入验证：

```python
SENSITIVE_PATTERNS = [
    re.compile(r"(password|passwd|pwd)\s*[:=]\s*\S+", re.I),
    re.compile(r"(secret|token|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"\b\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dxX]\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
]
```

## 5. 数据模型

### 5.1 核心实体

```python
@dataclass
class Chunk:
    hash: str              # 内容哈希
    file_name: str         # 文件名
    content: str           # 文本内容
    category: str          # 文档分类
    embedding: List[float] # 向量嵌入
    metadata: dict         # 元数据
    created_at: datetime   # 创建时间
    access_count: int      # 访问次数

@dataclass
class Entity:
    name: str              # 实体名称
    entity_type: str       # 实体类型
    properties: dict       # 属性
    relations: List[str]   # 关系

@dataclass
class Signal:
    signal_type: SignalType
    source: str            # 来源器官
    target: str            # 目标器官
    payload: dict          # 数据
    priority: Priority     # 优先级
    timestamp: float       # 时间戳
```

### 5.2 存储结构

| 存储 | 引擎 | 用途 |
|------|------|------|
| chunks.db | SQLite FTS5 | BM25全文检索 |
| ChromaDB | SQLite + HNSW | 语义向量检索 |
| knowledge_graph.json | JSON | 知识图谱 |
| feedback_log.jsonl | JSONL | 反馈日志 |

## 6. API设计

### 6.1 RESTful原则

- 资源导向: `/api/documents`, `/api/search`, `/api/chat`
- HTTP方法: GET(查询), POST(创建), PUT(更新), DELETE(删除)
- 状态码: 200(成功), 400(客户端错误), 500(服务器错误)

### 6.2 认证机制

```
Authorization: Bearer <jwt_token>

# Token结构
{
  "user_id": "admin",
  "role": "admin",
  "exp": 1735689600
}
```

### 6.3 响应格式

```json
{
  "success": true,
  "data": {...},
  "meta": {
    "page": 1,
    "limit": 50,
    "total": 100
  }
}
```

## 7. 测试策略

### 7.1 测试层次

1. **单元测试**: 测试单个函数/类
2. **集成测试**: 测试模块间交互
3. **端到端测试**: 测试完整流程

### 7.2 测试覆盖

- 核心模块: 100%覆盖
- API路由: 90%覆盖
- 边界条件: 重点测试

### 7.3 测试运行

```bash
# 运行所有测试
python -m pytest tests/ -v

# 预期结果
202 passed, 9 skipped
```

## 8. 部署架构

### 8.1 生产环境

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   装载机         │     │   主服务         │     │   会话服务       │
│  172.25.30.16   │────▶│  172.25.30.200  │◀────│  172.25.30.10   │
│   :8090         │     │   :8080         │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 8.2 服务组件

| 服务 | 端口 | 功能 |
|------|------|------|
| kb-server | 8080 | FastAPI主服务 |
| local_receiver | 8090 | 文件上传接收 |
| embedder_server | 8081 | 文本向量化 |
| Ollama | 11434 | 本地LLM推理 |

## 9. 监控与运维

### 9.1 监控指标

- 系统指标: CPU、内存、磁盘
- 应用指标: 请求量、延迟、错误率
- 业务指标: 检索精度、用户满意度

### 9.2 日志管理

- 位置: `data/logs/`
- 格式: `伏羲·内世界.log`
- 轮转: 10MB, 5个备份

### 9.3 告警规则

- 错误率 > 5%: 紧急告警
- P95延迟 > 10s: 警告
- 磁盘使用 > 80%: 警告

## 10. 未来规划

### 10.1 短期 (v1.51)

- 多模态支持 (图片、表格)
- 实时协作编辑
- 移动端适配

### 10.2 中期 (v1.60)

- 分布式部署
- 多租户支持
- 知识图谱可视化

### 10.3 长期 (v2.0)

- 自主学习能力
- 跨组织知识共享
- AI驱动的知识演化
