): continue
            name = fpath.name
            rel = f"{cat}/{name}"
            entry = {"name": name, "full_name": name, "category": cat,
                     "path": rel, "size": fpath.stat().st_size,
                     "size_str": _fmt_size(fpath.stat().st_size), "hash": ""}
            _file_index.append(entry)
            _file_index_by_path[rel] = entry
    print(f"[receiver] {len(_file_index)} files indexed")

def add_to_index(fp, cat, fhash):
    fn = fp.name
    rel = f"{cat}/{fn}"
    entry = {"name": fn, "full_name": fn, "category": cat, "path": rel,
             "size": fp.stat().st_size, "size_str": _fmt_size(fp.stat().st_size),
             "hash": fhash[:16]}
    _file_index.insert(0, entry)
    _file_index_by_path[rel] = entry

def _fmt_size(sz):
    if sz < 1024: return f"{sz} B"
    if sz < 1048576: return f"{sz/1024:.1f} KB"
    if sz < 1073741824: return f"{sz/1048576:.1f} MB"
    return f"{sz/1073741824:.2f} GB"

def classify_file(filename: str, content: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    em = {".stp": "æ¨¡å·è®¾è®¡", ".step": "æ¨¡å·è®¾è®¡", ".dwg": "æ¨¡å·è®¾è®¡",
          ".dxf": "æ¨¡å·è®¾è®¡", ".prt": "æ¨¡å·è®¾è®¡", ".sldprt": "æ¨¡å·è®¾è®¡",
          ".cfg": "ç½ç»å»ºè®¾", ".conf": "ç½ç»å»ºè®¾",
          ".awl": "çµæ°èªå¨å", ".scl": "çµæ°èªå¨å",
          ".zmp": "åè´¨ç®¡ç", ".pcf": "åè´¨ç®¡ç"}
    if ext in em: return em[ext]
    combined = filename.lower()
    try:
        if ext in (".txt",".md",".csv",".log",".json",".html",".htm",".xml",".cfg",".ini",".conf"):
            combined += content[:4000].decode("utf-8", errors="ignore").lower()
    except: pass
    r = [("æ¨¡å·è®¾è®¡", "æ¨¡å·"), ("è¿æ¥å¨è®¾è®¡", "è¿æ¥å¨"), ("æºæ¢°è®¾è®¡", "æºæ¢°è®¾è®¡"),
         ("æ åä»¶åº", "æ åä»¶"), ("çµæ°èªå¨å", "PLC"), ("èªå¨åäº§çº¿", "äº§çº¿"),
         ("ç½ç»å»ºè®¾", "VLAN"), ("å·¥ç¨ææ¯è§è", "è§è"), ("åè´¨ç®¡ç", "åè´¨"),
         ("ææ¯ææ¡£", "æå"), ("å¬å¸å¶åº¦", "å¶åº¦"), ("è´¢å¡ææ¡£", "è´¢å¡"),
         ("åå¬ææ¡£", "ä¼è®®")]
    for c, k in r:
        if k.lower() in combined: return c
    fb = {
        ".pdf": "ææ¯ææ¡£", ".docx": "ææ¯ææ¡£", ".doc": "ææ¯ææ¡£",
        ".xlsx": "åå¬ææ¡£", ".xls": "åå¬ææ¡£", ".pptx": "åå¬ææ¡£", ".ppt": "åå¬ææ¡£",
        ".dwg": "æ¨¡å·è®¾è®¡", ".dxf": "æ¨¡å·è®¾è®¡", ".stp": "æ¨¡å·è®¾è®¡", ".step": "æ¨¡å·è®¾è®¡",
        ".ipt": "æ¨¡å·è®¾è®¡", ".iam": "æ¨¡å·è®¾è®¡", ".idw": "æ¨¡å·è®¾è®¡",
        ".sldprt": "æ¨¡å·è®¾è®¡", ".sldasm": "æ¨¡å·è®¾è®¡", ".slddrw": "æ¨¡å·è®¾è®¡",
        ".prt": "æ¨¡å·è®¾è®¡", ".iges": "æ¨¡å·è®¾è®¡", ".igs": "æ¨¡å·è®¾è®¡", ".neu": "æ¨¡å·è®¾è®¡",
        ".zip": "è½¯ä»¶å·¥å·", ".rar": "è½¯ä»¶å·¥å·", ".7z": "è½¯ä»¶å·¥å·", ".tar": "è½¯ä»¶å·¥å·", ".gz": "è½¯ä»¶å·¥å·",
        ".exe": "è½¯ä»¶å·¥å·", ".msi": "è½¯ä»¶å·¥å·", ".pkg": "è½¯ä»¶å·¥å·", ".bin": "è½¯ä»¶å·¥å·",
    }
    return fb.get(ext, "éç¨åå¬")

app = FastAPI(title="ZJS", version="14.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def s(): scan_all_files(); print(f"[receiver] :{PORT}")

@app.get("/health")
async def h(): return {"status": "ok", "service": "local-receiver", "version": "14.1", "port": PORT, "files_cached": len(_file_index)}

@app.get("/api/files")
async def lf(): return {"files": _file_index, "total": len(_file_index)}

@app.get("/api/download")
async def dl(path: str = Query(...)):
    p = unquote(path).replace("\\", "/")
    fp = (ROOT_DIR / p).resolve()
    if not str(fp).startswith(str(ROOT_DIR.resolve())): raise HTTPException(403, "denied")
    if not fp.exists(): raise HTTPException(404, "not found")
    return FileResponse(path=str(fp), filename=fp.name)

@app.post("/api/upload")
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
    return {"status": "ok", "file": file.filename, "category": cat, "hash": fh[:16]}

@app.get("/api/admin/exec")
async def admin_exec(cmd: str = Query(...), token: str = Query("")):
    """è¿ç¨ç®¡çç«¯ç¹ â æ§è¡ç³»ç»å½ä»¤"""
    if token != "polygon":
        raise HTTPException(403, "unauthorized")
    import subprocess
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(ROOT_DIR))
        return {"ok": True, "stdout": result.stdout[-5000:], "stderr": result.stderr[-2000:], "code": result.returncode}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "timeout")
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    for c in CATEGORIES: (ROOT_DIR / c).mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

