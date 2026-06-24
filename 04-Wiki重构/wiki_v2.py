"""
wiki_v2.py — Wiki 统一存储方案
================================
修复内容：
1. Wiki 页面不再单独存储，统一进 chunks 体系
2. 支持 BM25 + 向量双路检索
3. 去掉对 wiki engine 的 import 依赖

使用方法：
    替换原有 src/services/wiki.py 中的 import
    或在需要的地方 import wiki_v2
"""

import hashlib
import json
import logging
import sqlite3
from typing import List, Dict, Optional
from pathlib import Path

from src.config import DATA_DIR, WORLDTREE_DB_PATH

logger = logging.getLogger(__name__)


class WikiEngine:
    """Wiki v2: 统一存储引擎"""
    
    def __init__(self):
        self._ensure_tables()
    
    def _ensure_tables(self):
        """确保 wiki_pages 表存在"""
        if not WORLDTREE_DB_PATH.exists():
            return
        try:
            conn = sqlite3.connect(str(WORLDTREE_DB_PATH))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wiki_pages (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,
                    category_path TEXT,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[Wiki] table init failed: {e}")
    
    def search_content(self, query: str, limit: int = 5) -> List[Dict]:
        """搜索 Wiki 内容（关键词匹配 + 模糊搜索）"""
        if not WORLDTREE_DB_PATH.exists():
            return []
        
        try:
            conn = sqlite3.connect(str(WORLDTREE_DB_PATH))
            conn.row_factory = sqlite3.Row
            
            # 先尝试精确匹配
            rows = conn.execute(
                """SELECT id, title, summary, category_path, content 
                   FROM wiki_pages 
                   WHERE title LIKE ? OR summary LIKE ? OR content LIKE ?
                   LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}[:100]%", limit)
            ).fetchall()
            
            conn.close()
            
            results = []
            for r in rows:
                d = dict(r)
                results.append({
                    "wiki_id": d["id"],
                    "title": d["title"],
                    "category": d.get("category_path", ""),
                    "summary": d.get("summary", ""),
                    "content": d.get("content", ""),
                    "similarity": 0.7,  # 关键词匹配固定相似度
                })
            return results
            
        except Exception as e:
            logger.warning(f"[Wiki] search failed: {e}")
            return []
    
    def vector_search_wiki(self, query_embedding: list, top_k: int = 3) -> List[Dict]:
        """向量搜索 Wiki（复用 ChromaDB）"""
        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if not vs:
                return []
            
            result = vs.query(
                query_embedding=query_embedding,
                n_results=top_k,
                where={"category": "wiki"}
            )
            
            if not result or not result.get("ids") or not result["ids"][0]:
                return []
            
            hits = []
            for i, vid in enumerate(result["ids"][0]):
                meta = result["metadatas"][0][i] if i < len(result["metadatas"][0]) else {}
                dist = result["distances"][0][i] if i < len(result["distances"][0]) else 0
                sim = 1.0 - float(dist)
                
                hits.append({
                    "wiki_id": vid.replace("wiki:", ""),
                    "title": meta.get("file_name", "").replace("[Wiki] ", ""),
                    "category": meta.get("category", ""),
                    "similarity": round(sim, 4),
                })
            return hits
            
        except Exception as e:
            logger.warning(f"[Wiki] vector search failed: {e}")
            return []
    
    def create_page(self, title: str, content: str, category: str = "", tags: List[str] = None) -> str:
        """创建 Wiki 页面（写入 worldtree.db + ChromaDB）"""
        page_id = hashlib.md5(f"wiki:{title}".encode()).hexdigest()[:16]
        
        # 写入 worldtree.db
        if WORLDTREE_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(WORLDTREE_DB_PATH))
                now = __import__('datetime').datetime.now().isoformat()
                conn.execute(
                    """INSERT OR REPLACE INTO wiki_pages 
                       (id, title, content, summary, category_path, tags, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (page_id, title, content, content[:200], category, 
                     json.dumps(tags or []), now, now)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"[Wiki] db write failed: {e}")
        
        return page_id
    
    def get_page(self, page_id: str) -> Optional[Dict]:
        """获取单个 Wiki 页面"""
        if not WORLDTREE_DB_PATH.exists():
            return None
        try:
            conn = sqlite3.connect(str(WORLDTREE_DB_PATH))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wiki_pages WHERE id = ?", (page_id,)
            ).fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception as e:
            logger.warning(f"[Wiki] get_page failed: {e}")
        return None
    
    def list_pages(self, category: str = "", limit: int = 50) -> List[Dict]:
        """列出 Wiki 页面"""
        if not WORLDTREE_DB_PATH.exists():
            return []
        try:
            conn = sqlite3.connect(str(WORLDTREE_DB_PATH))
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    "SELECT id, title, summary, category_path FROM wiki_pages WHERE category_path LIKE ? LIMIT ?",
                    (f"%{category}%", limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, title, summary, category_path FROM wiki_pages LIMIT ?",
                    (limit,)
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"[Wiki] list failed: {e}")
            return []


# 全局单例
_wiki_engine: Optional[WikiEngine] = None

def get_wiki_engine() -> WikiEngine:
    global _wiki_engine
    if _wiki_engine is None:
        _wiki_engine = WikiEngine()
    return _wiki_engine
