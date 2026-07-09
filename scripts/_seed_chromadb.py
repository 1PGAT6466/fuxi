#!/usr/bin/env python3
"""Quick seed ChromaDB with 50+ vectors using random embeddings"""
import sys, os, hashlib, sqlite3, time, logging
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PROJECT_ROOT = Path(__file__).resolve().parent.parent

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

os.environ.setdefault("KB_CHROMA_DIR", "data/chromadb")
os.environ.setdefault("FUXI_DATA_DIR", str(PROJECT_ROOT / "data"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("chroma_seed")

SEED_DOCS = [
    ("伏羲系统概述", "伏羲是一个企业知识认知中枢，采用中医五行脏腑隐喻的生命体架构，将知识处理流程映射为人体的消化、循环、决策和表达过程。"),
    ("快速开始指南", "本指南帮助新用户在5分钟内完成伏羲系统的环境搭建和基本使用，包括Python环境配置、依赖安装和服务启动。"),
    ("四象架构详解", "伏羲采用四象架构：少阳·消化系统负责文档解析清洗，太阳·筑基系统负责检索排序，少阴·炼化系统负责决策合成，太阴·显化系统负责对外接口。"),
    ("ChromaDB集成", "ChromaDB是伏羲的向量存储引擎，支持高效的相似度搜索。本系统使用bge-small-zh-v1.5作为嵌入模型，向量维度为384。"),
    ("RAG管线设计", "检索增强生成(RAG)管线是伏羲的核心流程，包括文档分块、向量化入库、多路召回、融合排序和LLM生成五个阶段。"),
    ("API接口文档", "伏羲提供RESTful API接口，包括文档上传、知识检索、AI对话、系统监控等端点。所有接口均支持JWT认证和审计日志。"),
    ("部署运维指南", "本指南详细介绍伏羲在Ubuntu 22.04上的生产部署流程，包括Docker镜像构建、Nginx反向代理配置、SSL证书安装和性能调优。"),
    ("数据安全策略", "伏羲实施多层安全防护：传输层TLS加密、应用层JWT认证、数据库层访问控制、审计日志完整记录所有操作。"),
    ("性能优化手册", "涵盖PostgreSQL查询优化、ChromaDB索引调优、Rerank模型选择、缓存策略配置和并发处理最佳实践。"),
    ("MCP协议规范", "Model Context Protocol是伏羲与外部系统交互的标准协议，支持工具调用、资源访问和提示模板三大核心能力。"),
    ("监控告警系统", "伏羲集成Prometheus指标采集和Grafana可视化面板，覆盖请求延迟、错误率、内存使用、向量库状态等关键指标。"),
    ("知识图谱构建", "基于文档内容自动抽取实体和关系，构建企业知识图谱，支持图遍历检索和关联知识发现。"),
    ("多模态文档处理", "支持PDF、Word、Markdown、图片等多种格式的文档解析，通过OCR和布局分析提取结构化信息。"),
    ("LLM推理集成", "支持多种LLM后端：MiMo 2.5 Pro、Ollama本地部署、SiliconFlow API，具备自动降级和负载均衡能力。"),
    ("向量检索优化", "采用HNSW索引算法，支持IVF+PQ压缩，查询延迟控制在50ms以内，召回率保持在95%以上。"),
    ("语义分块策略", "基于语义边界检测的智能分块算法，保持文档的语义连贯性，支持自定义分块大小和重叠窗口参数。"),
    ("多路召回融合", "BM25关键词检索与向量语义检索的双路召回，通过RRF倒数排序融合算法，结合动态权重调整。"),
    ("Rerank精排模型", "四级降级精排策略：bge-reranker-v2-m3 → SiliconFlow API → LLM评分 → 原始分数回退。"),
    ("上下文压缩技术", "基于LLM的上下文压缩算法，将检索到的文档片段压缩为精炼摘要，在保证信息完整性的前提下减少Token消耗。"),
    ("事实性校验机制", "基于LLM-as-Judge的事实性校验管线，检测生成回答与源文档的一致性，标记潜在的幻觉内容。"),
    ("审计日志系统", "记录所有API请求的详细信息：时间戳、用户身份、操作类型、请求参数、响应状态和执行耗时。"),
    ("Feature Flag管理", "基于配置文件的功能开关系统，支持灰度发布、AB测试和紧急功能回滚，无需重启服务即可切换。"),
    ("中医脏腑隐喻", "伏羲借中医脏腑概念建立系统隐喻：心主血脉（数据流）、肝主疏泄（调度）、脾主运化（处理）、肺主宣发（输出）、肾主藏精（存储）。"),
    ("八卦象数体系", "乾天行健、坤厚德载物、震雷动风生、巽风行草偃、坎水润万物、离火炎上、艮山止静、兑泽悦说，八卦对应系统的八种运行状态。"),
    ("经络信号总线", "经络系统是伏羲的异步通信网络，支持心跳检测、告警通知、数据传输和命令下发四种信号类型。"),
    ("评估测试框架", "内置自动化评估测试：回归测试确保修改不破坏已有功能，冒烟测试验证核心流程，性能测试监控系统负载。"),
    ("知识生命周期管理", "从文档创建、版本更新、使用分析到自动归档的完整知识生命周期，支持手动和自动两种管理模式。"),
    ("跨平台客户端", "提供Web前端、桌面应用和移动端SDK，统一的API接口保证跨平台体验一致。"),
    ("搜索引擎优化", "支持全文检索、模糊匹配、拼音搜索和同义词扩展，基于jieba分词和BM25算法的中文优化。"),
    ("数据分析仪表盘", "实时展示知识库使用统计：热门文档、高频查询、用户活跃度、系统吞吐量和错误趋势。"),
    ("插件扩展机制", "基于钩子(Hook)的插件架构，支持自定义文档解析器、检索策略、后处理逻辑和通知渠道。"),
    ("用户权限管理", "多层级RBAC权限模型：系统管理员、知识管理员、编辑者和只读用户，支持部门级别隔离。"),
    ("备份恢复方案", "自动化备份策略：每日增量备份+每周全量备份，支持时间点恢复(PITR)和跨区域容灾。"),
    ("容器化部署", "基于Docker Compose的一键部署方案，支持开发、测试和生产环境隔离，内置健康检查和自动重启。"),
    ("国际化支持", "支持中英文双语界面和文档，基于Unicode的全文索引，Locale-aware的日期和数字格式化。"),
    ("缓存策略设计", "多级缓存架构：L1应用内存缓存、L2 Redis分布式缓存、L3语义缓存，命中率目标90%以上。"),
    ("搜索意图识别", "基于LLM的查询意图分类器，自动识别事实查询、概念解释、操作指南和系统命令四大类意图。"),
    ("文档版本控制", "基于内容哈希的文档去重和版本追踪，支持差异对比和任意版本回滚。"),
    ("在线评估系统", "基于用户反馈的在线评估，收集点赞/点踩、修改建议和质量评分，持续优化检索和生成质量。"),
    ("知识进化引擎", "自动发现知识库中的矛盾、过时和缺失信息，生成改进建议并触发知识更新流程。"),
    ("零停机迁移方案", "在线数据迁移策略：影子表写入→数据同步→原子切换，确保迁移过程中服务不中断。"),
    ("负载均衡架构", "基于Nginx的七层负载均衡，支持轮询、最少连接和IP哈希三种策略，自动剔除故障节点。"),
    ("数据库选型指南", "对比分析PostgreSQL+pgvector、ChromaDB、Milvus和Weaviate在性能、运维成本和生态方面的优劣。"),
    ("错误处理规范", "统一错误码体系：1xxx客户端错误、2xxx服务端错误、3xxx第三方服务错误，含中英文错误描述。"),
    ("提示词工程指南", "LLM提示词设计最佳实践：角色设定、Few-shot示例、CoT链式推理和结构化输出格式模板。"),
    ("AI幻觉防控", "多维度幻觉防控策略：源文档锚定、事实性交叉验证、置信度阈值过滤和不确定性标注。"),
    ("合规与隐私保护", "GDPR和网络安全法合规设计：数据脱敏、访问控制、操作审计、数据删除权和可携带权支持。"),
    ("灰度发布流程", "基于Feature Flag的渐进式发布：10%→30%→50%→100%，每个阶段监控错误率、延迟和用户反馈。"),
    ("系统组件拓扑", "物理部署拓扑：PGAT-CDB004(EasyClaw会话)、PGAT-CDT004(文件接收+清洗+OCR)、PGAT-storage(FastAPI主服务+Ollama+ChromaDB)。"),
    ("性能基准测试", "标准测试结果：文档摄入10MB/s、检索延迟<50ms、对话响应<2s、并发支持100QPS、可用性99.9%。"),
]

DIM = 384
ids = []
vectors = []
metadatas = []
documents = []

np.random.seed(42)
for i, (title, abstract) in enumerate(SEED_DOCS):
    chunk_id = f"seed_{i+1:03d}"
    hash_bytes = hashlib.sha256(abstract.encode("utf-8")).digest()
    seed_val = int.from_bytes(hash_bytes[:4], "big") % (2**32)
    rng = np.random.RandomState(seed_val)
    vec = rng.randn(DIM).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    ids.append(chunk_id)
    vectors.append(vec.tolist())
    documents.append(abstract)
    metadatas.append({
        "doc_id": f"seed_doc_{i+1}",
        "chunk_index": "0",
        "file_name": f"{title}.md",
        "category": "种子文档",
        "source_file": f"seed/{title}.md",
        "text_preview": abstract[:100],
        "origin": "seed",
        "title": title,
    })

logger.info(f"Prepared {len(ids)} seed vectors (dim={DIM})")

from src.db.vector_store import VectorStore

vs = VectorStore(db_dir=str(PROJECT_ROOT / "data"))
old = vs.count
logger.info(f"ChromaDB BEFORE: {old} vectors")

BATCH = 20
seeded = 0
for start in range(0, len(ids), BATCH):
    end = min(start + BATCH, len(ids))
    ok = vs.add(
        ids=ids[start:end],
        embeddings=vectors[start:end],
        metadata=metadatas[start:end],
        documents=documents[start:end],
    )
    if ok:
        seeded += end - start
        logger.info(f"  Batch {start//BATCH+1}: {end-start} OK")

time.sleep(1)
new_count = vs.count
logger.info(f"ChromaDB AFTER: {new_count}  (added: {new_count - old})")

# Verify via SQLite
chroma_path = PROJECT_ROOT / "data" / "chromadb" / "chroma.sqlite3"
if chroma_path.exists():
    c = sqlite3.connect(str(chroma_path))
    emb = c.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    c.close()
    logger.info(f"SQLite embeddings table: {emb} rows")
