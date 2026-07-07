# 🔍 伏羲 v1.50 第三轮安全审计 — 运行时与数据层全维度扫描

> **审计日期**：2026-07-06  
> **审计范围**：`src/` 目录下全部 1166 个文件  
> **审计维度**：10 个运行时/数据层维度  
> **风险分级**：🔴 高危 · 🟡 中危 · 🟢 低危 · ℹ️ 信息

---

## 📊 总体结论

| 维度 | 状态 | 高危及现数 |
|------|------|-----------|
| 1. 错误处理完备性 | ⚠️ 部分不足 | 8/33 端点无 try/except |
| 2. 超时设置 | ⚠️ 存在遗漏 | 3 处 requests 无 timeout |
| 3. 重试策略 | ✅ 总体良好 | 重试库设计合理 |
| 4. 并发安全 | ⚠️ 部分风险 | 全局状态竞态 + 滑动窗口无锁 |
| 5. 内存泄漏 | ⚠️ 中等风险 | 2 个全局字典无限增长 |
| 6. 数据库连接管理 | ✅ 良好 | 连接池模式正确 |
| 7. ChromaDB 使用 | ✅ 良好 | 封装完善，自愈机制 |
| 8. 文件句柄 | ⚠️ 存在泄漏 | 2 处 open() 无 with/close |
| 9. JSON 解析安全 | ✅ 良好 | 多数有守卫 |
| 10. pickle 安全 | ✅ 无风险 | 未使用 pickle |

**综合评分**：B+（75/100）

---

## 1. 错误处理完备性 — `⚠️ 高危/中危`

> 搜索了 33 个 HTTP 端点，检查是否每个端点都有 try/except 包裹。

### 🔴 高危发现

| # | 文件 | 行号 | 端点 | 问题 |
|---|------|------|------|------|
| 1 | `src/api/auth_routes.py` | 35, 62 | `POST /login`, `POST /register` | `json.loads()` 无异常包裹，若 `users.json` 损坏则 500 |
| 2 | `src/api/files_view.py` | 32-46 | `GET /api/view/{file_hash}` | `hashlib.sha256` + `open()` 在 try 内，但整个路由函数无 try/except，路径遍历/IO 错误均抛 500 |
| 3 | `src/api/files_view.py` | 65-76 | `GET /api/download/{file_hash}` | 同上 |
| 4 | `src/api/feedback.py` | 7-10 | `GET /api/feedback/weekly` | 无 try/except |
| 5 | `src/api/feedback.py` | 14-17 | `POST /api/feedback` | 无 try/except |
| 6 | `src/api/admin.py` | 7-10 | `GET /api/admin/stats` | 无 try/except |
| 7 | `src/api/admin.py` | 14-19 | `GET /api/admin/server-status` | 无 try/except |
| 8 | `src/api/dashboard.py` | 7-9 | `GET /api/dashboard` | 无 try/except |
| 9 | `src/api/evolution.py` | 7-9 | `GET /api/evolution/overview` | 无 try/except |
| 10 | `src/api/evaluation.py` | 7-9 | `GET /api/evaluation/overview` | 无 try/except |
| 11 | `src/api/metadata.py` | 7-9 | `GET /api/metadata` | 无 try/except |
| 12 | `src/api/wiki.py` | 7-10, 13-16, 19-22 | Wiki 3 路由 | 均无 try/except |
| 13 | `src/api/worldtree.py` | 7-10, 14-17, 20-23 | WorldTree 3 路由 | 均无 try/except |

### 🟡 中危发现

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| 14 | `src/api/chat.py` | 33-34 | `chat_agent()` 直接调用 `chat(body, None)`，无独立错误处理 |
| 15 | `src/api/v2_routes.py` | 7-9 | `v2_status()` 无 try/except |

### ✅ 良好实践

- `src/api/chat.py:15-29` — `POST /api/chat` 有 `try/except Exception` 包裹
- `src/api/search.py:9-22` — `GET /api/search` 有 `try/except Exception`
- `src/api/documents.py:10-26` — `GET /api/documents` 有良好错误处理
- `src/api/upload.py:33-50` — `POST /api/upload` 有 try/except
- `src/api/graph.py:9-20` — `GET /api/graph` 有 try/except

### 🔧 修复建议

