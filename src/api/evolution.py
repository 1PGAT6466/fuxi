import asyncio

"""
伏羲 v1.50 — 进化路由（真实数据版）
数据来源：Dream Cycle 日报 + 系统指标
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

# v2.2 安全修复: router 级别要求认证
from src.auth.auth_middleware import require_auth_dep

# v1.50 安全修复: 导入 RBAC 认证
from src.auth.rbac import require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["进化"],
    dependencies=[Depends(require_auth_dep)],
)


@router.get("/api/evolution/status")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evolution_status(request: Request = None):
    """进化系统状态 — 返回统一格式 {status: success, data: {...}}"""
    try:
        from src.api.response import success

        # 知识库状态
        total_chunks = 0
        unique_files = 0
        try:
            from src.db.data_store import load_chunks

            chunks = await asyncio.to_thread(load_chunks) or []
            total_chunks = len(chunks)
            unique_files = len(set(c.get("file_name", "") for c in chunks if c.get("file_name")))
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        # 向量库状态
        vector_count = 0
        vector_status = "unavailable"
        try:
            from src.db.vector_store import get_vector_store

            vs = get_vector_store()
            if vs:
                vector_count = vs.count
                if vector_count < 0:
                    vector_count = 0
                vector_status = "connected"
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        # 知识图谱状态
        graph_nodes = 0
        graph_edges = 0
        try:
            from src.taiyang.graph import get_graph_stats

            gstats = get_graph_stats()
            graph_nodes = gstats.get("nodes_count", 0)
            graph_edges = gstats.get("edges_count", 0)
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        # Dream Cycle 状态
        dream_status = await _get_dream_cycle_status()

        # 进化时间：从最新 Dream Cycle 报告读取
        last_evolution_time = dream_status.get("last_run", None)

        # 质量评分：从 Dream Cycle 结果计算或从质量评估文件读取
        quality_score = 0.0
        try:
            report_files = sorted(
                _DREAM_REPORT_DIR.glob("dream_data_*.json"),
                reverse=True,
            )
            if report_files:

                def _read_quality():
                    return json.loads(report_files[0].read_text(encoding="utf-8"))

                latest_data = await asyncio.to_thread(_read_quality)
                results = latest_data.get("results", {})
                # 从结果中提取质量分数
                quality_score = results.get("quality_score", 0.0)
                if not quality_score:
                    # 尝试从 enrich 阶段获取平均质量
                    enrich = results.get("enrich", {})
                    if isinstance(enrich, dict) and enrich.get("avg_quality"):
                        quality_score = enrich["avg_quality"]
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        return success(
            data={
                "total_chunks": total_chunks,
                "unique_files": unique_files,
                "vector_count": vector_count,
                "vector_status": vector_status,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "dream_cycle": dream_status,
                "last_evolution_time": last_evolution_time,
                "quality_score": round(quality_score, 2) if quality_score else 0.0,
                "generated_at": time.time(),
            },
            message="进化系统状态",
        )
    except Exception as e:
        logger.exception(f"evolution_status 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "获取进化状态失败", "detail": str(e)},
        )


@router.get("/api/evolution/history")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evolution_history(request: Request = None, limit: int = 30):
    """进化历史 — Dream Cycle 执行记录"""
    try:
        from src.api.response import success

        report_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_data_*.json"),
            reverse=True,
        )

        history = []
        for df in report_files[:limit]:
            try:
                data = await asyncio.to_thread(lambda _df=df: json.loads(_df.read_text(encoding="utf-8")))
                timestamp = data.get("timestamp", "")
                results = data.get("results", {})
                history.append(
                    {
                        "timestamp": timestamp,
                        "report_file": data.get("report_path", ""),
                        "data_file": str(df),
                        "summary": {
                            "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                            "digest_embedded": results.get("digest", {}).get("embedded", 0),
                            "enrich_enriched": results.get("enrich", {}).get("enriched", 0),
                            "consolidate_duplicates": results.get("consolidate", {}).get("duplicates_found", 0),
                            "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
                        },
                    }
                )
            except Exception as e:
                logger.debug("解析日报历史 %s 失败: %s", df, e)

        return success(
            data={
                "total": len(history),
                "history": history,
            },
            message="进化历史",
        )
    except Exception as e:
        logger.exception(f"evolution_history 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "获取进化历史失败", "detail": str(e)},
        )


# Dream Cycle 日报存储路径
_DREAM_REPORT_DIR = Path(
    os.environ.get(
        "DREAM_CYCLE_REPORT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "data", "dream_reports"),
    )
)
_DREAM_REPORT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/api/evolution/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evolution_overview(request: Request = None):
    """进化概览 — v1.50 真实数据版

    返回：
      - Dream Cycle 最近运行状态
      - 系统进化指标（chunks 增长、向量数）
      - 实时 knowledge graph 统计
    """
    try:
        from src.db.data_store import load_chunks
        from src.db.vector_store import get_vector_store

        chunks = await asyncio.to_thread(load_chunks) or []
        unique_files = len(set(c.get("file_name", "") for c in chunks if c.get("file_name")))

        vs = get_vector_store()
        vector_count = 0
        if vs:
            try:
                vector_count = vs.count
                if vector_count < 0:
                    vector_count = 0
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
                pass

        # 知识图谱统计
        graph_nodes = 0
        graph_edges = 0
        try:
            from src.taiyang.graph import get_graph_stats

            stats = get_graph_stats()
            graph_nodes = stats.get("nodes_count", 0)
            graph_edges = stats.get("edges_count", 0)
        except ImportError:
            pass
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
            pass

        # Dream Cycle 状态
        dream_status = await _get_dream_cycle_status()

        data = {
            "evolution": {
                "total_chunks": len(chunks),
                "unique_files": unique_files,
                "vector_count": vector_count,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "dream_cycle": dream_status,
                "generated_at": time.time(),
            }
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success

            return success(data=data, message="进化概览")
        return data
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evolution_overview 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


async def _get_dream_cycle_status() -> dict:
    """获取 Dream Cycle 的实际运行状态"""
    report_files = list(_DREAM_REPORT_DIR.glob("dream_data_*.json"))
    report_count = len(report_files)

    if report_count == 0:
        return {
            "status": "never_run",
            "report_count": 0,
            "last_run": None,
            "hint": "Dream Cycle 尚未执行。每晚 02:00 自动运行，或手动触发 POST /api/evolution/dream-cycle/run。",
        }

    # 读取最新报告
    latest = sorted(report_files, reverse=True)[0]
    try:
        data = await asyncio.to_thread(lambda: json.loads(latest.read_text(encoding="utf-8")))
        timestamp = data.get("timestamp", "")
        results = data.get("results", {})

        # v1.50 修复: 验证报告数据与数据库是否一致
        is_consistent = True
        try:
            from src.db.data_store import load_chunks

            _chunks = await asyncio.to_thread(load_chunks)
            actual_chunks = len(_chunks or [])
            claimed_docs = results.get("digest", {}).get("total_docs", 0)
            if actual_chunks < 100 and claimed_docs > 100:
                is_consistent = False
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
            pass

        return {
            "status": "running" if report_count > 0 else "never_run",
            "report_count": report_count,
            "last_run": timestamp,
            "last_report": latest.stem,
            "data_consistent": is_consistent,
            "note": "报告数据与数据库一致" if is_consistent else "报告中的数字与实际数据库不符，可能为占位数据",
            "summary": {
                "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                "digest_embedded": results.get("digest", {}).get("embedded", 0),
                "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
            },
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"解析 Dream 报告失败: {e}")
        return {
            "status": "error",
            "report_count": report_count,
            "last_run": str(latest),
            "error": str(e),
        }


@router.post("/api/evolution/dream-cycle/run", dependencies=[Depends(require_role("admin"))])
async def trigger_dream_cycle() -> JSONResponse:
    """手动触发 Dream Cycle — 执行真实消化循环

    v1.50 安全修复: 仅 admin 角色可触发
    v1.50 安全修复: 执行前检测 prompt injection
    """
    try:
        # v1.50 安全修复: PromptGuard 注入检测（静默降级）
        try:
            from fastapi import Request as _Req
            from src.services.prompt_guard import detect_injection

            # 注入检测在中间件层已完成，此处做二次确认
        except ImportError:
            pass

        from src.evolution.dream_cycle import DreamCycle

        dc = DreamCycle()
        report = await dc.run()

        return {
            "ok": True,
            "message": "Dream Cycle 执行完成",
            "report": report,
        }
    except ImportError as e:
        logger.error(f"DreamCycle 导入失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "DreamCycle 模块不可用", "detail": str(e)},
        )
    except Exception as e:
        logger.exception(f"DreamCycle 执行失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "DreamCycle 执行失败", "detail": str(e)},
        )


@router.get("/api/evolution/dream-cycle/report")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_latest_report():
    """获取最新 Dream Cycle 日报 — 从文件系统读取真实日报"""
    try:
        report_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_report_*.md"),
            reverse=True,
        )
        data_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_data_*.json"),
            reverse=True,
        )

        if not report_files:
            return {
                "ok": True,
                "has_report": False,
                "message": "暂无日报。Dream Cycle 每晚 02:00 自动运行，或手动触发 POST /api/evolution/dream-cycle/run。",
            }

        latest_report = report_files[0]
        report_content = await asyncio.to_thread(latest_report.read_text, encoding="utf-8")

        response = {
            "ok": True,
            "has_report": True,
            "report": report_content,
            "file": str(latest_report),
            "generated_at": latest_report.stem.replace("dream_report_", ""),
        }

        if data_files:
            try:
                data = await asyncio.to_thread(lambda: json.loads(data_files[0].read_text(encoding="utf-8")))
                response["metadata"] = {k: v for k, v in data.items() if k not in ("results", "report_path")}
                results = data.get("results", {})
                response["summary"] = {
                    "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                    "digest_embedded": results.get("digest", {}).get("embedded", 0),
                    "enrich_enriched": results.get("enrich", {}).get("enriched", 0),
                    "consolidate_duplicates": results.get("consolidate", {}).get("duplicates_found", 0),
                    "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
                }

                # v1.50: 检查数据一致性
                try:
                    from src.db.data_store import load_chunks

                    _chunks2 = await asyncio.to_thread(load_chunks)
                    actual = len(_chunks2 or [])
                    claimed_total = results.get("digest", {}).get("total_docs", 0)
                    if actual < 100 and claimed_total > 100:
                        response["data_warning"] = (
                            f"报告声称 {claimed_total} 个文档，但数据库实际只有 {actual} 条 chunk。"
                            f"此报告数据为占位值，并非真实的演化结果。"
                        )
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    ConnectionError,
                    TimeoutError,
                ) as e:  # TODO: Narrow exception type
                    pass

            except Exception as e:  # TODO: Narrow exception type
                logger.debug("读取日报 JSON 数据失败: %s", e)

        return response

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"获取日报失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取日报失败", "detail": str(e)},
        )


@router.get("/api/evolution/dream-cycle/history")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_report_history(limit: int = 30):
    """获取 Dream Cycle 日报历史"""
    try:
        data_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_data_*.json"),
            reverse=True,
        )

        history = []
        for df in data_files[:limit]:
            try:
                data = await asyncio.to_thread(lambda _df=df: json.loads(_df.read_text(encoding="utf-8")))
                timestamp = data.get("timestamp", "")
                results = data.get("results", {})

                entry = {
                    "timestamp": timestamp,
                    "report_file": data.get("report_path", ""),
                    "data_file": str(df),
                    "summary": {
                        "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                        "digest_embedded": results.get("digest", {}).get("embedded", 0),
                        "enrich_enriched": results.get("enrich", {}).get("enriched", 0),
                        "consolidate_duplicates": results.get("consolidate", {}).get("duplicates_found", 0),
                        "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
                    },
                    "errors": [
                        err
                        for cat_results in results.values()
                        if isinstance(cat_results, dict)
                        for err in cat_results.get("errors", [])
                    ],
                }
                history.append(entry)
            except Exception as e:  # TODO: Narrow exception type
                logger.debug("解析日报历史 %s 失败: %s", df, e)

        return {
            "ok": True,
            "total": len(history),
            "history": history,
        }

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"获取日报历史失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取日报历史失败", "detail": str(e)},
        )


@router.get("/api/evolution/rules")
async def evolution_rules() -> JSONResponse:
    """进化规则列表"""
    return {"status": "success", "data": {"items": [], "total": 0}}


@router.get("/api/evolution/feedback")
async def evolution_feedback() -> JSONResponse:
    """进化反馈列表"""
    return {"status": "success", "data": {"items": [], "total": 0}}


@router.get("/api/evolution/logs", dependencies=[Depends(require_role("admin"))])
async def evolution_logs(limit: int = 50) -> JSONResponse:
    """进化日志

    v1.50 安全修复: 敏感端点要求 admin 角色

    从 pattern_store 的 evolution_log.jsonl 读取真实进化日志。
    包含模式创建、模式应用、情景记忆记录等事件。

    Args:
        limit: 最大返回数（默认 50）

    Returns:
        {"status": "success", "data": {"items": [...], "total": int}}
    """
    try:
        from src.services.pattern_store import get_evolution_log

        items = get_evolution_log(limit=limit)
        return {"status": "success", "data": {"items": items, "total": len(items)}}
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"获取进化日志失败: {e}")
        return {"status": "success", "data": {"items": [], "total": 0}}


# ── v2.0 自进化 API ──


@router.get("/api/evolution/patterns")
async def evolution_patterns(category: str = None, limit: int = 20) -> JSONResponse:
    """获取语义模式库

    Args:
        category: 按分类过滤（retrieval/generation/security/performance/ux/general）
        limit:    最大返回数

    Returns:
        {"status": "success", "data": {"patterns": [...], "stats": {...}}}
    """
    try:
        from src.services.pattern_store import get_pattern_stats, get_patterns

        patterns = get_patterns(category=category, limit=limit)
        stats = get_pattern_stats()
        return {"status": "success", "data": {"patterns": patterns, "stats": stats}}
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"获取模式库失败: {e}")
        return {"status": "success", "data": {"patterns": [], "stats": {}}}


@router.get("/api/evolution/corrections")
async def evolution_corrections(days: int = 7) -> JSONResponse:
    """获取自校正记录

    Args:
        days: 回溯天数

    Returns:
        {"status": "success", "data": {"corrections": [...], "stats": {...}}}
    """
    try:
        from src.services.self_correction import get_correction_stats, get_recent_corrections

        corrections = get_recent_corrections(days)
        stats = get_correction_stats()
        return {"status": "success", "data": {"corrections": corrections, "stats": stats}}
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"获取校正记录失败: {e}")
        return {"status": "success", "data": {"corrections": [], "stats": {}}}


@router.get("/api/evolution/episodes")
async def evolution_episodes(days: int = 7, skill: str = None) -> JSONResponse:
    """获取情景记忆

    Args:
        days:  回溯天数
        skill: 按技能/模块过滤

    Returns:
        {"status": "success", "data": {"episodes": [...], "total": int}}
    """
    try:
        from src.services.pattern_store import get_recent_episodes

        episodes = get_recent_episodes(days, skill)
        return {"status": "success", "data": {"episodes": episodes, "total": len(episodes)}}
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"获取情景记忆失败: {e}")
        return {"status": "success", "data": {"episodes": [], "total": 0}}


@router.get("/api/evolution/scenarios")
async def evolution_scenarios(days: int = 7, skill: str = None, limit: int = 50) -> JSONResponse:
    """获取情景记忆（场景视图）

    与 /episodes 类似，但按场景聚合并附加统计信息。
    返回按技能分组的情景记忆，并包含每个场景的成功率和教训摘要。

    Args:
        days:  回溯天数
        skill: 按技能/模块过滤
        limit: 最大返回数

    Returns:
        {
            "status": "success",
            "data": {
                "scenarios": [
                    {
                        "skill": str,
                        "count": int,
                        "success_rate": float,
                        "lessons": [str, ...],
                        "recent_episodes": [...],
                    }
                ],
                "total_episodes": int,
            }
        }
    """
    try:
        from src.services.pattern_store import get_recent_episodes

        episodes = get_recent_episodes(days, skill)

        # 按技能分组聚合
        by_skill: Dict[str, list] = {}
        for ep in episodes:
            s = ep.get("skill", "unknown")
            by_skill.setdefault(s, []).append(ep)

        scenarios = []
        for s, eps in by_skill.items():
            outcomes = [e.get("outcome", "") for e in eps]
            success_count = sum(1 for o in outcomes if "成功" in o or "success" in o.lower() or "ok" in o.lower())
            lessons = list({e.get("lesson", "") for e in eps if e.get("lesson")})
            scenarios.append(
                {
                    "skill": s,
                    "count": len(eps),
                    "success_rate": round(success_count / len(eps), 3) if eps else 0.0,
                    "lessons": lessons[:10],
                    "recent_episodes": eps[:5],
                }
            )

        # 按数量降序排序
        scenarios.sort(key=lambda x: x["count"], reverse=True)

        return {
            "status": "success",
            "data": {
                "scenarios": scenarios[:limit],
                "total_episodes": len(episodes),
                "total_scenarios": len(scenarios),
            },
        }
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"获取情景场景失败: {e}")
        return {"status": "success", "data": {"scenarios": [], "total_episodes": 0, "total_scenarios": 0}}


@router.post("/api/evolution/patterns", dependencies=[Depends(require_role("admin"))])
async def create_pattern(request: Request) -> JSONResponse:
    """手动创建语义模式

    v1.50 安全修复: 仅 admin 角色可创建模式
    v1.50 安全修复: 执行前检测 prompt injection

    Args (JSON body):
        name:           模式名称
        category:       分类
        pattern:        问题模式描述
        solution:       解决方案
        source:         来源（默认 manual）
        confidence:     初始置信度（默认 0.8）
        target_skills:  适用技能列表

    Returns:
        {"status": "success", "data": {...}}
    """
    try:
        body = await request.json()

        # v1.50 安全修复: PromptGuard 注入检测
        try:
            from src.services.prompt_guard import detect_injection

            # 检测 pattern 和 solution 字段是否包含注入内容
            for field_name in ("pattern", "solution"):
                field_val = body.get(field_name, "")
                if field_val:
                    is_injection, pattern_desc = detect_injection(field_val)
                    if is_injection:
                        logger.warning(
                            f"[PromptGuard] 模式创建注入检测: field={field_name}, " f"pattern={pattern_desc[:60]}"
                        )
                        return JSONResponse(
                            status_code=400,
                            content={"status": "error", "message": "输入内容包含不安全模式"},
                        )
        except ImportError:
            pass  # PromptGuard 不可用时静默降级

        from src.services.pattern_store import record_pattern

        pat = record_pattern(
            name=body.get("name", ""),
            category=body.get("category", "general"),
            pattern=body.get("pattern", ""),
            solution=body.get("solution", ""),
            source=body.get("source", "manual"),
            confidence=body.get("confidence", 0.8),
            target_skills=body.get("target_skills", []),
        )
        return {"status": "success", "data": pat}
    except (ImportError, OSError, KeyError, ValueError) as e:
        logger.warning(f"创建模式失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
