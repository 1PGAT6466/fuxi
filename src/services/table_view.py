"""
table_view.py — Multi-View RAG 表格视图 v2 (RAG 3.0+)
独立表格检索引擎：入库预计算向量 → ChromaDB kb_tables 集合 → 查询直读

v2 升级:
  - 入库时预计算表格向量，存入独立 ChromaDB collection "kb_tables"
  - 检索时直接从 ChromaDB 查，不再实时遍历所有 chunk
  - 结果标记 result_type: "table" 供前端特殊渲染
  - LLM 修复兜底：表格质量差时调 LLM 纠正
"""
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Markdown 表格模式
_TABLE_ROW = re.compile(r'^\|.+\|$')
_TABLE_SEP = re.compile(r'^\|[\s\-:]+\|$')

# ChromaDB 表格集合名
TABLE_COLLECTION = "kb_tables"


def extract_tables_from_text(text: str) -> list:
    """从文本中提取所有 Markdown 表格"""
    if not text:
        return []
    
    lines = text.split('\n')
    tables = []
    in_table = False
    table_lines = []
    
    for line in lines:
        stripped = line.strip()
        if _TABLE_ROW.match(stripped):
            if not in_table:
                in_table = True
                table_lines = [stripped]
            else:
                table_lines.append(stripped)
        elif _TABLE_SEP.match(stripped) and in_table and len(table_lines) == 1:
            table_lines.append(stripped)
        else:
            if in_table and len(table_lines) >= 2:
                tables.append('\n'.join(table_lines))
            in_table = False
            table_lines = []
    
    if in_table and len(table_lines) >= 2:
        tables.append('\n'.join(table_lines))
    
    return tables


def _table_to_search_text(table: str) -> str:
    """将表格转为可检索的文本（表头 + 前 3 行数据）"""
    rows = [r for r in table.split('\n') if _TABLE_ROW.match(r.strip()) and not _TABLE_SEP.match(r.strip())]
    header = rows[0] if rows else ""
    data = rows[1:4] if len(rows) > 1 else []
    
    parts = [header]
    parts.extend(data)
    return ' | '.join(parts)


def _table_quality_score(table: str) -> float:
    """评估表格质量 (0-1)，低于 0.4 建议 LLM 修复"""
    if not table:
        return 0.0
    rows = [r for r in table.split('\n') if _TABLE_ROW.match(r.strip())]
    if len(rows) < 2:
        return 0.0
    
    score = 0.0
    # 列数是否一致
    col_counts = [len([c.strip() for c in r.split('|') if c.strip()]) for r in rows if not _TABLE_SEP.match(r.strip())]
    if col_counts and len(set(col_counts)) == 1:
        score += 0.4
    
    # 有表头分隔线
    if _TABLE_SEP.match(rows[1].strip()) if len(rows) > 1 else False:
        score += 0.3
    
    # 非空单元格比例
    total_cells = sum(len([c.strip() for c in r.split('|') if c.strip()]) for r in rows)
    non_empty = sum(1 for c in '|'.join(rows).split('|') if c.strip() and c.strip() != '-')
    if total_cells > 0:
        score += (non_empty / max(total_cells, 1)) * 0.3
    
    return min(score, 1.0)


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def _llm_fix_table(bad_table: str, context: str = "") -> Optional[str]:
    """LLM 修复低质量表格"""
    prompt = f"""你是一个表格修复专家。下面是一段从 PDF 中提取的表格文本，可能格式混乱、列错位、合并单元格被拆散。

请将它修复为标准 Markdown 表格格式：
- 第一行是表头
- 第二行是分隔线 |---|---|
- 每行列数一致
- 保留原始数据，不要编造

上下文（表格所在段落）：
{context[:500]}

原始表格文本：
{bad_table[:1000]}

只输出修复后的 Markdown 表格，不要加任何说明。"""
    
    try:
        from src.services.llm import call_ai_raw
        result = call_ai_raw(prompt)
        if result and '|' in result:
            return result.strip()
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"[TableView] LLM fix failed: {e}")
    return None


def get_table_store():
    """获取或创建 kb_tables ChromaDB collection"""
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    import os
    from src.data_service import get_chroma_dir
    
    persist_dir = get_chroma_dir()
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=TABLE_COLLECTION,
        metadata={
            "hnsw:space": "cosine",
            "hnsw:M": 16,
            "hnsw:construction_ef": 100,
            "hnsw:search_ef": 50,
        }
    )


