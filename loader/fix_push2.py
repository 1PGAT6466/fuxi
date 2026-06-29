# Fix stomach.py push_to_kb_server - map chunk fields correctly
with open(r'F:\公司知识平台\中宫--胃\stomach.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix: add file_hash and normalize chunk fields before pushing
old_push_start = '''        # 推送 chunks → 脾 (per-file format)
        if chunks:
            try:
                resp = await client.post(f'{KB_SERVER}/api/ingest-batch', json={
                    'file_name': file_name,
                    'file_hash': hashlib.md5(file_path.encode()).hexdigest()[:8],
                    'category': category,
                    'chunks': chunks,
                }, headers=headers)'''

new_push_start = '''        # 推送 chunks → 脾 (per-file format)
        if chunks:
            try:
                file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
                # Normalize chunk fields to match kb-server expectations
                clean_chunks = []
                for i, c in enumerate(chunks):
                    clean_chunks.append({
                        'text': c.get('text', ''),
                        'file_name': c.get('file_name', file_name),
                        'file_hash': c.get('file_hash', file_hash),
                        'category': c.get('category', category),
                        'chunk_index': c.get('chunk_index', i),
                        'chunk_type': c.get('chunk_type', 'text'),
                        'chunk_id': c.get('chunk_id', ''),
                    })
                resp = await client.post(f'{KB_SERVER}/api/ingest-batch', json={
                    'file_name': file_name,
                    'file_hash': file_hash,
                    'category': category,
                    'chunks': clean_chunks,
                }, headers=headers)'''

code = code.replace(old_push_start, new_push_start)
print('Push format fixed v2')

with open(r'F:\公司知识平台\中宫--胃\stomach.py', 'w', encoding='utf-8') as f:
    f.write(code)
