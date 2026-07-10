"""Fix compilation errors from previous patches."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

# ===== Fix notifications.py - await in sync function =====
print('Fixing src/api/notifications.py...')
with open('src/api/notifications.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The problem: we put asyncio.to_thread inside _load_notifications which is a sync function
# Fix: revert the _load_notifications change, and instead wrap the call in the async endpoint
old = '''        import asyncio as _aio
            def _read():
                with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            notifications = await _aio.to_thread(_read)'''
new = '''            with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)'''

if old in content:
    content = content.replace(old, new)
    print('  Reverted _load_notifications to sync')

# Now wrap the call in the async endpoint
old2 = '        notifications = _load_notifications()'
new2 = '        import asyncio as _aio\n        notifications = await _aio.to_thread(_load_notifications)'
if old2 in content:
    content = content.replace(old2, new2)
    print('  Wrapped _load_notifications call with to_thread')

# Also wrap _save_notifications calls
old3 = '            _save_notifications(notifications)\n\n        return {"ok": True, "id": notification_id, "read": found}'
new3 = '            await _aio.to_thread(_save_notifications, notifications)\n\n        return {"ok": True, "id": notification_id, "read": found}'
if old3 in content:
    content = content.replace(old3, new3)
    print('  Wrapped _save_notifications in mark_notification_read')

old4 = '            _save_notifications(notifications)\n\n        return {"ok": True, "read_all": True, "marked_count": count}'
new4 = '            await _aio.to_thread(_save_notifications, notifications)\n\n        return {"ok": True, "read_all": True, "marked_count": count}'
if old4 in content:
    content = content.replace(old4, new4)
    print('  Wrapped _save_notifications in mark_all_read')

with open('src/api/notifications.py', 'w', encoding='utf-8') as f:
    f.write(content)

# ===== Fix user_preferences.py - await in sync function =====
print('Fixing src/api/user_preferences.py...')
with open('src/api/user_preferences.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Same issue: await in sync _load_preferences and _save_preferences
# Revert to sync, wrap calls in async endpoints
old = '''        import asyncio as _aio
        def _rd():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        saved = await _aio.to_thread(_rd)'''
new = '''        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted _load_preferences to sync')

old = '''        import asyncio as _aio
        def _wr():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
        await _aio.to_thread(_wr)'''
new = '''        with open(path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted _save_preferences to sync')

# Wrap calls in async endpoints
old = '        prefs = _load_preferences(username)'
new = '        import asyncio as _aio\n        prefs = await _aio.to_thread(_load_preferences, username)'
if old in content:
    content = content.replace(old, new)
    print('  Wrapped _load_preferences call')

old = '        _save_preferences(username, current)'
new = '        await _aio.to_thread(_save_preferences, username, current)'
if old in content:
    content = content.replace(old, new)
    print('  Wrapped _save_preferences call')

with open('src/api/user_preferences.py', 'w', encoding='utf-8') as f:
    f.write(content)

# ===== Fix graph_traversal.py - indentation error =====
print('Fixing src/taiyang/graph_traversal.py...')
with open('src/taiyang/graph_traversal.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check what happened
lines = content.split('\n')
for i, line in enumerate(lines[48:62], start=49):
    print(f'  Line {i}: {repr(line)}')

with open('src/taiyang/graph_traversal.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