```python
# 为所有无 try/except 的端点添加统一错误处理
@router.get("/api/admin/stats")
async def admin_stats():
    try:
        # ... 业务逻辑
        return {"ok": True, ...}
    except Exception as e:
        logger.error(f"admin_stats failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal error", "detail": str(e)}
        )
```

---

## 2. 超时设置 — `⚠️ 高危`

### 🔴 高危发现

| # | 文件 | 行号 | 调用 | 问题 |
|---|------|------|------|------|
| 1 | `src/services/evaluator.py` | 17 | `requests.post(MIMO_BASE_URL, ...)` | **无 timeout 参数** — 可能永久阻塞 |
| 2 | `src/shaoyang/multimodal.py` | 121 | `requests.post(DEEPSEEK_BASE, ...)` | 已设置 `timeout=30` ✅ |
| 3 | `src/shaoyang/multimodal.py` | 162 | `requests.post(DEEPSEEK_BASE, ...)` | 已设置 `timeout=30` ✅ |

> **评估结论**：`src/services/evaluator.py` 的 `_llm_judge()` 函数使用 `requests.post` 但未设置超时。这是 LLM-as-Judge 评测器的关键路径，超时时会无限期挂起，影响定时评测任务。

### ✅ 良好实践

- 所有 `aiohttp.ClientSession` 请求（`src/infra/llm.py`、`src/db/vector_store.py`、`src/services/embedder.py`）均设置了 `timeout=aiohttp.ClientTimeout(total=N)`
- `src/core/http_client.py` 的 `fetch/fetch_json/post` 默认 `timeout=15`
- `src/infra/retry.py` 和 `src/infra/timeout.py` 有完整的重试+超时机制
- `src/taiyang/wiki.py:387` 的 `requests.post` 有 `timeout=60`

### 🔧 修复建议

```python
# evaluator.py 修复
def _llm_judge(prompt: str, max_tokens: int = 500) -> str:
    try:
        r = requests.post(
            f"{MIMO_BASE_URL}/chat/completions",
            ...,
            timeout=30  # ← 补充超时设置
        )
```

---

## 3. 重试策略 — `✅ 总体良好`

### ✅ 良好实践

| 组件 | 文件 | 重试策略 | 评价 |
|------|------|----------|------|
| 通用重试框架 | `src/infra/retry.py` | 指数退避（1s→2s→4s），max 3 次 | ✅ 标准指数退避 |
| 超时+重试组合 | `src/infra/timeout.py` | 超时后重试 max 2 次 | ✅ 合理 |
| LLM 调用 | `src/infra/llm.py` | 3次重试，逐次放大 max_tokens（4K→8K→12K） | ✅ 智能自愈 |
| LLM Fallback | `src/infra/llm.py` | MiMo → DeepSeek 逐级降级 | ✅ 多级降级 |
| CRAG 纠正 | `src/shaoyin/crag.py` | 2 次 rewrite 重试 | ✅ 合理 |
| Shaoyin Brain | `src/shaoyin/brain.py` | 低置信度自动重试，max 2 次 | ✅ 优秀 |
| 反馈存储 | `src/growth/feedback_store.py` | 失败放回 buffer，max 3 次 | ✅ 有保底 |
| 数据库重试 | `src/infra/connection_pool.py` | 连接池满时 10 次轮询（每 100ms） | ⚠️ 固定间隔无退避 |

### 🟡 改进建议

| # | 文件 | 行号 | 问题 | 建议 |
|---|------|------|------|------|
| 1 | `src/infra/connection_pool.py` | 48 | 连接池满时固定 `time.sleep(0.1)` × 10 | 改用指数退避：0.1s → 0.2s → 0.4s |
| 2 | `src/infra/llm.py` | 172-181 | `_call_api()` 内部 3 次重试使用线性延迟 | 当前 `sleep(1*(attempt+1))` 实际是线性非指数退避，建议改为 `2**attempt` |

---

## 4. 并发安全 — `⚠️ 中危`

### 🟡 并发不安全的全局状态

