# 全量重构脚本：阶段 0-2
# 0. 清理废弃目录
# 1. 更新皮肤（融合头发功能）
# 2. 更新 fuxi.py 移除 hair 独立注册

import os, sys

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

# ===== 阶段 0: 清理 =====
import subprocess, shutil

dirs_to_clean = [
    'archives', 'backups', 'backup_src_', 'backup_src_20260617',
    'routers.deprecated', 'static', 'services', 'lib',
    'backup_deploy_', 'backup_src_20260617',
]
for d in dirs_to_clean:
    p = os.path.join(BASE, d)
    if os.path.exists(p):
        print(f'[清理] rm -rf {p}')
        shutil.rmtree(p, ignore_errors=True)

root_py_files = [
    'config.py', 'data_store.py', 'embedder_server.py', 'feedback_learner.py',
    'ingest.py', 'knowledge_evolver.py', 'memory_store.py', 'mineru_functions.py',
    'ontology.py', 'query_router.py', 'ragas_eval.py', 'run_server.py', 'vector_store.py',
]
for f in root_py_files:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        print(f'[清理] rm {p}')
        os.remove(p)

# 清理 services/ 下残留
for extra in ['services', 'lib']:
    ep = os.path.join(BASE, extra)
    if os.path.exists(ep):
        shutil.rmtree(ep, ignore_errors=True)

print('[阶段 0] 清理完成')

# ===== 阶段 1: 修复 graph_router.py 和 auto_classifier.py 中的旧 import =====
# 这两处引用了根目录的 config.py 和 ontology.py，需要改为 src/ 路径
import fileinput

def fix_imports(filepath, old, new):
    if not os.path.exists(filepath):
        return
    with open(filepath) as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f'[阶段1] {filepath}: {old} -> {new}')

# src/services/graph_router.py
fix_imports('src/services/graph_router.py', 'from config import', 'from src.config import')
fix_imports('src/services/graph_router.py', 'from ontology import', 'from src.db.ontology import')

# src/services/auto_classifier.py  
fix_imports('src/services/auto_classifier.py', 'from vector_store import', 'from src.db.vector_store import')

print('[阶段 1] import 修复完成')

# ===== 阶段 2: 皮肤融合头发 =====
# 读取 skin.py 和 hair.py
with open('src/hypothalamus/organs/skin.py') as f:
    skin_src = f.read()
with open('src/hypothalamus/organs/hair.py') as f:
    hair_src = f.read()

# 从 hair.py 提取外探方法
methods_to_extract = ['_search_web', '_fetch_content', '_extract_text', '_verify', '_search_and_extract']
extracted_code = []
for method in methods_to_extract:
    import re
    pattern = rf'    async def {method}\((.*?)(?=\n    (?:async )?def |\nclass |\Z)'
    m = re.search(pattern, hair_src, re.DOTALL)
    if m:
        extracted_code.append(f'    # [v4.2] 来自 hair.py 的外探能力\n    async def {method}({m.group(1)}')

