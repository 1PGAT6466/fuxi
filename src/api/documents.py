# 兼容层 - 文档路由
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pathlib import Path

router = APIRouter(tags=["文档管理"])

@router.get("/api/documents")
async def documents(page: int = 1, page_size: int = 50):
    """文档列表"""
    from src.db.data_store import load_chunks
    try:
        chunks = load_chunks()
        seen = {}
        for c in chunks:
            fh = c.get("file_hash", "")
            if fh and fh not in seen:
                seen[fh] = {
                    "file_name": c.get("file_name", ""),
                    "file_hash": fh,
                    "category": c.get("category", ""),
                    "chunk_count": 1,
                }
            elif fh:
                seen[fh]["chunk_count"] += 1
        files = list(seen.values())
        return {"files": files, "total": len(files), "page": page, "page_size": page_size}
    except Exception as e:
        return {"files": [], "total": 0, "error": str(e)}

@router.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """文件上传"""
    from src.shaoyang.pipeline import ShaoyangPipeline
    from src.hypothalamus.meridian import Meridian
    import tempfile
    
    try:
        # 保存临时文件
        tmp_dir = Path("data/uploads")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / file.filename
        
        content = await file.read()
        tmp_path.write_bytes(content)
        
        # 通过少阳处理
        meridian = Meridian()
        pipeline = ShaoyangPipeline(meridian)
        result = await pipeline.digest(str(tmp_path), source="upload")
        
        return {
            "status": "ok",
            "file_name": file.filename,
            "chunks": len(result.chunks),
            "duration_ms": result.duration_ms,
        }
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")
