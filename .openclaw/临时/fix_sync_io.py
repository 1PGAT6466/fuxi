"""Fix sync I/O in async functions across the codebase."""
import re

def fix_file(filepath, replacements):
    """Apply replacements to a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f'  Fixed: {old[:60]}...')
        else:
            print(f'  SKIP (not found): {old[:60]}...')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== admin.py =====
print('Fixing src/api/admin.py...')

with open('src/api/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix admin_create_user: wrap read_text and write_text
old1 = '        users = json.loads(users_file.read_text(encoding="utf-8")) if users_file.exists() else {}\n\n        if username in users:'
new1 = '        import asyncio as _aio\n        def _rd():\n            return json.loads(users_file.read_text(encoding="utf-8")) if users_file.exists() else {}\n        users = await _aio.to_thread(_rd)\n\n        if username in users:'

old2 = '        users_file.parent.mkdir(parents=True, exist_ok=True)\n        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")\n\n        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")\n        if _wants_v2:\n            from src.api.response import success\n            return success(data={"username": username, "role": role, "display_name": display_name}, message="\u9375\u7528\u6236\u5275\u5efa\u6210\u529f")'
new2 = '        users_file.parent.mkdir(parents=True, exist_ok=True)\n        def _wr():\n            users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")\n        await _aio.to_thread(_wr)\n\n        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")\n        if _wants_v2:\n            from src.api.response import success\n            return success(data={"username": username, "role": role, "display_name": display_name}, message="\u9375\u7528\u6236\u5275\u5efa\u6210\u529f")'

# Fix admin_update_user
old3 = '        users = json.loads(users_file.read_text(encoding="utf-8"))\n        if user_id not in users:'
new3 = '        import asyncio as _aio\n        def _rd():\n            return json.loads(users_file.read_text(encoding="utf-8"))\n        users = await _aio.to_thread(_rd)\n        if user_id not in users:'

old4 = '        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")\n\n        _wants_v2 = request.query_params.get("format") == "v2'
new4 = '        def _wr():\n            users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")\n        await _aio.to_thread(_wr)\n\n        _wants_v2 = request.query_params.get("format") == "v2'

# Fix admin_delete_user
old5 = '        users = json.loads(users_file.read_text(encoding="utf-8"))\n        if user_id not in users:\n            return JSONResponse(status_code=404, content={"error": "\u7528\u6237\u672a\u627e\u5230"})\n\n        del users[user_id]\n        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")'
new5 = '        import asyncio as _aio\n        def _rd():\n            return json.loads(users_file.read_text(encoding="utf-8"))\n        users = await _aio.to_thread(_rd)\n        if user_id not in users:\n            return JSONResponse(status_code=404, content={"error": "\u7528\u6237\u672a\u627e\u5230"})\n\n        del users[user_id]\n        def _wr():\n            users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")\n        await _aio.to_thread(_wr)'

for old, new in [(old1, new1), (old2, new2), (old3, new3), (old4, new4), (old5, new5)]:
    if old in content:
        content = content.replace(old, new)
        print(f'  Fixed pattern')
    else:
        print(f'  SKIP (not found)')

with open('src/api/admin.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('  Done')