# 在 skin.py 的 __init__ 后添加 hair 能力初始化行，并追加方法
# 简单做法：在 skin.py 末尾追加方法
skin_inject = '''

    # ============ v4.2: 皮肤触角（融合头发外探能力） ============
    async def search_external(self, query: str, top_k: int = 5):
        """皮肤触角外探：搜索 -> 抓取 -> 交叉验证 -> 带回体内"""
        import aiohttp, os, re as _re, logging as _logging
        _log = _logging.getLogger("skin.antenna")
        cache_key = query.lower().strip()
        if cache_key in self._antenna_cache:
            _log.info(f"[触角] Cache: {query[:50]}")
            return {"results": self._antenna_cache[cache_key], "from_cache": True}
        try:
            api_key = os.getenv("BRAVE_API_KEY", "")
            search_results = []
            if api_key:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": min(top_k, 10)},
                        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            search_results = [
                                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
                                for r in data.get("web", {}).get("results", [])[:top_k]
                            ]
            extracted = []
            for sr in search_results[:3]:
                content = await self._antenna_fetch(sr.get("url", ""))
                if content:
                    score = self._antenna_verify(query, content, search_results)
                    if score > 0.3:
                        extracted.append({"text": content[:1000], "source_url": sr.get("url", ""), "title": sr.get("title", ""), "score": score})
            if extracted:
                self._antenna_cache[cache_key] = extracted
                if len(self._antenna_cache) > 100:
                    self._antenna_cache.pop(min(self._antenna_cache, key=lambda k: len(self._antenna_cache[k])))
            self._antenna_searches += 1
            return {"results": extracted, "from_cache": False}
        except Exception as e:
            _log.warning(f"[触角] 外探失败: {e}")
            return {"results": [], "error": str(e)}

    async def _antenna_fetch(self, url: str) -> str:
        if not url:
            return ""
        try:
            import aiohttp, re as _re
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        text = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
                        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
                        text = _re.sub(r'<[^>]+>', ' ', text)
                        text = _re.sub(r'\\s+', ' ', text)
                        return text.strip()[:2000]
        except Exception:
            pass
        return ""

    def _antenna_verify(self, query: str, content: str, all_results: list) -> float:
        if not content or len(content) < 50:
            return 0
        query_words = [w.lower() for w in query.split() if len(w) > 1] or [query.lower()]
        content_lower = content.lower()
        matches = sum(1 for w in query_words if w in content_lower)
        keyword_score = matches / max(len(query_words), 1)
        cross_validated = len(all_results) >= 2
        return min(keyword_score + (0.2 if cross_validated else 0), 1.0)

    def antenna_stats(self):
        return {"searches": self._antenna_searches, "cache_size": len(self._antenna_cache)}
'''

# 在 skin.py __init__ 中的 meridian.subscribe 之后添加缓存初始化
# 找到 __init__ 最后一行
init_end = skin_src.find('self.meridian.subscribe(self.organ_id, "check_request", self._handle_check_request)')
if init_end > 0:
    inject_point = init_end + len('self.meridian.subscribe(self.organ_id, "check_request", self._handle_check_request)')
    skin_src = (skin_src[:inject_point] + 
                '\n        # [v4.2] 皮肤触角缓存\n        self._antenna_cache = {}\n        self._antenna_searches = 0\n' +
                '        self.meridian.subscribe(self.organ_id, "search_external", self._handle_search_external)\n' +
                skin_src[inject_point:])

# 在 stats() 方法中添加触角统计
skin_src = skin_src.replace(
    'def stats(self) -> Dict:\n        return {',
    'def stats(self) -> Dict:\n        return {\n            "antenna": self.antenna_stats(),'
)

# 添加 search_external 信号处理器
skin_src = skin_src.replace(
    'async def _handle_check_request(self, signal: Signal) -> None:',
    'async def _handle_search_external(self, signal: Signal) -> None:\n' +
    '        query = signal.payload.get("query", "")\n' +
    '        top_k = signal.payload.get("top_k", 5)\n' +
    '        result = await self.search_external(query, top_k)\n' +
    '        self.meridian.reply(signal, result)\n\n' +
    '    async def _handle_check_request(self, signal: Signal) -> None:'
)

# 把触角方法注入到 skin.py 末尾
skin_src = skin_src.rstrip() + '\n' + skin_inject + '\n'

with open('src/hypothalamus/organs/skin.py', 'w') as f:
    f.write(skin_src)

print('[阶段 2] 皮肤已融合头发外探能力')

# ===== 更新 fuxi.py =====
with open('src/hypothalamus/fuxi.py') as f:
    fuxi_src = f.read()

