#!/usr/bin/env python3
"""Seed chunks.db with 20 real chunks"""
import sqlite3, hashlib
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

CHUNKS = [
    ("# 伏羲 Fuxi — 企业知识认知体系\n\n伏羲以中医脏腑隐喻构建的企业知识认知体系，经络为信号总线，四象为功能系统。", "README.md", "系统文档"),
    ("## 技术栈\n\n- Web框架：FastAPI + Uvicorn\n- LLM推理：MiMo 2.5 Pro / Ollama qwen2.5:1.5b\n- 嵌入模型：BAAI/bge-small-zh-v1.5\n- 向量数据库：ChromaDB", "README.md", "技术文档"),
    ("## 快速开始\n\n1. pip install -r requirements.txt\n2. cp .env.example .env\n3. python main.py\n4. 访问 http://localhost:8080/docs", "README.md", "入门指南"),
    ("## API端点\n\n- GET /api/health — 健康检查\n- POST /api/upload — 文档上传\n- POST /api/search — 知识检索\n- POST /api/chat — AI对话", "docs/API.md", "API文档"),
    ("## 少阳·消化系统\n\n负责文档的解析、清洗、分块和知识提取。pipeline.py统一处理管线，extractor.py SAG式提取，semantic_chunker.py语义分块。", "ARCHITECTURE.md", "架构文档"),
    ("## 太阳·筑基系统\n\n负责检索和排序。retrieval.py混合检索，multi_hop.py多跳检索，fusion.py RRF融合，dynamic_alpha.py动态融合权重。", "ARCHITECTURE.md", "架构文档"),
    ("## 少阴·炼化系统\n\n负责答案生成和质量控制。brain.py决策合成引擎，judge_v2.py LLM评分，fact_check.py事实性校验。", "ARCHITECTURE.md", "架构文档"),
    ("## 太阴·显化系统\n\n负责体系对外服务。server.py接口，audit.py审计日志，metrics.py监控指标，security.py安全模块。", "ARCHITECTURE.md", "架构文档"),
    ("## 经络系统\n\n伏羲的经络系统是体系内唯一的通信网络，负责异步通信和状态同步。信号类型：HEARTBEAT、ALERT、DATA、COMMAND。", "ARCHITECTURE.md", "技术文档"),
    ("## 部署架构\n\nEasyClaw节点(PGAT-CDB004)、装载机(PGAT-CDT004:8090/8093)、服务器(PGAT-storage:8080/11434/8081)。", "docs/DEPLOYMENT.md", "部署文档"),
    ("## 数据流：文档入库\n\n用户上传→少阳消化系统(解析→清洗→分块→提取)→MemoryStore存储→ChromaDB向量化", "ARCHITECTURE.md", "技术文档"),
    ("## 安全设计\n\n多层防护：传输层TLS、应用层JWT、数据库访问控制、审计日志完整记录。v1.50新增SQL注入防护。", "docs/SECURITY.md", "安全文档"),
    ("## Feature Flag\n\n基于JSON配置的功能开关，支持灰度发布和AB测试，无需重启服务切换功能。", "docs/FEATURE_FLAGS.md", "技术文档"),
    ("## 迁移策略\n\n零停机方案：ALTER TABLE IF NOT EXISTS、CREATE INDEX CONCURRENTLY、影子表写入+原子切换。", "docs/MIGRATION.md", "技术文档"),
    ("## 连接池\n\nPgBouncer管理连接池，事务模式5432，会话模式6432。max_client_conn=100, default_pool_size=20。", "docs/DEPLOYMENT.md", "运维文档"),
    ("## 缓存架构\n\n多级缓存：L1 lru_cache、L2 Redis(TTL=5min)、L3语义缓存。目标命中率：L1>60%, L2>80%, L3>90%。", "docs/CACHE.md", "技术文档"),
    ("## 监控指标\n\nPrometheus采集：请求延迟p50/p95/p99、错误率、内存RSS/堆、向量库状态、LLM调用次数/耗时/token。", "docs/MONITORING.md", "运维文档"),
    ("## AB测试\n\n内置引擎：多变量分组、卡方+t检验、自动终止规则。数据保存在data/ab_tests/。", "docs/AB_TEST.md", "技术文档"),
    ("## 文档解析\n\nPDF(pdfplumber+PyPDF2)、Word(python-docx)、Markdown(markdown)、图片(PaddleOCR)、HTML(BeautifulSoup)。", "docs/PARSER.md", "技术文档"),
    ("## 版本历史\n\nv1.50: 术语统一+MiMo 2.5 Pro+JWT升级+审计/指标/安全\nv1.44: 四象归位+语义分块+动态融合\nv1.30: 多路召回+RRF融合+Rerank降级", "CHANGELOG.md", "版本记录"),
]

conn = sqlite3.connect(str(PROJECT_ROOT / "data" / "chunks.db"))
old = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
print(f"chunks.db BEFORE: {old}")

for i, (text, fname, cat) in enumerate(CHUNKS):
    h = hashlib.md5(text.encode()).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO chunks (doc, file_hash, file_name, category, chunk_index, status, created_at, uploaded_by) VALUES (?,?,?,?,?,?,?,?)",
        (text, h, fname, cat, i, 'active', NOW, 'quick_seed')
    )

conn.commit()
new_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
conn.close()
print(f"chunks.db AFTER: {new_count}  (added: {new_count - old})")
