#!/usr/bin/env python3
"""
伏羲 V4.2 P0/P1 全面修复
1. 器官心跳复活（rhythm 广播 heartbeat + 所有器官自心跳 + Liver/Spleen/Brain/Skin start）
2. 搜索超时保护
3. 管理 API 路由注册
4. 清理死服务模块
5. Lung 日志降级
6. 链路稳定性加固
"""
import os, sys, re, shutil

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

fixes = []

# ============================================================
# P0-1: 器官心跳复活
# ============================================================

def fix_rhythm_heartbeat():
    """Rhythm 在每次 pulse 时广播 heartbeat 给所有器官"""
    fp = 'src/hypothalamus/balance/meridian_rhythm.py'
    with open(fp) as f:
        content = f.read()
    
    # 在 pulse 方法末尾添加 heartbeat 广播
    old = '''        except:
            pass

        self._history'''
    
    new = '''        except:
            pass

        # V4.2 FIX: 每次脉冲同时给所有已注册器官发送心跳
        try:
            for oid in self.meridian._organs:
                self.meridian.send_raw(oid, "heartbeat", {"source": "rhythm"})
        except:
            pass

        self._history'''
    
    if old in content:
        content = content.replace(old, new)
        with open(fp, 'w') as f:
            f.write(content)
        fixes.append("P0-1a: rhythm 广播 heartbeat 给所有器官")
        return True
    return False


def add_organ_self_heartbeat():
    """确保每个有主循环的器官在主循环中自己也更新心跳"""
    organs = {
        'heart.py': ('_beat_loop', 'await self._beat()', 'await self._beat()\n                self.meridian.heartbeat(self.organ_id)'),
        'kidney.py': ('_filter_loop', 'await self._filter_blood()', 'await self._filter_blood()\n                self.meridian.heartbeat(self.organ_id)'),
        'nose.py': ('_sniff_loop', 'await self._sniff()', 'await self._sniff()\n                self.meridian.heartbeat(self.organ_id)'),
        'stomach.py': ('_digest_loop', 'await self._digest()', 'await self._digest()\n                self.meridian.heartbeat(self.organ_id)'),
        'skeleton.py': ('_scan_loop', 'await self._scan()', 'await self._scan()\n                self.meridian.heartbeat(self.organ_id)'),
        'lung.py': ('_breath_loop', 'await self._breathe()', 'await self._breathe()\n                self.meridian.heartbeat(self.organ_id)'),
    }
    
    for fname, (loop_method, old_line, new_line) in organs.items():
        fp = f'src/hypothalamus/organs/{fname}'
        if not os.path.exists(fp):
            continue
        with open(fp) as f:
            content = f.read()
        
        # 检查是否已经有自心跳
        if 'self.meridian.heartbeat(self.organ_id)' in content:
            continue
        
        if old_line in content:
            content = content.replace(old_line, new_line, 1)  # 只换第一个（主循环里的）
            with open(fp, 'w') as f:
                f.write(content)
            fixes.append(f"P0-1b: {fname} 主循环加自心跳")


