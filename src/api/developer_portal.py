"""
伏羲 v1.50 — 开发者门户 API
============================
提供 API 文档、SDK 下载、OAuth 应用管理、开发者社区等功能。
"""

import json
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/developer", tags=["developer-portal"])

# 数据目录
DATA_DIR = Path(__file__).parent.parent.parent / "data"
OAUTH_APPS_FILE = DATA_DIR / "oauth_apps.json"

# ── 版本历史 ──
API_VERSIONS = {
    "v1.0": {"release_date": "2024-01-01", "status": "deprecated"},
    "v1.44": {"release_date": "2025-03-15", "status": "stable"},
    "v1.50": {"release_date": "2026-06-01", "status": "latest"},
}

# ── SDK 列表 ──
SDK_CATALOG = {
    "python": {
        "name": "fuxi-python-sdk",
        "language": "Python",
        "version": "1.5.0",
        "download_url": "https://github.com/1PGAT6466/fuxi/releases/download/sdk-v1.5.0/fuxi_python_sdk-1.5.0.tar.gz",
        "docs_url": "https://fuxi.dev/sdk/python",
        "min_python": "3.9+",
        "install_cmd": "pip install fuxi-sdk",
        "example_code": (
            "from fuxi import FuxiClient\n\n"
            'client = FuxiClient(api_key="your_api_key")\n\n'
            "# 查询知识库\n"
            'results = client.knowledge.search(query="伏羲系统架构", top_k=5)\n'
            "for doc in results:\n"
            '    print(f"[{doc.score:.2f}] {doc.title}: {doc.content[:100]}")\n\n'
            "# 上传文档\n"
            'client.knowledge.upload(file_path="document.pdf", collection="tech-docs")\n\n'
            "# 聊天对话\n"
            'response = client.chat.send(message="解释RAG的工作原理")\n'
            "print(response.answer)"
        ),
    },
    "javascript": {
        "name": "fuxi-js-sdk",
        "language": "JavaScript",
        "version": "1.3.2",
        "download_url": "https://github.com/1PGAT6466/fuxi/releases/download/sdk-v1.3.2/fuxi-js-sdk-1.3.2.tgz",
        "docs_url": "https://fuxi.dev/sdk/javascript",
        "min_node": "18+",
        "install_cmd": "npm install @fuxi/sdk",
        "example_code": (
            "import { FuxiClient } from '@fuxi/sdk';\n\n"
            "const client = new FuxiClient({ apiKey: 'your_api_key' });\n\n"
            "// 查询知识库\n"
            "const results = await client.knowledge.search({\n"
            "  query: '伏羲系统架构',\n"
            "  topK: 5\n"
            "});\n"
            "results.forEach(doc => {\n"
            "  console.log(`[${doc.score.toFixed(2)}] ${doc.title}`);\n"
            "});\n\n"
            "// 聊天对话\n"
            "const response = await client.chat.send({\n"
            "  message: '解释RAG的工作原理'\n"
            "});\n"
            "console.log(response.answer);"
        ),
    },
    "java": {
        "name": "fuxi-java-sdk",
        "language": "Java",
        "version": "1.2.0",
        "download_url": "https://github.com/1PGAT6466/fuxi/releases/download/sdk-v1.2.0/fuxi-java-sdk-1.2.0.jar",
        "docs_url": "https://fuxi.dev/sdk/java",
        "min_jdk": "17+",
        "install_cmd": (
            "<dependency>\n"
            "  <groupId>com.fuxi</groupId>\n"
            "  <artifactId>fuxi-sdk</artifactId>\n"
            "  <version>1.2.0</version>\n"
            "</dependency>"
        ),
        "example_code": (
            "import com.fuxi.sdk.FuxiClient;\n"
            "import com.fuxi.sdk.models.SearchResult;\n\n"
            "FuxiClient client = FuxiClient.builder()\n"
            '    .apiKey("your_api_key")\n'
            "    .build();\n\n"
            "// 查询知识库\n"
            "List<SearchResult> results = client.knowledge()\n"
            '    .search("伏羲系统架构", 5);\n'
            "results.forEach(doc ->\n"
            '    System.out.printf("[%.2f] %s%n", doc.getScore(), doc.getTitle())\n'
            ");\n\n"
            "// 聊天对话\n"
            "ChatResponse response = client.chat()\n"
            '    .send("解释RAG的工作原理");\n'
            "System.out.println(response.getAnswer());"
        ),
    },
}