async def index_tables_from_chunks(chunks: list, clear_first: bool = True) -> Dict:
    """入库：从 chunks 提取表格 → 向量化 → 存入 kb_tables 集合"""
    if not chunks:
        return {"tables_indexed": 0, "errors": []}
    
    from src.db.vector_store import embed_texts
    
    # 1. 提取所有表格
    table_entries = []
    for c in chunks:
        text = c.get("text", "")
        tables = extract_tables_from_text(text)
        for t in tables:
            if len(t) < 30:
                continue
            quality = _table_quality_score(t)
            # 低质量表格尝试 LLM 修复
            if quality < 0.4:
                fixed = await _llm_fix_table(t, text[:300])
                if fixed and _table_quality_score(fixed) > quality:
                    t = fixed
                    quality = _table_quality_score(fixed)
            
            search_text = _table_to_search_text(t)
            table_entries.append({
                "file_hash": c.get("file_hash", ""),
                "file_name": c.get("file_name", ""),
                "category": c.get("category", ""),
                "chunk_index": c.get("chunk_index", 0),
                "table_text": t,
                "search_text": search_text[:500],
                "quality": quality,
            })
    
    if not table_entries:
        return {"tables_indexed": 0, "note": "no tables found"}
    
    logger.info(f"[TableView] Indexing {len(table_entries)} tables into ChromaDB...")
    
    # 2. 获取 kb_tables collection
    try:
        collection = get_table_store()
        if clear_first:
            # 清空旧数据
            try:
                existing = collection.get()
                if existing and existing.get("ids"):
                    collection.delete(ids=existing["ids"])
                    logger.info(f"[TableView] Cleared {len(existing['ids'])} old table vectors")
            except Exception as e:  # TODO: Narrow exception type

                logger.warning(f"[{module}] suppressed exception", exc_info=True)
        # 3. 批量向量化
        search_texts = [e["search_text"] for e in table_entries]
        embeddings = await embed_texts(search_texts)
        if not embeddings:
            return {"tables_indexed": 0, "errors": ["embedding failed"]}
        
        # 4. 写入 ChromaDB
        ids = [f"table_{i}" for i in range(len(table_entries))]
        metadatas = [{k: str(v)[:512] for k, v in e.items() if k not in ("search_text",)} for e in table_entries]
        documents = [e["table_text"] for e in table_entries]
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        
        logger.info(f"[TableView] ✅ Indexed {len(table_entries)} tables")
        return {"tables_indexed": len(table_entries), "collection": TABLE_COLLECTION}
    
    except Exception as e:  # TODO: Narrow exception type
        logger.error(f"[TableView] Index failed: {e}")
        return {"tables_indexed": 0, "errors": [str(e)]}


async def table_view_search(query: str, top_k: int = 10) -> list:
    """检索：从 kb_tables ChromaDB 集合直查表格"""
    try:
        from src.db.vector_store import embed_texts
        
        collection = get_table_store()
        # 检查是否有数据
        count = collection.count()
        if count == 0:
            return []
        
        # query 向量化
        q_embs = await embed_texts([query])
        if not q_embs or not q_embs[0]:
            return []
        
        # ChromaDB 原生检索
        results = collection.query(
            query_embeddings=[q_embs[0]],
            n_results=min(top_k * 2, count),
        )
        
        if not results or not results.get("ids") or not results["ids"][0]:
            return []
        
        # 组装结果
        hits = []
        for i in range(len(results["ids"][0])):
            dist = results.get("distances", [[0]])[0][i] if results.get("distances") else 0
            # cosine distance → similarity score
            score = round((1.0 - dist) * 10, 2) if dist <= 2 else round(max(0, 2 - dist) * 5, 2)
            
            metadata = results.get("metadatas", [[{}]])[0][i] if results.get("metadatas") else {}
            document = results.get("documents", [[""]])[0][i] if results.get("documents") else ""
            
            if score > 0.2:
                hits.append({
                    "file_hash": metadata.get("file_hash", ""),
                    "file_name": metadata.get("file_name", ""),
                    "category": metadata.get("category", ""),
                    "table_text": document,
                    "score": score,
                    "_source": "table_view",
                    "result_type": "table",  # ← 前端渲染标记
                })
        
        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits[:top_k]
    
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"[TableView] search failed: {e}")
        return []


async def table_view_recall(query: str, chunks: list = None, top_k: int = 10) -> list:
    """兼容旧接口：优先从 ChromaDB 直查，无数据时回退实时计算"""
    # 优先走独立索引
    try:
        results = await table_view_search(query, top_k)
        if results:
            return results
    except Exception as e:  # TODO: Narrow exception type

        logger.warning(f"[{module}] suppressed exception", exc_info=True)
    # 回退：实时提取（兼容旧逻辑）
    if not chunks:
        return []
    
    table_chunks = []
    for c in chunks:
        text = c.get("text", "")
        tables = extract_tables_from_text(text)
        for t in tables:
            if len(t) > 30:
                table_chunks.append({
                    **c,
                    "table_text": t,
                    "search_text": _table_to_search_text(t),
                    "result_type": "table",
                })
    
    if not table_chunks:
        return []
    
    try:
        from src.db.vector_store import embed_texts
        q_emb = await embed_texts([query])
        if not q_emb or not q_emb[0]:
            return []
        
        table_texts = [tc["search_text"][:500] for tc in table_chunks]
        table_embs = await embed_texts(table_texts)
        if not table_embs:
            return []
        
        q_vec = q_emb[0]
        scored = []
        for i, tc in enumerate(table_chunks):
            if i < len(table_embs) and table_embs[i]:
                sim = _cosine_sim(q_vec, table_embs[i])
                if sim > 0.2:
                    scored.append({**tc, "score": round(sim * 10, 2), "_source": "table_view"})
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"[TableView] fallback recall failed: {e}")
        return []


def _cosine_sim(a: list, b: list) -> float:
    if not a or not b:
        return 0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0


# ====== 别名兼容 ======
# limbs 和其他器官用 search_tables 调用
search_tables = table_view_search
