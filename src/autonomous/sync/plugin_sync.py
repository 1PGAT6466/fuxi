"""
插件源同步器 (Plugin Sync)
============================
支持 NPM、GitHub、PyPI 三种源的增量同步。
基于版本号对比实现增量同步，状态持久化到 SQLite。
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from src.autonomous.sync.config import (
    PLUGIN_SYNC_SOURCES,
    SYNC_DB_PATH,
    SYNC_MAX_RETRIES,
    SYNC_RETRY_DELAY,
)

logger = logging.getLogger("fuxi.sync.plugin")


class SyncStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功


class SourceType(str, Enum):
    NPM = "npm"
    GITHUB = "github"
    PYPI = "pypi"


@dataclass
class PluginRecord:
    """插件记录"""

    source: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    repository: str = ""
    keywords: List[str] = field(default_factory=list)
    last_updated: str = ""
    raw_data: str = ""


@dataclass
class SyncRunRecord:
    """同步执行记录"""

    run_id: int = 0
    source: str = ""
    status: str = "success"
    started_at: str = ""
    finished_at: str = ""
    duration_ms: float = 0.0
    total_plugins: int = 0
    new_plugins: int = 0
    updated_plugins: int = 0
    error_count: int = 0
    errors: str = ""


# ───────────────────────────────────────────────────
# SQLite 存储层
# ───────────────────────────────────────────────────
class PluginSyncStore:
    """插件同步状态的 SQLite 持久化"""

    def __init__(self, db_path: str = SYNC_DB_PATH):
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
            CREATE TABLE IF NOT EXISTS plugin_registry (
                source      TEXT NOT NULL,
                name        TEXT NOT NULL,
                version     TEXT NOT NULL,
                description TEXT DEFAULT '',
                author      TEXT DEFAULT '',
                homepage    TEXT DEFAULT '',
                repository  TEXT DEFAULT '',
                keywords    TEXT DEFAULT '[]',
                last_updated TEXT DEFAULT '',
                raw_data    TEXT DEFAULT '{}',
                synced_at   TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (source, name)
            );

            CREATE TABLE IF NOT EXISTS plugin_sync_history (
                run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source          TEXT NOT NULL,
                status          TEXT NOT NULL,
                started_at      TEXT,
                finished_at     TEXT,
                duration_ms     REAL DEFAULT 0.0,
                total_plugins   INTEGER DEFAULT 0,
                new_plugins     INTEGER DEFAULT 0,
                updated_plugins INTEGER DEFAULT 0,
                error_count     INTEGER DEFAULT 0,
                errors          TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_plugin_sync_source
                ON plugin_sync_history(source, created_at DESC);

            CREATE TABLE IF NOT EXISTS plugin_sync_state (
                source      TEXT PRIMARY KEY,
                last_sync   TEXT,
                last_version TEXT DEFAULT '{}',
                status      TEXT DEFAULT 'idle',
                error       TEXT DEFAULT ''
            );
        """)
        conn.commit()

    # ── 插件记录 ──
    def upsert_plugin(self, plugin: PluginRecord):
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO plugin_registry (source, name, version, description, author,
                homepage, repository, keywords, last_updated, raw_data, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(source, name) DO UPDATE SET
                version=excluded.version, description=excluded.description,
                author=excluded.author, homepage=excluded.homepage,
                repository=excluded.repository, keywords=excluded.keywords,
                last_updated=excluded.last_updated, raw_data=excluded.raw_data,
                synced_at=datetime('now')
        """,
            (
                plugin.source,
                plugin.name,
                plugin.version,
                plugin.description,
                plugin.author,
                plugin.homepage,
                plugin.repository,
                json.dumps(plugin.keywords, ensure_ascii=False),
                plugin.last_updated,
                plugin.raw_data,
            ),
        )
        conn.commit()

    def get_plugin(self, source: str, name: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM plugin_registry WHERE source=? AND name=?", (source, name)).fetchone()
        return dict(row) if row else None

    def get_plugins(self, source: str, limit: int = 100, offset: int = 0) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM plugin_registry WHERE source=? ORDER BY name LIMIT ? OFFSET ?", (source, limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_plugin_count(self, source: str) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM plugin_registry WHERE source=?", (source,)).fetchone()
        return row["cnt"] if row else 0

    # ── 同步状态 ──
    def get_sync_state(self, source: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM plugin_sync_state WHERE source=?", (source,)).fetchone()
        return dict(row) if row else None

    def update_sync_state(self, source: str, status: str, last_version: Optional[dict] = None, error: str = ""):
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO plugin_sync_state (source, last_sync, last_version, status, error)
            VALUES (?, datetime('now'), ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_sync=datetime('now'),
                last_version=excluded.last_version,
                status=excluded.status,
                error=excluded.error
        """,
            (source, json.dumps(last_version or {}, ensure_ascii=False), status, error),
        )
        conn.commit()

    # ── 同步历史 ──
    def add_sync_history(self, record: SyncRunRecord):
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO plugin_sync_history (source, status, started_at, finished_at,
                duration_ms, total_plugins, new_plugins, updated_plugins, error_count, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.source,
                record.status,
                record.started_at,
                record.finished_at,
                record.duration_ms,
                record.total_plugins,
                record.new_plugins,
                record.updated_plugins,
                record.error_count,
                record.errors,
            ),
        )
        conn.commit()

    def get_sync_history(self, source: Optional[str] = None, limit: int = 50) -> List[dict]:
        conn = self._get_conn()
        if source:
            rows = conn.execute(
                "SELECT * FROM plugin_sync_history WHERE source=? ORDER BY created_at DESC LIMIT ?", (source, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM plugin_sync_history ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_last_versions(self, source: str) -> Dict[str, str]:
        """获取上次同步的版本快照"""
        state = self.get_sync_state(source)
        if state and state.get("last_version"):
            try:
                return json.loads(state["last_version"])
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ───────────────────────────────────────────────────
# 插件源同步器
# ───────────────────────────────────────────────────
class PluginSyncer:
    """
    插件源同步器
    支持 NPM、GitHub、PyPI 三种源的增量同步。
    """

    def __init__(self):
        self._store = PluginSyncStore()
        self._running = False
        self._current_status: Dict[str, SyncStatus] = {}

    @property
    def store(self) -> PluginSyncStore:
        return self._store

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self, source: Optional[str] = None) -> dict:
        """获取同步状态"""
        if source:
            state = self._store.get_sync_state(source)
            plugins_count = self._store.get_plugin_count(source)
            return {
                "source": source,
                "status": self._current_status.get(source, SyncStatus.IDLE).value,
                "last_sync": state["last_sync"] if state else None,
                "plugin_count": plugins_count,
                "error": state["error"] if state else "",
            }
        else:
            result = {}
            for src in SourceType:
                result[src.value] = self.get_status(src.value)
            return result

    def get_history(self, source: Optional[str] = None, limit: int = 50) -> List[dict]:
        """获取同步历史"""
        return self._store.get_sync_history(source, limit)

    async def sync_all(self) -> Dict[str, SyncRunRecord]:
        """同步所有源"""
        results = {}
        for src in SourceType:
            try:
                record = await self.sync_source(src.value)
                results[src.value] = record
            except Exception as e:
                logger.error(f"[PluginSync] 同步 {src.value} 失败: {e}")
                results[src.value] = SyncRunRecord(
                    source=src.value,
                    status="failed",
                    error_count=1,
                    errors=str(e),
                )
        return results

    async def sync_source(self, source: str) -> SyncRunRecord:
        """同步单个源（增量）"""
        self._running = True
        self._current_status[source] = SyncStatus.RUNNING
        started_at = datetime.now(timezone.utc).isoformat()
        started_ts = time.monotonic()

        record = SyncRunRecord(source=source, status="running", started_at=started_at)
        errors = []

        try:
            # 获取上次版本快照
            old_versions = self._store.get_last_versions(source)

            # 根据源类型执行同步
            if source == SourceType.NPM:
                plugins = await self._sync_npm(old_versions)
            elif source == SourceType.GITHUB:
                plugins = await self._sync_github(old_versions)
            elif source == SourceType.PYPI:
                plugins = await self._sync_pypi(old_versions)
            else:
                raise ValueError(f"不支持的源类型: {source}")

            # 统计变更
            new_count = 0
            updated_count = 0
            new_versions = {}

            for plugin in plugins:
                old_ver = old_versions.get(plugin.name)
                if old_ver is None:
                    new_count += 1
                elif old_ver != plugin.version:
                    updated_count += 1

                new_versions[plugin.name] = plugin.version
                self._store.upsert_plugin(plugin)

            # 更新同步状态
            duration_ms = (time.monotonic() - started_ts) * 1000
            finished_at = datetime.now(timezone.utc).isoformat()

            record.status = "success"
            record.finished_at = finished_at
            record.duration_ms = round(duration_ms, 2)
            record.total_plugins = len(plugins)
            record.new_plugins = new_count
            record.updated_plugins = updated_count

            self._store.update_sync_state(source, "success", new_versions)
            self._current_status[source] = SyncStatus.SUCCESS

            logger.info(
                f"[PluginSync] {source} 同步完成: "
                f"总计 {len(plugins)}, 新增 {new_count}, 更新 {updated_count}, "
                f"耗时 {duration_ms:.0f}ms"
            )

        except Exception as e:
            duration_ms = (time.monotonic() - started_ts) * 1000
            finished_at = datetime.now(timezone.utc).isoformat()

            record.status = "failed"
            record.finished_at = finished_at
            record.duration_ms = round(duration_ms, 2)
            record.error_count = 1
            record.errors = str(e)

            self._store.update_sync_state(source, "failed", error=str(e))
            self._current_status[source] = SyncStatus.FAILED

            logger.error(f"[PluginSync] {source} 同步失败: {e}")

        finally:
            self._store.add_sync_history(record)
            self._running = False

        return record

    # ── NPM 同步 ──
    async def _sync_npm(self, old_versions: Dict[str, str]) -> List[PluginRecord]:
        """从 NPM 同步插件列表"""
        config = PLUGIN_SYNC_SOURCES["npm"]
        plugins = []

        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            # 搜索 fuxi 相关包
            search_terms = ["fuxi", "fuxi-plugin", "fuxi-adapter"]
            seen = set()

            for term in search_terms:
                try:
                    resp = await client.get(
                        f"{config['registry']}{config['search_endpoint']}",
                        params={"text": term, "size": 250},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for obj in data.get("objects", []):
                        pkg = obj.get("package", {})
                        name = pkg.get("name", "")
                        if name in seen or not name:
                            continue
                        seen.add(name)

                        version = pkg.get("version", "0.0.0")
                        # 增量：跳过版本未变化的
                        if old_versions.get(name) == version:
                            continue

                        plugins.append(
                            PluginRecord(
                                source="npm",
                                name=name,
                                version=version,
                                description=pkg.get("description", ""),
                                author=str(pkg.get("author", "")),
                                homepage=pkg.get("links", {}).get("homepage", ""),
                                repository=pkg.get("links", {}).get("repository", ""),
                                keywords=pkg.get("keywords", []),
                                last_updated=pkg.get("date", ""),
                                raw_data=json.dumps(pkg, ensure_ascii=False)[:5000],
                            )
                        )

                except httpx.HTTPError as e:
                    logger.warning(f"[PluginSync:NPM] 搜索 '{term}' 失败: {e}")

        return plugins

    # ── GitHub 同步 ──
    async def _sync_github(self, old_versions: Dict[str, str]) -> List[PluginRecord]:
        """从 GitHub 同步插件仓库"""
        config = PLUGIN_SYNC_SOURCES["github"]
        plugins = []
        headers = {}

        if config.get("token"):
            headers["Authorization"] = f"token {config['token']}"
        headers["Accept"] = "application/vnd.github.v3+json"

        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            org = config.get("org", "")
            if not org:
                logger.warning("[PluginSync:GitHub] 未配置 GITHUB_ORG，跳过")
                return plugins

            page = 1
            while True:
                try:
                    resp = await client.get(
                        f"{config['api_base']}/orgs/{org}/repos",
                        headers=headers,
                        params={"page": page, "per_page": 100, "type": "public"},
                    )
                    resp.raise_for_status()
                    repos = resp.json()

                    if not repos:
                        break

                    for repo in repos:
                        name = repo.get("name", "")
                        # 使用 tag 或 pushed_at 作为版本标识
                        version = repo.get("pushed_at", "unknown")

                        if old_versions.get(name) == version:
                            continue

                        plugins.append(
                            PluginRecord(
                                source="github",
                                name=name,
                                version=version,
                                description=repo.get("description", "") or "",
                                author=repo.get("owner", {}).get("login", ""),
                                homepage=repo.get("homepage", "") or "",
                                repository=repo.get("html_url", ""),
                                keywords=repo.get("topics", []),
                                last_updated=repo.get("pushed_at", ""),
                                raw_data=json.dumps(
                                    {
                                        "stars": repo.get("stargazers_count", 0),
                                        "forks": repo.get("forks_count", 0),
                                        "language": repo.get("language", ""),
                                        "license": (
                                            repo.get("license", {}).get("spdx_id", "") if repo.get("license") else ""
                                        ),
                                    },
                                    ensure_ascii=False,
                                ),
                            )
                        )

                    page += 1

                except httpx.HTTPError as e:
                    logger.warning(f"[PluginSync:GitHub] 获取仓库列表失败 (page={page}): {e}")
                    break

        return plugins

    # ── PyPI 同步 ──
    async def _sync_pypi(self, old_versions: Dict[str, str]) -> List[PluginRecord]:
        """从 PyPI 同步插件包"""
        config = PLUGIN_SYNC_SOURCES["pypi"]
        plugins = []

        # PyPI 没有统一搜索 API，需要已知包名列表
        known_packages = [
            "fuxi-rag",
            "fuxi-core",
            "fuxi-plugin",
            "fuxi-connector",
            "fuxi-adapter",
        ]

        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            for pkg_name in known_packages:
                try:
                    resp = await client.get(f"{config['api_base']}/{pkg_name}/json")
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                    info = data.get("info", {})
                    version = info.get("version", "0.0.0")

                    if old_versions.get(pkg_name) == version:
                        continue

                    plugins.append(
                        PluginRecord(
                            source="pypi",
                            name=pkg_name,
                            version=version,
                            description=info.get("summary", ""),
                            author=info.get("author", "") or info.get("author_email", ""),
                            homepage=info.get("home_page", ""),
                            repository=(
                                info.get("project_urls", {}).get("Repository", "") if info.get("project_urls") else ""
                            ),
                            keywords=(info.get("keywords", "") or "").split(","),
                            last_updated="",
                            raw_data=json.dumps(
                                {
                                    "requires_python": info.get("requires_python", ""),
                                    "license": info.get("license", ""),
                                    "classifiers": info.get("classifiers", [])[:5],
                                },
                                ensure_ascii=False,
                            ),
                        )
                    )

                except httpx.HTTPError as e:
                    logger.warning(f"[PluginSync:PyPI] 获取 {pkg_name} 失败: {e}")

        return plugins

    def close(self):
        self._store.close()
