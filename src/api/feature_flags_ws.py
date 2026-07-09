"""
feature_flags_ws.py — 伏羲 v2.1 Feature Flags WebSocket 推送

WebSocket 端点: ws://host/api/feature-flags/ws
当 flags 变更时（PUT 操作），向所有连接的 WebSocket 客户端推送变更事件。

前端 featureFlags store 收到推送后自动更新状态。
"""
import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger("feature_flags_ws")

router = APIRouter(tags=["feature-flags-ws"])

# ── 活动连接管理器 ──
_active_connections: Set[WebSocket] = set()
_connections_lock = asyncio.Lock()


async def _safe_send(ws: WebSocket, data: dict):
    """安全发送消息，忽略已断开的连接"""
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json(data)
    except Exception:  # TODO: Narrow exception type
        pass


async def broadcast_flag_change(flag_name: str, old_value: bool, new_value: bool):
    """
    向所有连接的 WebSocket 客户端广播 flag 变更事件。

    供 feature_flags 模块在 set_flag() 后调用。
    """
    if not _active_connections:
        return

    event = {
        "type": "flag_changed",
        "flag": flag_name,
        "old_value": old_value,
        "new_value": new_value,
    }

    async with _connections_lock:
        dead_connections = []
        for ws in _active_connections:
            try:
                await _safe_send(ws, event)
            except Exception as e:  # TODO: Narrow exception type
                logger.debug(f"[FF-WS] 发送失败，标记失活: {e}")
                dead_connections.append(ws)

        for ws in dead_connections:
            _active_connections.discard(ws)


@router.websocket("/api/feature-flags/ws")
async def feature_flags_websocket(websocket: WebSocket):
    """
    WebSocket 端点 — Feature Flag 变更实时推送

    连接后:
      - 首次推送当前所有 flags 快照
      - 后续发送 flag_changed 事件
    """
    await websocket.accept()
    logger.info("[FF-WS] 客户端已连接")

    async with _connections_lock:
        _active_connections.add(websocket)

    try:
        # 发送初始快照
        from src.services.feature_flags import load_flags, DEFAULT_FLAGS
        await _safe_send(websocket, {
            "type": "snapshot",
            "flags": load_flags(),
            "defaults": DEFAULT_FLAGS,
        })

        # 保持连接，接收心跳消息
        while True:
            data = await websocket.receive_text()
            # 处理 ping/pong
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await _safe_send(websocket, {"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info("[FF-WS] 客户端断开连接")
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"[FF-WS] 连接异常: {e}")
    finally:
        async with _connections_lock:
            _active_connections.discard(websocket)
