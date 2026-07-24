import requests

r = requests.post('http://localhost:8080/api/auth/login', json={'username':'testuser_round3','password':'Test@Round3Pass1'})
token = r.json().get('token')

r2 = requests.get('http://localhost:8080/api/documents', headers={'Authorization': f'Bearer {token}'})
print(f'Documents status: {r2.status_code}')
data = r2.json()
total = data.get('total', 0)
print(f'Total files: {total}')
for f in data.get('files', []):
    fname = f.get('file_name', '')
    chunks = f.get('chunk_count', 0)
    fhash = f.get('file_hash', 'N/A')[:20]
    print(f'  - {fname}: {chunks} chunks, hash: {fhash}')
