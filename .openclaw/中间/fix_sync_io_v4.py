"""
fix_sync_io.py — 修复 async 函数中的同步 I/O 阻塞
策略: 在调用处用 asyncio.to_thread() 包裹同步函数
"""
import re
import os

REPO = r"E:\easyclaw\伏羲-v1.44\repo"

# Files and their specific fixes
# Each fix: (file, old_pattern, new_pattern)
FIXES = []

# ============================================================
# 1. src/api/chat.py — wrap sync DB calls in asyncio.to_thread
# ============================================================
chat_py = os.path.join(REPO, "src", "api", "chat.py")
with open(chat_py, "r", encoding="utf-8") as f:
    content = f.read()

# Fix: _save_session_to_db(session) → await asyncio.to_thread(_save_session_to_db, session)
# Fix: _save_message_to_db(session_id, msg) → await asyncio.to_thread(_save_message_to_db, session_id, msg)
# Fix: _delete_session_from_db(session_id) → await asyncio.to_thread(_delete_session_from_db, session_id)

# Pattern for _save_session_to_db(session)
content = re.sub(
    r'(\s+)(_save_session_to_db\()([^)]+)\)',
    r'\1await asyncio.to_thread(_save_session_to_db, \3)',
    content
)

# Pattern for _save_message_to_db(session_id, msg)
content = re.sub(
    r'(\s+)(_save_message_to_db\()([^)]+)\)',
    r'\1await asyncio.to_thread(_save_message_to_db, \3)',
    content
)

# Pattern for _delete_session_from_db(session_id)
content = re.sub(
    r'(\s+)(_delete_session_from_db\()([^)]+)\)',
    r'\1await asyncio.to_thread(_delete_session_from_db, \3)',
    content
)

