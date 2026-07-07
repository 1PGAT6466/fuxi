#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_data_pipeline_smoke.py — 伏羲 0→64 数据管道端到端冒烟测试

验证路径: 震卦消化(解析→清洗→分块→入库)
        → 坤卦存储(向量+Wiki+知识图谱)
        → 巽卦检索
        → 离卦生成答案

测试文档: 项目根目录的 README.md（或 tests/fixtures/sample.md）

用法:
    cd E:\easyclaw\伏羲-v1.44\repo
    python tests/test_data_pipeline_smoke.py

输出: 逐项 [OK] / [FAIL] 标注，文件+行号+实现描述
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

# 确保 src 在 sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smoke_test")

TEST_DOC_CONTENT = """# 伏羲智能知识库系统

## 概述
伏羲是一个基于八卦架构的智能知识库系统，具备文档解析、向量检索、知识图谱构建和智能问答等核心能力。

## 核心模块

### 震卦 - 消化管线
震卦负责文件消化，包括文件指纹检测、文本解析、清洗、分块和向量化。

### 坤卦 - 知识存储
坤卦负责知识存储，包括短期记忆、Wiki 知识库和知识图谱的持久化。

### 巽卦 - 数据检索
巽卦负责数据检索，包括向量检索、关键词搜索和外部搜索。

### 离卦 - 知识蒸馏
离卦负责知识蒸馏，包括 LLM 推理、内容生成和结果后处理。

## 技术栈
- Python 3.11+
- ChromaDB 向量数据库
- SQLite 关系存储
- FastAPI Web 框架
- PyMuPDF 文档解析

## 知识图谱实体
- 系统名称: 伏羲
- 核心技术: ChromaDB, SQLite, FastAPI, PyMuPDF
- 模块: 震卦, 坤卦, 巽卦, 离卦
"""


