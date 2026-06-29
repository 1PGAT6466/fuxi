# 给 local_receiver.py 的 raw-store 加上 target 参数
# 修改位置：第 122-138 行的 up 函数

OLD_BLOCK = """@app.post("/api/upload")
@app.post("/api/raw-store")
async def up(file: UploadFile = File(...)):
    if not file.filename: raise HTTPException(400, "no filename")
    data = await file.read()
    cat = classify_file(file.filename, data)
    (ROOT_DIR / cat).mkdir(parents=True, exist_ok=True)
    fh = hashlib.sha256(data).hexdigest()
    for e in _file_index:
        if e.get("hash", "") == fh[:16]:
            return {"status": "duplicate", "file": file.filename, "category": cat, "hash": fh[:16]}
    sn = file.filename.replace(",", "_").replace('"', "_")
    d = ROOT_DIR / cat / sn
    d.write_bytes(data)
    print(f"[receiver] ok [{cat}] {file.filename} {len(data)}b")
    add_to_index(d, cat, fh)
    return {"status": "ok", "file": file.filename, "category": cat, "hash": fh[:16]}"""

NEW_BLOCK = """@app.post("/api/upload")
@app.post("/api/raw-store")
async def up(file: UploadFile = File(...), target: str = Query("")):
    if not file.filename: raise HTTPException(400, "no filename")
    data = await file.read()
    # 如果传了 target 参数，直接存入指定目录；否则自动分类
    cat = target.strip() if target.strip() else classify_file(file.filename, data)
    (ROOT_DIR / cat).mkdir(parents=True, exist_ok=True)
    fh = hashlib.sha256(data).hexdigest()
    for e in _file_index:
        if e.get("hash", "") == fh[:16]:
            return {"status": "duplicate", "file": file.filename, "category": cat, "hash": fh[:16]}
    sn = file.filename.replace(",", "_").replace('"', "_")
    d = ROOT_DIR / cat / sn
    d.write_bytes(data)
    print(f"[receiver] ok [{cat}] {file.filename} {len(data)}b")
    add_to_index(d, cat, fh)
    return {"status": "ok", "file": file.filename, "category": cat, "hash": fh[:16]}"""

print("OLD and NEW blocks ready for replacement")