# ── 社区帖子（静态示例数据） ──
COMMUNITY_POSTS = [
    {
        "id": "post-001",
        "title": "伏羲 RAG 引擎性能优化实践",
        "author": "张工",
        "content": (
            "在生产环境中，我们通过以下方式将 RAG 查询延迟从 800ms 降至 200ms：\n\n"
            "1. **向量索引优化**：将暴力搜索替换为 HNSW 索引，召回率保持 95% 以上\n"
            "2. **缓存层**：对高频查询引入 Redis 缓存，命中率达 60%\n"
            "3. **Rerank 模型量化**：使用 INT8 量化，精度损失 <1%，速度提升 3x\n"
            "4. **异步批处理**：合并并发请求，减少 GPU 空闲时间\n\n"
            "附压测报告和配置建议。"
        ),
        "created_at": "2026-07-10T09:30:00+08:00",
        "tags": ["RAG", "性能优化", "生产实践"],
    },
    {
        "id": "post-002",
        "title": "接入自定义 Embedding 模型的完整指南",
        "author": "李明",
        "content": (
            "伏羲 v1.44 开始支持自定义 Embedding 模型，本文介绍如何接入 BAAI/bge-large-zh-v1.5：\n\n"
            "**步骤一**：部署 Embedding 服务\n"
            "```python\n# embedder_server.py\n"
            "from sentence_transformers import SentenceTransformer\n"
            "model = SentenceTransformer('BAAI/bge-large-zh-v1.5')\n```\n\n"
            "**步骤二**：修改伏羲配置\n"
            "```yaml\nembedding:\n  provider: custom\n"
            "  endpoint: http://your-server:8080/embed\n"
            "  model: bge-large-zh-v1.5\n  dimensions: 1024\n```\n\n"
            "**步骤三**：重新索引知识库\n"
            "```bash\npython -m fuxi.kb.reindex --collection all\n```\n\n"
            "实测中文检索 MAP@10 提升 23%。"
        ),
        "created_at": "2026-07-08T14:15:00+08:00",
        "tags": ["Embedding", "自定义模型", "教程"],
    },
    {
        "id": "post-003",
        "title": "伏羲 + MCP 协议：让 AI 工具调用更丝滑",
        "author": "王架构",
        "content": (
            "MCP（Model Context Protocol）是 Anthropic 提出的工具调用标准。"
            "伏羲 v1.50 已原生支持 MCP，本文分享集成经验。\n\n"
            "**核心优势**：\n"
            "- 标准化工具描述（JSON Schema）\n"
            "- 自动发现和注册工具\n"
            "- 流式调用支持\n\n"
            "**集成示例**：\n"
            "```python\nfrom src.core.mcp_routes import register_mcp_routes\n"
            "register_mcp_routes(app)\n```\n\n"
            "我们已将内部 15 个微服务通过 MCP 暴露给伏羲，"
            "LLM 调用成功率从 72% 提升至 94%。"
        ),
        "created_at": "2026-07-05T11:00:00+08:00",
        "tags": ["MCP", "工具调用", "架构"],
    },
    {
        "id": "post-004",
        "title": "知识图谱可视化：从 Neo4j 到伏羲 Graph API",
        "author": "赵数据",
        "content": (
            "伏羲的 Graph API 支持知识图谱的存储和查询，配合前端可实现交互式可视化。\n\n"
            "**数据模型**：\n"
            "- 节点：实体（人、组织、概念）\n"
            "- 边：关系（属于、引用、相关）\n"
            "- 属性：时间戳、权重、类型\n\n"
            "**查询示例**：\n"
            "```python\n# 查询实体关系\n"
            'graph = client.graph.query(entity="伏羲", depth=2)\n'
            "for node in graph.nodes:\n"
            '    print(f"{node.type}: {node.name}")\n'
            "```\n\n"
            "**前端渲染**：推荐使用 AntV G6 或 D3.js，伏羲前端已内置 GraphView 组件。"
        ),
        "created_at": "2026-07-02T16:45:00+08:00",
        "tags": ["知识图谱", "可视化", "Graph API"],
    },
    {
        "id": "post-005",
        "title": "伏羲多租户架构设计与实践",
        "author": "陈总",
        "content": (
            "在 SaaS 化部署中，多租户隔离是核心需求。伏羲 v1.44 引入了完整的多租户支持。\n\n"
            "**隔离策略**：\n"
            "- **数据层**：每个租户独立 ChromaDB collection，SQLite 按 tenant_id 分区\n"
            "- **权限层**：RBAC + 租户级 API Key，支持细粒度资源控制\n"
            "- **配置层**：租户可自定义 LLM 模型、Prompt 模板、知识库集合\n\n"
            "**关键代码**：\n"
            "```python\n# 获取当前租户上下文\n"
            "from src.api.tenant_routes import get_current_tenant\n"
            "tenant = get_current_tenant(request)\n\n"
            "# 租户级资源访问\n"
            "chunks = load_chunks(tenant_id=tenant.id)\n"
            "```\n\n"
            "目前支撑 50+ 租户、200万+ 文档，P99 延迟 < 500ms。"
        ),
        "created_at": "2026-06-28T10:20:00+08:00",
        "tags": ["多租户", "SaaS", "架构设计"],
    },
]


# ── Pydantic 模型 ──


class OAuthAppCreate(BaseModel):
    app_name: str
    redirect_uri: str


# ── 辅助函数 ──