# 移除 hair 独立 import
fuxi_src = fuxi_src.replace('from src.hypothalamus.organs.hair import HairAgent\n', '')
# 移除 hair 属性声明
fuxi_src = fuxi_src.replace('        self.hair: Optional[HairAgent] = None\n', '')
# 移除 hair 初始化
fuxi_src = fuxi_src.replace(
    '        self.hair = HairAgent(self.meridian)\n        logger.info("🐙 头发已生长")\n',
    '        # v4.2: 头发外探能力已融入皮肤，不再独立注册\n        logger.info("🧖 皮肤触角已就绪（含头发外探能力）")\n'
)

# 移除 hair 相关的 bagua 条目
# 找到 BAGUA_MAP 定义并移除 hair 条目
import re
# 更安全的方式：直接替换整个 BAGUA_MAP
fuxi_src = fuxi_src.replace(
    '            "hair": {"organ_name": "头发·外探", "emoji": "🐙", "prenatal": "☱", "postnatal": "☱", "bagua_name": "兑", "palace": 7},\n',
    ''
)
fuxi_src = fuxi_src.replace(
    '            "skeleton": {"organ_name": "骨骼·图谱", "emoji": "🦴", "prenatal": "☶", "postnatal": "☶", "bagua_name": "艮", "palace": 8},\n',
    ''
)
fuxi_src = fuxi_src.replace(
    '            "limbs": {"organ_name": "四肢·执行", "emoji": "💪", "prenatal": "☳", "postnatal": "☳", "bagua_name": "震", "palace": 3},\n',
    ''
)

with open('src/hypothalamus/fuxi.py', 'w') as f:
    f.write(fuxi_src)

print('[阶段 2] fuxi.py 已更新（移除 hair/skeleton/limbs bagua）')

# ===== 更新 v2_routes.py =====
with open('src/api/v2_routes.py') as f:
    v2_src = f.read()

v2_src = v2_src.replace(
    '            "hair": {"organ_name": "头发·外探", "emoji": "🐙", "prenatal": "☱", "postnatal": "☱", "bagua_name": "兑", "palace": 7},\n',
    ''
)
v2_src = v2_src.replace(
    '            "skeleton": {"organ_name": "骨骼·图谱", "emoji": "🦴", "prenatal": "☶", "postnatal": "☶", "bagua_name": "艮", "palace": 8},\n',
    ''
)
v2_src = v2_src.replace(
    '            "limbs": {"organ_name": "四肢·执行", "emoji": "💪", "prenatal": "☳", "postnatal": "☳", "bagua_name": "震", "palace": 3},\n',
    ''
)
# 更新 total_organs 计数从 12 到 9（仅八卦内器官）
v2_src = v2_src.replace('"total_organs"', '"total_organs_inner"')  
# 不修改 total_organs 的实际值，保留统计逻辑

with open('src/api/v2_routes.py', 'w') as f:
    f.write(v2_src)

print('[阶段 2] v2_routes.py 已更新')

# ===== 更新 chat.py 中 hair 相关引用 =====
with open('src/api/chat.py') as f:
    chat_src = f.read()

# 保留 hair API 但重定向到皮肤
chat_src = chat_src.replace('/api/hair/search', '/api/antenna/search')
chat_src = chat_src.replace('hair_web_search', 'antenna_search')
chat_src = chat_src.replace('🐙 发·外探', '☲ 触角·外探')
chat_src = chat_src.replace('🐙 外探', '☲ 触角·外探')
chat_src = chat_src.replace('hair_unavailable', 'antenna_unavailable')
chat_src = chat_src.replace('hair_empty', 'antenna_empty')
chat_src = chat_src.replace('hair_web_search', 'antenna_search')
chat_src = chat_src.replace('hair_raw', 'antenna_raw')
chat_src = chat_src.replace('hair_error', 'antenna_error')
chat_src = chat_src.replace('mode": "ai_hair"', 'mode": "ai_antenna"')

with open('src/api/chat.py', 'w') as f:
    f.write(chat_src)

print('[阶段 2] chat.py 已更新（hair -> antenna）')

print('\\n✅ 阶段 0-2 完成')