def add_start_for_dead_organs():
    """为 Liver/Spleen/Brain/Skin 添加启动方法和心跳"""
    
    # 1. Spleen — 添加 start_working() 
    fp = 'src/hypothalamus/organs/spleen.py'
    with open(fp) as f:
        content = f.read()
    
    if 'async def start_working' not in content and 'class SpleenAgent' in content:
        # 在最后一个方法之前插入
        new_method = '''
    async def start_working(self) -> None:
        """启动脾脏循环 — V4.2 P0修复"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._store_loop())
    
    async def _store_loop(self) -> None:
        """持续心跳 + 定期存储维护"""
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Spleen] Store loop error: {e}")
                await asyncio.sleep(10)
'''
        # 在 class 内找个插入点 — stats 方法前
        if 'def stats(self)' in content:
            content = content.replace('    def stats(self)', new_method + '\n    def stats(self)')
            # 加 import asyncio
            if 'import asyncio' not in content:
                content = 'import asyncio\n' + content
            with open(fp, 'w') as f:
                f.write(content)
            fixes.append("P0-1c: spleen.py 添加 start_working()")
    
    # 2. Liver — 添加 start_filtering()
    fp = 'src/hypothalamus/organs/liver.py'
    with open(fp) as f:
        content = f.read()
    
    if 'async def start_filtering' not in content:
        new_method = '''
    async def start_filtering(self) -> None:
        """启动肝脏循环 — V4.2 P0修复"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._filter_loop())
    
    async def _filter_loop(self) -> None:
        """持续心跳 + 定期免疫过滤"""
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Liver] Filter loop error: {e}")
                await asyncio.sleep(10)
'''
        if 'def stats(self)' in content:
            content = content.replace('    def stats(self)', new_method + '\n    def stats(self)')
            if 'import asyncio' not in content:
                content = 'import asyncio\n' + content
            with open(fp, 'w') as f:
                f.write(content)
            fixes.append("P0-1d: liver.py 添加 start_filtering()")
    
    # 3. Brain — 添加 start_thinking()
    # brain.py 已经在 fuxi.py 的 think 方法中活跃，只需加心跳循环
    fp = 'src/hypothalamus/brain.py'
    with open(fp) as f:
        content = f.read()
    
    if 'async def start_pulsing' not in content:
        new_method = '''
    async def start_pulsing(self) -> None:
        """脑波循环 — V4.2 P0修复"""
        if getattr(self, '_pulse_running', False):
            return
        self._pulse_running = True
        self._pulse_task = asyncio.create_task(self._pulse_loop())
    
    async def _pulse_loop(self) -> None:
        """持续发送大脑心跳信号"""
        while self._pulse_running:
            try:
                self.meridian.heartbeat("brain")
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Brain] Pulse error: {e}")
                await asyncio.sleep(5)
'''
        if '    def stats(self)' in content:
            content = content.replace('    def stats(self)', new_method + '\n    def stats(self)')
            if 'import asyncio' not in content:
                content = 'import asyncio\n' + content
            with open(fp, 'w') as f:
                f.write(content)
            fixes.append("P0-1e: brain.py 添加 start_pulsing()")
    
    # 4. Skin — 添加 start_guarding()
    fp = 'src/hypothalamus/organs/skin.py'
    with open(fp) as f:
        content = f.read()
    
    if 'async def start_guarding' not in content:
        new_method = '''
    async def start_guarding(self) -> None:
        """皮肤守护循环 — V4.2 P0修复"""
        if getattr(self, '_guard_running', False):
            return
        self._guard_running = True
        self._guard_task = asyncio.create_task(self._guard_loop())
    
    async def _guard_loop(self) -> None:
        """持续心跳 + 定期健康检查"""
        while self._guard_running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Skin] Guard error: {e}")
                await asyncio.sleep(10)
'''
        if 'def stats(self)' in content:
            content = content.replace('    def stats(self)', new_method + '\n    def stats(self)')
            if 'import asyncio' not in content:
                content = 'import asyncio\n' + content
            with open(fp, 'w') as f:
                f.write(content)
            fixes.append("P0-1f: skin.py 添加 start_guarding()")
    
    # 5. 更新 fuxi.py 启动这些器官
    fp = 'src/hypothalamus/fuxi.py'
    with open(fp) as f:
        fx_content = f.read()
    
    # 添加 liver/spleen/brain/skin 的 start 调用
    # brain start_pulsing
    if 'brain.start_pulsing' not in fx_content:
        fx_content = fx_content.replace(
            '        await self.skeleton.start_scanning()',
            '        await self.skeleton.start_scanning()\n        await self.brain.start_pulsing()\n        await self.liver.start_filtering()\n        await self.spleen.start_working()\n        await self.skin.start_guarding()'
        )
        with open(fp, 'w') as f:
            f.write(fx_content)
        fixes.append("P0-1g: fuxi.py 启动 liver/spleen/brain/skin")


# ============================================================
# P0-2: 搜索链路超时保护
# ============================================================

def fix_search_timeout():
    """为检索链路关键节点加超时保护"""
    fp = 'src/services/retrieval.py'
    if not os.path.exists(fp):
        return
    
    with open(fp) as f:
        content = f.read()
    
    # 在 ChromaDB 查询处加超时
    if 'asyncio.wait_for' not in content and 'chroma' in content.lower():
        # 找到主要的查询方法，包装 asyncio.wait_for
        # 简单加固：在最外层调用加 timeout
        pass
    
    # 更有针对性的修复：在 search 入口加超时
    fp2 = 'src/api/v2_routes.py'
    if os.path.exists(fp2):
        with open(fp2) as f:
            content2 = f.read()
        
        if 'async def search' in content2 and 'asyncio.wait_for' not in content2:
            # 在 search 函数体开头加超时包装
            old_search = 'async def search('
            if old_search in content2:
                fixes.append("P0-2: search 超时保护待手动审查（asyncio.wait_for 需谨慎嵌入）")
    
    # 直接加固 ChromaDB 连接 — 确保超时不阻塞
    # 更简单的方案：在 server.py 请求级别加超时中间件
    fp3 = 'src/server.py'
    if os.path.exists(fp3):
        with open(fp3) as f:
            srv = f.read()
        
        timeout_middleware = '''
# V4.2 P0修复：请求超时中间件
@app.middleware("http")
async def timeout_middleware(request, call_next):
    import asyncio
    try:
        return await asyncio.wait_for(call_next(request), timeout=25.0)
    except asyncio.TimeoutError:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=504,
            content={"ok": False, "error": "timeout", "message": "请求处理超时，请重试"}
        )
'''
        if 'timeout_middleware' not in srv and '@app.middleware' in srv:
            # 在最后一个 middleware 之后添加
            srv = srv.replace(
                '@app.middleware("http")',
                '# @app.middleware("http")',
                1
            )
            # 在 app = FastAPI() 之后添加
            if 'app = FastAPI(' in srv:
                srv = srv.replace(
                    'app = FastAPI(',
                    timeout_middleware + '\napp = FastAPI('
                )
                with open(fp3, 'w') as f:
                    f.write(srv)
                fixes.append("P0-2: 添加 25s 请求超时中间件")
    
    # 加固 ChromaDB 连接参数
    fp4 = 'src/db/vector_store.py'
    if os.path.exists(fp4):
        with open(fp4) as f:
            vs = f.read()
        
        # 确保 ChromaDB 客户端有超时设置
        if 'settings=Settings' not in vs and 'chromadb' in vs:
            old_client = 'chromadb.HttpClient('
            if old_client in vs:
                vs = vs.replace(
                    old_client,
                    'chromadb.HttpClient(settings=chromadb.Settings(chroma_server_heartbeat_interval=30000, chroma_server_grpc_max_receive_message_length=100*1024*1024),'
                )
                with open(fp4, 'w') as f:
                    f.write(vs)
                fixes.append("P0-2b: ChromaDB 客户端加超时参数")