def _load_oauth_apps() -> List[dict]:
    """加载 OAuth 应用数据"""
    if not OAUTH_APPS_FILE.exists():
        return []
    with open(OAUTH_APPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_oauth_apps(apps: List[dict]) -> None:
    """保存 OAuth 应用数据"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OAUTH_APPS_FILE, "w", encoding="utf-8") as f:
        json.dump(apps, f, ensure_ascii=False, indent=2)


def _scan_routes(request: Request) -> List[dict]:
    """从 FastAPI app.routes 中扫描所有已注册路由"""
    routes_info = []
    for route in request.app.routes:
        if not hasattr(route, "methods"):
            continue
        methods = list(route.methods - {"HEAD", "OPTIONS"})
        if not methods:
            continue
        routes_info.append(
            {
                "path": route.path,
                "methods": methods,
                "summary": getattr(route, "summary", "") or getattr(route, "description", "") or "",
                "tags": getattr(route, "tags", []) or [],
            }
        )
    routes_info.sort(key=lambda r: r["path"])
    return routes_info


# ── API 端点 ──


@router.get("/docs")
async def get_api_docs(request: Request):
    """获取 API 文档摘要（所有端点列表）"""
    try:
        routes = _scan_routes(request)
        return {
            "status": "success",
            "data": {
                "title": "伏羲 API",
                "description": "伏羲智能知识平台 API 文档",
                "current_version": "v1.50",
                "total_endpoints": len(routes),
                "endpoints": routes,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs/{version}")
async def get_api_docs_by_version(version: str):
    """获取指定版本 API 文档"""
    if version not in API_VERSIONS:
        raise HTTPException(
            status_code=404,
            detail=f"版本 {version} 不存在，可用版本: {', '.join(API_VERSIONS.keys())}",
        )
    version_info = API_VERSIONS[version]
    return {
        "status": "success",
        "data": {
            "version": version,
            "release_date": version_info["release_date"],
            "status": version_info["status"],
            "changelog": f"https://github.com/1PGAT6466/fuxi/releases/tag/{version}",
            "openapi_spec": f"/api/developer/docs/{version}/openapi.json",
        },
    }


@router.get("/sdk")
async def list_sdks():
    """获取 SDK 列表及下载链接"""
    sdk_list = []
    for lang, info in SDK_CATALOG.items():
        sdk_list.append(
            {
                "language": info["language"],
                "name": info["name"],
                "version": info["version"],
                "download_url": info["download_url"],
                "docs_url": info["docs_url"],
                "install_cmd": info["install_cmd"],
            }
        )
    return {
        "status": "success",
        "data": {
            "total": len(sdk_list),
            "sdks": sdk_list,
        },
    }


@router.get("/sdk/{language}")
async def get_sdk_detail(language: str):
    """获取指定语言 SDK 详情"""
    lang_key = language.lower()
    if lang_key not in SDK_CATALOG:
        raise HTTPException(
            status_code=404,
            detail=f"不支持的语言: {language}，可用: {', '.join(SDK_CATALOG.keys())}",
        )
    info = SDK_CATALOG[lang_key]
    return {
        "status": "success",
        "data": info,
    }


@router.post("/oauth/register-app")
async def register_oauth_app(body: OAuthAppCreate):
    """注册 OAuth2.0 应用"""
    app_id = str(uuid.uuid4())
    app_secret = secrets.token_urlsafe(32)
    now = datetime.now().isoformat()

    new_app = {
        "app_id": app_id,
        "app_name": body.app_name,
        "app_secret": app_secret,
        "redirect_uri": body.redirect_uri,
        "created_at": now,
    }

    apps = _load_oauth_apps()
    apps.append(new_app)
    _save_oauth_apps(apps)

    return {
        "status": "success",
        "data": new_app,
    }


@router.get("/oauth/apps")
async def list_oauth_apps():
    """获取已注册 OAuth2.0 应用列表"""
    apps = _load_oauth_apps()
    # 隐藏 app_secret，只返回前6位 + ***
    safe_apps = []
    for app in apps:
        safe_app = dict(app)
        secret = safe_app.get("app_secret", "")
        safe_app["app_secret"] = secret[:6] + "***" if len(secret) > 6 else "***"
        safe_apps.append(safe_app)
    return {
        "status": "success",
        "data": {
            "total": len(safe_apps),
            "apps": safe_apps,
        },
    }


@router.get("/community/posts")
async def list_community_posts():
    """获取开发者社区帖子（静态示例数据）"""
    return {
        "status": "success",
        "data": {
            "total": len(COMMUNITY_POSTS),
            "posts": COMMUNITY_POSTS,
        },
    }


@router.get("/community/posts/{post_id}")
async def get_community_post(post_id: str):
    """获取社区帖子详情"""
    for post in COMMUNITY_POSTS:
        if post["id"] == post_id:
            return {
                "status": "success",
                "data": post,
            }
    raise HTTPException(status_code=404, detail=f"帖子不存在: {post_id}")
