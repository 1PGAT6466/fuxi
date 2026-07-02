"""
services/wiki_engine.py — LLM-Wiki 引擎（Phase 2 核心）

核心理念：
  碎片 Chunk → 检索「最像的片断」
  LLM-Wiki → 检索「最懂的知识点」

架构：
  1. Wiki 页面 = 一个知识主题的完整结构化页面
     - 标题、摘要、正文、表格、引用链接
     - 每个页面 500-3000 字（大幅超越碎片 Chunk 的 200-800 字）
  2. 索引策略
     - 页面摘要（200 字）入 ChromaDB 做向量召回
     - 页面全文入 SQLite，检索命中后全文注入 LLM 上下文
  3. 生成流程
     - 用户 query → 检索 Top 3 Wiki 页面摘要
     - 展开完整页面内容（结构化 Markdown）
     - 注入 LLM 生成最终答案

与传统 Chunk 检索的对比：

| 维度 | 碎片 Chunk | LLM-Wiki |
|------|-----------|----------|
| 单条信息量 | 200-800 字 | 500-3000 字 |
| 结构化程度 | 纯文本片断 | Markdown 标题/表格/列表 |
| 知识完整性 | 断章取义 | 主题闭环 |
| 幻觉风险 | 高（缺少上下文） | 低（页面包含完整上下文） |
| 更新方式 | 重新分词 | 编辑 Markdown 页面 |
| 可审计性 | 难追踪来源 | 页面级溯源 |

Wiki 页面结构：
  {
    "id": "wiki_001",
    "title": "PA66 工程塑料",
    "category": "机械设计 > 材料",
    "tags": ["PA66", "尼龙", "工程塑料", "机械性能"],
    "summary": "PA66（聚酰胺66）是一种热塑性工程塑料...（200字）",
    "content": "# PA66 工程塑料\n\n## 基本信息\n...（完整 Markdown）",
    "sources": ["file_hash_xxx", "file_hash_yyy"],
    "version": 1,
    "updated_at": "2026-06-09",
    "quality_score": 0.85
  }
"""
import json, time, os, re
from pathlib import Path
from typing import List, Dict, Optional
import sqlite3
import chromadb
from chromadb.config import Settings as _ChromaSettings
import logging; logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
from src.config import WORLDTREE_DB_PATH
WIKI_DB = WORLDTREE_DB_PATH  # P2-4: merged
WIKI_CHROMA_COLLECTION = "wiki_pages"  # 只存摘要向量




def _safe_float(value, default=0.5):
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
def _safe_json_parse(value, default=None):
    """Safely parse a value that might be JSON string, comma-separated string, or None."""
    if value is None:
        return default or []
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return default or []
    value = value.strip()
    if not value:
        return default or []
    # Try JSON first
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        pass
    # Try comma-separated
    if "," in value:
        return [t.strip() for t in value.split(",") if t.strip()]
    return [value]