| # | 文件 | 变量 | 是否有锁 | 风险评估 |
|---|------|------|----------|----------|
| 1 | `src/services/cache.py` / `src/taiyang/cache.py` | `_cache_hits`, `_cache_misses` | `_cache_lock` ✅ | 读写操作均在 asyncio.Lock 保护下，**安全** |
| 2 | `src/infra/llm.py` | `_ai_cache: dict` | `_ai_cache_lock` ✅ | 仅在 `call_mimo_async` 中写入，**安全** |
| 3 | `src/orchestration/state_manager.py` | `_sessions: OrderedDict` | ❌ 无锁 | `get_or_create` 被多个协程并发调用时 `OrderedDict` 存在竞态风险 |
| 4 | `src/db/memory_store.py` | `_cache_hash/_cache_name` | `self._lock` ✅ | 在 MemoryStore 实例级别持有 threading.Lock，**安全** |
| 5 | `src/db/memory_store.py` | `_files_cache`, `_files_cache_time` | ❌ 部分无锁 | `self._files_cache` 在 `_get_files_meta` 中被访问但未始终在 `self._lock` 持有区间内 |
| 6 | `src/infra/rate_limiter.py` | `_rate_limiters: Dict` | ❌ 无锁 | 全局字典被多线程并发访问 `get_rate_limiter()` 无锁 |
| 7 | `src/infra/concurrency.py` | `_requests: list`（RateLimiter 类） | `self._lock` ✅ | 类的 `_lock` 是 asyncio.Lock，在 asyncio 环境下安全。**但** `get_remaining()` 方法未获取锁！ |

### 🔴 高危发现

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| 1 | `src/infra/concurrency.py` | 43-46 | `RateLimiter.get_remaining()` 直接修改 `self._requests` 列表但未获取 `self._lock`，会产生数据竞争 |

### 🟡 中等风险

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| 2 | `src/infra/rate_limiter.py` | 69 | `SlidingWindowRateLimiter.acquire()` 和 `get_remaining()` 操作 `_requests` deque **没有锁** |
| 3 | `src/infra/rate_limiter.py` | 82 | 全局 `_rate_limiters` 字典的 `get_rate_limiter()` 无锁保护写入 |

### 🔧 修复建议

```python
# concurrency.py — RateLimiter.get_remaining() 加锁
def get_remaining(self) -> int:
    """获取剩余许可数"""
    now = time.time()
    with self._lock:  # ← 补充
        self._requests = [t for t in self._requests if t > now - self.period_seconds]
        return max(0, self.max_requests - len(self._requests))
```

---

## 5. 内存泄漏风险 — `⚠️ 中危`

### 🔴 高危：无限增长的全局缓存

| # | 文件 | 行号 | 变量 | 风险 |
|---|------|------|------|------|
| 1 | `src/infra/llm.py` | 20 | `_ai_cache: dict` | 通过 `call_mimo_async()` 写入，仅 `get_cached_answer()` 调用 `.pop()` 清理。若 `get_cached_answer` 调用频率低或 skip 某些 key，则无限增长 |
| 2 | `src/services/llm.py` | 20 | `_ai_cache: dict` | 同上（services/llm.py 是 infra/llm.py 的副本） |
| 3 | `src/infra/rate_limiter.py` | 77 | `_rate_limiters: Dict` | 无限增长，每个新 name 创建新 SlidingWindowRateLimiter |

### ✅ 有防护的缓存（良好）

| 缓存 | 最大容量 | TTL | 评价 |
|------|----------|-----|------|
| `src/services/cache.py` L1 | 200 条 | 3600s | ✅ 写满了淘汰旧条目 |
| `src/services/cache.py` L2 | 100 条 | 3600s | ✅ 有过期清理 |
| `src/taiyang/cache.py` L1/L2 | 200/100 条 | 3600s | ✅ 同上 |
| `src/orchestration/state_manager.py` | 100 sessions | 3600s | ✅ LRU 淘汰 + 过期清理 |
| `src/db/memory_store.py` | 500 条/缓存 | N/A | ✅ OrderedDict 有上限 |
| `src/db/data_store.py` | 动态 TTL | 30-120s | ✅ 时间过期 |

### 🔧 修复建议

```python
# llm.py — 限制 _ai_cache 大小
MAX_CACHE_SIZE = 1000

async def call_mimo_async(query, sources, messages, api_key):
    answer = await call_llm(query, ...)
    if answer:
        async with _ai_cache_lock:
            if len(_ai_cache) >= MAX_CACHE_SIZE:
                # 淘汰最旧的 key（dict 保序自 3.7）
                _ai_cache.pop(next(iter(_ai_cache)))
            _ai_cache[query] = answer
```

