"""
renderer.py — DXF渲染数据生成器
将解析后的DXF数据转换为前端Canvas渲染所需的JSON格式
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("services.dxf-viewer.renderer")


def _compute_viewport(bounds: Optional[Tuple[float, float, float, float]]) -> Dict[str, Any]:
    if not bounds:
        return {
            "bounds": None,
            "center": (0, 0),
            "scale": 1.0,
            "width": 0,
            "height": 0,
        }

    min_x, min_y, max_x, max_y = bounds
    width = max_x - min_x
    height = max_y - min_y
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    if width <= 0 and height <= 0:
        scale = 1.0
    elif width <= 0:
        scale = 1000.0 / height if height > 0 else 1.0
    elif height <= 0:
        scale = 1000.0 / width
    else:
        scale = min(1000.0 / width, 1000.0 / height)

    return {
        "bounds": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        },
        "center": (center_x, center_y),
        "scale": scale,
        "width": width,
        "height": height,
    }


def _extract_layers(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    layer_map: Dict[str, int] = {}
    for e in entities:
        layer = e.get("layer", "0")
        layer_map[layer] = layer_map.get(layer, 0) + 1
    return [
        {"name": name, "entity_count": count}
        for name, count in sorted(layer_map.items())
    ]


def _convert_entity(entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    etype = entity.get("type", "")
    result = {
        "type": etype,
        "layer": entity.get("layer", "0"),
        "geometry": {},
    }

    if etype == "LINE":
        result["geometry"] = {
            "type": "line",
            "start": entity["start"],
            "end": entity["end"],
        }
    elif etype == "CIRCLE":
        result["geometry"] = {
            "type": "circle",
            "center": entity["center"],
            "radius": entity["radius"],
        }
    elif etype == "ARC":
        result["geometry"] = {
            "type": "arc",
            "center": entity["center"],
            "radius": entity["radius"],
            "start_angle": entity["start_angle"],
            "end_angle": entity["end_angle"],
        }
    elif etype in ("POLYLINE", "LWPOLYLINE"):
        result["geometry"] = {
            "type": "polyline",
            "points": entity["points"],
            "closed": entity.get("is_closed") or entity.get("closed", False),
        }
    elif etype == "TEXT":
        result["geometry"] = {
            "type": "text",
            "text": entity["text"],
            "position": entity["insert"],
            "height": entity["height"],
        }
    elif etype == "MTEXT":
        result["geometry"] = {
            "type": "text",
            "text": entity["text"],
            "position": entity["insert"],
            "height": entity["char_height"],
        }
    elif etype == "DIMENSION":
        result["geometry"] = {
            "type": "dimension",
            "defpoint": entity["defpoint"],
            "text": entity.get("text", ""),
        }
    else:
        return None

    return result


def generate_render_data(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将解析后的DXF数据转换为前端Canvas渲染格式

    返回:
        {
            "viewport": { "bounds", "center", "scale", "width", "height" },
            "layers": [{"name": str, "entity_count": int}],
            "entities": [{"type", "layer", "geometry": {...}}],
        }
    """
    metadata = parsed_data.get("metadata", {})
    entities = parsed_data.get("entities", [])

    viewport = _compute_viewport(metadata.get("bounds"))
    layers = _extract_layers(entities)

    render_entities = []
    for entity in entities:
        converted = _convert_entity(entity)
        if converted:
            render_entities.append(converted)

    return {
        "viewport": viewport,
        "layers": layers,
        "entities": render_entities,
    }
