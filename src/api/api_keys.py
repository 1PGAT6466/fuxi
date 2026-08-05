"""
伏羲 v1.44 — API 密钥管理路由
=============================
提供 API 密钥的 CRUD 操作。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])

# 数据目录
DATA_DIR = Path(__file__).parent.parent.parent / "data"
API_KEYS_FILE = DATA_DIR / "api_keys.json"


class ApiKeyCreate(BaseModel):
    name: str
    permissions: List[str] = ["read"]
    expires_at: Optional[str] = None


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    expires_at: Optional[str] = None
    is_active: Optional[bool] = None


class ApiKey(BaseModel):
    id: str
    name: str
    key: str
    permissions: List[str]
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]
    is_active: bool


def _load_keys() -> List[dict]:
    """加载 API 密钥数据"""
    if not API_KEYS_FILE.exists():
        return []
    with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_keys(keys: List[dict]) -> None:
    """保存 API 密钥数据"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)


def _mask_key(key: str) -> str:
    """只显示密钥前缀"""
    return key[:12] + "..." if len(key) > 12 else key


@router.get("")
async def list_api_keys():
    """获取所有 API 密钥列表"""
    keys = _load_keys()
    # 只返回掩码后的密钥
    masked_keys = []
    for k in keys:
        masked = k.copy()
        masked["key"] = _mask_key(k["key"])
        masked_keys.append(masked)
    return {"status": "success", "data": masked_keys}


@router.post("")
async def create_api_key(body: ApiKeyCreate):
    """创建新的 API 密钥"""
    keys = _load_keys()

    new_key = {
        "id": uuid.uuid4().hex[:12],
        "name": body.name,
        "key": f"fuxi_{uuid.uuid4().hex}",
        "permissions": body.permissions,
        "created_at": datetime.now().isoformat(),
        "expires_at": body.expires_at,
        "last_used_at": None,
        "is_active": True,
    }

    keys.append(new_key)
    _save_keys(keys)

    return {
        "status": "success",
        "data": new_key,
        "message": "API 密钥创建成功（密钥仅在此次返回，请妥善保管）",
    }


@router.delete("/{key_id}")
async def delete_api_key(key_id: str):
    """删除指定 API 密钥"""
    keys = _load_keys()
    initial_len = len(keys)
    keys = [k for k in keys if k["id"] != key_id]

    if len(keys) == initial_len:
        raise HTTPException(status_code=404, detail="API 密钥不存在")

    _save_keys(keys)
    return {"status": "success", "message": f"API 密钥 {key_id} 已删除"}


@router.put("/{key_id}")
async def update_api_key(key_id: str, body: ApiKeyUpdate):
    """更新 API 密钥"""
    keys = _load_keys()

    for i, k in enumerate(keys):
        if k["id"] == key_id:
            if body.name is not None:
                keys[i]["name"] = body.name
            if body.permissions is not None:
                keys[i]["permissions"] = body.permissions
            if body.expires_at is not None:
                keys[i]["expires_at"] = body.expires_at
            if body.is_active is not None:
                keys[i]["is_active"] = body.is_active

            _save_keys(keys)
            masked = keys[i].copy()
            masked["key"] = _mask_key(keys[i]["key"])
            return {"status": "success", "data": masked, "message": "API 密钥更新成功"}

    raise HTTPException(status_code=404, detail="API 密钥不存在")
