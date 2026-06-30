# Update stomach.py for correct paths
import asyncio, sys, os

sys.path.insert(0, r'F:\公司知识平台\中宫--胃')
os.chdir(r'F:\公司知识平台\中宫--胃')

# Patch stomach.py storage path
with open('stomach.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update paths
code = code.replace(r"C:\fuxi-stomach\storage", r"F:\公司知识平台\中宫--胃\storage")
code = code.replace(r"C:\技术文档", r"F:\公司知识平台\传入数据\原始文件")

with open('stomach.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Paths updated in stomach.py')

# Now digest all
from stomach import digest_file

async def main():
    base = r'F:\公司知识平台\传入数据\原始文件'
    files = []
    for root, dirs, filenames in os.walk(base):
        for fn in filenames:
            if fn.startswith('~$'):
                continue
            fp = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext in ('.docx', '.doc', '.pdf', '.xlsx', '.xls', '.txt', '.md', '.csv', '.cfg'):
                files.append(fp)
    
    print(f'Found {len(files)} files')
    
    ok, fail = 0, 0
    for fp in files:
        try:
            r = await digest_file(fp, push=True)
            if r.get('ok'):
                ok += 1
                print(f"  OK [{r['category']}]: {r['file_name']} -> {r['chunks']} chunks, {r['wiki']} wiki")
            else:
                fail += 1
                print(f"  FAIL: {os.path.basename(fp)} -> {r.get('error','')}")
        except Exception as e:
            fail += 1
            print(f"  ERROR: {os.path.basename(fp)} -> {e}")
        sys.stdout.flush()
    
    print(f'\n=== Done: {ok} ok, {fail} failed ===')

asyncio.run(main())