class SmokeTestRunner:
    """数据管道端到端冒烟测试"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results: list = []
        self.test_doc_path: str = ""
        self.doc_id: str = ""

    # ========================================================================
    # 测试方法
    # ========================================================================

    def run_all(self) -> bool:
        """运行全部测试"""
        logger.info("=" * 60)
        logger.info("伏羲 0→64 数据管道端到端冒烟测试")
        logger.info("=" * 60)

        # 0. 准备测试文档
        self._prepare_test_doc()

        # 1. 震卦消化管线测试
        self._test_zhen_digest_pipeline()

        # 2. 坤卦存储接口测试
        self._test_kun_store_interfaces()

        # 3. 知识图谱自动构建测试
        self._test_knowledge_graph_build()

        # 4. Wiki 持久化测试
        self._test_wiki_persistence()

        # 5. 巽卦检索测试
        self._test_xun_retrieval()

        # 6. 离卦生成测试
        self._test_li_generation()

        # 7. 端到端链路验证
        self._test_end_to_end_chain()

        # -- 输出汇总 --
        self._print_summary()

        return self.failed == 0

    # ========================================================================
    # 0. 准备测试文档
    # ========================================================================

    def _prepare_test_doc(self):
        """创建测试用的临时文档"""
        tmp_dir = tempfile.mkdtemp(prefix="fuxi_smoke_")
        doc_path = os.path.join(tmp_dir, "test_knowledge.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(TEST_DOC_CONTENT)
        self.test_doc_path = doc_path
        logger.info(f"[SETUP] 测试文档: {doc_path}")

    # ========================================================================
    # 1. 震卦消化管线
    # ========================================================================

    def _test_zhen_digest_pipeline(self):
        """验证震卦端到端消化管线"""
        logger.info("\n--- 1. 震卦消化管线 ---")

        try:
            from src.bagua.zhen import ZhenGua

            zhen = ZhenGua()
            zhen.start()

            # [1.1] ZhenGua 实例化
            self._check(
                "1.1", "src/bagua/zhen.py:ZhenGua.__init__",
                "震卦实例化成功",
                zhen is not None and zhen.GUA_NAME == "zhen",
            )

            # [1.2] 文件指纹计算
            fp = zhen.compute_file_fingerprint(self.test_doc_path)
            self._check(
                "1.2", "src/bagua/zhen.py:compute_file_fingerprint",
                f"文件指纹计算: {fp[:16]}...",
                bool(fp) and len(fp) == 32,
            )

            # [1.3] 文件变化检测
            changed = zhen.check_file_changed(self.test_doc_path)
            self._check(
                "1.3", "src/bagua/zhen.py:check_file_changed",
                f"文件变化检测: {changed}（首次应为 True）",
                changed is True,
            )

            # [1.4] digest_and_store 入口存在
            has_method = hasattr(zhen, "digest_and_store") and callable(zhen.digest_and_store)
            self._check(
                "1.4", "src/bagua/zhen.py:digest_and_store",
                "digest_and_store 端到端消化入口已定义",
                has_method,
            )

            # [1.5] batch_digest 入口存在
            has_batch = hasattr(zhen, "batch_digest") and callable(zhen.batch_digest)
            self._check(
                "1.5", "src/bagua/zhen.py:batch_digest",
                "batch_digest 批量消化入口已定义",
                has_batch,
            )

            # 清除指纹缓存（check_file_changed 会写入缓存，导致 digest_and_store 跳过）
            zhen.invalidate_cache(self.test_doc_path)

            # [1.6] 端到端消化流程（解析→清洗→分块→入库）
            result = zhen.digest_and_store(self.test_doc_path, store_in_kun=False)
            self._check(
                "1.6", "src/bagua/zhen.py:digest_and_store",
                f"端到端消化结果: ok={result.get('ok')}, chunks={result.get('chunks_count')}",
                result.get("ok") is True and result.get("chunks_count", 0) > 0,
            )

            self.doc_id = result.get("file_hash", "")

            zhen.stop()

        except Exception as e:
            logger.error(f"震卦测试异常: {e}", exc_info=True)
            self._check("1.E", "src/bagua/zhen.py", f"异常: {e}", False)

    # ========================================================================
    # 2. 坤卦存储接口
    # ========================================================================

    def _test_kun_store_interfaces(self):
        """验证坤卦三个标准化存储接口"""
        logger.info("\n--- 2. 坤卦存储接口 ---")

        try:
            from src.bagua.kun import KunGua

            kun = KunGua()
            kun.start()

            # [2.1] store_vector 方法存在
            has_sv = hasattr(kun, "store_vector") and callable(kun.store_vector)
            self._check(
                "2.1", "src/bagua/kun.py:store_vector",
                "store_vector 向量存储接口已定义",
                has_sv,
            )

            # [2.2] store_graph 方法存在
            has_sg = hasattr(kun, "store_graph") and callable(kun.store_graph)
            self._check(
                "2.2", "src/bagua/kun.py:store_graph",
                "store_graph 知识图谱存储接口已定义",
                has_sg,
            )

            # [2.3] store_wiki 方法存在
            has_sw = hasattr(kun, "store_wiki") and callable(kun.store_wiki)
            self._check(
                "2.3", "src/bagua/kun.py:store_wiki",
                "store_wiki Wiki 持久化接口已定义",
                has_sw,
            )

            # [2.4] store_wiki 数据校验（空 content）
            result_empty = kun.store_wiki(doc_id="test", content="")
            self._check(
                "2.4", "src/bagua/kun.py:store_wiki → 数据校验",
                f"空 content 校验: ok={result_empty.get('ok')}（应为 False）",
                result_empty.get("ok") is False and "content" in result_empty.get("error", "").lower(),
            )

            # [2.5] store_wiki 正常写入
            result_wiki = kun.store_wiki(
                doc_id=self.doc_id or "test_smoke_001",
                content=TEST_DOC_CONTENT,
                title="伏羲智能知识库系统",
                source=self.test_doc_path,
                category="技术文档",
            )
            self._check(
                "2.5", "src/bagua/kun.py:store_wiki → 正常写入",
                f"store_wiki 写入: ok={result_wiki.get('ok')}, page_id={result_wiki.get('page_id')}",
                result_wiki.get("ok") is True,
            )

            # [2.6] store_vector 空数据校验
            result_vec = kun.store_vector(doc_id="test", chunks=[])
            self._check(
                "2.6", "src/bagua/kun.py:store_vector → 数据校验",
                f"空 chunks 校验: ok={result_vec.get('ok')}",
                "chunks 为空" in result_vec.get("error", "").lower(),
            )

            # [2.7] store_graph 空数据校验
            result_gr = kun.store_graph(entities=[], relations=[])
            self._check(
                "2.7", "src/bagua/kun.py:store_graph → 数据校验",
                f"空数据校验: ok={result_gr.get('ok')}（应为 False）",
                result_gr.get("ok") is False,
            )

            # [2.8] store_graph 正常写入
            test_entities = [
                {"name": "伏羲", "type": "system", "description": "智能知识库系统"},
                {"name": "ChromaDB", "type": "technology", "description": "向量数据库"},
                {"name": "震卦", "type": "module", "description": "消化管线模块"},
                {"name": "坤卦", "type": "module", "description": "知识存储模块"},
            ]
            test_relations = [
                {"source": "伏羲", "target": "ChromaDB", "relation": "uses"},
                {"source": "伏羲", "target": "震卦", "relation": "contains"},
                {"source": "伏羲", "target": "坤卦", "relation": "contains"},
                {"source": "震卦", "target": "坤卦", "relation": "related_to"},
            ]
            result_gr2 = kun.store_graph(
                entities=test_entities,
                relations=test_relations,
                doc_id=self.doc_id or "test_smoke_001",
            )
            self._check(
                "2.8", "src/bagua/kun.py:store_graph → 正常写入",
                f"store_graph 写入: ok={result_gr2.get('ok')}, entities={result_gr2.get('entities_count')}, relations={result_gr2.get('relations_count')}",
                result_gr2.get("ok") is True,
            )

            kun.stop()

        except Exception as e:
            logger.error(f"坤卦测试异常: {e}", exc_info=True)
            self._check("2.E", "src/bagua/kun.py", f"异常: {e}", False)

    # ========================================================================
    # 3. 知识图谱自动构建
    # ========================================================================

    def _test_knowledge_graph_build(self):
        """验证知识图谱自动构建功能"""
        logger.info("\n--- 3. 知识图谱自动构建 ---")

        try:
            from src.bagua.kun import KunGua

            kun = KunGua()
            kun.start()

            # [3.1] build_knowledge_graph 方法存在
            has_bkg = hasattr(kun, "build_knowledge_graph") and callable(kun.build_knowledge_graph)
            self._check(
                "3.1", "src/bagua/kun.py:build_knowledge_graph",
                "build_knowledge_graph 方法已定义",
                has_bkg,
            )

            # [3.2] 从文档自动构建知识图谱
            if self.doc_id:
                result_bkg = kun.build_knowledge_graph(doc_id=self.doc_id)
                self._check(
                    "3.2", "src/bagua/kun.py:build_knowledge_graph → 自动构建",
                    f"知识图谱构建: ok={result_bkg.get('ok')}, "
                    f"chunks={result_bkg.get('chunks_processed')}, "
                    f"entities={result_bkg.get('entities_extracted')}, "
                    f"relations={result_bkg.get('relations_extracted')}",
                    result_bkg.get("ok") is True,
                )
            else:
                self._check(
                    "3.2", "src/bagua/kun.py:build_knowledge_graph",
                    "跳过（无 doc_id）",
                    True,  # 非阻塞跳过
                )

            # [3.3] 验证 knowledge_graph.json 是否被更新
            from src.config import GRAPH_PATH
            if os.path.exists(str(GRAPH_PATH)):
                with open(str(GRAPH_PATH), "r", encoding="utf-8") as f:
                    graph_data = json.load(f)
                nodes_count = len(graph_data.get("nodes", {}))
                edges_count = len(graph_data.get("edges", []))
                self._check(
                    "3.3", "src/bagua/kun.py:store_graph → knowledge_graph.json",
                    f"knowledge_graph.json: nodes={nodes_count}, edges={edges_count}",
                    nodes_count > 0 or edges_count > 0,
                )
            else:
                self._check("3.3", "knowledge_graph.json", "文件不存在", False)

            # [3.4] 规则提取 fallback 方法存在
            has_rule = hasattr(kun, "_rule_based_kg_extraction") and callable(kun._rule_based_kg_extraction)
            self._check(
                "3.4", "src/bagua/kun.py:_rule_based_kg_extraction",
                "规则提取 fallback 方法已定义",
                has_rule,
            )

            kun.stop()

        except Exception as e:
            logger.error(f"知识图谱测试异常: {e}", exc_info=True)
            self._check("3.E", "src/bagua/kun.py", f"异常: {e}", False)

    # ========================================================================
    # 4. Wiki 持久化
    # ========================================================================

    def _test_wiki_persistence(self):
        """验证 Wiki 确实写入 worldtree.db"""
        logger.info("\n--- 4. Wiki 持久化 ---")

        try:
            import sqlite3
            from src.config import WORLDTREE_DB_PATH

            db_path = str(WORLDTREE_DB_PATH)

            # [4.1] worldtree.db 存在并包含 wiki_pages 表
            conn = sqlite3.connect(db_path, timeout=10)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='wiki_pages'"
            ).fetchall()
            self._check(
                "4.1", "src/config.py → worldtree.db/wiki_pages",
                f"wiki_pages 表存在: {len(tables) > 0}",
                len(tables) > 0,
            )

            # [4.2] wiki_pages 表有数据
            count = conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
            self._check(
                "4.2", "src/bagua/kun.py:store_wiki → worldtree.db",
                f"wiki_pages 行数: {count}（应 > 0）",
                count > 0,
            )

            # [4.3] 验证数据内容
            if count > 0:
                row = conn.execute(
                    "SELECT id, title, category, LENGTH(content) as content_len FROM wiki_pages LIMIT 1"
                ).fetchone()
                self._check(
                    "4.3", "src/bagua/kun.py:store_wiki → 数据验证",
                    f"Wiki 页面: id={row[0]}, title={row[1]}, category={row[2]}, len={row[3]}",
                    row[3] > 0,
                )

            conn.close()

        except Exception as e:
            logger.error(f"Wiki 持久化测试异常: {e}", exc_info=True)
            self._check("4.E", "worldtree.db", f"异常: {e}", False)

    # ========================================================================
    # 5. 巽卦检索
    # ========================================================================

    def _test_xun_retrieval(self):
        """验证巽卦检索能力"""
        logger.info("\n--- 5. 巽卦检索 ---")

        try:
            from src.bagua.xun import XunGua

            xun = XunGua()
            xun.start()

            # [5.1] XunGua 实例化
            self._check(
                "5.1", "src/bagua/xun.py:XunGua.__init__",
                "巽卦实例化成功",
                xun is not None and xun.GUA_NAME == "xun",
            )

            # [5.2] execute + stats
            stats = xun.execute({"operation": "stats"})
            self._check(
                "5.2", "src/bagua/xun.py:XunGua.stats",
                f"巽卦统计: search_count={stats.get('search_count')}, cache_size={stats.get('cache_size')}",
                isinstance(stats, dict),
            )

            # [5.3] 交叉验证功能
            content = "伏羲是一个基于八卦的智能知识库系统，使用 ChromaDB 作为向量数据库。这是一个完整的知识管理平台。"
            score = xun.cross_validate("伏羲 ChromaDB 知识库", content, [{"title": "t1"}, {"title": "t2"}])
            self._check(
                "5.3", "src/bagua/xun.py:cross_validate",
                f"交叉验证: score={score:.2f}（应 > 0）",
                score > 0,
            )

            xun.stop()

        except Exception as e:
            logger.error(f"巽卦测试异常: {e}", exc_info=True)
            self._check("5.E", "src/bagua/xun.py", f"异常: {e}", False)

    # ========================================================================
    # 6. 离卦生成
    # ========================================================================

    def _test_li_generation(self):
        """验证离卦检索和生成能力"""
        logger.info("\n--- 6. 离卦生成 ---")

        try:
            from src.bagua.li import LiGua

            li = LiGua()
            li.start()

            # [6.1] LiGua 实例化
            self._check(
                "6.1", "src/bagua/li.py:LiGua.__init__",
                "离卦实例化成功",
                li is not None and li.GUA_NAME == "li",
            )

            # [6.2] search action — 使用精确子串匹配（_tokenize 将连续中文视为单 token）
            test_docs = [
                {"doc_id": "d1", "content": "伏羲是一个基于八卦架构的智能知识库系统。"},
                {"doc_id": "d2", "content": "震卦负责文件消化，包括解析和向量化。"},
                {"doc_id": "d3", "content": "坤卦负责知识存储和知识图谱构建。"},
                {"doc_id": "d4", "content": "ChromaDB 是一个高性能向量数据库，支持快速检索。"},
            ]
            search_result = li.execute({
                "action": "search",
                "query": "ChromaDB 高性能 向量",
                "documents": test_docs,
                "top_k": 3,
            })
            self._check(
                "6.2", "src/bagua/li.py:LiGua._search",
                f"检索结果: matched={search_result.get('total_matched')}, results={len(search_result.get('results', []))}",
                search_result.get("total_matched", 0) > 0,
            )

            # [6.3] distill action
            long_text = "伏羲知识库系统" * 50 + " 基于八卦架构" * 30
            distill_result = li.execute({
                "action": "distill",
                "content": long_text,
                "query": "八卦",
                "max_length": 200,
            })
            self._check(
                "6.3", "src/bagua/li.py:LiGua._distill",
                f"蒸馏结果: original={distill_result.get('original_length')}, "
                f"distilled={len(distill_result.get('distilled', ''))}",
                distill_result.get("truncated") is True,
            )

            # [6.4] summarize action
            sum_result = li.execute({
                "action": "summarize",
                "content": TEST_DOC_CONTENT,
                "max_length": 100,
            })
            self._check(
                "6.4", "src/bagua/li.py:LiGua._summarize",
                f"摘要: len={len(sum_result.get('summary', ''))}, "
                f"chars={sum_result.get('stats', {}).get('chars', 0)}",
                len(sum_result.get("summary", "")) > 0,
            )

            # [6.5] compare action
            candidates = [
                {"id": "a", "content": "伏羲知识库系统", "score": 0.9},
                {"id": "b", "content": "八卦架构说明", "score": 0.7},
                {"id": "c", "content": "无关内容", "score": 0.1},
            ]
            cmp_result = li.execute({
                "action": "compare",
                "candidates": candidates,
                "query": "伏羲",
                "top_k": 2,
            })
            self._check(
                "6.5", "src/bagua/li.py:LiGua._compare",
                f"对比结果: best={cmp_result.get('best', {}).get('item', {}).get('id', '?')}, "
                f"total={cmp_result.get('total')}",
                cmp_result.get("best") is not None,
            )

            li.stop()

        except Exception as e:
            logger.error(f"离卦测试异常: {e}", exc_info=True)
            self._check("6.E", "src/bagua/li.py", f"异常: {e}", False)

    # ========================================================================
    # 7. 端到端链路
    # ========================================================================

    def _test_end_to_end_chain(self):
        """验证完整链路：震卦消化 → 坤卦存储 → 检索 → 生成"""
        logger.info("\n--- 7. 端到端链路 ---")

        try:
            from src.bagua.zhen import ZhenGua
            from src.bagua.kun import KunGua
            from src.bagua.li import LiGua

            zhen = ZhenGua()
            zhen.start()

            kun = KunGua()
            kun.start()

            li = LiGua()
            li.start()

            # [7.1] 震卦消化文件
            result_zhen = zhen.digest_and_store(self.test_doc_path, store_in_kun=True)
            self._check(
                "7.1", "震→坤 链路: zhen.digest_and_store → kun.store_wiki + store_vector + build_knowledge_graph",
                f"震卦消化: ok={result_zhen.get('ok')}, chunks={result_zhen.get('chunks_count')}, "
                f"digested={result_zhen.get('digested')}",
                result_zhen.get("ok") is True,
            )

            # [7.2] 坤卦 Wiki 召回（从 worldtree.db 读取）
            from src.taiyang.wiki import get_wiki_engine
            wiki_engine = get_wiki_engine()
            wiki_pages = wiki_engine.list_pages(limit=10)
            self._check(
                "7.2", "坤→检索: wiki_engine.list_pages (worldtree.db)",
                f"Wiki 检索: pages={len(wiki_pages)}",
                len(wiki_pages) > 0,
            )

            # [7.3] 离卦基于坤卦数据的检索+蒸馏
            if wiki_pages:
                docs = [
                    {"doc_id": r.get("id", ""), "content": r.get("content", "")}
                    for r in wiki_pages
                ]
                li_search = li.execute({
                    "action": "search",
                    "query": "伏羲 知识库 八卦",
                    "documents": docs,
                    "top_k": 3,
                })

                combined = "\n".join([
                    r.get("content", "")[:500]
                    for r in li_search.get("results", [])
                ])
                distill = li.execute({
                    "action": "distill",
                    "content": combined,
                    "query": "伏羲知识库",
                    "max_length": 300,
                })

                self._check(
                    "7.3", "坤→离 链路: kun.recall_wiki → li.search → li.distill",
                    f"端到端生成: search_results={len(li_search.get('results', []))}, "
                    f"distill_len={len(distill.get('distilled', ''))}",
                    len(li_search.get("results", [])) > 0,
                )
            else:
                self._check(
                    "7.3", "坤→离 链路",
                    "跳过（无 Wiki 数据）",
                    True,
                )

            # [7.4] 验证数据流向：chunks.db 有数据
            from src.db.memory_store import get_store
            store = get_store()
            total = store.total_chunks
            self._check(
                "7.4", "数据验证: chunks.db",
                f"chunks.db 总行数: {total}（应 > 1）",
                total > 1,
            )

            zhen.stop()
            kun.stop()
            li.stop()

        except Exception as e:
            logger.error(f"端到端测试异常: {e}", exc_info=True)
            self._check("7.E", "端到端链路", f"异常: {e}", False)

    # ========================================================================
    # 工具方法
    # ========================================================================

    def _check(self, test_id: str, location: str, description: str, passed: bool):
        """记录单个检查点"""
        status = "[OK]" if passed else "[FAIL]"
        if passed:
            self.passed += 1
        else:
            self.failed += 1

        self.results.append({
            "id": test_id,
            "location": location,
            "description": description,
            "passed": passed,
        })

        logger.info(f"  {status} [{test_id}] {location}")
        logger.info(f"       {description}")

    def _print_summary(self):
        """输出汇总"""
        total = self.passed + self.failed
        logger.info("\n" + "=" * 60)
        logger.info(f"  测试汇总: {self.passed}/{total} 通过, {self.failed}/{total} 失败")
        logger.info("=" * 60)

        for r in self.results:
            status = "✅" if r["passed"] else "❌"
            logger.info(f"  {status} [{r['id']}] {r['description']}")

        if self.failed == 0:
            logger.info("\n🎉 全部测试通过！数据管道端到端链路正常。")
        else:
            logger.warning(f"\n⚠️ {self.failed} 个测试失败，请检查上述 [FAIL] 项。")


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    runner = SmokeTestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
