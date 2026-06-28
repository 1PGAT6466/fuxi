"""
yggdrasil-server — 向量存储层
===============================
ChromaDB 封装：增删查 + 故障自愈 + 批量嵌入代理

设计原则:
- 每个写操作返回 bool 表示成功/失败，调用方据此决策
- query 失败时区别于"真的无结果"
- 自动重连：_collection 失效时惰性重建
"""
import os
import logging
from typing import Optional, List, Dict, Any

import aiohttp
import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# ============ 配置 ============
EMBEDDER_URL = os.getenv("KB_EMBEDDER_URL", "http://127.0.0.1:8081")
CHROMA_DIR = os.getenv("KB_CHROMA_DIR", "data/chromadb")
COLLECTION_NAME = "kb_chunks"

# ============ 自愈阈值 ============
MAX_CONSECUTIVE_FAILS = 3  # 连续失败超过此数触发重建

# ============ VectorStore ============

class VectorStore:
    """ChromaDB 向量存储封装，带自愈能力"""

    def __init__(self, db_dir: str = "data", collection_name: str = COLLECTION_NAME):
        self.db_dir = db_dir
        self.collection_name = collection_name
        self._fail_count = 0
        persist_dir = os.path.join(db_dir, "chroma")
        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:M": 32,
                "hnsw:construction_ef": 200,
                "hnsw:search_ef": 100,
            },
            embedding_function=None,
        )
        self._usable = True

    # ---------- 内部 ----------

    def _reset_connection(self) -> bool:
        """惰性重建 collection 引用（ChromaDB 进程重启后恢复）"""
        try:
            persist_dir = os.path.join(self.db_dir, "chroma")
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_collection(self.collection_name)
            self._fail_count = 0
            self._usable = True
            logger.info(f"VectorStore: reconnected to collection '{self.collection_name}'")
            return True
        except Exception:
            logger.error(
                f"VectorStore: failed to reconnect to '{self.collection_name}'",
                exc_info=True,
            )
            return False

    def _mark_failure(self) -> None:
        """记录一次失败，达到阈值触发自愈"""
        self._fail_count += 1
        if self._fail_count >= MAX_CONSECUTIVE_FAILS:
            logger.warning(
                f"VectorStore: {self._fail_count} consecutive failures, triggering reconnect..."
            )
            self._reset_connection()

    def _mark_success(self) -> None:
        """成功调用时重置失败计数器"""
        if self._fail_count > 0:
            self._fail_count = 0

    def _clean_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """清洗元数据为 ChromaDB 原生类型，截断超长字符串"""
        clean: Dict[str, Any] = {}
        for k, v in meta.items():
            if isinstance(v, str) and len(v) > 1000:
                clean[k] = v[:1000]
            elif isinstance(v, (str, int, float, bool)):
                clean[k] = v
            else:
                clean[k] = str(v)[:500]
        return clean

    # ---------- 公开 API ----------

    @property
    def count(self) -> int:
        """向量数量（-1 表示故障不可用）"""
        try:
            c = self._collection.count()
            self._mark_success()
            return c
        except Exception:
            self._mark_failure()
            return -1

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]],
        documents: list = None,
    ) -> bool:
        """批量写入向量

        Returns:
            True 写入成功；False 写入失败
        """
        if not ids or not embeddings:
            return False
        try:
            clean_metas = [self._clean_metadata(m) for m in metadata]
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=clean_metas,
                documents=documents,
            )
            self._mark_success()
            return True
        except Exception:
            logger.error(f"VectorStore.add({len(ids)} ids) failed", exc_info=True)
            self._mark_failure()
            return False

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """向量检索

        Returns:
            {"ids": [...], "distances": [...], ...} 成功
            {"error": True, "reason": str} 失败（区别于空结果）
        """
        try:
            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["metadatas", "distances", "documents"],
            )
            self._mark_success()
            return result
        except Exception:
            logger.error(
                f"VectorStore.query(n={n_results}) failed", exc_info=True
            )
            self._mark_failure()
            return {"error": True, "reason": "ChromaDB query failed"}

    def upsert(
        self,
        target_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str = None,
    ) -> bool:
        """更新/插入单条向量

        Returns:
            True 成功；False 失败
        """
        try:
            clean = self._clean_metadata(metadata)
            self._collection.upsert(
                ids=[target_id],
                embeddings=[embedding],
                metadatas=[clean],
                documents=[document] if document else None,
            )
            self._mark_success()
            return True
        except Exception:
            logger.error(
                f"VectorStore.upsert({target_id}) failed", exc_info=True
            )
            self._mark_failure()
            return False

    def delete_by_file(self, file_hash: str) -> bool:
        """按文件哈希删除所有关联向量

        Returns:
            True 成功（包括无数据时）；False 操作失败
        """
        try:
            results = self._collection.get(
                where={"file_hash": file_hash}, include=[]
            )
            removed = 0
            if results and results.get("ids"):
                ids = results["ids"]
                removed = len(ids)
                self._collection.delete(ids=ids)
            self._mark_success()
            if removed:
                logger.debug(f"VectorStore: deleted {removed} vectors for {file_hash}")
            return True
        except Exception:
            logger.error(
                f"VectorStore.delete_by_file({file_hash}) failed", exc_info=True
            )
            self._mark_failure()
            return False

    # 兼容旧接口
    persist = lambda self: None

    def count_chunks(self) -> int:
        return self.count


# ============ 全局单例 ============

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> Optional[VectorStore]:
    """获取全局 VectorStore 单例。返回 None 表示初始化失败（ChromaDB 不可用）"""
    global _vector_store
    if _vector_store is None:
        try:
            _vector_store = VectorStore()
        except Exception:
            logger.error("VectorStore: init failed", exc_info=True)
            return None
    return _vector_store


# ============ 批量嵌入代理 ============

async def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """调用外部 embedder 服务做批量文本嵌入

    Returns:
        向量列表（成功）或 None（服务不可用）
    """
    if not texts:
        return None
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{EMBEDDER_URL}/embed",
                json={"texts": texts},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    vectors = data.get("vectors")
                    if vectors:
                        logger.debug(f"embed_texts: got {len(vectors)} vectors")
                        return vectors
                    logger.warning("embed_texts: no vectors in response")
                    return None
                logger.warning(f"embed_texts: HTTP {resp.status}")
                return None
    except aiohttp.ClientError as e:
        logger.warning(f"embed_texts: embedder unreachable — {e}")
        return None
    except Exception:
        logger.error("embed_texts: unexpected error", exc_info=True)
        return None
