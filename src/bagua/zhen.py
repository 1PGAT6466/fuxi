#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zhen.py — 震卦 ☳ · 伏羲 v2.1

震为雷，主主动推送与通知。
对应能力：WebSocket 推送、消息通知、事件广播。

Phase 1 器官迁移：肺(LungAgent) → 震卦
  - 文件指纹变化检测（compute_file_fingerprint / check_file_changed）
  - 脏标记机制（_dirty + 文件 change 检测）
  - 呼吸间隔 BREATH_INTERVAL = 25s
"""


import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.bagua.base_gua import GuaBase

logger = logging.getLogger("bagua.zhen")

# ============================================================================
# 震卦 — 主动推送与通知（含文件变化检测能力）
# ============================================================================


class ZhenGua(GuaBase):
    """震卦 — 主动推送与通知

    继承自 GuaBase，拥有完整的健康管理、降级矩阵和断路器。

    Phase 1 从肺(LungAgent)迁移的能力：
      - 文件指纹变化检测
      - 脏标记机制
      - 呼吸间隔
    """

    GUA_NAME = "zhen"
    GUA_EMOJI = "☳"
    GUA_DESCRIPTION = "主动推送与通知 — WebSocket、消息、事件广播"

    # 呼吸间隔（秒）— 从肺迁移
    BREATH_INTERVAL: float = 25.0

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # ---- 文件指纹缓存 {file_path: fingerprint} ----
        self._fingerprint_cache: Dict[str, str] = {}

        # ---- 脏标记：有未处理的变化时为 True ----
        self._dirty: bool = True

        # ---- 统计 ----
        self._check_count: int = 0
        self._change_count: int = 0
        self._digested_count: int = 0

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_dependencies(self) -> None:
        """注册震卦外部依赖断路器"""
        self.register_dependency(
            "file_io",
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=3,
        )
        self.register_dependency(
            "vector_store",
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_max_calls=2,
        )
        self.register_dependency(
            "embedder_server",
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_max_calls=2,
        )
        self.register_dependency(
            "kun_store",
            failure_threshold=3,
            recovery_timeout=30.0,
            half_open_max_calls=2,
        )

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """震卦降级规则：文件 I/O / 向量存储 / embedder / kun 故障时降级"""
        from src.bagua.base_gua import DegradationRule, FallbackAction

        # 规则 1: 文件 I/O 持续失败 → 返回空指纹
        def _empty_fingerprint_fallback(params: Dict[str, Any]) -> str:
            return ""

        self.add_rule(DegradationRule(
            name="file_read_degraded",
            condition_fn=lambda: not self._fingerprint_cache and self._check_count > 10,
            fallback=FallbackAction(
                name="empty_fingerprint",
                handler=_empty_fingerprint_fallback,
                description="文件读取持续失败时返回空指纹",
            ),
            priority=10,
        ))

        # 规则 2: 向量存储断路器断开 → 跳过向量化，仅存文本
        def _vector_store_unavailable() -> bool:
            cb = self.get_dependency("vector_store")
            return cb is not None and not cb.is_healthy

        def _skip_vectorization_fallback(params: Dict[str, Any]) -> Dict[str, Any]:
            file_path = params.get("file_path", "")
            return {
                "ok": True,
                "file_path": file_path,
                "digested": True,
                "degraded": True,
                "message": "向量存储不可用，仅存文本块",
            }

        self.add_rule(DegradationRule(
            name="vector_store_degraded",
            condition_fn=_vector_store_unavailable,
            fallback=FallbackAction(
                name="skip_vectorization",
                handler=_skip_vectorization_fallback,
                description="向量存储断路时跳过向量化",
            ),
            priority=20,
        ))

        # 规则 3: embedder_server 断路 → 跳过向量化
        def _embedder_unavailable() -> bool:
            cb = self.get_dependency("embedder_server")
            return cb is not None and not cb.is_healthy

        self.add_rule(DegradationRule(
            name="embedder_degraded",
            condition_fn=_embedder_unavailable,
            fallback=FallbackAction(
                name="skip_embedding",
                handler=_skip_vectorization_fallback,
                description="embedder 断路时跳过向量化",
            ),
            priority=25,
        ))

        # 规则 4: kun_store 断路 → 跳过坤卦存储
        def _kun_store_unavailable() -> bool:
            cb = self.get_dependency("kun_store")
            return cb is not None and not cb.is_healthy

        def _skip_kun_fallback(params: Dict[str, Any]) -> Dict[str, Any]:
            file_path = params.get("file_path", "")
            return {
                "ok": True,
                "file_path": file_path,
                "digested": True,
                "degraded": True,
                "message": "坤卦存储不可用，跳过知识库存储",
            }

        self.add_rule(DegradationRule(
            name="kun_store_degraded",
            condition_fn=_kun_store_unavailable,
            fallback=FallbackAction(
                name="skip_kun_store",
                handler=_skip_kun_fallback,
                description="坤卦断路时跳过知识库存储",
            ),
            priority=30,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """核心推送逻辑

        params:
          - action: "push" | "notify" | "broadcast" | "check_file" | "digest_file" |
                    "digest_and_store" | "batch_digest"
          - file_path: 文件路径（check_file / digest_file / digest_and_store 时必需）
          - message: 推送消息（push 时使用）
          - event: 事件数据（broadcast 时使用）
          - store_in_kun: 是否将消化结果存入坤卦（digest_and_store 时，默认 True）
          - file_paths: 批量文件路径列表（batch_digest 时）
        """
        action = params.get("action", "")

        if action == "check_file":
            file_path = params.get("file_path", "")
            if not file_path:
                raise ValueError("check_file 需要 file_path 参数")
            return self.check_file_changed(file_path)

        if action == "digest_file":
            file_path = params.get("file_path", "")
            if not file_path:
                raise ValueError("digest_file 需要 file_path 参数")
            self.on_file_digested(file_path)
            return {"ok": True, "file_path": file_path}

        if action == "digest_and_store":
            file_path = params.get("file_path", "")
            if not file_path:
                raise ValueError("digest_and_store 需要 file_path 参数")
            store_in_kun = params.get("store_in_kun", True)
            return self.digest_and_store(file_path, store_in_kun=store_in_kun)

        if action == "batch_digest":
            file_paths = params.get("file_paths", [])
            if not file_paths:
                raise ValueError("batch_digest 需要 file_paths 参数")
            store_in_kun = params.get("store_in_kun", True)
            return self.batch_digest(file_paths, store_in_kun=store_in_kun)

        if action == "fingerprint":
            file_path = params.get("file_path", "")
            if not file_path:
                raise ValueError("fingerprint 需要 file_path 参数")
            return self.compute_file_fingerprint(file_path)

        if action == "stats":
            return self.stats()

        if action == "upload_progress":
            return self.track_upload_progress(params)

        if action == "get_progress":
            return self.get_upload_progress(
                params.get("file_path", "")
            )

        # 默认：推送/通知/广播 — Phase 0 占位模式
        message = params.get("message", "")
        event = params.get("event", {})
        logger.info(
            "[%s] 推送请求: action=%s, message=%s, event=%s",
            self.GUA_NAME, action, message, event,
        )
        return {
            "ok": True,
            "action": action,
            "message": message,
            "event": event,
            "timestamp": time.time(),
        }

    # ========================================================================
    # 文件指纹变化检测（从肺迁移）
    # ========================================================================

    def compute_file_fingerprint(self, file_path: str) -> str:
        """计算文件指纹

        使用 MD5 计算文件内容的 hash 作为指纹。
        如果文件不存在或无法读取，返回空字符串。

        Args:
            file_path: 文件路径

        Returns:
            文件内容的 MD5 hash（32 位 hex 字符串），失败时返回 ""
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()
        except FileNotFoundError:
            logger.debug("[%s] 文件不存在，fingerprint='': %s", self.GUA_NAME, file_path)
            return ""
        except PermissionError:
            logger.warning("[%s] 无权限读取文件: %s", self.GUA_NAME, file_path)
            return ""
        except OSError as e:
            logger.warning("[%s] 文件读取失败: %s — %s", self.GUA_NAME, file_path, e)
            return ""
        except Exception as e:  # TODO: Narrow exception type
            logger.error(
                "[%s] compute_file_fingerprint 异常: %s — %s",
                self.GUA_NAME, file_path, e, exc_info=True,
            )
            return ""

    def check_file_changed(self, file_path: str) -> bool:
        """检测文件是否发生变化

        对比当前文件指纹与缓存中的上一轮指纹。
        首次检测（无缓存）时视为有变化。
        每次检测后自动更新指纹缓存（对齐肺的 _inhale 行为）。

        副作用：
          - 更新 _dirty 标记
          - 更新 _fingerprint_cache

        Args:
            file_path: 文件路径

        Returns:
            True 表示文件有变化或首次检测，False 表示无变化
        """
        self._check_count += 1

        current_fp = self.compute_file_fingerprint(file_path)
        cached_fp = self._fingerprint_cache.get(file_path, "")

        # 每次检测都更新指纹缓存（对齐肺的 _inhale → self._last_fingerprint = fingerprint）
        self._fingerprint_cache[file_path] = current_fp

        # 标记脏数据
        if current_fp != cached_fp:
            self._dirty = True
            self._change_count += 1
            logger.info(
                "[%s] 文件已变化: %s (fp: %s... → %s...)",
                self.GUA_NAME, file_path,
                cached_fp[:16] if cached_fp else "<none>",
                current_fp[:16] if current_fp else "<empty>",
            )
            return True

        logger.debug("[%s] 文件无变化: %s", self.GUA_NAME, file_path)
        return False

    def on_file_digested(self, file_path: str) -> None:
        """文件消化完成后更新指纹缓存

        当文件内容已被消费/蒸馏后调用此方法，
        将当前指纹写入缓存，并清除脏标记。

        Args:
            file_path: 文件路径
        """
        current_fp = self.compute_file_fingerprint(file_path)
        self._fingerprint_cache[file_path] = current_fp
        self._dirty = False
        self._digested_count += 1
        logger.info(
            "[%s] 文件已消化，指纹已更新: %s → %s",
            self.GUA_NAME, file_path,
            current_fp[:16] if current_fp else "<empty>",
        )

    # ========================================================================
    # 脏标记管理
    # ========================================================================

    @property
    def is_dirty(self) -> bool:
        """是否有未处理的文件变化"""
        return self._dirty

    def mark_dirty(self) -> None:
        """手动标记为脏（外部触发）"""
        self._dirty = True
        logger.debug("[%s] 脏标记已设置", self.GUA_NAME)

    def clear_dirty(self) -> None:
        """手动清除脏标记"""
        self._dirty = False
        logger.debug("[%s] 脏标记已清除", self.GUA_NAME)

    def invalidate_cache(self, file_path: Optional[str] = None) -> None:
        """使指纹缓存失效

        Args:
            file_path: 指定文件路径，为 None 时清空全部缓存
        """
        if file_path is None:
            self._fingerprint_cache.clear()
            self._dirty = True
            logger.info("[%s] 全部指纹缓存已清除", self.GUA_NAME)
        else:
            self._fingerprint_cache.pop(file_path, None)
            self._dirty = True
            logger.info("[%s] 指纹缓存已清除: %s", self.GUA_NAME, file_path)

    # ========================================================================
    # 统计
    # ========================================================================

    # ========================================================================
    # 端到端消化管线（震卦核心：文件上传→解析→清洗→分块→入库）
    # ========================================================================

    def digest_and_store(
        self,
        file_path: str,
        store_in_kun: bool = True,
    ) -> Dict[str, Any]:
        """端到端文件消化：解析→清洗→分块→向量化→入库

        这是震卦消化管线的端到端入口函数。
        将文件从原始形式经过完整的 ETL pipeline 处理后存入知识库。

        Pipeline 流程:
          1. 检查文件变化（指纹检测）
          2. 解析文件内容 (UnifiedParser)
          3. 清洗文本 (UnifiedCleaner)
          4. 分块 (UnifiedChunker)
          5. 分类 (UnifiedClassifier)
          6. 向量化 (UnifiedEmbedder)
          7. 存储到 SQLite chunks + ChromaDB vector (UnifiedSaver)
          8. 可选：存入坤卦知识库 (KunGua)

        Args:
            file_path: 文件路径
            store_in_kun: 是否同时存入坤卦知识库 (默认 True)

        Returns:
            {
                "ok": True/False,
                "file_path": str,
                "file_hash": str,
                "chunks_count": int,
                "digested": bool,
                "duration_ms": float,
                "errors": [...],
            }
        """
        start_time = time.time()
        errors: List[str] = []
        result: Dict[str, Any] = {
            "ok": False,
            "file_path": file_path,
            "file_hash": "",
            "chunks_count": 0,
            "digested": False,
            "duration_ms": 0,
            "errors": [],
        }

        path = Path(file_path)
        if not path.exists():
            errors.append(f"文件不存在: {file_path}")
            result["errors"] = errors
            return result

        # Step 0: 指纹检测（跳过未变化的文件）
        file_hash = self.compute_file_fingerprint(file_path)
        cached_fp = self._fingerprint_cache.get(file_path, "")
        result["file_hash"] = file_hash

        if file_hash and file_hash == cached_fp and cached_fp:
            logger.info("[%s] 文件未变化，跳过消化: %s", self.GUA_NAME, file_path)
            result["ok"] = True
            result["digested"] = False
            result["duration_ms"] = (time.time() - start_time) * 1000
            result["message"] = "文件未变化，跳过"
            self._check_count += 1
            return result

        try:
            # Step 1: 解析（file_io 断路器保护）
            from src.pipeline.unified import (
                UnifiedParser, UnifiedCleaner, UnifiedChunker,
                UnifiedClassifier, UnifiedEmbedder, UnifiedSaver,
            )
            parser_config = {}
            parser = UnifiedParser(parser_config)

            # 获取 file_io 断路器
            file_io_cb = self.get_dependency("file_io")
            if file_io_cb and not file_io_cb.is_healthy:
                logger.warning("[%s] file_io 断路器断开，跳过文件解析: %s", self.GUA_NAME, file_path)
                errors.append("file_io 断路器断开")
                result["errors"] = errors
                return result

            try:
                parsed = parser.parse(file_path)
                if file_io_cb:
                    file_io_cb.record_success()
            except Exception as e:
                if file_io_cb:
                    file_io_cb.record_failure()
                raise

            raw_text = parsed.get("text", "")
            tables = parsed.get("tables", [])

            if not raw_text.strip():
                errors.append("文件解析结果为空")
                result["errors"] = errors
                return result

            # Step 2: 清洗
            cleaner = UnifiedCleaner({})
            try:
                cleaned = cleaner.clean(parsed)
                cleaned_text = cleaned.get("text", raw_text)
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("[%s] 清洗失败，使用原文: %s", self.GUA_NAME, e)
                cleaned_text = raw_text
                errors.append(f"CleanWarning: {e}")

            # Step 3: 分块
            chunker = UnifiedChunker({})
            try:
                from src.models.chunk import Chunk
                chunks = chunker.chunk(parsed, tables)
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("[%s] 分块失败，降级为单块: %s", self.GUA_NAME, e)
                from src.models.chunk import Chunk
                chunks = [Chunk(text=cleaned_text, chunk_index=0)]
                errors.append(f"ChunkWarning: {e}")

            # Step 4: 分类
            classifier = UnifiedClassifier({})
            for chunk in chunks:
                try:
                    chunk.category = classifier.classify(chunk)
                except Exception:  # TODO: Narrow exception type
                    chunk.category = "通用办公"

            # Step 5: 设置来源信息
            for chunk in chunks:
                chunk.file_hash = file_hash
                chunk.file_name = path.name
                chunk.file_type = path.suffix.lower()
                chunk.source_pipeline = "zhen_digest"
                chunk.source_file = str(path)

            # Step 6: 向量化（embedder_server 断路器保护）
            embedder_cb = self.get_dependency("embedder_server")
            if embedder_cb and not embedder_cb.is_healthy:
                logger.warning("[%s] embedder_server 断路器断开，跳过向量化", self.GUA_NAME)
                errors.append("embedder_server 断路器断开，跳过向量化")
            else:
                try:
                    import asyncio
                    embedder = UnifiedEmbedder({})
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        future = asyncio.ensure_future(
                            embedder.embed_batch([c.text for c in chunks])
                        )
                        # 同步等待（在 async context 中这是合理的）
                        # 如果是纯同步调用，使用 run_until_complete
                    else:
                        embeddings = loop.run_until_complete(
                            embedder.embed_batch([c.text for c in chunks])
                        )
                        if embeddings:
                            for chunk, emb in zip(chunks, embeddings):
                                chunk.embedding = emb
                    if embedder_cb:
                        embedder_cb.record_success()
                except Exception as e:  # TODO: Narrow exception type
                    if embedder_cb:
                        embedder_cb.record_failure()
                    logger.warning("[%s] 向量化失败: %s", self.GUA_NAME, e)
                    errors.append(f"EmbedWarning: {e}")

            # Step 7: 存储到 chunks.db + ChromaDB（vector_store 断路器保护）
            vector_store_cb = self.get_dependency("vector_store")
            if vector_store_cb and not vector_store_cb.is_healthy:
                logger.warning("[%s] vector_store 断路器断开，跳过向量存储", self.GUA_NAME)
                errors.append("vector_store 断路器断开，跳过向量存储")
            else:
                try:
                    import asyncio
                    saver = UnifiedSaver({})
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(saver.save(chunks))
                    else:
                        loop.run_until_complete(saver.save(chunks))
                    logger.info("[%s] 已存储 %d 个 chunk: %s", self.GUA_NAME, len(chunks), file_path)
                    if vector_store_cb:
                        vector_store_cb.record_success()
                except Exception as e:  # TODO: Narrow exception type
                    if vector_store_cb:
                        vector_store_cb.record_failure()
                    logger.error("[%s] 存储失败: %s", self.GUA_NAME, e)
                    errors.append(f"SaveError: {e}")
                    raise

            result["chunks_count"] = len(chunks)
            self._digested_count += 1
            self._fingerprint_cache[file_path] = file_hash
            self._dirty = False

            # Step 8: 存入坤卦知识库（kun_store 断路器保护）
            if store_in_kun:
                kun_store_cb = self.get_dependency("kun_store")
                if kun_store_cb and not kun_store_cb.is_healthy:
                    logger.warning("[%s] kun_store 断路器断开，跳过坤卦存储", self.GUA_NAME)
                    errors.append("kun_store 断路器断开，跳过坤卦存储")
                else:
                    try:
                        self._store_to_kun(file_path, chunks, cleaned_text)
                        if kun_store_cb:
                            kun_store_cb.record_success()
                    except Exception as e:  # TODO: Narrow exception type
                        if kun_store_cb:
                            kun_store_cb.record_failure()
                        logger.warning("[%s] 坤卦存储失败: %s", self.GUA_NAME, e)
                        errors.append(f"KunStoreWarning: {e}")

            result["ok"] = True
            result["digested"] = True
            result["errors"] = errors
            result["duration_ms"] = (time.time() - start_time) * 1000

            logger.info(
                "[%s] 消化完成: %s → %d chunks, %.0fms",
                self.GUA_NAME, file_path, len(chunks), result["duration_ms"],
            )
            return result

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[%s] 消化异常: %s — %s", self.GUA_NAME, file_path, e, exc_info=True)
            errors.append(f"DigestError: {e}")
            result["errors"] = errors
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result

    def batch_digest(
        self,
        file_paths: List[str],
        store_in_kun: bool = True,
    ) -> Dict[str, Any]:
        """批量消化多个文件

        Args:
            file_paths: 文件路径列表
            store_in_kun: 是否存入坤卦知识库

        Returns:
            {
                "ok": True,
                "total_files": int,
                "digested": int,
                "skipped": int,
                "failed": int,
                "results": [...],
            }
        """
        results = []
        digested = 0
        skipped = 0
        failed = 0

        for fp in file_paths:
            r = self.digest_and_store(fp, store_in_kun=store_in_kun)
            results.append(r)
            if r.get("digested"):
                digested += 1
            elif r.get("ok"):
                skipped += 1
            else:
                failed += 1

        return {
            "ok": failed == 0,
            "total_files": len(file_paths),
            "digested": digested,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }

    def _store_to_kun(
        self,
        file_path: str,
        chunks: list,
        cleaned_text: str,
    ) -> None:
        """将消化结果存入坤卦知识库

        调用坤卦的 store_vector / store_wiki / build_knowledge_graph
        建立完整的知识存储链路。

        Args:
            file_path: 源文件路径
            chunks: 分块列表
            cleaned_text: 清洗后的文本
        """
        try:
            from src.bagua.kun import KunGua

            # 从全局上下文获取坤卦实例，或创建新实例
            kun = _get_kun_instance()
            if kun is None:
                logger.warning("[%s] 坤卦实例不可用，跳过知识库存储", self.GUA_NAME)
                return

            file_name = Path(file_path).name
            file_hash = self.compute_file_fingerprint(file_path)
            doc_id = file_hash[:16] if file_hash else file_name

            # 1. 存储向量
            vectorized_chunks = [c for c in chunks if hasattr(c, 'embedding') and c.embedding]
            if vectorized_chunks:
                kun.store_vector(
                    doc_id=doc_id,
                    chunks=vectorized_chunks,
                    metadata={
                        "source_file": file_path,
                        "file_name": file_name,
                        "file_hash": file_hash,
                    },
                )

            # 2. 存储 Wiki
            kun.store_wiki(
                doc_id=doc_id,
                content=cleaned_text,
                title=file_name,
                source=file_path,
                category=chunks[0].category if chunks else "通用办公",
            )

            # 3. 构建知识图谱
            kun.build_knowledge_graph(doc_id=doc_id)

            logger.info("[%s] 坤卦知识库已更新: %s", self.GUA_NAME, doc_id)

        except Exception as e:  # TODO: Narrow exception type
            logger.warning("[%s] _store_to_kun 异常: %s", self.GUA_NAME, e)

    # ========================================================================
    # 上传进度跟踪
    # ========================================================================

    def track_upload_progress(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """记录大文件上传进度

        由调用方在上传过程中定期调用，更新指定文件的进度。
        进度数据写入 in-memory dict，由 get_upload_progress 查询。

        Args:
            params: {
                "file_path": str,   # 文件路径/标识
                "progress": float,  # 进度 [0.0, 1.0]
                "status": str,      # "uploading"|"processing"|"done"|"error"
                "message": str,     # 附带信息
            }

        Returns:
            {"ok": bool, "file_path": str, "progress": float}
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return {"ok": False, "error": "缺少 file_path"}

        if not hasattr(self, "_upload_progress"):
            self._upload_progress: Dict[str, Dict[str, Any]] = {}

        progress = max(0.0, min(1.0, float(params.get("progress", 0))))
        self._upload_progress[file_path] = {
            "progress": progress,
            "status": params.get("status", "uploading"),
            "message": params.get("message", ""),
            "updated_at": time.time(),
        }

        # 广播进度变化（通过 IntentBus 通知兑卦）
        try:
            self._broadcast_progress(file_path, progress,
                                     params.get("status", ""),
                                     params.get("message", ""))
        except Exception:  # TODO: Narrow exception type
            pass

        return {
            "ok": True,
            "file_path": file_path,
            "progress": round(progress, 4),
        }

    def get_upload_progress(self, file_path: str) -> Dict[str, Any]:
        """查询文件的上传进度

        Args:
            file_path: 文件路径/标识

        Returns:
            {"progress": float, "status": str, ...} 或 {"error": "not_found"}
        """
        if not hasattr(self, "_upload_progress"):
            return {"error": "not_found", "message": "无上传记录"}

        entry = self._upload_progress.get(file_path)
        if entry is None:
            return {"error": "not_found", "message": f"未找到文件: {file_path}"}

        return dict(entry)

    def _broadcast_progress(
        self, file_path: str, progress: float, status: str, message: str
    ) -> None:
        """通过 IntentBus 广播进度信号到兑卦"""
        try:
            self._intent_bus.send_progress(
                session_id="upload",
                source="震",
                target="兑",
                progress=progress,
                message=f"{file_path}: {status} — {message}"[:100],
            )
        except Exception:  # TODO: Narrow exception type
            pass

    def stats(self) -> Dict[str, Any]:
        """返回震卦运行统计"""
        return {
            "gua": self.GUA_NAME,
            "emoji": self.GUA_EMOJI,
            "dirty": self._dirty,
            "cached_files": len(self._fingerprint_cache),
            "check_count": self._check_count,
            "change_count": self._change_count,
            "digested_count": self._digested_count,
            "health": self._health.value,
            "uptime_sec": round(self.uptime_sec, 1),
        }


# ============================================================================
# 全局坤卦实例缓存（避免重复创建）
# ============================================================================

_kun_instance: Optional[Any] = None


def _get_kun_instance():
    """获取或创建坤卦实例"""
    global _kun_instance
    if _kun_instance is None:
        try:
            from src.bagua.kun import KunGua
            _kun_instance = KunGua()
            _kun_instance.start()
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("坤卦实例创建失败: %s", e)
            return None
    return _kun_instance


__all__ = ["ZhenGua"]
