# 伏羲 Fuxi — 企业知识认知系统

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.44-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="python">
  <img src="https://img.shields.io/badge/framework-FastAPI-orange" alt="framework">
  <img src="https://img.shields.io/badge/license-Proprietary-red" alt="license">
</p>

> **伏羲**——以中医脏腑隐喻构建的企业知识认知中枢，经络为信号总线，四象为功能模块。

---

## 🏗️ 架构总览

```
src/
├── shaoyang/              # 少阳·消化（知识消化中枢）
│   ├── pipeline.py        # 统一处理管线
│   └── extractor.py       # SAG式事件/实体提取
│
├── taiyang/               # 太阳·筑基（精炼排序中枢）
│   ├── retrieval.py       # 混合检索管线
│   ├── multi_hop.py       # SAG式多跳检索
│   ├── fusion.py          # RRF融合
│   ├── rerank.py          # 四级降级精排
│   └── query_expansion.py # 查询扩展
│
├── shaoyin/               # 少阴·炼化（决策合成中枢）
│   ├── brain.py           # 决策合成引擎
│   └── strategy.py        # 策略选择
│
├── taiyin/                # 太阴·显化（对外接口中枢）
│   ├── server.py          # 对外接口
│   └── flags.py           # Feature Flag管理
│
├── infra/                 # 基础设施
│   ├── symbol_base.py     # 四象基类
│   ├── protocol.py        # 象间通信协议
│   ├── llm.py             # LLM调用封装
│   └── logging.py         # 统一日志
│
├── models/                # 数据模型
├── pipeline/              # 周天大阵统一管线
├── db/                    # 数据存储层
├── hypothalamus/          # 生命体核心（经络+五行平衡）
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
python -m pytest tests/ -q --ignore=tests/test_smoke.py

# 运行系统测试
python test_comprehensive.py
```

## 📝 版本历史

- v1.44: 四象归位架构重构
- v1.43: 周天大阵统一管线
- v1.42: SAG式事件/实体提取
- v1.41: 多跳检索 + seed_score