with open(chat_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {chat_py}")

# ============================================================
# 2. src/api/files_view.py — wrap urllib.request.urlopen in asyncio.to_thread
# ============================================================
files_view_py = os.path.join(REPO, "src", "api", "files_view.py")
with open(files_view_py, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the bare urllib.request.urlopen block with asyncio.to_thread
old_urllib = '''                import urllib.request
                import json as _json
                req = urllib.request.Request(
                    f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count=5",
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": brave_key,
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    web_results = data.get("web", {}).get("results", [])
                    results = [
                        {
                            "title": wr.get("title", ""),
                            "snippet": wr.get("description", "")[:200],
                            "url": wr.get("url", ""),
                            "score": 1.0,
                            "source": "web_brave",
                        }
                        for wr in web_results
                    ]
                    source = "web_brave"
                    message = f"联网搜索找到 {len(results)} 条结果"'''

new_urllib = '''                import urllib.request
                import json as _json
                def _brave_search():
                    req = urllib.request.Request(
                        f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count=5",
                        headers={
                            "Accept": "application/json",
                            "Accept-Encoding": "gzip",
                            "X-Subscription-Token": brave_key,
                        }
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return _json.loads(resp.read().decode("utf-8"))
                data = await asyncio.to_thread(_brave_search)
                web_results = data.get("web", {}).get("results", [])
                results = [
                    {
                        "title": wr.get("title", ""),
                        "snippet": wr.get("description", "")[:200],
                        "url": wr.get("url", ""),
                        "score": 1.0,
                        "source": "web_brave",
                    }
                    for wr in web_results
                ]
                source = "web_brave"
                message = f"联网搜索找到 {len(results)} 条结果"'''

content = content.replace(old_urllib, new_urllib)

# Add asyncio import if not present
if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

with open(files_view_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {files_view_py}")

# ============================================================
# 3. src/api/documents.py — wrap load_chunks/save_chunks in asyncio.to_thread
# ============================================================
documents_py = os.path.join(REPO, "src", "api", "documents.py")
with open(documents_py, "r", encoding="utf-8") as f:
    content = f.read()

# Already has asyncio import at top

# Fix load_chunks() calls in async functions
# Pattern: chunks = load_chunks() → chunks = await asyncio.to_thread(load_chunks)
content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

# Fix save_chunks(kept) calls
content = re.sub(
    r'(\s+)(save_chunks\()([^)]+)\)',
    r'\1await asyncio.to_thread(save_chunks, \3)',
    content
)

with open(documents_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {documents_py}")

# ============================================================
# 4. src/api/dashboard.py — wrap load_chunks
# ============================================================
dashboard_py = os.path.join(REPO, "src", "api", "dashboard.py")
with open(dashboard_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    # Add after first import
    content = content.replace('from fastapi', 'import asyncio\nfrom fastapi', 1)

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(dashboard_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {dashboard_py}")

# ============================================================
# 5. src/api/evolution.py — wrap load_chunks
# ============================================================
evolution_py = os.path.join(REPO, "src", "api", "evolution.py")
with open(evolution_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(evolution_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {evolution_py}")

# ============================================================
# 6. src/api/files_alias.py — wrap load_chunks/save_chunks
# ============================================================
files_alias_py = os.path.join(REPO, "src", "api", "files_alias.py")
with open(files_alias_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

content = re.sub(
    r'(\s+)(save_chunks\()([^)]+)\)',
    r'\1await asyncio.to_thread(save_chunks, \3)',
    content
)

with open(files_alias_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {files_alias_py}")

# ============================================================
# 7. src/api/graph.py — wrap load_graph
# ============================================================
graph_py = os.path.join(REPO, "src", "api", "graph.py")
with open(graph_py, "r", encoding="utf-8") as f:
    content = f.read()

# Already has asyncio import

content = re.sub(
    r'(\s+)(data = )load_graph\(\)',
    r'\1\2await asyncio.to_thread(load_graph)',
    content
)

with open(graph_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {graph_py}")

# ============================================================
# 8. src/api/kb.py — wrap load_chunks
# ============================================================
kb_py = os.path.join(REPO, "src", "api", "kb.py")
with open(kb_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(kb_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {kb_py}")

# ============================================================
# 9. src/api/metadata.py — wrap load_chunks
# ============================================================
metadata_py = os.path.join(REPO, "src", "api", "metadata.py")
with open(metadata_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(metadata_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {metadata_py}")

# ============================================================
# 10. src/api/rag.py — wrap load_graph
# ============================================================
rag_py = os.path.join(REPO, "src", "api", "rag.py")
with open(rag_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(data = )load_graph\(\)',
    r'\1\2await asyncio.to_thread(load_graph)',
    content
)

with open(rag_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {rag_py}")

# ============================================================
# 11. src/api/synthesis.py — wrap load_graph
# ============================================================
synthesis_py = os.path.join(REPO, "src", "api", "synthesis.py")
with open(synthesis_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(graph_data = )load_graph\(\)',
    r'\1\2await asyncio.to_thread(load_graph)',
    content
)

with open(synthesis_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {synthesis_py}")

# ============================================================
# 12. src/api/worldtree.py — wrap load_chunks
# ============================================================
worldtree_py = os.path.join(REPO, "src", "api", "worldtree.py")
with open(worldtree_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(worldtree_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {worldtree_py}")

# ============================================================
# 13. src/core/routes.py — wrap load_chunks
# ============================================================
core_routes_py = os.path.join(REPO, "src", "core", "routes.py")
with open(core_routes_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(core_routes_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {core_routes_py}")

# ============================================================
# 14. src/evolution/dream_cycle.py — wrap load_graph
# ============================================================
dream_py = os.path.join(REPO, "src", "evolution", "dream_cycle.py")
with open(dream_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(data = )load_graph\(\)',
    r'\1\2await asyncio.to_thread(load_graph)',
    content
)

with open(dream_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {dream_py}")

# ============================================================
# 15. src/infra/health_check.py — wrap load_chunks
# ============================================================
health_py = os.path.join(REPO, "src", "infra", "health_check.py")
with open(health_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(health_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {health_py}")

# ============================================================
# 16. src/services/retrieval.py — wrap load_chunks
# ============================================================
retrieval_py = os.path.join(REPO, "src", "services", "retrieval.py")
with open(retrieval_py, "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(retrieval_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {retrieval_py}")

# ============================================================
# 17. src/shaoyang/relation_builder.py — wrap load_chunks
# ============================================================
rel_py = os.path.join(REPO, "src", "shaoyang", "relation_builder.py")
with open(rel_py, "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(([^)]*)\)',
    r'\1\2await asyncio.to_thread(load_chunks, \3)',
    content
)

with open(rel_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {rel_py}")

# ============================================================
# 18. src/taiyang/crag.py — wrap load_chunks
# ============================================================
crag_py = os.path.join(REPO, "src", "taiyang", "crag.py")
with open(crag_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(crag_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {crag_py}")

# ============================================================
# 19. src/taiyang/integrated_search.py — wrap load_chunks
# ============================================================
integrated_py = os.path.join(REPO, "src", "taiyang", "integrated_search.py")
with open(integrated_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(integrated_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {integrated_py}")

# ============================================================
# 20. src/taiyin/mcp_tools.py — wrap load_chunks
# ============================================================
mcp_py = os.path.join(REPO, "src", "taiyin", "mcp_tools.py")
with open(mcp_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(mcp_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {mcp_py}")

# ============================================================
# 21. src/agents_old/retrieval_agent.py — wrap load_chunks
# ============================================================
ret_agent_py = os.path.join(REPO, "src", "agents_old", "retrieval_agent.py")
with open(ret_agent_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(ret_agent_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {ret_agent_py}")

# ============================================================
# 22. src/agents_old/yang_agent.py — wrap load_chunks
# ============================================================
yang_py = os.path.join(REPO, "src", "agents_old", "yang_agent.py")
with open(yang_py, "r", encoding="utf-8") as f:
    content = f.read()

if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

content = re.sub(
    r'(\s+)(chunks = )load_chunks\(\)',
    r'\1\2await asyncio.to_thread(load_chunks)',
    content
)

with open(yang_py, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Fixed: {yang_py}")

print("\n=== All fixes applied ===")
