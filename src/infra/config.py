"""
config.py — 基础设施·配置管理
集中管理URL/端口配置
"""
import os
from pathlib import Path

BASE_DIR = Path(os.getenv("FUXI_DATA_DIR", Path(__file__).parent.parent.parent / "data"))
STATIC_DIR = Path(__file__).parent.parent.parent / "frontend"

MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.mimo.ai/v1")
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
MIMO_TIMEOUT = int(os.getenv("MIMO_TIMEOUT", "60"))

EMBEDDER_URL = os.getenv("KB_EMBEDDER_URL", "http://localhost:8091")
LOADER_URL = os.getenv("LOADER_URL", "http://localhost:8090")
RERANK_URL = os.getenv("KB_RERANK_PROXY", "")

PORT = int(os.getenv("KB_PORT", "8080"))
HOST = os.getenv("KB_HOST", "0.0.0.0")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "200"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

CORS_ORIGINS = os.getenv("KB_CORS_ORIGINS", f"http://localhost:{PORT},http://127.0.0.1:{PORT}")

DB_PATH = str(BASE_DIR / "memory.db")
CHROMA_PATH = str(BASE_DIR / "chroma_db")
