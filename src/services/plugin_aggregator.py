"""
插件聚合器 — 对接外部插件市场
从 NPM、GitHub 等源获取真实可用的插件
"""

import logging
import time
import httpx
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExternalPlugin:
    """外部插件数据结构"""
    id: str
    name: str
    description: str
    author: str
    category: str
    source: str  # npm/github/custom
    version: str
    icon: str
    install_url: str
    homepage: str
    downloads: int
    rating: float
    tags: List[str] = field(default_factory=list)
    installed: bool = False


class PluginAggregator:
    """插件聚合器"""
    
    # 缓存配置
    _cache: Dict[str, tuple] = {}
    _cache_ttl = 3600  # 1小时缓存
    _plugin_cache: Dict[str, ExternalPlugin] = {}  # 单个插件缓存

    # 预定义的优质 AI/工具类 NPM 包
    FEATURED_NPM_PACKAGES = [
        # AI/ML 核心
        "langchain", "llamaindex", "openai", "anthropic",
        "@google/generative-ai", "@azure/openai", "cohere-ai", "huggingface",
        "replicate", "together-ai", "groq-sdk", "mistralai",
        # 向量数据库
        "chromadb", "pinecone", "weaviate", "qdrant",
        "@azure/cosmos", "redis", "elasticsearch",
        # Web 框架
        "fastapi", "flask", "express", "next",
        "nestjs", "koa", "hapi", "tRPC",
        # 机器学习
        "tensorflow", "pytorch", "transformers", "diffusers",
        "@xenova/transformers", "onnxruntime", "openvino",
        # 浏览器自动化
        "puppeteer", "playwright", "selenium",
        "cheerio", "jsdom", "cypress",
        # 数据库 ORM
        "prisma", "drizzle-orm", "typeorm",
        "sequelize", "knex", "mongoose",
        # 验证库
        "zod", "joi", "yup", "ajv", "superstruct",
        # UI 组件
        "tailwindcss", "shadcn-ui", "radix-ui",
        "@mui/material", "@chakra-ui/react", "antd",
        "@headlessui/react", "@heroicons/react",
        # 工具库
        "lodash", "ramda", "date-fns", "dayjs",
        "uuid", "nanoid", "chalk", "commander",
        # 测试
        "jest", "mocha", "vitest", "cypress",
        # 文档
        "swagger-ui-express", "@storybook/react", "docusaurus",
    ]

    # GitHub 热门 AI 项目
    FEATURED_GITHUB_REPOS = [
        # LLM 框架
        "langchain-ai/langchain",
        "run-llama/llama_index",
        "microsoft/semantic-kernel",
        "langgenius/dify",
        "lobehub/lobe-chat",
        # 向量数据库
        "chroma-core/chroma",
        "qdrant/qdrant",
        "weaviate/weaviate",
        "milvus-io/milvus",
        # AI 应用
        "openai/openai-cookbook",
        "anthropics/anthropic-cookbook",
        "microsoft/autogen",
        "Significant-Gravitas/AutoGPT",
        "geekan/MetaGPT",
        # 前端 UI
        "vercel/ai",
        "streamlit/streamlit",
        "gradio-app/gradio",
        # 数据处理
        "unstructured-io/unstructured",
        # 模型推理
        "ollama/ollama",
        "ggerganov/llama.cpp",
        # 工具链
        "astral-sh/uv",
        "astral-sh/ruff",
    ]
    
    # NPM 包中文名称映射
    PLUGIN_NAME_CN = {
        "langchain": "LangChain 链式框架",
        "llamaindex": "Llama 索引引擎",
        "openai": "OpenAI 官方 SDK",
        "anthropic": "Anthropic Claude SDK",
        "@google/generative-ai": "Google Gemini SDK",
        "@azure/openai": "Azure OpenAI SDK",
        "cohere-ai": "Cohere 嵌入与生成",
        "huggingface": "HuggingFace 客户端",
        "replicate": "Replicate 模型运行",
        "together-ai": "Together AI 推理",
        "groq-sdk": "Groq 高速推理",
        "mistralai": "Mistral AI SDK",
        "chromadb": "ChromaDB 向量库",
        "pinecone": "Pinecone 向量数据库",
        "weaviate": "Weaviate 向量引擎",
        "qdrant": "Qdrant 向量搜索",
        "@azure/cosmos": "Azure Cosmos DB",
        "redis": "Redis 缓存数据库",
        "elasticsearch": "Elasticsearch 搜索引擎",
        "fastapi": "FastAPI 框架",
        "flask": "Flask 轻量框架",
        "express": "Express Node框架",
        "next": "Next.js 全栈框架",
        "nestjs": "NestJS Node框架",
        "koa": "Koa 轻量框架",
        "hapi": "hapi 企业框架",
        "tRPC": "tRPC 类型安全API",
        "tensorflow": "TensorFlow 机器学习",
        "pytorch": "PyTorch 深度学习",
        "transformers": "HuggingFace Transformers",
        "diffusers": "Stable Diffusion 扩散模型",
        "@xenova/transformers": "浏览器端AI推理",
        "onnxruntime": "ONNX 模型推理",
        "openvino": "Intel 模型优化",
        "puppeteer": "Puppeteer 浏览器自动化",
        "playwright": "Playwright 测试框架",
        "selenium": "Selenium 自动化测试",
        "cheerio": "jQuery式HTML解析",
        "jsdom": "Node DOM 实现",
        "cypress": "E2E 测试框架",
        "prisma": "Prisma ORM 数据库",
        "drizzle-orm": "Drizzle ORM",
        "typeorm": "TypeORM 数据库映射",
        "sequelize": "Node.js ORM",
        "knex": "SQL 查询构建器",
        "mongoose": "MongoDB ODM",
        "zod": "Zod 数据验证",
        "joi": "Joi 参数校验",
        "yup": "Yup 表单验证",
        "ajv": "JSON Schema 验证",
        "superstruct": "结构体验证",
        "tailwindcss": "Tailwind CSS 框架",
        "shadcn-ui": "shadcn/ui 组件库",
        "radix-ui": "Radix UI 原语",
        "@mui/material": "Material UI",
        "@chakra-ui/react": "Chakra UI",
        "antd": "Ant Design",
        "@headlessui/react": "Headless UI",
        "@heroicons/react": "Heroicons 图标",
        "lodash": "Lodash 工具库",
        "ramda": "函数式工具库",
        "date-fns": "日期处理库",
        "dayjs": "轻量日期库",
        "uuid": "UUID 生成器",
        "nanoid": "短ID生成器",
        "chalk": "终端颜色输出",
        "commander": "CLI 框架",
        "jest": "JavaScript 测试框架",
        "mocha": "Mocha 测试框架",
        "vitest": "Vite 测试框架",
        "swagger-ui-express": "Swagger 文档UI",
        "@storybook/react": "Storybook 组件文档",
        "docusaurus": "文档站点生成器",
    }
    
    # NPM 包中文描述映射 — 对伏羲的提升价值
    PLUGIN_DESC_CN = {
        "langchain": "为伏羲提供完整的LLM应用开发框架，支持知识库RAG检索、智能Agent自主决策、多轮对话记忆管理，是伏羲智能体能力的核心增强",
        "llamaindex": "为伏羲接入专业级数据连接与索引能力，优化知识库检索准确率，支持PDF/网页/数据库等多源数据接入，提升知识图谱查询效率",
        "openai": "为伏羲接入GPT-4o顶级大模型能力，支持文本生成、语音识别、图像理解，增强伏羲的自然语言理解与多模态处理能力",
        "anthropic": "为伏羲接入Claude 3.5 Sonnet/Opus模型，擅长长文本理解、代码生成、复杂推理，提升伏羲的专业分析与创作能力",
        "@google/generative-ai": "为伏羲接入Google Gemini大模型，支持多模态理解与生成，扩展伏羲的AI能力边界",
        "@azure/openai": "为伏羲接入Azure OpenAI服务，企业级安全与合规，适合生产环境部署",
        "cohere-ai": "为伏羲提供Cohere嵌入与生成模型，优化语义搜索与文本生成质量",
        "huggingface": "为伏羲接入HuggingFace模型库，快速集成数千个预训练模型",
        "replicate": "为伏羲提供云端模型运行平台，无需本地GPU即可运行大模型",
        "together-ai": "为伏羲提供高速AI推理服务，支持多种开源模型，降低推理成本",
        "groq-sdk": "为伏羲接入Groq超高速推理芯片，LPU加速，毫秒级响应",
        "mistralai": "为伏羲接入Mistral AI模型，欧洲顶级开源模型，性能优异",
        "chromadb": "为伏羲提供高性能向量数据库，加速知识库嵌入存储与相似性搜索，提升RAG检索速度与准确率",
        "pinecone": "为伏羲提供全托管向量数据库服务，毫秒级查询响应，适合大规模知识库部署，降低运维成本",
        "weaviate": "为伏羲提供AI原生向量数据库，支持多模态搜索（文本+图像+音频），扩展知识库检索维度",
        "qdrant": "为伏羲提供高性能向量搜索引擎，支持实时过滤与批量更新，提升知识库查询灵活性",
        "@azure/cosmos": "为伏羲提供全球分布式数据库，多区域复制，适合全球化部署",
        "redis": "为伏羲提供高性能缓存数据库，加速会话存储与热点数据访问",
        "elasticsearch": "为伏羲提供全文搜索引擎，支持复杂查询与聚合分析",
        "fastapi": "为伏羲提供现代Python Web框架，自动API文档生成、高性能异步处理，优化后端服务性能与开发效率",
        "flask": "为伏羲提供轻量级Web框架，快速构建微服务接口，适合原型开发与小型功能模块",
        "express": "为伏羲提供Node.js Web框架，快速构建API服务，支持前后端分离架构",
        "next": "为伏羲提供React全栈框架，支持SSR/SSG渲染，优化前端性能与SEO，提升用户体验",
        "nestjs": "为伏羲提供企业级Node.js框架，模块化架构，适合大型应用",
        "koa": "为伏羲提供轻量级Node.js框架，中间件灵活，适合微服务",
        "hapi": "为伏羲提供企业级Node.js框架，配置驱动，适合复杂业务",
        "tRPC": "为伏羲提供类型安全API框架，前后端类型共享，减少调试时间",
        "tensorflow": "为伏羲接入Google机器学习框架，支持模型训练与推理，增强伏羲的AI模型开发能力",
        "pytorch": "为伏羲接入Meta深度学习框架，动态计算图便于研究实验，提升伏羲的AI模型训练灵活性",
        "transformers": "为伏羲接入HuggingFace预训练模型库，支持NLP/CV/音频任务，快速集成最新AI模型",
        "diffusers": "为伏羲接入Stable Diffusion图像生成能力，支持文生图/图生图，扩展伏羲的创意内容生成",
        "@xenova/transformers": "为伏羲提供浏览器端AI推理能力，无需后端即可运行模型，保护数据隐私",
        "onnxruntime": "为伏羲提供跨平台模型推理，支持多种硬件加速，优化推理性能",
        "openvino": "为伏羲接入Intel模型优化工具，CPU推理加速，降低硬件成本",
        "puppeteer": "为伏羲提供无头浏览器自动化能力，支持网页抓取、截图、PDF生成，增强数据采集功能",
        "playwright": "为伏羲提供跨浏览器自动化测试框架，支持E2E测试，保障系统稳定性与兼容性",
        "selenium": "为伏羲提供经典浏览器自动化能力，支持多语言脚本，适合复杂Web交互场景",
        "cheerio": "为伏羲提供jQuery式HTML解析，快速抓取网页数据，适合爬虫场景",
        "jsdom": "为伏羲提供Node.js DOM实现，支持服务端渲染与测试",
        "cypress": "为伏羲提供E2E测试框架，保障前端功能稳定性",
        "prisma": "为伏瑟提供类型安全的Node.js ORM，自动数据库迁移，优化数据层开发效率与代码质量",
        "drizzle-orm": "为伏瑟提供TypeScript ORM，SQL-like API风格，类型安全，提升数据库操作的开发体验",
        "typeorm": "为伏瑟提供Node.js ORM，支持Active Record与Data Mapper模式，灵活适配不同项目架构",
        "sequelize": "为伏瑟提供Node.js ORM，支持多种数据库，简化数据层开发",
        "knex": "为伏瑟提供SQL查询构建器，支持多种数据库，灵活构建复杂查询",
        "mongoose": "为伏瑟提供MongoDB ODM，简化文档数据库操作",
        "zod": "为伏瑟提供TypeScript数据验证库，类型推断自动补全，提升API参数校验的开发效率与安全性",
        "joi": "为伏瑟提供JavaScript对象模式验证，支持复杂嵌套结构校验，增强API接口的健壮性",
        "yup": "为伏瑟提供表单验证库，支持异步验证与链式调用，优化前端表单处理逻辑",
        "ajv": "为伏瑟提供JSON Schema验证，确保API参数格式正确",
        "superstruct": "为伏瑟提供结构体验证，简洁的类型定义与校验",
        "tailwindcss": "为伏瑟提供原子化CSS框架，快速构建响应式UI，提升前端开发效率与视觉一致性",
        "shadcn-ui": "为伏瑟提供高质量可复用组件库，基于Radix UI与Tailwind，加速前端界面开发",
        "radix-ui": "为伏瑟提供无样式UI原语，高可访问性支持，完全可控的组件定制能力",
        "@mui/material": "为伏瑟提供Material Design组件库，丰富的UI组件，提升开发效率",
        "@chakra-ui/react": "为伏瑟提供可访问性优先的UI组件库，快速构建美观界面",
        "antd": "为伏瑟提供Ant Design组件库，企业级UI解决方案，后台管理系统首选",
        "@headlessui/react": "为伏瑟提供无样式UI原语，完全可控的组件定制",
        "@heroicons/react": "为伏瑟提供精美SVG图标库，提升界面视觉效果",
        "lodash": "为伏瑟提供实用工具函数库，简化数据处理与操作",
        "ramda": "为伏瑟提供函数式编程工具，提升代码可读性与可维护性",
        "date-fns": "为伏瑟提供日期处理工具，模块化设计，按需加载",
        "dayjs": "为伏瑟提供轻量级日期库，API兼容Moment.js，体积更小",
        "uuid": "为伏瑟提供UUID生成器，确保数据唯一性",
        "nanoid": "为伏瑟提供短ID生成器，更短更安全的唯一标识",
        "chalk": "为伏瑟提供终端颜色输出，提升命令行工具可读性",
        "commander": "为伏瑟提供CLI框架，快速构建命令行工具",
        "jest": "为伏瑟提供JavaScript测试框架，保障代码质量",
        "mocha": "为伏瑟提供灵活测试框架，支持多种断言库",
        "vitest": "为伏瑟提供Vite原生测试框架，极速测试执行",
        "swagger-ui-express": "为伏瑟提供API文档UI，自动生成交互式API文档",
        "@storybook/react": "为伏瑟提供组件文档工具，可视化展示UI组件库",
        "docusaurus": "为伏瑟提供文档站点生成器，快速构建产品文档",
    }
    
    # GitHub 项目中文名称映射
    GITHUB_NAME_CN = {
        "langchain": "LangChain 链式框架",
        "llama_index": "Llama 索引引擎",
        "chroma": "ChromaDB 向量库",
        "qdrant": "Qdrant 向量搜索",
        "weaviate": "Weaviate 向量引擎",
        "milvus": "Milvus 向量数据库",
        "openai-cookbook": "OpenAI 示例集",
        "anthropic-cookbook": "Anthropic 示例集",
        "semantic-kernel": "微软语义内核",
        "ai": "Vercel AI SDK",
        "streamlit": "Streamlit 数据应用",
        "gradio": "Gradio ML界面",
        "dify": "Dify AI 应用平台",
        "lobe-chat": "Lobe Chat AI助手",
        "autogen": "微软 AutoGen 多智能体",
        "AutoGPT": "AutoGPT 自主智能体",
        "MetaGPT": "MetaGPT 多角色协作",
        "unstructured": "非结构化数据处理",
        "ollama": "Ollama 本地模型运行",
        "llama.cpp": "llama.cpp 模型推理",
        "uv": "UV 包管理器",
        "ruff": "Ruff Python代码检查",
    }
    
    # GitHub 项目中文描述映射 — 对伏羲的提升价值
    GITHUB_DESC_CN = {
        "langchain": "为伏羲提供完整的LLM应用开发框架，支持知识库RAG检索、智能Agent自主决策、多轮对话记忆管理",
        "llama_index": "为伏羲接入专业级数据连接与索引能力，优化知识库检索准确率，支持PDF/网页/数据库等多源数据接入",
        "chroma": "为伏羲提供高性能向量数据库，加速知识库嵌入存储与相似性搜索，提升RAG检索速度与准确率",
        "qdrant": "为伏羲提供高性能向量搜索引擎，支持实时过滤与批量更新，提升知识库查询灵活性",
        "weaviate": "为伏羲提供AI原生向量数据库，支持多模态搜索（文本+图像+音频），扩展知识库检索维度",
        "milvus": "为伏羲提供分布式向量数据库，适合大规模向量检索场景，支持百亿级向量数据",
        "openai-cookbook": "为伏羲提供OpenAI官方示例与最佳实践，加速LLM应用开发，提升API调用效率",
        "anthropic-cookbook": "为伏羲提供Anthropic官方示例与集成指南，优化Claude模型使用，提升提示工程效果",
        "semantic-kernel": "为伏羲接入微软AI编排框架，集成LLM与传统代码，支持复杂工作流编排",
        "ai": "为伏羲接入Vercel AI SDK，提供流式UI组件与LLM集成方案，优化前端AI交互体验",
        "streamlit": "为伏羲提供快速构建数据应用工具，适合原型开发与数据可视化，加速功能验证",
        "gradio": "为伏羲提供ML模型Web界面构建工具，支持拖拽上传，快速创建AI演示与交互界面",
        "dify": "为伏羲提供开源AI应用开发平台，可视化编排工作流，快速构建RAG和Agent应用",
        "lobe-chat": "为伏羲提供开源AI聊天助手框架，支持多模型、插件系统，优化对话交互体验",
        "autogen": "为伏羲提供微软多智能体框架，支持Agent协作与任务分解，增强复杂任务处理能力",
        "AutoGPT": "为伏羲提供自主智能体框架，支持目标驱动的自动任务执行",
        "MetaGPT": "为伏羲提供多角色协作框架，模拟软件开发团队，提升代码生成质量",
        "unstructured": "为伏羲提供非结构化数据处理工具，支持PDF/图片/音频解析，扩展知识库数据源",
        "ollama": "为伏羲提供本地模型运行工具，无需云端API即可运行大模型，保护数据隐私",
        "llama.cpp": "为伏羲提供高效模型推理引擎，CPU优化，适合边缘设备部署",
        "uv": "为伏羲提供超快Python包管理器，比pip快10倍，加速依赖安装",
        "ruff": "为伏羲提供Python代码检查工具，比flake8快100倍，提升代码质量",
    }

    async def get_all_plugins(self, category: str = "", search: str = "") -> List[ExternalPlugin]:
        """获取所有可用插件（带缓存）"""
        # 检查缓存
        cache_key = "all_plugins"
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                plugins = cached_data
            else:
                plugins = await self._refresh_cache()
        else:
            plugins = await self._refresh_cache()
        
        # 分类筛选
        if category:
            plugins = [p for p in plugins if p.category == category]

        # 搜索筛选
        if search:
            search_lower = search.lower()
            plugins = [p for p in plugins if
                      search_lower in p.name.lower() or
                      search_lower in p.description.lower() or
                      search_lower in ' '.join(p.tags).lower()]

        # 按下载量排序
        plugins.sort(key=lambda p: p.downloads, reverse=True)

        return plugins

    async def _refresh_cache(self) -> List[ExternalPlugin]:
        """刷新缓存"""
        plugins = []
        
        # 获取 NPM 包（限制数量避免超时）
        npm_plugins = await self._fetch_npm_plugins()
        plugins.extend(npm_plugins)

        # 获取 GitHub 项目
        github_plugins = await self._fetch_github_plugins()
        plugins.extend(github_plugins)
        
        # 更新缓存
        self._cache["all_plugins"] = (plugins, time.time())
        # 更新单个插件缓存
        for p in plugins:
            self._plugin_cache[p.id] = p
        logger.info(f"[PluginAggregator] 缓存已刷新，共 {len(plugins)} 个插件")
        
        return plugins

    async def _fetch_npm_plugins(self) -> List[ExternalPlugin]:
        """从 NPM 获取插件信息（限制数量避免超时）"""
        plugins = []
        async with httpx.AsyncClient(timeout=5.0) as client:
            for pkg_name in self.FEATURED_NPM_PACKAGES[:20]:  # 限制为20个避免超时
                try:
                    resp = await client.get(f"https://registry.npmjs.org/{pkg_name}")
                    if resp.status_code == 200:
                        data = resp.json()
                        latest = data.get("dist-tags", {}).get("latest", "")
                        versions = data.get("versions", {})
                        latest_version = versions.get(latest, {})

                        # 提取 author: 可能是对象 {"name": "..."} 或字符串
                        author_raw = latest_version.get("author", "Unknown")
                        if isinstance(author_raw, dict):
                            author_name = author_raw.get("name", "Unknown")
                        elif isinstance(author_raw, str):
                            author_name = author_raw
                        else:
                            author_name = "Unknown"

                        # 获取中文名称和描述
                        name_cn = self.PLUGIN_NAME_CN.get(pkg_name, pkg_name)
                        desc_cn = self.PLUGIN_DESC_CN.get(pkg_name, data.get("description", ""))
                        
                        plugins.append(ExternalPlugin(
                            id=f"npm-{pkg_name}",
                            name=name_cn,
                            description=desc_cn,
                            author=author_name,
                            category=self._categorize_npm(pkg_name),
                            source="npm",
                            version=latest,
                            icon=f"https://cdn.jsdelivr.net/npm/{pkg_name}@latest/icon.png",
                            install_url=f"npm install {pkg_name}",
                            homepage=data.get("homepage", ""),
                            downloads=data.get("downloads", 0),
                            rating=0.0,
                            tags=list(latest_version.get("keywords", [])),
                        ))
                except Exception as e:
                    logger.warning(f"NPM fetch failed for {pkg_name}: {e}")
                    continue

        return plugins

    async def _fetch_github_plugins(self) -> List[ExternalPlugin]:
        """从 GitHub 获取项目信息"""
        plugins = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for repo in self.FEATURED_GITHUB_REPOS[:15]:
                try:
                    resp = await client.get(
                        f"https://api.github.com/repos/{repo}",
                        headers={"Accept": "application/vnd.github.v3+json"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        repo_name = repo.split("/")[-1]
                        # 获取中文名称和描述
                        name_cn = self.GITHUB_NAME_CN.get(repo_name, data.get("name", repo_name))
                        desc_cn = self.GITHUB_DESC_CN.get(repo_name, data.get("description", ""))
                        plugins.append(ExternalPlugin(
                            id=f"github-{repo.replace('/', '-')}",
                            name=name_cn,
                            description=desc_cn,
                            author=data.get("owner", {}).get("login", "Unknown"),
                            category=self._categorize_github(data),
                            source="github",
                            version=data.get("default_branch", "main"),
                            icon=data.get("owner", {}).get("avatar_url", ""),
                            install_url=f"git clone {data.get('clone_url', '')}",
                            homepage=data.get("homepage", ""),
                            downloads=data.get("stargazers_count", 0),
                            rating=0.0,
                            tags=data.get("topics", []),
                        ))
                    elif resp.status_code == 403:
                        # API 限流，使用静态数据
                        logger.warning("GitHub API rate limit, using static data")
                        return self._get_static_github_plugins()
                except Exception as e:
                    logger.warning(f"GitHub fetch failed for {repo}: {e}")
                    continue

        # 如果没有获取到任何数据，使用静态数据
        if not plugins:
            return self._get_static_github_plugins()
        return plugins

    def _get_static_github_plugins(self) -> List[ExternalPlugin]:
        """静态 GitHub 项目数据（当 API 限流时使用）"""
        static_projects = [
            {
                "name": "langchain",
                "full_name": "langchain-ai/langchain",
                "description": "为伏羲提供完整的LLM应用开发框架，支持知识库RAG检索、智能Agent自主决策、多轮对话记忆管理",
                "owner": "langchain-ai",
                "stars": 98000,
                "topics": ["ai", "llm", "rag", "agent"],
            },
            {
                "name": "llama_index",
                "full_name": "run-llama/llama_index",
                "description": "为伏羲接入专业级数据连接与索引能力，优化知识库检索准确率，支持PDF/网页/数据库等多源数据接入",
                "owner": "run-llama",
                "stars": 38000,
                "topics": ["ai", "llm", "rag", "index"],
            },
            {
                "name": "chroma",
                "full_name": "chroma-core/chroma",
                "description": "为伏羲提供高性能向量数据库，加速知识库嵌入存储与相似性搜索，提升RAG检索速度与准确率",
                "owner": "chroma-core",
                "stars": 16000,
                "topics": ["vector-database", "ai", "embeddings"],
            },
            {
                "name": "qdrant",
                "full_name": "qdrant/qdrant",
                "description": "为伏羲提供高性能向量搜索引擎，支持实时过滤与批量更新，提升知识库查询灵活性",
                "owner": "qdrant",
                "stars": 22000,
                "topics": ["vector-database", "ai", "search"],
            },
            {
                "name": "weaviate",
                "full_name": "weaviate/weaviate",
                "description": "为伏羲提供AI原生向量数据库，支持多模态搜索（文本+图像+音频），扩展知识库检索维度",
                "owner": "weaviate",
                "stars": 12000,
                "topics": ["vector-database", "ai", "multimodal"],
            },
            {
                "name": "milvus",
                "full_name": "milvus-io/milvus",
                "description": "为伏羲提供分布式向量数据库，适合大规模向量检索场景，支持百亿级向量数据",
                "owner": "milvus-io",
                "stars": 31000,
                "topics": ["vector-database", "ai", "distributed"],
            },
            {
                "name": "openai-cookbook",
                "full_name": "openai/openai-cookbook",
                "description": "为伏羲提供OpenAI官方示例与最佳实践，加速LLM应用开发，提升API调用效率",
                "owner": "openai",
                "stars": 58000,
                "topics": ["ai", "llm", "openai", "examples"],
            },
            {
                "name": "anthropic-cookbook",
                "full_name": "anthropics/anthropic-cookbook",
                "description": "为伏羲提供Anthropic官方示例与集成指南，优化Claude模型使用，提升提示工程效果",
                "owner": "anthropics",
                "stars": 8000,
                "topics": ["ai", "llm", "anthropic", "examples"],
            },
            {
                "name": "semantic-kernel",
                "full_name": "microsoft/semantic-kernel",
                "description": "为伏羲接入微软AI编排框架，集成LLM与传统代码，支持复杂工作流编排",
                "owner": "microsoft",
                "stars": 22000,
                "topics": ["ai", "llm", "orchestration"],
            },
            {
                "name": "ai",
                "full_name": "vercel/ai",
                "description": "为伏羲接入Vercel AI SDK，提供流式UI组件与LLM集成方案，优化前端AI交互体验",
                "owner": "vercel",
                "stars": 12000,
                "topics": ["ai", "llm", "ui", "streaming"],
            },
            {
                "name": "streamlit",
                "full_name": "streamlit/streamlit",
                "description": "为伏羲提供快速构建数据应用工具，适合原型开发与数据可视化，加速功能验证",
                "owner": "streamlit",
                "stars": 36000,
                "topics": ["data", "ui", "python"],
            },
            {
                "name": "gradio",
                "full_name": "gradio-app/gradio",
                "description": "为伏羲提供ML模型Web界面构建工具，支持拖拽上传，快速创建AI演示与交互界面",
                "owner": "gradio-app",
                "stars": 34000,
                "topics": ["ai", "ml", "ui", "demo"],
            },
            {
                "name": "dify",
                "full_name": "langgenius/dify",
                "description": "为伏羲提供开源AI应用开发平台，可视化编排工作流，快速构建RAG和Agent应用",
                "owner": "langgenius",
                "stars": 55000,
                "topics": ["ai", "llm", "rag", "agent", "platform"],
            },
            {
                "name": "lobe-chat",
                "full_name": "lobehub/lobe-chat",
                "description": "为伏羲提供开源AI聊天助手框架，支持多模型、插件系统，优化对话交互体验",
                "owner": "lobehub",
                "stars": 48000,
                "topics": ["ai", "llm", "chat", "ui"],
            },
            {
                "name": "autogen",
                "full_name": "microsoft/autogen",
                "description": "为伏羲提供微软多智能体框架，支持Agent协作与任务分解，增强复杂任务处理能力",
                "owner": "microsoft",
                "stars": 32000,
                "topics": ["ai", "agent", "multi-agent"],
            },
            {
                "name": "AutoGPT",
                "full_name": "Significant-Gravitas/AutoGPT",
                "description": "为伏羲提供自主智能体框架，支持目标驱动的自动任务执行",
                "owner": "Significant-Gravitas",
                "stars": 169000,
                "topics": ["ai", "agent", "autonomous"],
            },
            {
                "name": "MetaGPT",
                "full_name": "geekan/MetaGPT",
                "description": "为伏羲提供多角色协作框架，模拟软件开发团队，提升代码生成质量",
                "owner": "geekan",
                "stars": 48000,
                "topics": ["ai", "agent", "multi-agent"],
            },
            {
                "name": "unstructured",
                "full_name": "unstructured-io/unstructured",
                "description": "为伏羲提供非结构化数据处理工具，支持PDF/图片/音频解析，扩展知识库数据源",
                "owner": "unstructured-io",
                "stars": 9000,
                "topics": ["data", "parsing", "etl"],
            },
            {
                "name": "ollama",
                "full_name": "ollama/ollama",
                "description": "为伏羲提供本地模型运行工具，无需云端API即可运行大模型，保护数据隐私",
                "owner": "ollama",
                "stars": 110000,
                "topics": ["ai", "llm", "local", "inference"],
            },
            {
                "name": "llama.cpp",
                "full_name": "ggerganov/llama.cpp",
                "description": "为伏羲提供高效模型推理引擎，CPU优化，适合边缘设备部署",
                "owner": "ggerganov",
                "stars": 72000,
                "topics": ["ai", "llm", "inference", "cpp"],
            },
            {
                "name": "uv",
                "full_name": "astral-sh/uv",
                "description": "为伏羲提供超快Python包管理器，比pip快10倍，加速依赖安装",
                "owner": "astral-sh",
                "stars": 28000,
                "topics": ["python", "package-manager", "fast"],
            },
            {
                "name": "ruff",
                "full_name": "astral-sh/ruff",
                "description": "为伏羲提供Python代码检查工具，比flake8快100倍，提升代码质量",
                "owner": "astral-sh",
                "stars": 32000,
                "topics": ["python", "linter", "fast"],
            },
        ]
        
        plugins = []
        for proj in static_projects:
            name_cn = self.GITHUB_NAME_CN.get(proj["name"], proj["name"])
            desc_cn = self.GITHUB_DESC_CN.get(proj["name"], proj.get("description", ""))
            plugins.append(ExternalPlugin(
                id=f"github-{proj['full_name'].replace('/', '-')}",
                name=name_cn,
                description=desc_cn,
                author=proj["owner"],
                category=self._categorize_by_topics(proj.get("topics", [])),
                source="github",
                version="main",
                icon=f"https://github.com/{proj['full_name']}.png",
                install_url=f"git clone https://github.com/{proj['full_name']}.git",
                homepage=f"https://github.com/{proj['full_name']}",
                downloads=proj.get("stars", 0),
                rating=0.0,
                tags=proj.get("topics", []),
            ))
        return plugins

    def _categorize_by_topics(self, topics: list) -> str:
        """根据 topics 分类"""
        if "ai" in topics or "llm" in topics or "agent" in topics:
            return "ai"
        elif "vector-database" in topics or "database" in topics:
            return "database"
        elif "ui" in topics:
            return "ui"
        else:
            return "tool"

    def _categorize_npm(self, name: str) -> str:
        """NPM 包分类"""
        ai_keywords = ["langchain", "llama", "openai", "anthropic",
                        "transformers", "tensorflow", "pytorch", "diffusers",
                        "google", "azure", "cohere", "huggingface", "replicate",
                        "together", "groq", "mistral"]
        db_keywords = ["chroma", "pinecone", "weaviate", "qdrant",
                        "prisma", "drizzle", "typeorm", "redis", "elasticsearch",
                        "cosmos", "sequelize", "knex", "mongoose"]
        ui_keywords = ["tailwind", "shadcn", "radix", "chakra", "mui", "antd",
                        "headless", "heroicons"]

        name_lower = name.lower()
        if any(k in name_lower for k in ai_keywords):
            return "ai"
        elif any(k in name_lower for k in db_keywords):
            return "database"
        elif any(k in name_lower for k in ui_keywords):
            return "ui"
        else:
            return "tool"

    def _categorize_github(self, data: dict) -> str:
        """GitHub 项目分类"""
        topics = data.get("topics", [])
        if "ai" in topics or "llm" in topics or "machine-learning" in topics:
            return "ai"
        elif "database" in topics or "vector-database" in topics:
            return "database"
        else:
            return "tool"


# 全局实例
aggregator = PluginAggregator()