---

## 6. 数据库连接管理 — `✅ 良好`

### ✅ 良好实践

| 组件 | 文件 | 机制 | 评价 |
|------|------|------|------|
| 统一 DB 模块 | `src/core/db.py` | `@contextmanager connect(name)` with 自动 close | ✅ 事务安全 |
| 连接池 | `src/infra/connection_pool.py` | `SQLiteConnectionPool` + `contextmanager` | ✅ finally 确保归还 |
| MemoryStore | `src/db/memory_store.py` | 单例长连接 `self._db_conn`，`check_same_thread=False` | ✅ 适合 SQLite |
| Wiki Engine | `src/taiyang/wiki.py` | 每个方法独立 `connect + execute + close` | ✅ 方法级连接 |
| Distiller | `src/shaoyang/distiller.py` | 同上 | ✅ |
| AutoClassifier | `src/shaoyang/auto_classifier.py` | 同上 | ✅ |
| 评测模块 | `src/eval/eval_dataset.py` | 同上 | ✅ |

### 🟡 改进建议

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| 1 | `src/db/memory_store.py` | 67-71 | `_ensure_db()` 创建连接后无异常回滚机制（如果建表失败，连接留在初始状态） |

### 🔧 改进建议

```python
# connection_pool.py — 为异常路径添加回滚
@contextmanager
def get_connection(self):
    conn = None
    # ... 获取逻辑 ...
    try:
        yield conn
    except Exception:
        conn.rollback()  # ← 补充异常时回滚
        raise
    finally:
        with self._lock:
            self._pool.append(conn)
            self._active_connections -= 1
```

---

## 7. ChromaDB 使用 — `✅ 良好`

### 📊 ChromaDB 实例总览

| 实例 | 文件 | 类型 | 使用方式 | 评价 |
|------|------|------|----------|------|
| kb_chunks | `src/db/vector_store.py` | PersistentClient | 单例 + 自愈重连 | ✅ 封装完善 |
| wiki_summaries | `src/taiyang/wiki.py` | PersistentClient | WikiEngine 实例变量 | ✅ |
| kb_tables | `src/services/table_view.py` | 每次新建 PersistentClient | ⚠️ 性能考虑 |

### 🟡 改进建议

| # | 文件 | 行号 | 问题 | 建议 |
|---|------|------|------|------|
| 1 | `src/services/table_view.py` | 133 | `get_table_store()` 每次调用都创建新的 `PersistentClient`，没有复用 | 改为单例或复用连接 |

### 🔧 修复建议

```python
# table_view.py — 复用 ChromaDB client
_table_client = None
_table_collection = None

def get_table_store():
    global _table_client, _table_collection
    if _table_collection is not None:
        return _table_collection
    # ... 初始化逻辑复用 ...
```

---

## 8. 文件句柄泄漏 — `⚠️ 中危`

### 🔴 高危：无 with 且无显式 close

| # | 文件 | 行号 | 代码 | 风险 |
|---|------|------|------|------|
| 1 | `src/shaoyang/auto_classifier.py` | 187 | `json.load(open("...", encoding="utf-8"))` | **文件句柄永不关闭** — 虽然一次性读取后短时间内 GC 回收，但不可靠 |
| 2 | `src/api/evaluation.py` | 37 | `return json.load(f)` | 已通过 `with open()` 传入（外层有 with），✅ 安全 |

### ✅ 良好：使用 with 或显式 close

以下模式覆盖了绝大多数文件操作：
- `src/pipeline/parsers.py` — `fitz.open()` 后有 `doc.close()` ✅
- `src/pipeline/unified.py` — 同上 ✅
- `src/shaoyang/ingest.py` — 各种 `with open/fitz.open/pdfplumber.open` ✅
- All 日志写入 — `with open(log_file, "a")` ✅

### 🔧 修复建议

```python
# auto_classifier.py:187
# Before:
graph = json.load(open("data/knowledge_graph.json", encoding="utf-8"))
# After:
with open("data/knowledge_graph.json", encoding="utf-8") as f:
    graph = json.load(f)
```

---

## 9. JSON 解析安全 — `⚠️ 中危`

### 📊 JSON 解析统计

共发现 **73 处** `json.loads/json.load` 调用。

