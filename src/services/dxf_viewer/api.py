"""
api.py — DXF看图服务API路由
FastAPI路由：上传、查看、文件列表、健康检查
"""

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from src.services.dxf_viewer.parser import extract_dxf, EZDXF_AVAILABLE
from src.services.dxf_viewer.renderer import generate_render_data
from src.services.dxf_viewer.dedup import check_duplicate, register_hash

logger = logging.getLogger("services.dxf-viewer.api")

router = APIRouter(prefix="/api/dxf", tags=["dxf-viewer"])

DATA_DIR = Path("data/services/dxf-viewer")
FILES_DIR = DATA_DIR / "files"
INDEX_FILE = DATA_DIR / "file_index.json"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def _ensure_dirs() -> None:
    FILES_DIR.mkdir(parents=True, exist_ok=True)


def _load_file_index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("加载文件索引失败: %s", e, exc_info=True)
    return {}


def _save_file_index(index: dict) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "dxf-viewer",
        "version": "1.0.0",
        "ezdxf_available": EZDXF_AVAILABLE,
    }


@router.post("/upload")
async def upload_dxf(file: UploadFile = File(...)):
    if not EZDXF_AVAILABLE:
        raise HTTPException(503, "ezdxf not installed — DXF parsing unavailable")

    _ensure_dirs()

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".dxf", ".dwg"):
        raise HTTPException(
            400, f"Unsupported file type: {suffix}. Supported: .dxf, .dwg"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            413, f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    temp_path = FILES_DIR / f"temp_{file.filename}"
    try:
        temp_path.write_bytes(content)

        dup_result = check_duplicate(str(temp_path))
        hash_value = dup_result["hash_value"]

        if dup_result["is_duplicate"]:
            existing_hash = dup_result["existing_hash"]
            temp_path.unlink(missing_ok=True)
            return {
                "status": "duplicate",
                "message": "File with identical geometry already exists",
                "hash": existing_hash,
            }

        final_dir = FILES_DIR / hash_value
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / file.filename
        shutil.move(str(temp_path), str(final_path))

        parsed = extract_dxf(str(final_path))
        render_data = generate_render_data(parsed)

        render_path = final_dir / "render.json"
        render_path.write_text(
            json.dumps(render_data, ensure_ascii=False), encoding="utf-8"
        )

        meta_path = final_dir / "metadata.json"
        meta_path.write_text(
            json.dumps(
                {
                    "filename": file.filename,
                    "hash": hash_value,
                    "entity_count": parsed["metadata"]["entity_count"],
                    "layers": parsed["metadata"]["layers"],
                    "text_content": parsed["text_content"],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        register_hash(hash_value, hash_value)

        index = _load_file_index()
        index[hash_value] = {
            "filename": file.filename,
            "hash": hash_value,
            "entity_count": parsed["metadata"]["entity_count"],
        }
        _save_file_index(index)

        return {
            "status": "ok",
            "hash": hash_value,
            "filename": file.filename,
            "entity_count": parsed["metadata"]["entity_count"],
        }

    except ValueError as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Invalid DXF file: {e}")
    except Exception as e:  # TODO: Narrow exception type
        temp_path.unlink(missing_ok=True)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(500, f"Upload processing failed: {e}")


@router.get("/files")
def list_files():
    index = _load_file_index()
    return {
        "files": list(index.values()),
        "total": len(index),
    }


@router.get("/view/{hash_value}")
def view_dxf(hash_value: str):
    render_path = FILES_DIR / hash_value / "render.json"
    if not render_path.exists():
        raise HTTPException(404, f"DXF file not found: {hash_value}")

    try:
        data = json.loads(render_path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(500, f"Failed to load render data: {e}")


@router.get("/download/{hash_value}")
def download_dxf(hash_value: str):
    file_dir = FILES_DIR / hash_value
    if not file_dir.exists():
        raise HTTPException(404, f"DXF file not found: {hash_value}")

    dxf_files = list(file_dir.glob("*.dxf"))
    if not dxf_files:
        dxf_files = list(file_dir.glob("*.dwg"))
    if not dxf_files:
        raise HTTPException(404, "Original file not found")

    file_path = dxf_files[0]
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )
