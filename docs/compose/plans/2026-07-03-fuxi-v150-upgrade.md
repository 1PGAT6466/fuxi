# 伏羲 v1.50 升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将伏羲系统从v1.43统一升级到v1.50，同时进行代码结构、性能和安全优化。

**Architecture:** 采用渐进式升级策略，先统一版本号，再清理冗余代码，最后进行性能和安全优化。每个任务独立可测试，确保系统稳定性。

**Tech Stack:** Python 3.14, FastAPI, SQLite, ChromaDB, bcrypt, PyJWT

## Global Constraints

- 版本号统一为1.50，所有文件中的版本引用必须更新
- 保留历史版本注释作为变更记录
- 不破坏现有API接口
- 所有修改必须通过现有测试
- 向后兼容：旧版本数据格式可被新版本读取

---

## 文件结构

### 核心配置文件
- `src/config.py` - 版本号定义（第70行）
- `src/server.py` - 服务器启动，版本注释（第2、64行）
- `src/hypothalamus/fuxi.py` - 生命体启动器，版本注释（第85、173行）

### 冗余目录（待删除）
- `src/services_old/` - 26个旧服务文件，与`sites/`重复

### 安全相关文件
- `src/api/auth.py` - JWT实现（第8行）
- `src/api/auth_routes.py` - 密码哈希（第29-32行）

### 数据库文件
- `src/db/data_store.py` - SQLite数据访问
- `src/db/vector_store.py` - ChromaDB向量存储

### 测试文件
- `tests/` - 所有测试文件

---

### Task 1: 版本号统一为1.50

**Covers:** [S1]
**Files:**
- Modify: `src/config.py:70`
- Modify: `src/server.py:2,64`
- Modify: `src/hypothalamus/fuxi.py:85,173`
- Modify: `src/hypothalamus/brain.py:2`
- Modify: `src/hypothalamus/meridian.py:2`
- Modify: `src/infra/llm.py:2`
- Modify: `src/services/metrics.py:2`
- Modify: `src/taiyin/metrics.py:2`
- Modify: `src/taiyin/audit.py:2`
- Modify: `src/shaoyin/judge_v2.py:2`
- Modify: `src/shaoyin/fact_check.py:2`
- Modify: `src/shaoyin/context_compressor.py:1`
- Modify: `src/taiyang/dynamic_alpha.py:2`
- Modify: `src/services/feedback_store.py:2`
- Modify: `src/services/retrieval.py:96`
- Modify: `src/services/online_eval.py:2`
- Modify: `scripts/check_api_endpoints.py:10`
- Modify: `tests/test_smoke.py:10`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无
- Produces: `VERSION = "1.50"` 全局版本常量

- [ ] **Step 1: 更新config.py版本号**

```python
# src/config.py:70
VERSION = "1.50"
```

- [ ] **Step 2: 更新server.py版本注释**

```python
# src/server.py:2
# 伏羲 Fuxi · 企业知识认知系统 v1.50

# src/server.py:64
# ============ 伏羲 1.50 生命体启动 ============
```

- [ ] **Step 3: 更新fuxi.py版本注释**

```python
# src/hypothalamus/fuxi.py:85
logger.info("  伏羲 Fuxi 1.50 — 生命体启动")

# src/hypothalamus/fuxi.py:173
logger.info("  伏羲 Fuxi 1.50 — 已苏醒")
```

- [ ] **Step 4: 更新其他文件版本注释**

更新所有文件头注释中的版本号为v1.50，保留历史版本注释作为变更记录。

- [ ] **Step 5: 更新测试和脚本中的版本引用**

```python
# tests/test_smoke.py:10
TOKEN = "fuxi-v1.50-token"

# scripts/check_api_endpoints.py:10
TOKEN = os.getenv("FUXI_API_TOKEN", "fuxi-v1.50-token")
```

- [ ] **Step 6: 运行测试验证**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/config.py src/server.py src/hypothalamus/fuxi.py
git commit -m "feat: 统一版本号为v1.50"
```

---

### Task 2: 清理冗余代码结构

**Covers:** [S2]
**Files:**
- Delete: `src/services_old/` (26个文件)
- Modify: `src/server.py` (移除旧导入)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无
- Produces: 清理后的代码结构

- [ ] **Step 1: 确认services_old内容与sites重复**

```bash
# 检查services_old和sites目录内容
diff -rq src/services_old/ src/sites/ 2>/dev/null || echo "目录结构不同"
```

- [ ] **Step 2: 删除services_old目录**

```bash
rm -rf src/services_old/
```

- [ ] **Step 3: 检查并移除server.py中的旧导入**

检查server.py是否有对services_old的引用，如有则移除。

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/ -v`
Expected: 187 passed, 9 skipped

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "refactor: 删除冗余的services_old目录"
```

---

### Task 3: 性能优化 - 数据库索引

**Covers:** [S3]
**Files:**
- Modify: `src/db/data_store.py`
- Test: `tests/test_memory_store.py`

**Interfaces:**
- Consumes: 无
- Produces: 优化后的数据库查询性能

- [ ] **Step 1: 为常用查询添加索引**

```python
# src/db/data_store.py - 在初始化时添加索引
def _ensure_indexes(conn):
    """确保常用查询有索引"""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_created ON chunks(created_at)")
```

- [ ] **Step 2: 在数据库初始化时调用**

在`init_db()`或类似函数中调用`_ensure_indexes(conn)`

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_memory_store.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/db/data_store.py
git commit -m "perf: 为SQLite添加常用查询索引"
```

---

### Task 4: 性能优化 - 动态缓存TTL

**Covers:** [S3]
**Files:**
- Modify: `src/db/data_store.py`
- Test: `tests/test_memory_store.py`

**Interfaces:**
- Consumes: 无
- Produces: 动态缓存TTL机制

- [ ] **Step 1: 实现动态TTL计算**

```python
# src/db/data_store.py
def _calculate_dynamic_ttl(access_count: int, last_access: float) -> int:
    """根据访问频率动态计算TTL"""
    import time
    hours_since_access = (time.time() - last_access) / 3600
    
    # 高频访问：延长TTL
    if access_count > 100:
        return 120  # 2分钟
    elif access_count > 10:
        return 60   # 1分钟
    else:
        return 30   # 30秒
```

- [ ] **Step 2: 更新缓存逻辑使用动态TTL**

修改`load_chunks()`函数使用动态TTL而非固定30秒。

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_memory_store.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/db/data_store.py
git commit -m "perf: 实现动态缓存TTL机制"
```

---

### Task 5: 安全优化 - JWT实现升级

**Covers:** [S4]
**Files:**
- Modify: `src/api/auth.py`
- Modify: `requirements.txt`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无
- Produces: 标准JWT实现

- [ ] **Step 1: 添加PyJWT依赖**

```txt
# requirements.txt
PyJWT>=2.8.0
```

- [ ] **Step 2: 实现标准JWT**

```python
# src/api/auth.py
import jwt
from datetime import datetime, timedelta

