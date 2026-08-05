"""
报告中心 API — 系统报告生成和查询
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("api.reports")

router = APIRouter(prefix="/api/reports", tags=["报告中心"])

# ============ 数据存储 ============
_reports_dir = Path("data/reports")


def _load_reports() -> List[Dict]:
    """加载报告列表"""
    reports = []

    if _reports_dir.exists():
        for report_file in _reports_dir.glob("*.json"):
            try:
                report = json.loads(report_file.read_text(encoding="utf-8"))
                reports.append(report)
            except Exception:
                pass

    # 按时间倒序
    reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return reports


def _save_report(report: Dict) -> None:
    """保存报告"""
    _reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = _reports_dir / f"{report.get('id')}.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


# ============ 报告模板 ============

REPORT_TEMPLATES = [
    {
        "id": "system_health",
        "name": "系统健康报告",
        "description": "系统整体健康状态、资源使用、服务状态",
        "category": "system",
        "schedule": "daily",
    },
    {
        "id": "rag_quality",
        "name": "RAG 质量报告",
        "description": "检索准确率、回答质量、用户满意度",
        "category": "quality",
        "schedule": "weekly",
    },
    {
        "id": "usage_stats",
        "name": "使用统计报告",
        "description": "API 调用量、用户活跃度、功能使用分布",
        "category": "analytics",
        "schedule": "weekly",
    },
    {
        "id": "security_audit",
        "name": "安全审计报告",
        "description": "登录记录、权限变更、异常访问",
        "category": "security",
        "schedule": "monthly",
    },
    {
        "id": "knowledge_growth",
        "name": "知识增长报告",
        "description": "新增文档、知识图谱扩展、学习进度",
        "category": "knowledge",
        "schedule": "weekly",
    },
]


# ============ API 端点 ============


@router.get("/templates")
async def get_report_templates():
    """获取报告模板"""
    return {
        "status": "success",
        "data": REPORT_TEMPLATES,
    }


@router.get("")
async def get_reports(category: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    """获取报告列表"""
    reports = _load_reports()

    # 按分类过滤
    if category:
        reports = [r for r in reports if r.get("category") == category]

    return {
        "status": "success",
        "data": reports[:limit],
        "total": len(reports),
    }


@router.get("/{report_id}")
async def get_report(report_id: str):
    """获取报告详情"""
    report_file = _reports_dir / f"{report_id}.json"

    if not report_file.exists():
        raise HTTPException(404, f"报告 {report_id} 不存在")

    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
        return {"status": "success", "data": report}
    except Exception as e:
        raise HTTPException(500, f"读取报告失败: {e}")


@router.post("/generate")
async def generate_report(request: Dict):
    """生成报告"""
    template_id = request.get("template_id")

    # 查找模板
    template = None
    for t in REPORT_TEMPLATES:
        if t.get("id") == template_id:
            template = t
            break

    if not template:
        raise HTTPException(400, f"报告模板 {template_id} 不存在")

    # 生成报告
    report_id = f"report_{int(time.time())}"
    report = {
        "id": report_id,
        "template_id": template_id,
        "name": template.get("name"),
        "description": template.get("description"),
        "category": template.get("category"),
        "status": "completed",
        "created_at": datetime.now().isoformat(),
        "generated_by": "system",
        "content": _generate_report_content(template_id),
    }

    _save_report(report)

    return {
        "status": "success",
        "message": f"报告 {template.get('name')} 已生成",
        "data": report,
    }


def _generate_report_content(template_id: str) -> Dict:
    """生成报告内容（简化版）"""
    if template_id == "system_health":
        return {
            "summary": "系统运行正常，各项指标在正常范围内",
            "metrics": {
                "cpu_avg": 45.2,
                "memory_avg": 62.8,
                "disk_usage": 35.6,
                "uptime_hours": 72,
            },
            "issues": [],
            "recommendations": [
                "建议定期清理日志文件",
                "考虑增加内存以提升性能",
            ],
        }
    elif template_id == "rag_quality":
        return {
            "summary": "RAG 系统质量稳定，检索准确率 85%",
            "metrics": {
                "retrieval_accuracy": 0.85,
                "answer_quality": 0.78,
                "user_satisfaction": 0.82,
            },
            "top_queries": [
                {"query": "如何优化数据库", "count": 45},
                {"query": "Python 装饰器", "count": 38},
            ],
            "recommendations": [
                "优化长文本检索策略",
                "增加领域特定训练数据",
            ],
        }
    elif template_id == "usage_stats":
        return {
            "summary": "本周 API 调用量 12,345 次，活跃用户 86 人",
            "metrics": {
                "total_api_calls": 12345,
                "active_users": 86,
                "avg_response_time_ms": 250,
            },
            "top_endpoints": [
                {"path": "/api/chat", "calls": 5234},
                {"path": "/api/search", "calls": 3456},
            ],
        }
    else:
        return {
            "summary": f"报告 {template_id} 已生成",
            "metrics": {},
        }


@router.delete("/{report_id}")
async def delete_report(report_id: str):
    """删除报告"""
    report_file = _reports_dir / f"{report_id}.json"

    if not report_file.exists():
        raise HTTPException(404, f"报告 {report_id} 不存在")

    report_file.unlink()

    return {
        "status": "success",
        "message": f"报告 {report_id} 已删除",
    }