### 🔴 高危：LLM 输出 JSON 无异常守护

| # | 文件 | 行号 | 代码 | 问题 |
|---|------|------|------|------|
| 1 | `src/services/evaluator.py` | 57 | `return json.loads(resp[s:e])` | LLM 输出可能不是有效 JSON，在 try 内有 except pass 但返回 dict 不完整 |
| 2 | `src/services/evaluator.py` | 79 | `return json.loads(resp[s:e])` | 同上 |
| 3 | `src/shaoyin/judge_v2.py` | 45 | `data = json.loads(result)` | 如果 LLM 返回非 JSON 会抛出未捕获异常 |
| 4 | `src/shaoyin/judge_v2.py` | 52 | `return json.loads(match.group())` | 正则匹配后直接解析，可能失败 |
| 5 | `src/shaoyin/judge.py` | 42 | `return json.loads(result)` | 同上 |

### 🟡 中危：文件读取 JSON 无异常守护

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| 6 | `src/api/auth_routes.py` | 35, 62 | `json.loads(users_file.read_text(...))` — 如果文件损坏则 500 |
| 7 | `src/db/data_store.py` | 100, 177, 243, 272, 284 | 多处 `json.loads(XXX.read_text(...))` 无 try/except |
| 8 | `src/eval/evolver.py` | 136, 207, 230 | 同上 |
| 9 | `src/growth/learner.py` | 25 | 同上 |

### ✅ 良好：有异常守护

| # | 文件 | 行号 | 机制 |
|---|------|------|------|
| 1 | `src/config/__init__.py` | 43 | `json.loads(raw, strict=False)` — 容错模式 |
| 2 | `src/infra/llm.py` | 145 | `try/except (json.JSONDecodeError, KeyError, IndexError)` |
| 3 | `src/db/memory_store.py` | 133 | `isinstance(doc_json, str)` 检查 |
| 4 | `src/taiyang/wiki.py` | 82 | `json.loads` 在 `_safe_json_parse` 内，有 try/except |

### 🔧 修复建议

```python
# 统一：所有 json.loads 应加 try/except
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    logger.warning(f"JSON parse error: {e}")
    return default_value
```

---

## 10. pickle 安全 — `✅ 无风险`

> 全仓库搜索 `pickle.load` 和 `pickle.loads`，**0 处调用**。
> 本项目未使用 pickle 序列化，无相关安全风险。

---

## 📋 改进优先级矩阵

| 优先级 | 维度 | 发现数 | 预估工作量 | 阻塞生产 |
|--------|------|--------|-----------|----------|
| 🔴 P0 | 2. 超时设置 | 1 高危 | 10 min | ❌ 但应修复 |
| 🔴 P0 | 8. 文件句柄泄漏 | 1 高危 | 5 min | ❌ |
| 🔴 P0 | 9. JSON 解析安全 (LLM) | 5 高危 | 30 min | ❌ 可能导致回答失败 |
| 🟡 P1 | 1. 错误处理完备性 | 13 端点 | 2 hr | ❌ 但不优雅 |
| 🟡 P1 | 4. 并发安全 (数据竞争) | 1 高危 + 2 中危 | 1 hr | ❌ 高并发才触发 |
| 🟡 P1 | 5. 内存泄漏 | 3 全局缓存 | 1 hr | ❌ 长期运行触发 |
| 🟢 P2 | 9. JSON 解析安全 (文件) | 10 处 | 1 hr | ❌ |
| 🟢 P2 | 7. ChromaDB 复用 | 1 处 | 15 min | ❌ 仅性能 |
| 🟢 P2 | 3. 重试策略优化 | 2 处 | 30 min | ❌ |

---

## 🔧 一键修复脚本参考

```bash
#!/bin/bash
# 快速修复 P0 问题

# 1. 修复 evaluator.py 超时问题
sed -i 's/headers={"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application\/json"},/headers={"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application\/json"},\n            timeout=30,/' src/services/evaluator.py

# 2. 修复 auto_classifier.py 文件句柄
sed -i 's/graph = json.load(open("data\/knowledge_graph.json", encoding="utf-8"))/with open("data\/knowledge_graph.json", encoding="utf-8") as f:\n    graph = json.load(f)/' src/shaoyang/auto_classifier.py
```

---

*审计结束，报告生成于 `docs/audit_round3_runtime.md`*