class WikiEngine:
    """LLM-Wiki 存储与检索引擎"""
    
    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or WIKI_DB)
        self._init_db()
        self._wiki_collection = None
        try:
            import os
            _cdir = os.path.join(str(DATA_DIR), "chroma_wiki")
            os.makedirs(_cdir, exist_ok=True)
            _cli = chromadb.PersistentClient(path=_cdir, settings=_ChromaSettings(anonymized_telemetry=False))
            self._wiki_collection = _cli.get_or_create_collection(name="wiki_summaries", metadata={"hnsw:space": "cosine"})
        except Exception:
            logger.warning(f"[wiki] suppressed exception", exc_info=True)
            pass
    
    def _init_db(self):
        """初始化 SQLite 表"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wiki_pages (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                summary TEXT DEFAULT '',
                content TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                version INTEGER DEFAULT 1,
                quality_score REAL DEFAULT 0.5,
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wiki_cross_links (
                from_id TEXT,
                to_id TEXT,
                link_type TEXT DEFAULT 'related',
                PRIMARY KEY (from_id, to_id)
            )
        """)
        conn.commit()
        conn.close()
    
    def create_page(self, title: str, content: str, category: str = "", 
                    tags: list = None, sources: list = None, summary: str = "") -> str:
        """创建 Wiki 页面"""
        page_id = f"wiki_{int(time.time()*1000)}"
        now = time.strftime("%Y-%m-%d %H:%M")
        
        if not summary:
            summary = self._generate_summary(content)
        
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """INSERT OR REPLACE INTO wiki_pages 
               (id, title, category, tags, summary, content, sources, version, quality_score, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (page_id, title, category, json.dumps(tags or []), 
             summary, content, json.dumps(sources or []), 
             1, 0.7, now, now)
        )
        conn.commit()
        conn.close()
        return page_id
    
    def update_page(self, page_id: str, content: str = None, summary: str = None,
                    quality_score: float = None) -> bool:
        """更新 Wiki 页面"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute("SELECT * FROM wiki_pages WHERE id = ?", (page_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        
        updates = {"updated_at": time.strftime("%Y-%m-%d %H:%M")}
        if content:
            updates["content"] = content
            if not summary:
                summary = self._generate_summary(content)
        if summary:
            updates["summary"] = summary
        if quality_score is not None:
            updates["quality_score"] = quality_score
        
        # P2: Record version history before update
        try:
            conn.execute(
                "INSERT INTO wiki_history (page_id, version, content_snapshot, summary_snapshot, changed_at, source) VALUES (?, ?, ?, ?, ?, ?)",
                (page_id, row[7] if len(row) > 7 else 1, row[5] if len(row) > 5 else "", row[4] if len(row) > 4 else "", updates.get("updated_at", ""), "manual_update")
            )
        except Exception:
            logger.warning(f"[wiki] suppressed exception", exc_info=True)
            pass
        
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [page_id]
        conn.execute(f"UPDATE wiki_pages SET {set_clause} WHERE id=?", values)
        conn.commit()
        conn.close()
        return True
    
    def get_page(self, page_id: str) -> Optional[Dict]:
        """获取单个 Wiki 页面"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute("SELECT * FROM wiki_pages WHERE id = ?", (page_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_dict(row)
    
    def delete_page(self, page_id: str) -> bool:
        """删除 Wiki 页面"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute("DELETE FROM wiki_pages WHERE id = ?", (page_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def search_by_title(self, query: str, limit: int = 5) -> list:
        """按标题关键词搜索"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        keywords = query.split()
        if not keywords:
            conn.close()
            return []
        conditions = " OR ".join(["title LIKE ?" for _ in keywords[:5]])
        params = [f"%{kw}%" for kw in keywords[:5]]
        cur = conn.execute(
            f"SELECT * FROM wiki_pages WHERE {conditions} ORDER BY quality_score DESC LIMIT ?",
            params + [limit]
        )
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search_content(self, query: str, limit: int = 5) -> list:
        """全文搜索 Wiki 内容（标题 + 正文 + 标签）"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        keywords = [kw.strip() for kw in query.split() if len(kw.strip()) >= 1][:5]
        if not keywords:
            conn.close()
            return []
        title_conds = " OR ".join(["title LIKE ?" for _ in keywords])
        content_conds = " OR ".join(["content LIKE ?" for _ in keywords])
        tag_conds = " OR ".join(["tags LIKE ?" for _ in keywords])
        sql = f"""SELECT * FROM wiki_pages WHERE
            ({title_conds}) OR ({content_conds}) OR ({tag_conds})
            ORDER BY quality_score DESC LIMIT ?"""
        params = [f"%{kw}%" for kw in keywords] * 3
        cur = conn.execute(sql, params + [limit])
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search_by_tag(self, tag: str, limit: int = 10) -> list:
        """按标签搜索"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute(
            "SELECT * FROM wiki_pages WHERE tags LIKE ? ORDER BY quality_score DESC LIMIT ?",
            (f"%{tag}%", limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]
    
    def list_pages(self, category: str = "", limit: int = 50) -> list:
        """列出页面"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        if category:
            cur = conn.execute(
                "SELECT * FROM wiki_pages WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category, limit)
            )
        else:
            cur = conn.execute(
                "SELECT * FROM wiki_pages ORDER BY quality_score DESC LIMIT ?",
                (limit,)
            )
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]
    
    def get_summaries_for_indexing(self) -> list:
        """获取所有页面的摘要（用于向量索引）"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute("SELECT id, title, summary, category, tags FROM wiki_pages")
        rows = cur.fetchall()
        conn.close()
        return [{"id": r[0], "title": r[1], "summary": r[2], 
                 "category": r[3], "tags": json.loads(r[4] or "[]")} for r in rows]
    
    def get_full_content(self, page_ids: List[str]) -> List[Dict]:
        """获取页面完整内容（用于注入 LLM）"""
        if not page_ids:
            return []
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        placeholders = ",".join(["?" for _ in page_ids])
        cur = conn.execute(
            f"SELECT id, title, content, category, sources FROM wiki_pages WHERE id IN ({placeholders})",
            page_ids
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "content": r[2], 
             "category": r[3], "sources": json.loads(r[4] or "[]")}
            for r in rows
        ]
    
    def add_cross_link(self, from_id: str, to_id: str, link_type: str = "related"):
        """添加页面间交叉引用"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            "INSERT OR REPLACE INTO wiki_cross_links VALUES (?, ?, ?)",
            (from_id, to_id, link_type)
        )
        conn.commit()
        conn.close()
    
    def get_linked_pages(self, page_id: str) -> list:
        """获取关联页面"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute(
            "SELECT to_id, link_type FROM wiki_cross_links WHERE from_id = ?",
            (page_id,)
        )
        links = cur.fetchall()
        result = []
        for to_id, ltype in links:
            page = self.get_page(to_id)
            if page:
                page["link_type"] = ltype
                result.append(page)
        conn.close()
        return result
    
    def _generate_summary(self, content: str, max_chars: int = 200) -> str:
        """自动生成摘要（取前 N 个字符的完整句子）"""
        # 去除 Markdown 标记
        clean = re.sub(r'[#*`\[\]()\|]', '', content[:500])
        # 取前 max_chars 个字符，截断到最后一个句号
        if len(clean) <= max_chars:
            return clean.strip()
        truncated = clean[:max_chars]
        last_period = max(truncated.rfind('。'), truncated.rfind('.'), truncated.rfind('\n'))
        if last_period > max_chars // 2:
            return truncated[:last_period+1].strip()
        return truncated.strip() + '...'
    
    def sync_vectors(self):
        """Sync all wiki page summaries into ChromaDB vectors"""
        if not self._wiki_collection:
            return {"ok": False, "error": "ChromaDB not available"}
        pages = self.list_pages(limit=2000)
        if not pages:
            return {"ok": True, "synced": 0, "message": "no pages"}
        try:
            import requests
            from src.db.vector_store import EMBEDDER_URL
            summaries = [p.get("summary", "")[:200] or p.get("title", "")[:50] for p in pages]
            ids_list = [p["id"] for p in pages]
            vectors = None
            try:
                r = requests.post(f"{EMBEDDER_URL}/embed", json={"texts": summaries}, timeout=60)
                if r.status_code == 200:
                    vectors = r.json().get("vectors")
            except Exception:
                logger.warning(f"[wiki] suppressed exception", exc_info=True)
                pass
            if not vectors or len(vectors) != len(ids_list):
                return {"ok": False, "error": "embedding mismatch"}
            try:
                old = self._wiki_collection.get(include=[])
                if old and old.get("ids"):
                    self._wiki_collection.delete(ids=old["ids"])
            except Exception:
                logger.warning(f"[wiki] suppressed exception", exc_info=True)
                pass
            metadatas = [{
                "wiki_id": p["id"],
                "title": p.get("title", "")[:100],
                "category": p.get("category", "")[:50],
                "quality_score": _safe_float(p.get("quality_score"), 0.5)
            } for p in pages]
            self._wiki_collection.add(ids=ids_list, embeddings=vectors, metadatas=metadatas)
            return {"ok": True, "synced": len(pages), "collection_count": self._wiki_collection.count()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def vector_search_wiki(self, query_embedding, top_k=5):
        """Vector search wiki summaries"""
        if not self._wiki_collection or self._wiki_collection.count() == 0:
            return []
        try:
            results = self._wiki_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["metadatas", "distances"]
            )
            if not results or not results.get("ids") or not results["ids"][0]:
                return []
            out = []
            for i, wid in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if i < len(results["metadatas"][0]) else {}
                dist = results["distances"][0][i] if i < len(results["distances"][0]) else 0
                sim = 1.0 - float(dist)
                if sim > 0.15:
                    out.append({
                        "wiki_id": wid,
                        "title": meta.get("title", ""),
                        "category": meta.get("category", ""),
                        "similarity": round(sim, 4)
                    })
            return out
        except Exception:
            return []

    
    def _row_to_dict(self, row) -> dict:
        """SQLite row → dict"""
        columns = ["id", "title", "category", "tags", "summary", "content",
                    "sources", "version", "quality_score", "created_at", "updated_at"]
        d = dict(zip(columns, row))
        d["tags"] = _safe_json_parse(d.get("tags") or "[]" or "[]", default=[])
        d["sources"] = _safe_json_parse(d.get("sources") or "[]" or "[]", default=[])
        return d
    
    def generate_from_chunks(self, topic: str, chunks: List[Dict], 
                              llm_endpoint: str = None) -> Optional[str]:
        """从检索到的 chunks 自底向上生成 Wiki 页面
        
        这需要 LLM 能力。在没有 LLM 时，退化为模板聚合。
        """
        if not chunks:
            return None
        
        # 模板聚合模式（无 LLM 依赖）
        texts = [c.get("text", "") for c in chunks if c.get("text")]
        source_files = list(set(c.get("file_name", "") for c in chunks))
        
        combined = "\n\n".join(texts[:5])
        summary = self._generate_summary(combined, 200)
        
        content = f"# {topic}\n\n"
        content += f"## 摘要\n{summary}\n\n"
        content += f"## 知识来源\n"
        for f in source_files[:10]:
            content += f"- {f}\n"
        content += f"\n## 原始内容\n{combined}"
        
        return content


# 全局单例
_wiki_engine: Optional[WikiEngine] = None


def get_wiki_engine() -> WikiEngine:
    global _wiki_engine
    if _wiki_engine is None:
        _wiki_engine = WikiEngine()
    return _wiki_engine

def sync_wiki_vectors():
    eng = get_wiki_engine()
    return eng.sync_vectors()
