"""
evolution — 第九宫（中宫）· 自进化中枢

伏羲 v2.1 增强：中宫承载自进化闭环，将原分散在 services/ 下的
feedback_store、learner、evolver、knowledge_lifecycle 统一封装进
八卦框架内，实现：
  - 反馈记录 → 去重 + 批量学习触发
  - 离线学习 → 术语权重调整、个性化 boost
  - 知识进化 → 实体发现、关系推理、图谱增量更新
  - 生命周期 → 知识事件记录、触发条件检查、置信度分类

所有模块包装自 src/services/ 的原实现，不重复代码，
保持向后兼容。

Usage::

    from src.evolution import EvolutionGua

    gua = EvolutionGua()
    gua.start()

    # 记录反馈
    result = gua.execute({"action": "feedback", "user_id": "u1", "query": "test"})

    # 查询健康
    print(gua.health_summary())

    gua.stop()
"""

from src.evolution.evolution_gua import EvolutionGua
from src.evolution.feedback_loop import (
    FeedbackLoop,
    record_feedback,
    has_feedback_loop,
    get_feedback_loop_stats,
    clear_feedback_dedup_cache,
)
from src.evolution.learner import (
    EvolutionLearner,
    learn_from_feedback,
    extract_new_terms,
    get_personalized_boost,
    get_learner_stats,
)
from src.evolution.evolver import (
    EvolutionEvolver,
    evolve_knowledge_graph,
    discover_entities_from_text,
    get_knowledge_graph_stats,
    get_knowledge_graph_nodes,
)
from src.evolution.lifecycle import (
    EvolutionLifecycle,
    record_lifecycle_event,
    check_lifecycle_triggers,
    get_lifecycle_candidates,
    classify_lifecycle_confidence,
)

__all__ = [
    # 核心
    "EvolutionGua",
    # 反馈闭环
    "FeedbackLoop",
    "record_feedback",
    "has_feedback_loop",
    "get_feedback_loop_stats",
    "clear_feedback_dedup_cache",
    # 离线学习
    "EvolutionLearner",
    "learn_from_feedback",
    "extract_new_terms",
    "get_personalized_boost",
    "get_learner_stats",
    # 知识进化
    "EvolutionEvolver",
    "evolve_knowledge_graph",
    "discover_entities_from_text",
    "get_knowledge_graph_stats",
    "get_knowledge_graph_nodes",
    # 生命周期
    "EvolutionLifecycle",
    "record_lifecycle_event",
    "check_lifecycle_triggers",
    "get_lifecycle_candidates",
    "classify_lifecycle_confidence",
]
