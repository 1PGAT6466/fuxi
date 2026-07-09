#!/usr/bin/env python3
"""Seed worldtree.db with 10 Wiki pages"""
import sqlite3, json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

PAGES = [
    ("wiki_seed_001", "伏羲系统介绍", "入门指南",
     ["伏羲", "企业知识", "认知系统", "RAG"],
     "伏羲是一个基于中医脏腑隐喻的企业知识认知体系，集成文档管理、智能检索和AI对话能力。",
     "# 伏羲系统介绍\n\n伏羲（Fuxi）是一个企业级知识认知体系。采用中医脏腑隐喻构建\"生命体\"架构，将知识处理流程映射为人体的消化、循环、决策和表达过程。\n\n核心能力：知识消化（少阳）、精准检索（太阳）、智能决策（少阴）、稳定服务（太阴）。",
     ["README.md"], 1, 0.95),

    ("wiki_seed_002", "快速开始指南", "入门指南",
     ["快速开始", "安装", "配置"],
     "5分钟完成伏羲系统的环境搭建和基本使用。",
     "# 快速开始指南\n\n环境要求：Python 3.10+，8GB+内存。\n\n步骤：1) pip install -r requirements.txt  2) cp .env.example .env  3) python main.py  4) 访问 http://localhost:8080/docs",
     ["README.md"], 1, 0.9),

    ("wiki_seed_003", "API接口文档", "API文档",
     ["API", "接口", "REST"],
     "伏羲RESTful API的完整参考文档，包含所有端点、参数说明和示例代码。",
     "# API接口文档\n\n## 认证：JWT Token (Authorization: Bearer <token>)\n\n## 端点：GET /api/health、POST /api/upload、POST /api/search、POST /api/chat、GET /api/wiki/{id}、DELETE /api/documents/{id}、GET /api/metrics、GET /api/audit/logs",
     ["docs/API.md"], 1, 0.85),

    ("wiki_seed_004", "部署运维指南", "运维文档",
     ["部署", "运维", "Docker", "Nginx"],
     "伏羲在Ubuntu 22.04上的生产部署流程。",
     "# 部署运维指南\n\n生产环境：Ubuntu 22.04 LTS, 16GB RAM, 4核CPU, 100GB SSD。\n\nDocker部署：docker-compose up -d\n\n手动部署：安装依赖→配置虚拟环境→systemd服务→Nginx反向代理→SSL证书\n\n性能调优：PostgreSQL shared_buffers=2GB, PgBouncer pool_size=20, Uvicorn workers=CPU*2",
     ["docs/DEPLOYMENT.md"], 1, 0.9),

    ("wiki_seed_005", "常见问题FAQ", "帮助文档",
     ["FAQ", "常见问题", "故障排查"],
     "用户经常遇到的问题和解决方案。",
     "# 常见问题FAQ\n\nQ: 服务无法启动？检查端口8080占用，确认.env配置，查看日志。\nQ: 文档上传失败？确认格式(PDF/Word/MD)，检查文件大小<100MB，验证JWT。\nQ: 检索结果为空？确认ChromaDB运行、文档已入库、更换关键词。\nQ: LLM响应超时？检查Ollama状态、API配额、网络连接。",
     ["docs/FAQ.md"], 1, 0.8),

    ("wiki_seed_006", "四象架构设计", "架构文档",
     ["架构", "四象", "设计"],
     "伏羲四象架构的详细设计文档。",
     "# 四象架构设计\n\n少阳·消化：文档全生命周期管理（Pipeline/SemanticChunker/Extractor）\n太阳·筑基：检索排序（BM25+向量双路→RRF融合→Dynamic Alpha调整→Top-K）\n少阴·炼化：LLM生成（LLM-as-Judge评分、事实性验证、上下文压缩）\n太阴·显化：对外服务（API接口、监控、审计、安全）",
     ["ARCHITECTURE.md"], 1, 0.95),

    ("wiki_seed_007", "安全策略文档", "安全文档",
     ["安全", "JWT", "审计", "合规"],
     "伏羲系统的安全设计策略，涵盖认证、授权、加密和审计。",
     "# 安全策略\n\n认证：JWT(HS256)，Token有效期24h，支持刷新。\n授权：RBAC（管理员/编辑者/只读用户）。\n数据安全：TLS 1.2+、敏感配置加密。\n输入验证：SQL注入防护、XSS过滤、文件类型白名单、速率限制。",
     ["docs/SECURITY.md"], 1, 0.88),

    ("wiki_seed_008", "监控告警配置", "运维文档",
     ["监控", "Prometheus", "Grafana"],
     "监控告警系统的配置指南。",
     "# 监控告警配置\n\nPrometheus指标：request_duration_seconds、request_total、active_connections、chroma_vectors_total。\n告警规则：错误率>5%(P1)、P99延迟>2s(P2)、内存>90%(P1)。\nGrafana面板：系统概览、知识库状态、LLM调用统计。",
     ["docs/MONITORING.md"], 1, 0.85),

    ("wiki_seed_009", "数据备份恢复", "运维文档",
     ["备份", "恢复", "灾备"],
     "自动化备份恢复方案的操作手册。",
     "# 数据备份恢复\n\n策略：每日增量(凌晨2点)+每周全量(周日3点)。\n内容：ChromaDB、SQLite(chunks/worldtree/memory)、配置文件、上传文档。\n恢复流程：停止服务→恢复备份→启动服务→健康检查。\nRPO<1小时，RTO<4小时。",
     ["docs/BACKUP.md"], 1, 0.82),

    ("wiki_seed_010", "开发贡献指南", "开发文档",
     ["开发", "贡献", "规范", "测试"],
     "开发者贡献代码的规范和流程。",
     "# 开发贡献指南\n\n代码规范：PEP 8、类型注解、Google风格docstring。\nGit提交：feat/fix/docs/refactor/test。\n测试要求：新功能单测、核心逻辑回归测试、PR冒烟测试全绿。\nCode Review：至少一人审批，关注安全/性能/可维护性。",
     ["CONTRIBUTING.md"], 1, 0.8),
]

conn = sqlite3.connect(str(PROJECT_ROOT / "data" / "worldtree.db"))
old = conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
print(f"worldtree.db BEFORE: {old}")

for pid, title, cat, tags, summary, content, sources, ver, score in PAGES:
    conn.execute(
        "INSERT OR IGNORE INTO wiki_pages (id, title, category, tags, summary, content, sources, version, quality_score, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, title, cat, json.dumps(tags, ensure_ascii=False), summary, content, json.dumps(sources), ver, score, NOW, NOW)
    )

conn.commit()
new_count = conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
conn.close()
print(f"worldtree.db AFTER: {new_count}  (added: {new_count - old})")
