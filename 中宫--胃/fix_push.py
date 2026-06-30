with open(r'F:\公司知识平台\中宫--胃\stomach.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix: push chunks per-file, not as batch
old_push = '''        # 推送 chunks → 脾
        if chunks:
            try:
                resp = await client.post(f'{KB_SERVER}/api/ingest-batch', json={
                    'chunks': chunks,
                    'source': 'stomach-loader'
                }, headers=headers)'''

new_push = '''        # 推送 chunks → 脾 (per-file format)
        if chunks:
            try:
                resp = await client.post(f'{KB_SERVER}/api/ingest-batch', json={
                    'file_name': file_name,
                    'file_hash': hashlib.md5(file_path.encode()).hexdigest()[:8],
                    'category': category,
                    'chunks': chunks,
                }, headers=headers)'''

code = code.replace(old_push, new_push)

# Also need file_path in push_to_kb_server - check signature
old_sig = 'async def push_to_kb_server(chunks: List[Dict], wiki: List[Dict], entities: Dict):'
new_sig = 'async def push_to_kb_server(chunks: List[Dict], wiki: List[Dict], entities: Dict, file_path: str, file_name: str, category: str):'
code = code.replace(old_sig, new_sig)

# Update caller in digest_file
old_call = 'push_result = await push_to_kb_server(chunks, wiki, entities)'
new_call = 'push_result = await push_to_kb_server(chunks, wiki, entities, file_path, file_name, category)'
code = code.replace(old_call, new_call)

with open(r'F:\公司知识平台\中宫--胃\stomach.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Push format fixed')
