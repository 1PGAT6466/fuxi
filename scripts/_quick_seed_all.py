#!/usr/bin/env python3
"""Quick seed all databases: ChromaDB + chunks.db + worldtree.db"""
import sys, os, hashlib, sqlite3, json, time, logging
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PROJECT_ROOT = Path(__file__).resolve().parent.parent

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

os.environ.setdefault("KB_CHROMA_DIR", "data/chromadb")
os.environ.setdefault("FUXI_DATA_DIR", str(PROJECT_ROOT / "data"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("quick_seed")

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Stats helper
def get_db_counts():
    counts = {}
    chroma_path = PROJECT_ROOT / "data" / "chromadb" / "chroma.sqlite3"
    if chroma_path.exists():
        c = sqlite3.connect(str(chroma_path))
        counts["chromadb_embeddings"] = c.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        c.close()
    else:
        counts["chromadb_embeddings"] = 0

    chunks_path = PROJECT_ROOT / "data" / "chunks.db"
    if chunks_path.exists():
        c = sqlite3.connect(str(chunks_path))
        counts["chunks"] = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        c.close()
    else:
        counts["chunks"] = 0

    wt_path = PROJECT_ROOT / "data" / "worldtree.db"
    if wt_path.exists():
        c = sqlite3.connect(str(wt_path))
        counts["wiki_pages"] = c.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
        c.close()
    else:
        counts["wiki_pages"] = 0
    return counts

stats = {"before": get_db_counts()}
logger.info(f"BEFORE: {stats['before']}")
