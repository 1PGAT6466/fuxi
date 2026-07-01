"""直接迁移脚本 - 四象归位"""
import shutil
import os

# 1. 复制必要文件到四象目录
files_to_migrate = {
    'src/services/query_expansion.py': 'src/taiyang/',
    'src/services/fusion.py': 'src/taiyang/',
    'src/services/rerank.py': 'src/taiyang/',
    'src/services/results_postprocess.py': 'src/taiyang/',
    'src/services/llm.py': 'src/infra/',
}

for src, dst_dir in files_to_migrate.items():
    if os.path.exists(src):
        dst = os.path.join(dst_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        print(f'Copied: {src} -> {dst}')

# 2. 更新 taiyang/retrieval.py 的 import
retrieval_path = 'src/taiyang/retrieval.py'
with open(retrieval_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'from src.services.query_expansion': 'from src.taiyang.query_expansion',
    'from src.services.fusion': 'from src.taiyang.fusion',
    'from src.services.rerank': 'from src.taiyang.rerank',
    'from src.services.results_postprocess': 'from src.taiyang.results_postprocess',
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(retrieval_path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Updated: {retrieval_path}')

# 3. 更新 shaoyin/brain.py 的 import
brain_path = 'src/shaoyin/brain.py'
with open(brain_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('from src.services.llm', 'from src.infra.llm')

with open(brain_path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Updated: {brain_path}')

# 4. 删除旧目录
old_dirs = ['src/services', 'src/agents', 'src/api']
for d in old_dirs:
    if os.path.exists(d):
        shutil.rmtree(d)
        print(f'Deleted: {d}')

print('\nMigration complete!')
