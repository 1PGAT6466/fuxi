"""
四象迁移映射表 — services_old → 四象模块
"""
MIGRATION_MAP = {
    # 少阳·消化
    "services_old/ingest.py": "shaoyang/pipeline.py",
    "services_old/semantic_chunker.py": "shaoyang/semantic_chunker.py",
    "services_old/auto_classifier.py": "shaoyang/auto_classifier.py",
    "services_old/chunker_quality.py": "shaoyang/quality.py",
    "services_old/mineru.py": "shaoyang/mineru.py",
    "services_old/distiller.py": "shaoyang/distiller.py",
    "services_old/multimodal.py": "shaoyang/multimodal.py",
    "services_old/long_doc_handler.py": "shaoyang/long_doc.py",
    "services_old/relation_builder.py": "shaoyang/relation_builder.py",
    "services_old/kg_extractor.py": "shaoyang/kg_extractor.py",

    # 太阳·筑基
    "services_old/retrieval.py": "taiyang/retrieval.py",
    "services_old/fusion.py": "taiyang/fusion.py",
    "services_old/rerank.py": "taiyang/rerank.py",
    "services_old/query_expansion.py": "taiyang/query_expansion.py",
    "services_old/results_postprocess.py": "taiyang/results_postprocess.py",
    "services_old/multi_hop.py": "taiyang/multi_hop.py",
    "services_old/cache.py": "taiyang/cache.py",
    "services_old/cache_manager.py": "taiyang/cache_manager.py",
    "services_old/graph_router.py": "taiyang/graph_router.py",
    "services_old/graph_traversal.py": "taiyang/graph_traversal.py",
    "services_old/self_rag.py": "taiyang/self_rag.py",
    "services_old/crag.py": "taiyang/crag.py",
    "services_old/dynamic_alpha.py": "taiyang/dynamic_alpha.py",
    "services_old/synonym_loader.py": "taiyang/synonym_loader.py",
    "services_old/table_parser.py": "taiyang/table_parser.py",
    "services_old/table_view.py": "taiyang/table_view.py",
    "services_old/wiki.py": "taiyang/wiki.py",
    "services_old/wiki_distiller.py": "taiyang/wiki_distiller.py",
    "services_old/integrated_search.py": "taiyang/integrated_search.py",

    # 少阴·炼化
    "agents_old/yin_agent.py": "shaoyin/validator.py",
    "agents_old/yang_agent.py": "shaoyin/tools.py",
    "agents_old/orchestrator.py": "shaoyin/orchestrator.py",
    "services_old/judge.py": "shaoyin/judge.py",
    "services_old/judge_v2.py": "shaoyin/judge_v2.py",
    "services_old/fact_check.py": "shaoyin/fact_check.py",
    "services_old/query_planner.py": "shaoyin/query_planner.py",
    "services_old/query_resolver.py": "shaoyin/query_resolver.py",
    "services_old/query_router.py": "shaoyin/router.py",
    "services_old/context_compressor.py": "shaoyin/context_compressor.py",

    # 太阴·显化
    "services_old/security.py": "taiyin/security.py",
    "services_old/error_handler.py": "taiyin/error_handler.py",
    "services_old/audit.py": "taiyin/audit.py",

    # 基础设施
    "services_old/llm.py": "infra/llm.py",
    "services_old/embedder.py": "infra/embedder.py",
    "services_old/memory.py": "infra/memory.py",

    # 跨象模块 → services/
    "services_old/feedback_store.py": "services/feedback_store.py",
    "services_old/learner.py": "services/learner.py",
    "services_old/evolver.py": "services/evolver.py",
    "services_old/evaluator.py": "services/evaluator.py",
    "services_old/eval_dataset.py": "services/eval_dataset.py",
    "services_old/eval_updater.py": "services/eval_updater.py",
    "services_old/online_eval.py": "services/online_eval.py",
    "services_old/knowledge_lifecycle.py": "services/knowledge_lifecycle.py",
}

print("=== 迁移映射表 ===")
print(f"总计: {len(MIGRATION_MAP)} 个文件")

# 按目标分组
groups = {}
for src, dst in MIGRATION_MAP.items():
    group = dst.split("/")[0] if "/" in dst else "root"
    if group not in groups:
        groups[group] = []
    groups[group].append((src, dst))

for group, items in groups.items():
    print(f"\n{group}: {len(items)} 个文件")
    for src, dst in items:
        print(f"  {src} → {dst}")
