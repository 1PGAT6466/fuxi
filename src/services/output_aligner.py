"""
output_aligner.py — 输出格式对齐器
装载机和kb-server输出格式统一
"""
import logging
from typing import Dict, List

logger = logging.getLogger("services.output_aligner")


class OutputFormatAligner:
    """输出格式对齐器"""

    UNIFIED_FORMAT = {
        "chunks": [
            {
                "text": str,
                "file_name": str,
                "file_hash": str,
                "chunk_index": int,
                "total_chunks": int,
                "category": str,
                "source_pipeline": str,
                "metadata": dict,
            }
        ],
        "events": list,
        "entities": list,
        "file_hash": str,
        "file_name": str,
        "file_type": str,
        "total_chunks": int,
        "duration_ms": float,
    }

    @staticmethod
    def align_loader_output(loader_output: Dict) -> Dict:
        """对齐装载机输出格式"""
        aligned = {
            "chunks": [],
            "events": [],
            "entities": [],
            "file_hash": loader_output.get("file_hash", ""),
            "file_name": loader_output.get("file_name", ""),
            "file_type": loader_output.get("file_type", ""),
            "total_chunks": loader_output.get("total_chunks", 0),
            "duration_ms": 0,
        }

        for chunk in loader_output.get("chunks", []):
            aligned_chunk = {
                "text": chunk.get("text", ""),
                "file_name": chunk.get("file_name", ""),
                "file_hash": chunk.get("file_hash", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "total_chunks": chunk.get("total_chunks", 0),
                "category": chunk.get("category", "未分类"),
                "source_pipeline": "loader",
                "metadata": chunk.get("metadata", {}),
            }
            aligned["chunks"].append(aligned_chunk)

        return aligned

    @staticmethod
    def align_shaoyang_output(shaoyang_output: Dict) -> Dict:
        """对齐shaoyang输出格式"""
        return shaoyang_output

    @staticmethod
    def validate_output(output: Dict) -> Dict:
        """验证输出格式"""
        errors = []

        if "chunks" not in output:
            errors.append("缺少chunks字段")

        for i, chunk in enumerate(output.get("chunks", [])):
            if "text" not in chunk:
                errors.append(f"chunks[{i}]缺少text字段")
            if "file_name" not in chunk:
                errors.append(f"chunks[{i}]缺少file_name字段")
            if "file_hash" not in chunk:
                errors.append(f"chunks[{i}]缺少file_hash字段")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }
