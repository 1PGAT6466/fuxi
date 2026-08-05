"""
infra/__init__.py — 基础设施层（v2.3）

解决 services ↔ 四象 双向依赖问题。所有导入使用惰性加载避免循环导入。

规则：
  - infra/ 不依赖 services/、bagua/、四象/（所有导入惰性化）
  - services/ 可以依赖 infra/
  - 四象/ 可以依赖 infra/
"""

import logging

logger = logging.getLogger(__name__)

__all__ = [
    "call_llm",
    "call_deepseek",
    "call_llm_fast",
    "call_ai_raw",
    "hybrid_search",
    "sanitize_document_content",
    "detect_injection",
    "is_enabled",
    "load_flags",
    "get_entity_context",
    "multi_hop_traverse",
    "find_paths",
    "get_wiki_engine",
    "search_tables",
    "index_tables_from_chunks",
    "extract_tables_from_markdown",
    "enhance_table_extraction",
    "transcribe_image",
    "parse_file",
    "load_synonyms",
    "get_personalized_boost",
    "get_online_evaluator",
    "get_eval_automation",
    "embed",
]


def __getattr__(name: str):
    """惰性导入 — 只在首次访问时才加载对应模块"""

    if name == "call_llm":
        from src.services.llm import call_llm

        return call_llm
    if name == "call_deepseek":
        from src.services.llm import call_deepseek

        return call_deepseek
    if name == "call_llm_fast":
        from src.services.llm import call_llm_fast

        return call_llm_fast
    if name == "call_ai_raw":
        from src.services.llm import call_ai_raw

        return call_ai_raw
    if name == "hybrid_search":
        from src.services.retrieval import hybrid_search

        return hybrid_search
    if name == "sanitize_document_content":
        from src.services.prompt_guard import sanitize_document_content

        return sanitize_document_content
    if name == "detect_injection":
        from src.services.prompt_guard import detect_injection

        return detect_injection
    if name == "is_enabled":
        from src.services.feature_flags import is_enabled

        return is_enabled
    if name == "load_flags":
        from src.services.feature_flags import load_flags

        return load_flags
    if name == "get_entity_context":
        from src.services.graph_router import get_entity_context

        return get_entity_context
    if name == "multi_hop_traverse":
        from src.services.graph_traversal import multi_hop_traverse

        return multi_hop_traverse
    if name == "find_paths":
        from src.services.graph_traversal import find_paths

        return find_paths
    if name == "get_wiki_engine":
        from src.services.wiki import get_wiki_engine

        return get_wiki_engine
    if name in ("search_tables", "index_tables_from_chunks"):
        from src.services import table_view

        return getattr(table_view, name)
    if name == "extract_tables_from_markdown":
        from src.services.table_parser import extract_tables_from_markdown

        return extract_tables_from_markdown
    if name == "enhance_table_extraction":
        from src.services.multimodal import enhance_table_extraction

        return enhance_table_extraction
    if name == "transcribe_image":
        from src.services.multimodal import transcribe_image

        return transcribe_image
    if name == "parse_file":
        from src.services.parsers import parse_file

        return parse_file
    if name == "load_synonyms":
        from src.services.synonym_loader import load_synonyms

        return load_synonyms
    if name == "get_personalized_boost":
        from src.services.learner import get_personalized_boost

        return get_personalized_boost
    if name == "get_online_evaluator":
        from src.services.online_eval import get_online_evaluator

        return get_online_evaluator
    if name == "get_eval_automation":
        from src.services.eval_automation import get_eval_automation

        return get_eval_automation
    if name == "embed":
        from src.services.embedder import embed

        return embed

    raise AttributeError(f"module 'src.infra' has no attribute '{name}'")
