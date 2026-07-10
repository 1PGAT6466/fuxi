"""Fix evolution.py sync I/O in async functions."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

with open('src/api/evolution.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: _get_dream_cycle_status uses await in non-async function - make it async
# and wrap read_text with asyncio.to_thread
old1 = 'def _get_dream_cycle_status() -> dict:'
new1 = 'async def _get_dream_cycle_status() -> dict:'
if old1 in content:
    content = content.replace(old1, new1)
    print('Fixed: made _get_dream_cycle_status async')

# Fix 2: wrap read_text inside _get_dream_cycle_status
old2 = '        data = json.loads(latest.read_text(encoding="utf-8"))'
new2 = '        data = await asyncio.to_thread(lambda: json.loads(latest.read_text(encoding="utf-8")))'
if old2 in content:
    content = content.replace(old2, new2)
    print('Fixed: wrapped read_text in _get_dream_cycle_status')

# Fix 3: evolution_overview calls _get_dream_cycle_status() - needs await
old3 = '        dream_status = _get_dream_cycle_status()'
new3 = '        dream_status = await _get_dream_cycle_status()'
if old3 in content:
    content = content.replace(old3, new3)
    print('Fixed: added await to _get_dream_cycle_status call')

# Fix 4: get_latest_report - wrap read_text calls
old4 = '        report_content = latest_report.read_text(encoding="utf-8")'
new4 = '        report_content = await asyncio.to_thread(latest_report.read_text, encoding="utf-8")'
if old4 in content:
    content = content.replace(old4, new4)
    print('Fixed: wrapped read_text in get_latest_report')

old5 = '                data = json.loads(data_files[0].read_text(encoding="utf-8"))'
new5 = '                data = await asyncio.to_thread(lambda: json.loads(data_files[0].read_text(encoding="utf-8")))'
if old5 in content:
    content = content.replace(old5, new5)
    print('Fixed: wrapped data read in get_latest_report')

# Fix 5: get_report_history - wrap read_text in loop
old6 = '                data = json.loads(df.read_text(encoding="utf-8"))'
new6 = '                data = await asyncio.to_thread(lambda _df=df: json.loads(_df.read_text(encoding="utf-8")))'
if old6 in content:
    content = content.replace(old6, new6)
    print('Fixed: wrapped read_text in get_report_history')

with open('src/api/evolution.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done with evolution.py')