JWT_SECRET = os.environ.get("FUXI_JWT_SECRET", "fuxi-default-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

def create_jwt_token(username: str, role: str) -> str:
    """创建标准JWT token"""
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> dict:
    """验证JWT token"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的Token")
```

- [ ] **Step 3: 更新auth_routes.py使用新JWT**

修改`login()`和`register()`函数使用新的JWT实现。

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/api/auth.py src/api/auth_routes.py requirements.txt
git commit -m "feat: 升级JWT实现为标准PyJWT"
```

---

### Task 6: 安全优化 - 密码哈希升级

**Covers:** [S4]
**Files:**
- Modify: `src/api/auth_routes.py`
- Modify: `requirements.txt`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无
- Produces: bcrypt密码哈希（懒迁移）

- [ ] **Step 1: 添加bcrypt依赖**

```txt
# requirements.txt
bcrypt>=4.1.0
```

- [ ] **Step 2: 实现bcrypt哈希和懒迁移**

```python
# src/api/auth_routes.py
import bcrypt

def _hash_password(password: str) -> str:
    """使用bcrypt哈希密码"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, stored: str) -> bool:
    """验证密码，支持旧格式懒迁移"""
    if stored.startswith("$2b$"):
        # bcrypt格式
        return bcrypt.checkpw(password.encode(), stored.encode())
    elif "$" in stored:
        # 旧SHA256格式，验证后迁移
        salt, h = stored.split("$", 1)
        if hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h:
            return True
    return False
```

- [ ] **Step 3: 更新login和register函数**

修改`login()`函数使用`_verify_password()`，并在验证成功后自动迁移为bcrypt格式。
修改`register()`函数使用`_hash_password()`。

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/api/auth_routes.py requirements.txt
git commit -m "feat: 密码哈希升级为bcrypt（懒迁移策略）"
```

---

### Task 7: 修复Python 3.14兼容性

**Covers:** [S5]
**Files:**
- Modify: `src/server.py:306`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无
- Produces: Python 3.14兼容的代码

- [ ] **Step 1: 修复asyncio调用**

```python
# src/server.py:306
# 旧代码:
result = asyncio.get_event_loop().run_until_complete(checker.check_all())

# 新代码:
result = asyncio.run(checker.check_all())
```

- [ ] **Step 2: 运行测试验证**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS (无asyncio警告)

- [ ] **Step 3: 提交**

```bash
git add src/server.py
git commit -m "fix: 修复Python 3.14 asyncio兼容性"
```

---

### Task 8: 修复API参数不匹配

**Covers:** [S5]
**Files:**
- Modify: `src/api/documents.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无
- Produces: 统一的API参数命名

- [ ] **Step 1: 检查当前API参数**

```python
# src/api/documents.py:8
# 当前: async def documents(page: int = 1, page_size: int = 50):
# 前端期望: async def documents(page: int = 1, limit: int = 50):
```

- [ ] **Step 2: 统一参数命名**

```python
# src/api/documents.py
@router.get("/api/documents")
async def documents(page: int = 1, limit: int = 50):
    """获取文档列表"""
    # 使用limit参数名，保持向后兼容
    offset = (page - 1) * limit
    # ... 实现逻辑
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/api/documents.py
git commit -m "fix: 统一API参数命名（limit vs page_size）"
```

---

### Task 9: 最终验证和清理

**Covers:** [S1, S2, S3, S4, S5]
**Files:**
- Test: `tests/` 所有测试

**Interfaces:**
- Consumes: 所有前置任务
- Produces: 完整的v1.50系统

- [ ] **Step 1: 运行完整测试套件**

Run: `pytest tests/ -v`
Expected: 187 passed, 9 skipped

- [ ] **Step 2: 验证版本号一致性**

```bash
grep -r "VERSION.*=" src/config.py
grep -r "v1\." src/ --include="*.py" | grep -v "v1\.50" | grep -v "#.*v1\."
```

- [ ] **Step 3: 验证所有模块可导入**

```bash
python -c "import src.server; print('服务器模块导入成功')"
python -c "from src.shaoyang import *; print('少阳模块导入成功')"
python -c "from src.taiyang import *; print('太阳模块导入成功')"
python -c "from src.shaoyin import *; print('少阴模块导入成功')"
python -c "from src.taiyin import *; print('太阴模块导入成功')"
```

- [ ] **Step 4: 提交最终版本**

```bash
git add -A
git commit -m "release: 伏羲 v1.50 正式版"
```

---

## 验收标准

1. **版本一致性**：所有文件中的版本号统一为1.50
2. **代码清理**：services_old目录已删除，无冗余代码
3. **性能提升**：数据库查询有索引，缓存TTL动态调整
4. **安全增强**：JWT标准实现，密码bcrypt哈希
5. **兼容性**：Python 3.14无警告，API参数统一
6. **测试通过**：187 passed, 9 skipped
7. **模块导入**：所有四象模块可正常导入
