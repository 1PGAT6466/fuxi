"""
报告生成器 (Report Generator)
==============================
伏羲自运转 Phase 3 核心模块：
  - 异步生成日报/周报
  - 支持 Markdown + HTML 双格式输出
  - 文件系统存储 + SQLite 索引
  - 手动生成与定时调度集成
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .aggregator import AggregatedData, DataAggregator
from .config import (
    MAX_REPORTS_PER_TYPE,
    REPORT_DB_PATH,
    REPORT_DIR,
    REPORT_FORMATS,
    REPORT_RETENTION_DAYS,
)
from .templates import ReportTemplate, get_template, list_templates

logger = logging.getLogger("fuxi.reporter")


# ───────────────────────────────────────────────────
# 报告存储模型
# ───────────────────────────────────────────────────


class ReportStore:
    """报告索引的 SQLite 持久化"""

    def __init__(self, db_path: str = REPORT_DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id       TEXT PRIMARY KEY,
                report_type     TEXT NOT NULL,       -- daily | weekly
                title           TEXT NOT NULL,
                start_time      TEXT NOT NULL,
                end_time        TEXT NOT NULL,
                generated_at    TEXT NOT NULL,
                format          TEXT DEFAULT 'markdown',
                file_path       TEXT,                -- Markdown 文件路径
                html_path       TEXT,                -- HTML 文件路径
                summary         TEXT DEFAULT '',     -- 摘要（前 500 字）
                data_json       TEXT DEFAULT '{}',   -- 聚合数据 JSON
                status          TEXT DEFAULT 'success',  -- success | failed
                duration_ms     REAL DEFAULT 0.0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_reports_type_time
                ON reports(report_type, generated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_reports_created
                ON reports(created_at DESC);
        """)
        conn.commit()

    def save_report(self, report: Dict[str, Any]):
        """保存报告索引"""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO reports
            (report_id, report_type, title, start_time, end_time,
             generated_at, format, file_path, html_path, summary,
             data_json, status, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                report["report_id"],
                report["report_type"],
                report["title"],
                report["start_time"],
                report["end_time"],
                report["generated_at"],
                report.get("format", "markdown"),
                report.get("file_path"),
                report.get("html_path"),
                report.get("summary", "")[:500],
                report.get("data_json", "{}"),
                report.get("status", "success"),
                report.get("duration_ms", 0.0),
            ),
        )
        conn.commit()

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取单个报告"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM reports WHERE report_id=?", (report_id,)).fetchone()
        return dict(row) if row else None

    def list_reports(
        self,
        report_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取报告列表"""
        conn = self._get_conn()
        if report_type:
            rows = conn.execute(
                "SELECT * FROM reports WHERE report_type=? ORDER BY generated_at DESC LIMIT ? OFFSET ?",
                (report_type, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY generated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_reports(self, report_type: Optional[str] = None) -> int:
        """统计报告数量"""
        conn = self._get_conn()
        if report_type:
            row = conn.execute("SELECT COUNT(*) FROM reports WHERE report_type=?", (report_type,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM reports").fetchone()
        return row[0] if row else 0

    def cleanup_old_reports(self, retention_days: int = REPORT_RETENTION_DAYS):
        """清理过期报告"""
        conn = self._get_conn()
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        rows = conn.execute("SELECT file_path, html_path FROM reports WHERE created_at < ?", (cutoff,)).fetchall()
        for row in rows:
            for path in (row["file_path"], row["html_path"]):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        conn.execute("DELETE FROM reports WHERE created_at < ?", (cutoff,))
        conn.commit()
        return len(rows)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ───────────────────────────────────────────────────
# 报告生成器
# ───────────────────────────────────────────────────


class ReportGenerator:
    """
    报告生成器
    异步生成日报/周报，存储到文件系统和数据库索引。
    """

    def __init__(self):
        self._store = ReportStore()
        self._aggregator = DataAggregator()
        os.makedirs(REPORT_DIR, exist_ok=True)

    @property
    def store(self) -> ReportStore:
        return self._store

    async def generate(
        self,
        report_type: str = "daily",
        end_time: Optional[datetime] = None,
        template_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成报告。

        Args:
            report_type: "daily" 或 "weekly"
            end_time: 报告结束时间（默认当前时间）
            template_name: 模板名称（默认使用 report_type 对应模板）

        Returns:
            报告信息字典
        """
        started = time.monotonic()

        if end_time is None:
            end_time = datetime.now()

        if template_name is None:
            template_name = report_type

        template = get_template(template_name)
        if template is None:
            return {
                "status": "error",
                "message": f"模板不存在: {template_name}",
                "available_templates": list(list_templates().keys()),
            }

        # 计算时间范围
        if report_type == "daily":
            start_time = end_time - timedelta(hours=24)
            title = f"系统日报 {end_time.strftime('%Y-%m-%d')}"
        elif report_type == "weekly":
            start_time = end_time - timedelta(days=7)
            title = f"系统周报 {end_time.strftime('%Y-%m-%d')}"
        else:
            return {"status": "error", "message": f"未知报告类型: {report_type}"}

        # 生成报告 ID
        report_id = f"{report_type}_{end_time.strftime('%Y%m%d_%H%M%S')}"

        try:
            logger.info(f"[Reporter] 开始生成{title}...")

            # 1. 数据聚合
            data = await self._aggregator.aggregate(report_type, end_time)

            # 2. 渲染 Markdown
            md_content = template.render_markdown(data)

            # 3. 渲染 HTML
            html_content = template.render_html(data)

            # 4. 保存文件
            date_str = end_time.strftime("%Y%m%d")
            report_subdir = os.path.join(REPORT_DIR, report_type)
            os.makedirs(report_subdir, exist_ok=True)

            md_path = os.path.join(report_subdir, f"{report_id}.md")
            html_path = os.path.join(report_subdir, f"{report_id}.html")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            duration_ms = (time.monotonic() - started) * 1000

            # 5. 保存索引
            report_info = {
                "report_id": report_id,
                "report_type": report_type,
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "generated_at": datetime.now().isoformat(),
                "format": "markdown+html",
                "file_path": md_path,
                "html_path": html_path,
                "summary": md_content[:500],
                "data_json": json.dumps(
                    {
                        "health_ratio": data.health.healthy_ratio,
                        "total_requests": data.requests.total_requests,
                        "success_rate": data.requests.success_rate,
                        "total_errors": data.errors.total_errors,
                        "cpu_avg": data.resources.cpu_avg,
                        "memory_avg": data.resources.memory_avg,
                        "total_alerts": data.alerts.total_alerts,
                        "total_repairs": data.repairs.total_repairs,
                    },
                    ensure_ascii=False,
                ),
                "status": "success",
                "duration_ms": round(duration_ms, 2),
            }

            self._store.save_report(report_info)

            # 6. 清理旧报告
            self._store.cleanup_old_reports()

            logger.info(f"[Reporter] ✓ {title} 生成完成 ({duration_ms:.0f}ms)")

            return {
                "status": "ok",
                "message": f"{title} 生成成功",
                "report_id": report_id,
                "file_path": md_path,
                "html_path": html_path,
                "duration_ms": round(duration_ms, 2),
            }

        except Exception as exc:
            duration_ms = (time.monotonic() - started) * 1000
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(f"[Reporter] ✗ {title} 生成失败: {error_msg}")

            # 保存失败记录
            self._store.save_report(
                {
                    "report_id": report_id,
                    "report_type": report_type,
                    "title": title,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "generated_at": datetime.now().isoformat(),
                    "status": "failed",
                    "duration_ms": round(duration_ms, 2),
                    "summary": error_msg,
                }
            )

            return {
                "status": "error",
                "message": f"报告生成失败: {error_msg}",
                "report_id": report_id,
                "duration_ms": round(duration_ms, 2),
            }

    async def get_report_content(self, report_id: str, fmt: str = "markdown") -> Optional[str]:
        """读取报告文件内容"""
        report = self._store.get_report(report_id)
        if not report:
            return None

        path = report.get("file_path") if fmt == "markdown" else report.get("html_path")
        if not path or not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def list_reports(
        self,
        report_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """获取报告列表"""
        reports = self._store.list_reports(report_type, limit, offset)
        total = self._store.count_reports(report_type)

        # 解析 JSON 字段
        for r in reports:
            data_json = r.get("data_json", "{}")
            if isinstance(data_json, str):
                try:
                    r["data_json"] = json.loads(data_json)
                except (json.JSONDecodeError, TypeError):
                    r["data_json"] = {}

        return {
            "reports": reports,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取单个报告详情"""
        report = self._store.get_report(report_id)
        if not report:
            return None

        data_json = report.get("data_json", "{}")
        if isinstance(data_json, str):
            try:
                report["data_json"] = json.loads(data_json)
            except (json.JSONDecodeError, TypeError):
                report["data_json"] = {}

        return report

    def get_available_templates(self) -> Dict[str, str]:
        """获取可用模板列表"""
        return list_templates()

    def close(self):
        """关闭存储连接"""
        self._store.close()


# ───────────────────────────────────────────────────
# 调度器集成
# ───────────────────────────────────────────────────

# 全局单例
_report_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """获取报告生成器单例"""
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator


async def generate_daily_report() -> dict:
    """调度器回调：生成日报"""
    generator = get_report_generator()
    return await generator.generate(report_type="daily")


async def generate_weekly_report() -> dict:
    """调度器回调：生成周报"""
    generator = get_report_generator()
    return await generator.generate(report_type="weekly")
