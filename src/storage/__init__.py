"""
storage — 伏羲存储层 (v2.1)

职责：
  - 双写代理 (WriteProxy): 将写入同步/异步分派到 ChromaDB + SQLite
  - Entity Frontier: 维护实体边界，记录新增/变更的 entity，供八卦中宫自进化消费

所属层：基础设施层 (infra partner)，独立于四象八卦分层
不依赖任何四象模块（shaoyang/shaoyin/taiyang/taiyin）。

ADR-008: 双写一致性与 write-through 策略
"""

# 伏羲存储层 — 双写 + Entity Frontier
