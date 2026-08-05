"""
伏羲 v1.44 — Webhook 管理路由
=============================
提供 Webhook 的 CRUD 操作和连通性测试。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# 数据目录
DATA_DIR = Path(__file__).parent.parent.parent / "data"
WEBHOOKS_FILE = DATA_DIR / "webhooks.json"


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str] = []
    secret: Optional[str] = None


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


class Webhook(BaseModel):
    id: str
    name: str
    url: str
    events: List[str]
    secret: Optional[str]
    is_active: bool
    created_at: str
    last_triggered_at: Optional[str]
    trigger_count: int


def _load_webhooks() -> List[dict]:
    """加载 Webhook 数据"""
    if not WEBHOOKS_FILE.exists():
        return []
    with open(WEBHOOKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_webhooks(webhooks: List[dict]) -> None:
    """保存 Webhook 数据"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WEBHOOKS_FILE, "w", encoding="utf-8") as f:
        json.dump(webhooks, f, ensure_ascii=False, indent=2)


@router.get("")
async def list_webhooks():
    """获取所有 Webhook 列表"""
    webhooks = _load_webhooks()
    return {"status": "success", "data": webhooks}


@router.post("")
async def create_webhook(body: WebhookCreate):
    """创建新的 Webhook"""
    webhooks = _load_webhooks()

    new_webhook = {
        "id": uuid.uuid4().hex[:12],
        "name": body.name,
        "url": body.url,
        "events": body.events,
        "secret": body.secret,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "last_triggered_at": None,
        "trigger_count": 0,
    }

    webhooks.append(new_webhook)
    _save_webhooks(webhooks)

    return {
        "status": "success",
        "data": new_webhook,
        "message": "Webhook 创建成功",
    }


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """删除指定 Webhook"""
    webhooks = _load_webhooks()
    initial_len = len(webhooks)
    webhooks = [w for w in webhooks if w["id"] != webhook_id]

    if len(webhooks) == initial_len:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    _save_webhooks(webhooks)
    return {"status": "success", "message": f"Webhook {webhook_id} 已删除"}


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, body: WebhookUpdate):
    """更新 Webhook"""
    webhooks = _load_webhooks()

    for i, w in enumerate(webhooks):
        if w["id"] == webhook_id:
            if body.name is not None:
                webhooks[i]["name"] = body.name
            if body.url is not None:
                webhooks[i]["url"] = body.url
            if body.events is not None:
                webhooks[i]["events"] = body.events
            if body.secret is not None:
                webhooks[i]["secret"] = body.secret
            if body.is_active is not None:
                webhooks[i]["is_active"] = body.is_active

            _save_webhooks(webhooks)
            return {"status": "success", "data": webhooks[i], "message": "Webhook 更新成功"}

    raise HTTPException(status_code=404, detail="Webhook 不存在")


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """测试 Webhook 连通性"""
    webhooks = _load_webhooks()

    webhook = None
    for w in webhooks:
        if w["id"] == webhook_id:
            webhook = w
            break

    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    test_payload = {
        "event": "webhook.test",
        "timestamp": datetime.now().isoformat(),
        "data": {"message": "这是伏羲系统的 Webhook 连通性测试"},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook["url"],
                json=test_payload,
                headers={"Content-Type": "application/json"},
            )

        success = response.status_code < 400

        # 更新触发统计
        webhook["last_triggered_at"] = datetime.now().isoformat()
        webhook["trigger_count"] = webhook.get("trigger_count", 0) + 1
        _save_webhooks(webhooks)

        return {
            "status": "success" if success else "error",
            "data": {
                "url": webhook["url"],
                "status_code": response.status_code,
                "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                "success": success,
            },
            "message": "Webhook 测试成功" if success else f"Webhook 返回状态码 {response.status_code}",
        }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": "Webhook 请求超时",
        }
    except httpx.RequestError as e:
        return {
            "status": "error",
            "message": f"Webhook 请求失败: {str(e)}",
        }
