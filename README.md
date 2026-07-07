# 伏羲 Fuxi — 企业知识认知体系

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.50-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="python">
  <img src="https://img.shields.io/badge/framework-FastAPI-orange" alt="framework">
  <img src="https://img.shields.io/badge/license-Proprietary-red" alt="license">
</p>

> **伏羲**——以中医脏腑隐喻构建的企业知识认知体系，经络为信号总线，四象为功能系统。

## 术语定义

- **伏羲 = 体系（System of Systems）**：由多个系统组成的完整知识认知体系
- **四象 = 系统（System）**：少阳、太阳、少阴、太阴四大功能系统
- **器官 = 组件（Component）**：系统内的具体功能模块（心、肝、脾、肺、肾...）

---

## 🏗️ 架构总览

```
伏羲体系
├── 少阳·消化系统（知识消化中枢）
├── 太阳·筑基系统（精炼排序中枢）
├── 少阴·炼化系统（决策合成中枢）
├── 太阴·显化系统（对外接口中枢）
└── 器官组件（心、肝、脾、肺、肾...）

src/
├── shaoyang/              # 少阳·消化系统（知识消化中枢）
│   ├── pipeline.py        # 统一处理管线
│   ├── extractor.py       # SAG式事件/实体提取
│   └── semantic_chunker.py # 语义分块
│
├── taiyang/               # 太阳·筑基系统（精炼排序中枢）
│   ├── retrieval.py       # 混合检索管线
│   ├── multi_hop.py       # SAG式多跳检索
│   ├── fusion.py          # RRF融合
│   ├── rerank.py          # 四级降级精排
│   ├── dynamic_alpha.py   # 动态融合权重
│   └── query_expansion.py # 查询扩展
│
├── shaoyin/               # 少阴·炼化系统（决策合成中枢）
│   ├── brain.py           # 决策合成引擎
│   ├── judge_v2.py        # LLM-as-Judge评分
│   ├── fact_check.py      # 事实性校验
│   ├── context_compressor.py # 上下文压缩
│   └── strategy.py        # 策略选择
│
├── taiyin/                # 太阴·显化系统（对外接口中枢）
│   ├── server.py          # 对外接口
│   ├── audit.py           # 审计日志
│   ├── metrics.py         # Prometheus指标
│   ├── security.py        # 安全模块
│   └── flags.py           # Feature Flag管理
│
├── infra/                 # 基础设施
│   ├── symbol_base.py     # 四象系统基类
│   ├── protocol.py        # 象间通信协议
│   ├── llm.py             # LLM调用封装(MiMo 2.5 Pro)
│   └── logging.py         # 统一日志
│
├── models/                # 数据模型
├── pipeline/              # 周天大阵统一管线
├── db/                    # 数据存储层
├── hypothalamus/          # 体系核心（经络+五行平衡）
│   ├── brain.py           # 大脑（本能识别+意图路由）
│   ├── meridian.py        # 经络系统（信号总线）
│   └── organs/            # 五行器官
└── frontend/              # 前端静态资源
```

## 🔍 检索管线

```
L-1: QA对匹配 → L0: 语义缓存+图谱路由 → L1: 同义词+LLM改写 →
L1.5: HyDE → L2: BM25+向量双路 → L3: RRF融合+动态alpha →
L4: 三阶段精排 → L5: Rerank四级降级 → L6: Parent-Child+Sentence Window
```

## 🚀 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 API Key

# 3. 启动服务
python -m uvicorn src.server:app --host 0.0.0.0 --port 8080

# 4. 访问系统
# 浏览器打开 http://localhost:8080
# 默认账号: admin / fuxi2024
```

## 📊 测试

```bash
# 运行单元测试
python -m pytest tests/ -v

# 预期结果: 202 passed, 9 skipped
```

## 📁 项目结构

```
伏羲体系-v1.50/
├── src/                    # 源代码
│   ├── server.py           # FastAPI主入口
│   ├── config.py           # 全局配置
│   ├── shaoyang/           # 少阳·消化系统
│   ├── taiyang/            # 太阳·筑基系统
│   ├── shaoyin/            # 少阴·炼化系统
│   ├── taiyin/             # 太阴·显化系统
│   ├── infra/              # 基础设施
│   ├── hypothalamus/       # 体系核心（经络+器官）
│   ├── api/                # API路由
│   ├── services/           # 业务逻辑
│   └── db/                 # 数据存储
├── tests/                  # 测试文件
├── docs/                   # 文档
├── scripts/                # 工具脚本
├── frontend/               # 前端资源
├── config/                 # 配置文件
└── data/                   # 数据目录
```

## 🔧 核心系统说明

### 少阳·消化系统（知识消化中枢）
负责文档的解析、清洗、分块和知识提取。将原始文档转化为结构化的知识片段。

### 太阳·筑基系统（精炼排序中枢）
负责检索和排序。通过多路召回、融合、精排，从海量知识中找到最相关的内容。

### 少阴·炼化系统（决策合成中枢）
负责答案生成和质量控制。通过LLM合成答案，并进行事实性校验和质量评估。

### 太阴·显化系统（对外接口中枢）
负责体系对外服务。提供API接口、监控指标、审计日志和安全管理。

## 📝 版本历史

- v1.50: 术语统一（四象=系统，伏羲=体系）+ MiMo 2.5 Pro集成 + JWT升级 + 审计/指标/安全模块
- v1.44: 四象归位架构重构
- v1.43: 周天大阵统一管线
- v1.42: SAG式事件/实体提取
- v1.41: 多跳检索 + seed_score

## 📄 许可证

Proprietary - 企业内部使用