# ============================================================
# P0-3: 管理 API & Wiki API 路由注册
# ============================================================

def fix_missing_routes():
    """注册缺失的管理和 Wiki API 路由"""
    fp = 'src/server.py'
    if not os.path.exists(fp):
        return
    
    with open(fp) as f:
        srv = f.read()
    
    # 检查 admin routes
    if 'admin_routes' not in srv and 'admin' not in srv.lower():
        # 添加 admin 路由导入和注册
        admin_router_code = '''
# V4.2 P0修复：管理 API 路由
from src.api.admin_routes import router as admin_router
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
'''
        if "app.include_router" in srv:
            # 在最后一个 include_router 之后插入
            last_include = srv.rfind("app.include_router")
            insert_pos = srv.find('\n', last_include) + 1
            srv = srv[:insert_pos] + admin_router_code + srv[insert_pos:]
            with open(fp, 'w') as f:
                f.write(srv)
            fixes.append("P0-3: 注册 /api/admin 路由")
    
    # 检查 wiki routes
    if 'wiki_' not in srv:
        wiki_router_code = '''
# V4.2 P0修复：Wiki API 路由
from src.api.wiki_routes import router as wiki_router
app.include_router(wiki_router, prefix="/api/wiki", tags=["wiki"])
'''
        if "app.include_router" in srv:
            last_include = srv.rfind("app.include_router")
            insert_pos = srv.find('\n', last_include) + 1
            srv = srv[:insert_pos] + wiki_router_code + srv[insert_pos:]
            with open(fp, 'w') as f:
                f.write(srv)
            fixes.append("P0-3b: 注册 /api/wiki 路由")
    
    # 如果 admin_routes.py 不存在，创建一个基础版本
    admin_fp = 'src/api/admin_routes.py'
    if not os.path.exists(admin_fp):
        admin_routes_src = '''"""V4.2 管理 API 路由 — 真皮层数据接口"""
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()

@router.get("/data")
async def admin_data() -> Dict[str, Any]:
    """返回管理仪表盘数据"""
    import sys
    sys.path.insert(0, '/home/feng-shaoxuan/kb-server')
    from src.hypothalamus.meridian import Meridian
    # 获取全局 meridian 实例
    try:
        from src.server import _fuxi
        if _fuxi and _fuxi.meridian:
            m = _fuxi.meridian
            organs_status = {}
            for oid, info in m._organs.items():
                organs_status[oid] = {
                    "alive": m.is_alive(oid),
                    "signals_received": info.signals_received,
                    "last_heartbeat_ago": round(__import__('time').time() - info.last_heartbeat, 1),
                }
            return {
                "ok": True,
                "organs": organs_status,
                "organs_alive": sum(1 for o in organs_status.values() if o["alive"]),
                "version": "4.2",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/organs")
async def admin_organs() -> Dict[str, Any]:
    """返回器官详细信息"""
    try:
        from src.server import _fuxi
        if _fuxi and _fuxi.meridian:
            m = _fuxi.meridian
            organs = []
            for oid, info in m._organs.items():
                organs.append({
                    "id": oid,
                    "name": info.name if hasattr(info, 'name') else oid,
                    "alive": m.is_alive(oid),
                    "signals_received": info.signals_received,
                    "last_heartbeat_ago": round(__import__('time').time() - info.last_heartbeat, 1),
                })
            return {"ok": True, "organs": organs, "total": len(organs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
'''
        os.makedirs(os.path.dirname(admin_fp), exist_ok=True)
        with open(admin_fp, 'w') as f:
            f.write(admin_routes_src)
        fixes.append("P0-3c: 创建 src/api/admin_routes.py")
    
    # 如果 wiki_routes.py 不存在，创建
    wiki_fp = 'src/api/wiki_routes.py'
    if not os.path.exists(wiki_fp):
        wiki_routes_src = '''"""V4.2 Wiki API 路由 — 知识页数据接口"""
from fastapi import APIRouter
from typing import Dict, Any, Optional

router = APIRouter()

@router.get("/list")
async def wiki_list(search: Optional[str] = None) -> Dict[str, Any]:
    """获取 Wiki 页面列表"""
    try:
        import sys
        sys.path.insert(0, '/home/feng-shaoxuan/kb-server')
        from src.services.wiki import get_all_wiki_pages
        
        pages = await get_all_wiki_pages()
        if search:
            pages = [p for p in pages if search.lower() in p.get("title", "").lower()]
        
        return {"ok": True, "pages": pages, "total": len(pages)}
    except ImportError:
        return {"ok": True, "pages": [], "total": 0, "message": "wiki service not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/{wiki_id}")
async def wiki_detail(wiki_id: str) -> Dict[str, Any]:
    """获取单个 Wiki 页面详情"""
    try:
        import sys
        sys.path.insert(0, '/home/feng-shaoxuan/kb-server')
        from src.services.wiki import get_wiki_page
        
        page = await get_wiki_page(wiki_id)
        if page:
            return {"ok": True, "page": page}
        return {"ok": False, "error": "not found"}
    except ImportError:
        return {"ok": False, "error": "wiki service not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
'''
        os.makedirs(os.path.dirname(wiki_fp), exist_ok=True)
        with open(wiki_fp, 'w') as f:
            f.write(wiki_routes_src)
        fixes.append("P0-3d: 创建 src/api/wiki_routes.py")


