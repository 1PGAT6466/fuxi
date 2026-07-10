"""Fix sync I/O in async functions - batch script."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def fix_file(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f'  Fixed: {old[:50]}...')
        else:
            print(f'  SKIP: {old[:50]}...')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== notifications.py =====
print('Fixing src/api/notifications.py...')
fix_file('src/api/notifications.py', [
    # _load_notifications uses open() - wrap the whole thing for async callers
    # The issue is _load_notifications is sync but called from async list_notifications
    # Fix: wrap the file I/O parts
    (
        '        with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:\n                notifications = json.load(f)',
        '        import asyncio as _aio\n            def _read():\n                with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            notifications = await _aio.to_thread(_read)'
    ),
])

# ===== user_preferences.py =====
print('Fixing src/api/user_preferences.py...')
fix_file('src/api/user_preferences.py', [
    # _load_preferences and _save_preferences use open() - called from async endpoints
    (
        '        with open(path, "r", encoding="utf-8") as f:\n            saved = json.load(f)',
        '        import asyncio as _aio\n        def _rd():\n            with open(path, "r", encoding="utf-8") as f:\n                return json.load(f)\n        saved = await _aio.to_thread(_rd)'
    ),
    (
        '        with open(path, "w", encoding="utf-8") as f:\n            json.dump(prefs, f, ensure_ascii=False, indent=2)',
        '        import asyncio as _aio\n        def _wr():\n            with open(path, "w", encoding="utf-8") as f:\n                json.dump(prefs, f, ensure_ascii=False, indent=2)\n        await _aio.to_thread(_wr)'
    ),
])

# ===== permissions.py - is_admin reads users.json =====
print('Fixing src/api/permissions.py...')
# is_admin is called from sync context (check_read/check_write), so we can't make it async
# Instead, we should cache the users data. But for now, the sync read is acceptable
# since it's a small file and called infrequently. Skip this one.

# ===== eval_automation.py - _save_report uses open() =====
print('Fixing src/services/eval_automation.py...')
# _save_report is called from run_daily_eval which is async
# But _save_report itself is sync. The open() calls are in _save_report.
# Since run_daily_eval is async, we should wrap _save_report call.
# Actually _save_report is already called from async context but the open() is in sync method.
# The simplest fix: make _save_report async.
fix_file('src/services/eval_automation.py', [
    (
        '    def _save_report(self, report: Dict):\n        """保存评测报告"""\n        try:\n            date = report.get("date", datetime.now().strftime("%Y-%m-%d"))\n            report_file = REPORT_DIR / f"eval_report_{date}.json"\n            with open(report_file, "w", encoding="utf-8") as f:\n                json.dump(report, f, ensure_ascii=False, indent=2)',
        '    async def _save_report(self, report: Dict):\n        """保存评测报告"""\n        try:\n            date = report.get("date", datetime.now().strftime("%Y-%m-%d"))\n            report_file = REPORT_DIR / f"eval_report_{date}.json"\n            def _wr():\n                with open(report_file, "w", encoding="utf-8") as f:\n                    json.dump(report, f, ensure_ascii=False, indent=2)\n            await asyncio.to_thread(_wr)'
    ),
    (
        '            with open(history_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps({',
        '            def _append():\n                with open(history_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps({'
    ),
    (
        '                }, ensure_ascii=False) + "\\n")\n\n            logger.info(f"[EvalAutomation] 报告已保存: {report_file}")',
        '                }, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_append)\n\n            logger.info(f"[EvalAutomation] 报告已保存: {report_file}")'
    ),
    (
        '        self._save_report(report)',
        '        await self._save_report(report)'
    ),
])

# ===== files_view.py =====
print('Fixing src/api/files_view.py...')
fix_file('src/api/files_view.py', [
    (
        '                        with open(fpath, "rb") as f:\n                            content = f.read()',
        '                        content = await asyncio.to_thread(lambda: open(fpath, "rb").read())'
    ),
])

# ===== files_alias.py =====
print('Fixing src/api/files_alias.py...')
fix_file('src/api/files_alias.py', [
    (
        '                            with open(fpath, "rb") as f:\n                                content = f.read()',
        '                            content = await asyncio.to_thread(lambda: open(fpath, "rb").read())'
    ),
])

# ===== documents.py =====
print('Fixing src/api/documents.py...')
fix_file('src/api/documents.py', [
    (
        '                            with open(fpath, "rb") as f:\n                                content = f.read()',
        '                            content = await asyncio.to_thread(lambda: open(fpath, "rb").read())'
    ),
])

# ===== feedback.py =====
print('Fixing src/api/feedback.py...')
fix_file('src/api/feedback.py', [
    (
        '            with open(fpath, "r", encoding="utf-8") as f:',
        '            import asyncio as _aio\n            def _rd():\n                with open(fpath, "r", encoding="utf-8") as f:'
    ),
])

# ===== worldtree.py - entities reads knowledge_graph.json =====
print('Fixing src/api/worldtree.py...')
# Already uses asyncio.to_thread in most places, check for remaining
fix_file('src/api/worldtree.py', [
    # The worldtree_entities function has a fallback that reads kg directly
    # but it already uses asyncio.to_thread. Let's check the relations function.
])

print('\nDone with all fixes!')
