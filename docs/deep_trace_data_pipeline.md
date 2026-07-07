# 伏羲 v1.50 数据入库链路 · 深度全链路追踪报告

> 仓库路径: `E:\easyclaw\伏羲-v1.44\repo`
> 追踪时间: 2026-07-06
> 目标: 追溯从 API 入口到最终存储的完整数据路径，标注存储位置、数据格式和可能的数据丢失点。

---

## 目录

1. [总览：三条入库路径](#1-总览三条入库路径)
2. [路径一：API 上传 (`/api/upload`) + `ShaoyangPipeline.digest()`](#2-路径一api-上传)
3. [路径二：`UnifiedPipeline.process()`（pipeline/unified.py）](#3-路径二unifiedpipelineprocess)
4. [路径三：`ingest_document()`（shaoyang/ingest.py）](#4-路径三ingest_document)
5. [SAG 提取器调用链](#5-sag-提取器调用链)
6. [自动分类在管线中的位置](#6-自动分类在管线中的位置)
7. [语义分块器调用关系](#7-语义分块器调用关系)
8. [向量写入 ChromaDB](#8-向量写入-chromadb)
9. [BM25 索引（memory_store）写入](#9-bm25-索引写入)
10. [装载机代理链路](#10-装载机代理链路)
11. [向量嵌入服务](#11-向量嵌入服务)
12. [数据丢失的可能环节](#12-数据丢失的可能环节)
13. [Bug/致命缺陷发现](#13-bug致命缺陷发现)

---

## 1. 总览：三条入库路径

伏羲 v1.50 存在 **三条独立的数据入库路径**，它们**并没有统一**，且不同路径的数据格式和存储方式**各异**：

```
┌──────────────────────────────────────────────────────────────┐
│                    伏羲 v1.50 入库拓扑                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  路径A: /api/upload                                            │
│    └→ ShaoyangPipeline.digest()     ← src/shaoyang/pipeline.py │
│       ├─ _parse() → _clean() → _chunk() → _classify()          │
│       ├─ _vectorize() → embed_texts() → chunk.embedding        │
│       └─ _save() → store.insert_many(chunk_dicts)              │
│                                                              │
│  路径B: /api/proxy/loader/*  (装载机代理)                       │
│     └→ 前端 POST → server.py 代理 → http://localhost:8090      │
│        → 装载机处理 → 返回 JSON → (回传路径不明确)                │
│                                                              │
│  路径C: ingest_document()         ← src/shaoyang/ingest.py     │
│     └→ _prepare_chunks() → _store_to_vector() → _store_to_memory() │
│        → _index_tables()                                       │
│                                                              │
│  ★ 路径D: UnifiedPipeline.process() ← src/pipeline/unified.py │
│     (与路径A 重合但实现不同，且 ShaoyangPipeline 未使用它)       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 路径一：API 上传 (`/api/upload`) + `ShaoyangPipeline.digest()`

### 2.1 API 入口

**文件**: `src/api/documents.py`，第 40-81 行

```
POST /api/upload (multipart/form-data)
  │
  ├─ 接收 UploadFile
  ├─ 保存到临时目录: data/uploads/<filename>
  ├─ 创建 Meridian() 实例 → ShaoyangPipeline(meridian)
  └─ await pipeline.digest(str(tmp_path), source="upload")
```

**传入格式**: HTTP multipart → `UploadFile` 对象 → 临时文件路径 `str`
**传回格式**: 
```json
{
  "status": "ok",
  "file_name": "xxx.pdf",
  "chunks": 15,
  "duration_ms": 1234.5
}
```

### 2.2 `ShaoyangPipeline.digest()` — 7 步处理管线

**文件**: `src/shaoyang/pipeline.py`，第 54-95 行

```
Step 1: _parse(file_path)
  ├─ 根据扩展名分发到不同解析器
  ├─ .pdf → _parse_pdf() → fitz (PyMuPDF)
  ├─ .docx → _parse_docx() → python-docx
  ├─ .xlsx → _parse_excel() → pandas
  └─ 其他 → _parse_text() → open(utf-8)
  返回: {"text": "...", "tables": [...], "metadata": {...}}
  存储: 无持久化，仅在 result.raw_text 内存中

Step 2: _clean(result.raw_text)
  ├─ re.sub(r'<[^>]+>', '', text)     # 去除 HTML 标签
  ├─ re.sub(r'https?://\S+', '', text)  # 去除 URL
  └─ re.sub(r'\s+', ' ', text)         # 合并空白
  返回: str (cleaned_text)
  存储: 仅在 result.cleaned_text 内存中

Step 3: _chunk(result.cleaned_text, result.tables)
  ├─ chunk_size=1000, overlap=100
  ├─ 按自然句边界断开（\n\n → \n → 句号 → 分号 → . → ;）
  └─ 生成 List[Chunk]
  存储: 仅在 result.chunks 内存中

Step 4: _classify(chunk) — 逐个分类
  ├─ 调用 src.category_registry.match_category(chunk.text, file_ext=, file_name=)
  └─ chunk.category = "模具设计" / "品质测量" / "通用办公" / ...
  存储: 设置在 chunk.category 属性

Step 5: 设置来源信息
  ├─ chunk.file_hash = _compute_hash(file_path)  # SHA256
  ├─ chunk.file_name = Path(file_path).name
  ├─ chunk.file_type = Path(file_path).suffix.lower()
  └─ chunk.source_pipeline = source  # "upload"

Step 6: _vectorize(result.chunks)  ← ★ 异步调用
  └─ 调用 src.db.vector_store.embed_texts([c.text for c in chunks])
     └─ await embed_texts(texts) → 返回 List[List[float]]
     └─ chunk.embedding = embeddings[i]
     ★ 注意: 此步只是把向量写入 chunk 对象的 embedding 属性
     ★ 并未调用 ChromaDB 的 add()！

Step 7: _save(result.chunks)
  └─ store = get_store()  → MemoryStore 实例
  └─ chunk_dicts = [c.to_dict() for c in chunks]
  └─ store.insert_many(chunk_dicts)  ← ★ 致命: MemoryStore 无此方法！
```

### 2.3 数据在各层的传递格式

| 层级 | 数据类型 | 格式 |
|------|---------|------|
| HTTP | UploadFile | multipart/form-data |
| 临时文件 | 磁盘文件 | `data/uploads/<filename>` |
| 解析后 | Dict | `{"text": str, "tables": List[Dict], "metadata": Dict}` |
| 清洗后 | str | 纯文本（去除 HTML/URL/多余空白） |
| 分块后 | List[Chunk] | Dataclass 对象列表 |
| 分类后 | List[Chunk] | 同上，`.category` 已填充 |
| 向量化后 | List[Chunk] | 同上，`.embedding` 已填充（仅在内存） |
| 存入 Store | List[Dict] | `[c.to_dict() for c in chunks]` → JSON 序列化 |

---

## 3. 路径二：`UnifiedPipeline.process()`（pipeline/unified.py）

**文件**: `src/pipeline/unified.py`

这是一个**重构版本**的管线，但**没有在任何路由中被调用**。当前 `/api/upload` 端点使用的是 `ShaoyangPipeline`（即路径A），不是这个。

但它值得追踪，因为代码体现了预期的目标架构。

### 3.1 UnifiedPipeline.process() 的 8 步管线

```
Step 1: parser.parse(file_path) → UnifiedParser
  ├─ .pdf → _parse_pdf() → fitz → pdfplumber → PyPDF2 (三级降级)
  ├─ .docx → _parse_docx() → python-docx (含表格提取)
  ├─ .xlsx → _parse_excel() → pandas
  ├─ .csv → _parse_csv() → pandas
  ├─ .json → _parse_json()
  ├─ .html → _parse_html() → BeautifulSoup
  └─ 其他 → _parse_text()
  返回: {"text": str, "tables": List[Dict], "metadata": Dict}

Step 2: cleaner.clean(parsed) → UnifiedCleaner
  ├─ 去除 HTML 标签、URL、邮箱
  ├─ 去除页眉页脚（数字/页码）  
  ├─ 去除控制字符
  └─ 合并多余空白
  ★ 可恢复：失败时降级为原文
  返回: parsed (dict, text 已修改)

Step 3: chunker.chunk(parsed, result.tables) → UnifiedChunker
  ├─ 文本分块: chunk_size=1000, overlap=100
  ├─ 表格独立存储: 表格转为 Markdown → ChunkType.TABLE
  └─ 每个 Chunk 对象设置 total_chunks
  ★ 可恢复：失败时降级为单块
  返回: List[Chunk]

Step 4: classifier.classify(chunk) → UnifiedClassifier
  └─ 调用 src.category_registry.match_category()
  ★ 可恢复：失败时 → "通用办公"

Step 5: 设置来源信息
  ├─ chunk.file_hash = sha256
  ├─ chunk.file_name/.file_type/.source_pipeline/.source_file

Step 6: embedder.embed_batch(texts) → UnifiedEmbedder
  └─ 调用 src.db.vector_store.embed_texts(texts)
     → HTTP POST http://localhost:8081/embed
     → 返回 List[List[float]]
  ★ 可恢复：失败时标记待补
  存储: chunk.embedding 属性（内存中）

Step 7: saver.save(chunks) → UnifiedSaver
  ├─ store = get_store() → MemoryStore
  ├─ chunk_dicts = [c.to_dict() for c in chunks]
  ├─ store.insert_many(chunk_dicts)  ← ★ 致命: MemoryStore 无此方法！
  └─ ★ 不可恢复：失败时抛出 SaveError

Step 8: extractor.extract(chunks) → UnifiedExtractor (SAG 提取)
  ├─ ★ 必须 feature_flag "event_entity_extract"=True 才执行
  ├─ ★ 但 feature_flags.json 中配置的是 "shaoyang_sag_extract": false
  ├─ ★ 两个 key 名不匹配 → 永远不会执行
  ├─ 遍历每个 chunk，调用 LLM 提取事件/实体
  └─ 返回 (entities, events)
```

### 3.2 UnifiedPipeline 与 ShaoyangPipeline 的关键差异

| 特性 | ShaoyangPipeline | UnifiedPipeline |
|------|:---:|:---:|
| 实际被调用 | ✅ | ❌ 无路由调用 |
| 表格独立存储 | ❌ | ✅ (ChunkType.TABLE) |
| CSV/JSON/HTML 专用解析 | ❌ | ✅ |
| 三级 PDF 降级 | ❌ (仅 fitz) | ✅ (fitz→pdfplumber→PyPDF2) |
| 错误分级（可恢复/不可恢复） | ❌ | ✅ |
| SAG 事件实体提取 | ❌ | ✅ (但 Flag 名不匹配) |
| 文件哈希去重 | ❌ 无 | ✅ _processing 集 |
| ChromaDB 写入 | ❌ | ❌ 都没有！ |
| insert_many 实现 | ❌ | ❌ 都没有！ |

---

## 4. 路径三：`ingest_document()`（shaoyang/ingest.py）

**文件**: `src/shaoyang/ingest.py`，第 770-883 行

这是第三个入库入口，由 MCP ingest 等路径调用：

```
ingest_document(parse_result, file_name, category, embed_fn, vector_store, table_store, memory_store)

Phase 1: _prepare_chunks()
  ├─ 文本: smart_chunk_semantic(text) → 按段落边界分块
  ├─ 表格: chunk_table() → Markdown 格式整表
  └─ 图片: chunk_image() → 多模态转录 → OCR → 文件名 fallback
  返回: List[Dict] (每个 Dict 包含 text, file_hash, chunk_index, category 等)

Phase 2: _store_to_vector(chunks, file_hash, embed_fn, vector_store)
  ├─ texts = [c['text'][:1000] for c in chunks]
  ├─ embeddings = await embed_fn(texts)
  ├─ ids = [f"{file_hash}_{c['chunk_index']}" for c in chunks]
  └─ vector_store.add(ids=ids, embeddings=embeddings, documents=documents, metadata=metadatas)
  ★ 这是唯一真正调用 ChromaDB vector_store.add() 的路径！
  存储: ChromaDB collection "kb_chunks"

Phase 2: _store_to_memory(chunks, memory_store)
  └─ for c in chunks: memory_store.add_document(c)
  ★ 致命: MemoryStore 无 add_document() 方法！
  存储: 应为 chunks.db/chunks 表，但实际失败

Phase 2: _index_tables(chunks, tables, table_store)
  └─ index_tables_from_chunks(chunks) → ChromaDB collection "kb_tables"
  存储: ChromaDB table_store
```

### 4.1 `smart_chunk_semantic()` 分块策略

**文件**: `src/shaoyang/ingest.py`，第 424-448 行

```
smart_chunk_semantic(text, chunk_size=1500, overlap=200)
  ├─ 按 \n\n（段落边界）分割
  ├─ 标题检测: '#' / '【' / '[' 开头 → 新 chunk
  ├─ 累积策略: 当前 + 新段 ≤ 1500 → 拼接
  │           超过 → 结束当前 chunk，overlap=200 保留上文尾部
  └─ 返回 List[str]
```

---

## 5. SAG 提取器调用链

有三套提取器实现：

### 5.1 `shaoyang/extractor.py` — SAGExtractor（独立提取器）

**文件**: `src/shaoyang/extractor.py`

```
SAGExtractor.extract(chunk_text, chunk_meta)
  ├─ 构建六段式 Prompt (角色/任务/格式/约束/示例/文本)
  ├─ await _call_llm(prompt) → src.infra.llm.call_ai(prompt)
  ├─ _parse_response() → 清理 JSON 周围的 markdown ``` 标记
  ├─ _resolve_pronouns() → 代词消歧
  ├─ _annotate_hierarchy() → 层级事件标注 (level 1/2/3)
  ├─ _deduplicate_entities() → 名称归一化 + 描述合并
  └─ _save_to_db() → 写入 chunks.db 的 events 表和 entities 表
     ★ 直接操作 store._db_conn.execute("INSERT OR REPLACE INTO events/entities ...")
```

**调用位置**: ❌ 无任何代码调用 — 需要外部显式创建 SAGExtractor() 实例。

### 5.2 `pipeline/unified.py` — UnifiedExtractor

**文件**: `src/pipeline/unified.py`，第 389-497 行

由 `UnifiedPipeline.process()` 的 Step 8 调用，但需要 `event_entity_extract=True` 的 feature flag。

**实际状态**: ❌ 不会被执行，因为:
1. `UnifiedPipeline.process()` 无路由调用
2. feature flag 名为 `event_entity_extract`，但 `feature_flags.json` 中键名为 `shaoyang_sag_extract`
3. DEFAULT_FLAGS 中无 `event_entity_extract` 键，默认返回 False

### 5.3 SAG 提取器调用链完整图

```
┌──────────────────────────────────────────────────────────────┐
│ SAGExtractor (shaoyang/extractor.py)                         │
│   ★ 有完整实现，但无任何调用者                                  │
│   ★ 六段式 Prompt → LLM → JSON → 消歧 → 层级标注 → 去重       │
│   ★ 写入: chunks.db/events & chunks.db/entities               │
├──────────────────────────────────────────────────────────────┤
│ UnifiedExtractor (pipeline/unified.py)                       │
│   ★ 简化版实现                                                 │
│   ★ 仅在 UnifiedPipeline.process() Step 8 中调用               │
│   ★ 需要 feature_flag "event_entity_extract"=True             │
│   ★ 但因 UnifiedPipeline 未被实际路由调用 → 不生效             │
├──────────────────────────────────────────────────────────────┤
│ ShaoyangPipeline (shaoyang/pipeline.py)                      │
│   ★ 无 SAG 提取步骤                                            │
│   ★ 这是 /api/upload 实际使用的管线                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. 自动分类在管线中的位置

自动分类以**三种形式**出现在管线中：

### 6.1 `auto_classifier.py` — 独立批量分类器

**文件**: `src/shaoyang/auto_classifier.py`

```
classify_by_vectors(embeddings, texts, file_names)
  ├─ 方案1: 关键词匹配 (CATEGORY_KEYWORDS 字典)
  ├─ 方案2: 向量聚类 (HDBSCAN, 需全量数据)

reclassify_store(store)
  └─ 对 SQLite chunks.db 中所有 chunk 重新分类 (UPDATE chunks SET category=?)

sync_category_graph() / sync_graph_to_categories()
  └─ 将分类统计同步到知识图谱知识图谱
```

**调用状态**: ❌ 无任何管线代码调用这些函数，它们需要手动或外部触发。

### 6.2 `ShaoyangPipeline._classify()` — 管线内分类

**文件**: `src/shaoyang/pipeline.py`，第 163-168 行

调用位置: Step 4，对每个 chunk 调用 `src.category_registry.match_category()`

```
  for chunk in result.chunks:
      chunk.category = self._classify(chunk)  → match_category(chunk.text, file_ext, file_name)
```

### 6.3 `UnifiedPipeline.classifier.classify()` — 管经内分类

**文件**: `src/pipeline/unified.py`，第 320-327 行

调用位置: Step 4，对每个 chunk 调用 `match_category()`

---

## 7. 语义分块器调用关系

### 7.1 `semantic_chunker.py` — 话题转换检测分块

**文件**: `src/shaoyang/semantic_chunker.py`

```
chunk_text(text, max_chars=800)
  └─ split_by_semantic_boundary(text, max_chars, min_chars=100, overlap_threshold=0.15)
     ├─ 句子切分: SENT_SPLITTER = re.compile(r'[。！？!?\n]')
     ├─ 关键词重叠检测: _keyword_overlap(s1, s2)
     │  └─ 提取中文词(≥2字) + 英文词(≥3字符) → 计算 Jaccard 重叠率
     ├─ is_topic_shift(text_a, text_b, threshold=0.15)
     │  └─ 重叠率 < 0.15 → 话题转换
     └─ 累积分块: 当前 chunk + 新句超过 max_chars → 检查话题是否转换
        └─ 转换 → 新 chunk / 未转换 → 继续积累

  失败降级: 固定窗口 (max_chars - 50 overlap)
```

**调用状态**: ❌ 无任何管线代码导入或调用 `semantic_chunker.chunk_text()`

### 7.2 实际使用的分块策略

| 管线 | 分块方法 | 文件位置 |
|------|---------|---------|
| ShaoyangPipeline | `_chunk()` 内联固定窗口 (1000/100) | `shaoyang/pipeline.py:118-144` |
| UnifiedPipeline | `UnifiedChunker.chunk()` 内联固定窗口 (1000/100) | `pipeline/unified.py:262-300` |
| ingest_document | `smart_chunk_semantic()` 语义段落分块 | `shaoyang/ingest.py:424-448` |

---

## 8. 向量写入 ChromaDB

### 8.1 VectorStore 结构

**文件**: `src/db/vector_store.py`

```
VectorStore(db_dir="data", collection_name="kb_chunks")
  ├─ ChromaDB PersistentClient(path=<db_dir>/chroma)
  ├─ collection: "kb_chunks"  (HNSW, cosine distance, M=32, ef_construction=200)
  └─ embedding_function=None  (自行提供向量)
```

**实际数据库**: `data/chroma/chroma.sqlite3`

**Collections**:
- `kb_chunks` — 主向量存储 (hnsw:space=cosine), **当前 0 条**
- `kb_tables` — 表格向量存储 (hnsw:space=cosine), **当前 0 条**

### 8.2 VectorStore.add() 调用关系

```
┌────────────────────────────────────────────────────┐
│ 调用者                                                  │
├────────────────────────────────────────────────────┤
│                                                    │
│ ✅ ingest_document._store_to_vector()               │
│    → vector_store.add(ids, embeddings, documents, metadata) │
│    → 存入 collection "kb_chunks"                     │
│    → ★ 唯一一个实际调用 vector_store.add() 的路径       │
│                                                    │
│ ✅ _index_tables() → index_tables_from_chunks()     │
│    → 存入 collection "kb_tables"                     │
│                                                    │
│ ❌ ShaoyangPipeline.digest()                        │
│    → _vectorize() 只是把向量放在 chunk.embedding    │
│    → _save() 调用 store.insert_many() 只写 SQLite    │
│    → ★ 从未调用 vector_store.add()！                  │
│    → ★ 向量丢失：向量化成功但未存入 ChromaDB           │
│                                                    │
│ ❌ UnifiedPipeline.process()                        │
│    → embedder.embed_batch() 产生向量                 │
│    → saver.save() 只调 store.insert_many()           │
│    → ★ 同样从未调用 vector_store.add()！              │
│    → ★ 向量丢失                                       │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 8.3 embed_texts vs vector_store.add 的分离

这是设计上的关键分离：

- `embed_texts()` (在 `vector_store.py` 中): 调用 **外部 embedder 服务** (http://localhost:8081/embed) → 返回向量列表
- `VectorStore.add()`: 将**已有的向量**存入 ChromaDB

但当前代码中：
- `ShaoyangPipeline._vectorize()` 调用了 `embed_texts()` 获得向量，但 `_save()` 只写 SQLite
- 没有任何一步调用 `vector_store.add()`

**结论：向量嵌入会被计算，但永远不会存入 ChromaDB**（除了 `ingest_document` 路径）。

---

## 9. BM25 索引写入

### 9.1 MemoryStore 结构

**文件**: `src/db/memory_store.py`

```
MemoryStore(db_path="data/chunks.db")
  ├─ SQLite 数据库: data/chunks.db (WAL 模式, 64MB cache)
  ├─ 主表 chunks: (id, doc JSON, file_hash, file_name, category, chunk_index, status, created_at, loader_path, uploaded_by)
  │  ├─ 索引: idx_chunks_hash, idx_chunks_name, idx_chunks_status, idx_chunks_category, idx_chunks_index
  │  └─ FTS5 索引: chunks_fts (text, file_name) --- 全文搜索
  ├─ 附表 events: (event_id, title, summary, content, category, keywords, priority, parent_event_id, level, children, chunk_ids, entity_names, ref_list, file_hash, file_name, created_at)
  ├─ 附表 entities: (entity_id, name, entity_type, description, aliases, canonical_name, event_ids, chunk_ids, mentions, file_hash, file_name, created_at)
  ├─ 附表 relations: (relation_id, source_type, source_id, target_type, target_id, relation_type, weight, created_at)
  └─ LRU 缓存: _cache_hash (500条), _cache_name (500条), _files_cache
```

### 9.2 写入方法

```
写入方法:
  add(chunk_dict)           → INSERT INTO chunks (doc, file_hash, ...)
  add_batch(chunk_dicts)    → INSERT 批量

兼容属性 (已废弃):
  _chunks                  → 全量加载到内存 (get_all())
  _by_hash                 → 全量查询 (get_by_hash())
  _files                   → 文件摘要 (get_files_summary())
```

### 9.3 BM25 写入调用关系

```
┌────────────────────────────────────────────────────┐
│ MemoryStore 写入调用                                    │
├────────────────────────────────────────────────────┤
│                                                    │
│ ShaoyangPipeline._save() → store.insert_many()       │
│   ★ 致命: MemoryStore 无 insert_many 方法               │
│   ★ 当调用时会发生 AttributeError                       │
│                                                    │
│ UnifiedPipeline.saver.save() → store.insert_many()   │
│   ★ 同样的致命问题                                      │
│                                                    │
│ ingest_document._store_to_memory() → store.add_document(c) │
│   ★ 致命: MemoryStore 无 add_document 方法               │
│                                                    │
│ SAGExtractor._save_to_db() → store._db_conn.execute(...) │
│   ★ 直接访问 store._db_conn → events/entities 表        │
│   ★ 这是唯一能正常写入 events/entities 的路径             │
│   ★ 但 SAGExtractor 无任何调用者                            │
│                                                    │
└────────────────────────────────────────────────────┘
```

**严重发现**: `MemoryStore` 缺少 `insert_many()` 和 `add_document()` 方法。这两个方法在管线代码中被直接调用，但它们并不存在于 `MemoryStore` 类中。这意味着：

- `ShaoyangPipeline.digest()` 会在 `_save()` 步骤因 `AttributeError` 而崩溃
- `UnifiedPipeline.process()` 同样会在 `saver.save()` 步骤崩溃  
- `ingest_document._store_to_memory()` 会在调用 `memory_store.add_document(c)` 时崩溃

**不过要注意**：`MemoryStore` 有 `add(chunk)` 和 `add_batch(chunks)` 方法。正确做法应该是：
- `insert_many(chunk_dicts)` → 应改为 `add_batch(chunk_dicts)`
- `add_document(c)` → 应改为 `add(c)`

---

## 10. 装载机代理链路

### 10.1 代理路由

**文件**: `src/server.py`，第 450-480 行

```
前端 → GET /api/proxy/loader/files
     └─ 后端代理 → GET http://localhost:8090/api/files
        └─ 返回: {"files": [...]} 或 {"error": "..."}

前端 → POST /api/proxy/loader/upload (multipart)
     └─ 后端代理 → POST http://localhost:8090/api/upload (透传 body)
        └─ 返回: 装载机的 JSON 响应
```

**`LOADER_URL`**: 从环境变量 `LOADER_URL` 读取，默认 `http://localhost:8090`

### 10.2 装载机回传路径

```
┌─────────────────────────────────────────────────────┐
│ 装载机 (loader, 端口 8090)                              │
│   POST /api/upload → 接收文件                          │
│   处理 → 返回 JSON (chunks, entities, ...)              │
│   返回格式: {"chunks": [...], "file_hash": "...", ...} │
│                                                     │
│  代理回传 → 返回给前端（原始 JSON 透传）                  │
│                                                     │
│  对齐器: OutputFormatAligner.align_loader_output()     │
│    → 标准化输出格式（统一字段名）                         │
│    → 但从未在代理路由中被调用！                          │
│                                                     │
│  问题:                                                │
│    ★ 代理只是透传 JSON 给前端，不做入库！                  │
│    ★ 前端收到 JSON 后做什么？不明确                        │
│    ★ 装载机的 chunks 没有进入伏羲的 ChromaDB 或 SQLite   │
└─────────────────────────────────────────────────────┘
```

**结论**: `/api/proxy/loader/upload` 只是把文件转发到 8090 端口，并透传 JSON 给前端。装载机产生的 chunks **不会**被存入伏羲的 ChromaDB 或 SQLite 数据库。这是一个**数据丢失点**。

---

## 11. 向量嵌入服务

### 11.1 嵌入服务架构

**文件**: `src/services/embedder.py` + `src/db/vector_store.py` 中的 `embed_texts()`

```
HTTP 调用链:
  客户端 → embed_texts(texts)                (src/db/vector_store.py)
           │
           ├─ POST http://localhost:8081/embed
           ├─ Body: {"texts": ["文本1", "文本2", ...]}
           ├─ Timeout: connect=2s, total=5s
           │
           └─ 嵌入服务: src/services/embedder.py (FastAPI, 端口 8081)
                        ├─ 模型: BAAI/bge-small-zh-v1.5 (SentenceTransformers)
                        ├─ 环境变量: KB_MODEL (默认 bge-small-zh-v1.5)
                        ├─ batch_size=64
                        ├─ normalize_embeddings=True
                        ├─ 线程数: KB_EMBEDDER_WORKERS (默认4)
                        ├─ POST /embed → {"vectors": [[...], [...]]}
                        ├─ POST /rerank → {"scores": [...], "indices": [...]}
                        └─ GET /health → {"status": "ready", "model": "..."}

配置:
  EMBEDDER_URL = os.getenv("KB_EMBEDDER_URL", "http://localhost:8081")
  (在 src/config.py 中)
```

### 11.2 嵌入服务的健康检查

`embed_texts()` 中有健康检查缓存:
- 如果嵌入服务不可用 → `_embedder_available = False`
- 30 秒内不会再尝试重连 → 直接返回 None
- **向量化静默失败**（不抛异常，只记录警告日志）

### 11.3 谁在调用 embed_texts()？

| 调用方 | 文件位置 | 向量存哪 |
|-------|---------|---------|
| ShaoyangPipeline._vectorize() | `shaoyang/pipeline.py:214` | chunk.embedding (内存), 不存 ChromaDB |
| UnifiedEmbedder.embed_batch() | `pipeline/unified.py:347` | chunk.embedding (内存), 不存 ChromaDB |
| _store_to_vector() | `shaoyang/ingest.py:836` | ✅ ChromaDB "kb_chunks" |

---

## 12. 数据丢失的可能环节

### 🔴 致命缺陷 (Crash-level)

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| 1 | `shaoyang/pipeline.py:230` | `store.insert_many()` → MemoryStore 无此方法 | **AttributeError，导致 `/api/upload` 在上传后崩溃，整个管线无数据写入** |
| 2 | `pipeline/unified.py:380` | 同上：`store.insert_many()` | 如果 UnifiedPipeline 被调用，同样崩溃 |
| 3 | `shaoyang/ingest.py:855` | `memory_store.add_document()` → MemoryStore 无此方法 | ingest_document 路径的 BM25 写入崩溃 |

### 🟠 数据丢失 (Silent data loss)

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| 4 | `shaoyang/pipeline.py:214` | 向量化成功但从未调用 `vector_store.add()` | **所有上传文件的向量永久丢失**（仅留在 chunk.embedding 内存属性中，不持水化） |
| 5 | `pipeline/unified.py:604` | 同上 | 向量被计算但未存 ChromaDB |
| 6 | `server.py:459` | 装载机代理透传 JSON → 数据不进入伏羲数据库 | 装载机路径的数据完全丢失 |
| 7 | `shaoyang/extractor.py` | SAGExtractor 完整实现但无调用者 | 事件/实体提取功能完全未启用 |

### 🟡 功能死锁 (Functional deadlock)

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| 8 | `pipeline/unified.py:618` | Feature flag 检查 `event_entity_extract`，但实际配置为 `shaoyang_sag_extract` | SAG 提取永远不执行 |
| 9 | `shaoyang/semantic_chunker.py` | `chunk_text()` 已实现但无代码导入调用 | 语义分块功能未使用 |
| 10 | `shaoyang/auto_classifier.py` | 批量代码但无管线集成调用 | 自动向量聚类分类不可用 |
| 11 | `pipeline/unified.py:540` | `UnifiedPipeline` 完整实现但无路由注册调用 | 重构版管线完全闲置 |

### 🟢 潜在风险

| # | 位置 | 问题 |
|---|------|------|
| 12 | `shaoyang/pipeline.py:169` | `_compute_hash()` 每次计算 whole-file SHA256，大文件可能很慢 |
| 13 | `db/vector_store.py:186` | 如果 embedder 服务挂了 >30s，所有后续请求都静默返回 None |
| 14 | `services/output_aligner.py` | `align_loader_output()` 已定义但从未在代理路由中被调用 |

---

## 13. Bug/致命缺陷发现

### 13.1 致命：`insert_many()` 不存在的 AttributeError

```python
# 两处调用，方法不存在：
# shaoyang/pipeline.py:230
store.insert_many(chunk_dicts)  # MemoryStore 只有 add() 和 add_batch()

# pipeline/unified.py:380  

### 13.1 致命：`insert_many()` 不存在的 AttributeError

```python
# 两处调用，方法不存在：
# shaoyang/pipeline.py:230
store.insert_many(chunk_dicts)  # MemoryStore 只有 add() 和 add_batch()

# pipeline/unified.py:380  
store.insert_many(chunk_dicts)  # 同样的问题
```

**修复**: 将所有 `store.insert_many(chunk_dicts)` 替换为 `store.add_batch(chunk_dicts)`。

### 13.2 致命：`add_document()` 不存在的 AttributeError

```python
# shaoyang/ingest.py:855
memory_store.add_document(c)  # MemoryStore 只有 add(chunk)
```

**修复**: 替换为 `memory_store.add(c)`。

### 13.3 Feature Flag 键名不匹配

```python
# pipeline/unified.py:618 检查:
if flags.get("event_entity_extract", False):

# 但 data/feature_flags.json 中只有:
# "shaoyang_sag_extract": false

# DEFAULT_FLAGS 中也没有 "event_entity_extract" 键
```

**修复**: 统一键名为 `"shaoyang_sag_extract"` 或 `"event_entity_extract"`。

### 13.4 向量永不存入 ChromaDB（除 ingest_document 路径）

```
ShaoyangPipeline.digest() 流程:
  _vectorize() → embed_texts() 成功 → chunk.embedding = [向量]
  _save() → store.add_batch(chunk_dicts) → 只写 SQLite
  ❌ 从未调用 vector_store.add() → 向量丢失！

UnifiedPipeline.process() 流程:
  embedder.embed_batch() → 向量成功
  saver.save() → 只写 SQLite
  ❌ 从未调用 vector_store.add() → 向量丢失！
```

### 13.5 装载机数据不入库

```
POST /api/proxy/loader/upload
  → proxy 只是 HTTP 透传
  → 返回原始 JSON 给前端
  → 无任何代码将装载机返回的 chunks 写入 ChromaDB 或 SQLite
```

### 13.6 `ShaoyangPipeline._vectorize()` 的隐蔽问题

```python
async def _vectorize(self, chunks: List[Chunk]):
    from src.db.vector_store import embed_texts
    embeddings = await embed_texts([c.text for c in chunks])
    if embeddings:
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb
```

这里 `embed_texts()` 在嵌入服务不可用时返回 `None`，而不是抛异常。向量化失败时：
- chunk.embedding 保持 None
- `_save()` 仍然继续执行（不会跳过）
- 最终 chunks 被写入 SQLite，但缺少向量数据

---

## 总结：实际执行的入库流程

当用户通过 `POST /api/upload` 上传文件时，**实际发生的事**：

```
POST /api/upload
  │
  ├─ 临时文件: data/uploads/<filename>  ✅ 成功
  │
  ├─ ShaoyangPipeline.digest()
  │   ├─ Step 1 解析: ✅ fitz/pandas/docx 成功
  │   ├─ Step 2 清洗: ✅ 正则成功
  │   ├─ Step 3 分块: ✅ 固定窗口(1000/100)成功
  │   ├─ Step 4 分类: ✅ match_category() 成功
  │   ├─ Step 5 来源: ✅ file_hash/file_name 设置成功
  │   ├─ Step 6 向量化:
  │   │   ├─ embed_texts() → POST localhost:8081/embed
  │   │   │   ├─ 服务可用: ✅ 返回向量 → chunk.embedding 已赋值
  │   │   │   └─ 服务不可用: ⚠️ 静默返回 None → chunk.embedding = None
  │   │   └─ ❌ 向量未写入 ChromaDB (无 vector_store.add() 调用)
  │   └─ Step 7 存储:
  │       ├─ ❌ store.insert_many() → AttributeError 崩溃！
  │       └─ 💥 整个请求失败，数据丢失
  │
  └─ 返回 HTTP 500 给前端
```

## 各存储位置的最终状态

| 存储位置 | 表/Collection | 当前数据量 | 状态 |
|---------|-------------|----------|------|
| `data/chunks.db` | `chunks` | **0** | 因 insert_many() bug 无法写入 |
| `data/chunks.db` | `events` | **0** | SAGExtractor 无调用者 |
| `data/chunks.db` | `entities` | **0** | SAGExtractor 无调用者 |
| `data/chunks.db` | `relations` | **0** | 无写入逻辑 |
| `data/chunks.db` | `chunks_fts` | **0** | FTS 索引空 |
| `data/chroma/chroma.sqlite3` | `kb_chunks` | **0** | 无 vector_store.add() 调用 |
| `data/chroma/chroma.sqlite3` | `kb_tables` | **0** | 无 table_store.add() 调用 |
| `data/uploads/` | 文件系统 | 空 | 上传后临时文件 |

## 需要修复的最小改动清单

1. **`MemoryStore` 添加 `insert_many()` 方法** → 委托给 `add_batch()`
2. **`MemoryStore` 添加 `add_document()` 方法** → 委托给 `add()`
3. **`ShaoyangPipeline._save()` 中追加 ChromaDB 写入** → 调用 `get_vector_store().add()`
4. **`UnifiedPipeline.process()` Step 7 中追加 ChromaDB 写入**
5. **统一 feature flag 键名** → `"event_entity_extract"` ↔ `"shaoyang_sag_extract"`
6. **装载机代理中调用 `UnifiedPipeline.process()`** → 替代直接透传 JSON
7. **集成 `SAGExtractor` 到管线** → 在 `ShaoyangPipeline.digest()` 中添加 Step 8
8. **集成 `semantic_chunker.chunk_text()` 到分块步骤** → 替换固定窗口分块

---

*报告完成。总计发现 **3 个致命 AttributeError**、**4 处静默数据丢失**、**4 处功能死锁**、**3 处潜在风险**。*