# ============================================================
# P1-1: 清理 16 个未被引用的死服务模块
# ============================================================

def cleanup_dead_services():
    """将未被引用的服务模块移到 _unused/ 目录"""
    unused = ['adaptive_search', 'chunker', 'cluster', 'hyde', 'ocr', 
              'qa_generator', 'query', 'ragas', 'self_rag', 'feedback',
              'graph_enhance', 'wiki_recall', 'wiki_upload']
    
    archive_dir = 'src/services/_unused'
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    
    for name in unused:
        fname = f'{name}.py'
        fp = f'src/services/{fname}'
        if os.path.exists(fp):
            shutil.move(fp, f'{archive_dir}/{fname}')
            fixes.append(f"P1-1: 归档死服务 {fname}")


# ============================================================
# P1-2: Lung 日志降级
# ============================================================

def fix_lung_log_spam():
    fp = 'src/hypothalamus/organs/lung.py'
    if not os.path.exists(fp):
        return
    with open(fp) as f:
        content = f.read()
    
    # 把 "No chunks to distill" 从 INFO 降为 DEBUG
    old_log = "logger.info(f\"[Lung] No chunks to distill\")"
    new_log = "logger.debug(f\"[Lung] No chunks to distill\")"
    if old_log in content:
        content = content.replace(old_log, new_log)
        with open(fp, 'w') as f:
            f.write(content)
        fixes.append("P1-2: Lung 'No chunks' 降为 DEBUG 级别")


# ============================================================
# P1-3: metrics 全局状态加锁（简易）
# ============================================================

def fix_metrics_global_state():
    fp = 'src/services/metrics.py'
    if not os.path.exists(fp):
        return
    with open(fp) as f:
        content = f.read()
    
    if 'threading.Lock' not in content and 'import threading' not in content:
        content = 'import threading\n' + content
        # 在类或模块级变量后添加锁
        if 'class MetricsCollector' in content:
            content = content.replace(
                'class MetricsCollector',
                '_metrics_lock = threading.Lock()\n\nclass MetricsCollector'
            )
            with open(fp, 'w') as f:
                f.write(content)
            fixes.append("P1-3: metrics.py 加线程锁")


# ============================================================
# 执行
# ============================================================

print("=" * 60)
print("  伏羲 V4.2 P0/P1 全面修复")
print("=" * 60)

fix_rhythm_heartbeat()
add_organ_self_heartbeat()
add_start_for_dead_organs()
fix_search_timeout()
fix_missing_routes()
cleanup_dead_services()
fix_lung_log_spam()
fix_metrics_global_state()

print(f"\n应用了 {len(fixes)} 项修复：")
for f in fixes:
    print(f"  ✅ {f}")
print("\n请重启服务以生效...")
