"""
parser.py — DXF文件解析器
使用ezdxf库解析DXF文件，提取几何实体、文本内容和元数据
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("services.dxf-viewer.parser")

try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    logger.warning("ezdxf not installed — DXF parsing disabled. Install: pip install ezdxf")


def _extract_line(entity) -> Dict[str, Any]:
    return {
        "type": "LINE",
        "layer": entity.dxf.layer,
        "start": (entity.dxf.start.x, entity.dxf.start.y),
        "end": (entity.dxf.end.x, entity.dxf.end.y),
    }


def _extract_circle(entity) -> Dict[str, Any]:
    return {
        "type": "CIRCLE",
        "layer": entity.dxf.layer,
        "center": (entity.dxf.center.x, entity.dxf.center.y),
        "radius": entity.dxf.radius,
    }


def _extract_arc(entity) -> Dict[str, Any]:
    return {
        "type": "ARC",
        "layer": entity.dxf.layer,
        "center": (entity.dxf.center.x, entity.dxf.center.y),
        "radius": entity.dxf.radius,
        "start_angle": entity.dxf.start_angle,
        "end_angle": entity.dxf.end_angle,
    }


def _extract_polyline(entity) -> Dict[str, Any]:
    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    return {
        "type": "POLYLINE",
        "layer": entity.dxf.layer,
        "points": points,
        "is_closed": entity.is_closed,
    }


def _extract_lwpolyline(entity) -> Dict[str, Any]:
    points = [(p[0], p[1]) for p in entity.get_points(format="xy")]
    return {
        "type": "LWPOLYLINE",
        "layer": entity.dxf.layer,
        "points": points,
        "is_closed": entity.closed,
    }


def _extract_text(entity) -> Dict[str, Any]:
    return {
        "type": "TEXT",
        "layer": entity.dxf.layer,
        "text": entity.dxf.text,
        "insert": (entity.dxf.insert.x, entity.dxf.insert.y),
        "height": entity.dxf.height,
    }


def _extract_mtext(entity) -> Dict[str, Any]:
    return {
        "type": "MTEXT",
        "layer": entity.dxf.layer,
        "text": entity.plain_text(),
        "insert": (entity.dxf.insert.x, entity.dxf.insert.y),
        "char_height": entity.dxf.char_height,
    }


def _extract_dimension(entity) -> Dict[str, Any]:
    return {
        "type": "DIMENSION",
        "layer": entity.dxf.layer,
        "defpoint": (entity.dxf.defpoint.x, entity.dxf.defpoint.y),
        "text": entity.dxf.text if hasattr(entity.dxf, "text") else "",
    }


_ENTITY_EXTRACTORS = {
    "LINE": _extract_line,
    "CIRCLE": _extract_circle,
    "ARC": _extract_arc,
    "POLYLINE": _extract_polyline,
    "LWPOLYLINE": _extract_lwpolyline,
    "TEXT": _extract_text,
    "MTEXT": _extract_mtext,
    "DIMENSION": _extract_dimension,
}


def _compute_geometry_hash(entities: List[Dict[str, Any]]) -> str:
    normalized = []
    for e in entities:
        parts = [e.get("type", ""), e.get("layer", "")]
        for key in sorted(e.keys()):
            if key in ("type", "layer"):
                continue
            val = e[key]
            if isinstance(val, float):
                parts.append(f"{val:.6f}")
            elif isinstance(val, (list, tuple)):
                parts.append(",".join(
                    f"{v:.6f}" if isinstance(v, float) else str(v) for v in val
                ))
            else:
                parts.append(str(val))
        normalized.append("|".join(parts))
    normalized.sort()
    content = "\n".join(normalized)
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def _compute_bounds(
    entities: List[Dict[str, Any]]
) -> Optional[Tuple[float, float, float, float]]:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    found = False

    for e in entities:
        points = []
        if "start" in e and "end" in e:
            points.extend([e["start"], e["end"]])
        if "center" in e:
            cx, cy = e["center"]
            r = e.get("radius", 0)
            points.extend([(cx - r, cy - r), (cx + r, cy + r)])
        if "insert" in e:
            points.append(e["insert"])
        if "defpoint" in e:
            points.append(e["defpoint"])
        if "points" in e:
            points.extend(e["points"])

        for px, py in points:
            min_x = min(min_x, px)
            min_y = min(min_y, py)
            max_x = max(max_x, px)
            max_y = max(max_y, py)
            found = True

    return (min_x, min_y, max_x, max_y) if found else None


def extract_dxf(file_path: str) -> Dict[str, Any]:
    """
    解析DXF文件

    返回:
        {
            "metadata": {
                "version": str,
                "layers": List[str],
                "bounds": (min_x, min_y, max_x, max_y) or None,
                "entity_count": int,
            },
            "entities": List[Dict],
            "text_content": List[str],
            "geometry_hash": str,
        }

    异常:
        ValueError: 文件不存在或格式无效
        ImportError: ezdxf未安装
    """
    if not EZDXF_AVAILABLE:
        raise ImportError(
            "ezdxf is required for DXF parsing. Install: pip install ezdxf"
        )

    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"DXF file not found: {file_path}")

    try:
        doc = ezdxf.readfile(str(path))
    except ezdxf.DXFStructureError as e:
        raise ValueError(f"Invalid DXF file structure: {e}")
    except Exception as e:  # TODO: Narrow exception type
        raise ValueError(f"Failed to read DXF file: {e}")

    msp = doc.modelspace()
    entities = []
    text_content = []

    for entity in msp:
        dxftype = entity.dxftype()
        extractor = _ENTITY_EXTRACTORS.get(dxftype)
        if extractor:
            try:
                data = extractor(entity)
                entities.append(data)
                if dxftype in ("TEXT", "MTEXT") and data.get("text"):
                    text_content.append(data["text"])
            except Exception as e:  # TODO: Narrow exception type
                logger.warning(f"Failed to extract {dxftype}: {e}")

    bounds = _compute_bounds(entities)
    geometry_hash = _compute_geometry_hash(entities)

    layer_names = [layer.dxf.name for layer in doc.layers]

    return {
        "metadata": {
            "version": doc.dxf.version if hasattr(doc.dxf, "version") else "unknown",
            "layers": layer_names,
            "bounds": bounds,
            "entity_count": len(entities),
        },
        "entities": entities,
        "text_content": text_content,
        "geometry_hash": geometry_hash,
    }
