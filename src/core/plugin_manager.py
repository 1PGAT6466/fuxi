"""
伏羲插件管理器
负责插件的完整生命周期管理：安装、激活、停用、卸载、升级

作者: AI助手
日期: 2026-07-16
"""

import hashlib
import importlib.util
import json
import logging
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============ 插件注册表（SQLite） ============
class PluginRegistry:
    """插件注册表 - 使用SQLite持久化存储"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # 使用应用根目录下的 data/plugins.db
            app_root = Path(__file__).parent.parent.parent
            db_path = str(app_root / "data" / "plugins.db")
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> Any:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> Any:
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 插件主表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugins (
                name TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                display_name TEXT,
                description TEXT,
                author TEXT,
                status TEXT DEFAULT 'installed',
                manifest_json TEXT,
                config_json TEXT DEFAULT '{}',
                installed_at TEXT,
                updated_at TEXT
            )
        """)

        # 插件路由表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugin_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                path TEXT NOT NULL,
                method TEXT NOT NULL,
                handler TEXT,
                priority INTEGER DEFAULT 0,
                FOREIGN KEY (plugin_name) REFERENCES plugins(name) ON DELETE CASCADE
            )
        """)

        # 插件事件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugin_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                handler TEXT NOT NULL,
                FOREIGN KEY (plugin_name) REFERENCES plugins(name) ON DELETE CASCADE
            )
        """)

        # 插件依赖表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugin_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                dependency TEXT NOT NULL,
                version_constraint TEXT,
                FOREIGN KEY (plugin_name) REFERENCES plugins(name) ON DELETE CASCADE
            )
        """)

        conn.commit()
        conn.close()
        logger.info("插件注册表初始化完成")

    def register(self, manifest: dict, status: str = "installed") -> Any:
        """注册插件"""
        conn = self._get_conn()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO plugins 
            (name, version, type, display_name, description, author, status, manifest_json, installed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                manifest["name"],
                manifest["version"],
                manifest["type"],
                manifest.get("display_name", manifest["name"]),
                manifest.get("description", ""),
                manifest.get("author", ""),
                status,
                json.dumps(manifest, ensure_ascii=False),
                now,
                now,
            ),
        )

        # 注册路由
        for route in manifest.get("routes", []):
            cursor.execute(
                """
                INSERT INTO plugin_routes (plugin_name, path, method, handler, priority)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    manifest["name"],
                    route.get("path"),
                    route.get("method", "GET"),
                    route.get("handler"),
                    route.get("priority", 0),
                ),
            )

        # 注册事件
        events_data = manifest.get("events", [])
        if isinstance(events_data, list):
            for event in events_data:
                cursor.execute(
                    """
                    INSERT INTO plugin_events (plugin_name, event_type, handler)
                    VALUES (?, ?, ?)
                """,
                    (manifest["name"], event, "on_event"),
                )
        elif isinstance(events_data, dict):
            for event, handler in events_data.items():
                cursor.execute(
                    """
                    INSERT INTO plugin_events (plugin_name, event_type, handler)
                    VALUES (?, ?, ?)
                """,
                    (manifest["name"], event, handler),
                )

        # 注册依赖
        for dep in manifest.get("dependencies", []):
            cursor.execute(
                """
                INSERT INTO plugin_dependencies (plugin_name, dependency, version_constraint)
                VALUES (?, ?, ?)
            """,
                (manifest["name"], dep, None),
            )

        conn.commit()
        conn.close()
        logger.info(f"插件 {manifest['name']} 注册成功")

    def unregister(self, plugin_name: str) -> Any:
        """注销插件"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM plugins WHERE name = ?", (plugin_name,))
        cursor.execute("DELETE FROM plugin_routes WHERE plugin_name = ?", (plugin_name,))
        cursor.execute("DELETE FROM plugin_events WHERE plugin_name = ?", (plugin_name,))
        cursor.execute("DELETE FROM plugin_dependencies WHERE plugin_name = ?", (plugin_name,))

        conn.commit()
        conn.close()
        logger.info(f"插件 {plugin_name} 已注销")

    def get(self, plugin_name: str) -> Optional[dict]:
        """获取插件信息"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM plugins WHERE name = ?", (plugin_name,))
        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            result["manifest"] = json.loads(result.get("manifest_json", "{}"))
            result["config"] = json.loads(result.get("config_json", "{}"))
            return result
        return None

    def list_all(self, status: Optional[str] = None) -> List[dict]:
        """列出所有插件"""
        conn = self._get_conn()
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT * FROM plugins WHERE status = ? ORDER BY name", (status,))
        else:
            cursor.execute("SELECT * FROM plugins ORDER BY name")

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            result["manifest"] = json.loads(result.get("manifest_json", "{}"))
            result["config"] = json.loads(result.get("config_json", "{}"))
            results.append(result)

        return results

    def update_status(self, plugin_name: str, status: str) -> Any:
        """更新插件状态"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE plugins SET status = ?, updated_at = ? WHERE name = ?
        """,
            (status, datetime.now().isoformat(), plugin_name),
        )

        conn.commit()
        conn.close()

    def update_config(self, plugin_name: str, config: dict) -> Any:
        """更新插件配置"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE plugins SET config_json = ?, updated_at = ? WHERE name = ?
        """,
            (json.dumps(config, ensure_ascii=False), datetime.now().isoformat(), plugin_name),
        )

        conn.commit()
        conn.close()

    def get_routes(self, plugin_name: str) -> List[dict]:
        """获取插件路由"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM plugin_routes WHERE plugin_name = ?", (plugin_name,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


# ============ 插件管理器 ============
class PluginManager:
    """插件管理器 - 核心类"""

    def __init__(
        self, plugins_dir: str = "plugins", db_path: str = "data/plugins.db", backup_dir: str = ".fuxi/backups"
    ):
        self.plugins_dir = Path(plugins_dir)
        self.backup_dir = Path(backup_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.registry = PluginRegistry(db_path)
        self._active_plugins: Dict[str, Any] = {}
        self._app = None  # FastAPI app 实例
        logger.info(f"插件管理器初始化完成，插件目录: {self.plugins_dir}")

    # ============ 安装 ============
    def install(self, plugin_path: str, manifest: dict) -> Dict[str, Any]:
        """
        安装插件

        流程：验证 → 依赖检查 → 复制 → 注册 → 安装依赖

        Args:
            plugin_path: 插件源目录路径
            manifest: manifest.json 内容

        Returns:
            安装结果字典
        """
        result = {"success": False, "plugin": manifest.get("name"), "steps": [], "error": None}

        backup_id = None

        try:
            # Step 1: 验证 manifest
            self._validate_manifest(manifest)
            result["steps"].append({"name": "validate", "status": "done"})

            # Step 2: 检查依赖冲突
            self._check_dependencies(manifest)
            result["steps"].append({"name": "dependencies", "status": "done"})

            # Step 3: 复制插件文件（在备份之前，因为备份会删除源目录）
            dest = self._copy_plugin(plugin_path, manifest["name"])
            result["steps"].append({"name": "copy", "status": "done", "path": str(dest)})

            # Step 4: 创建备份（在复制之后）
            backup_id = self._create_backup(manifest["name"])
            result["steps"].append({"name": "backup", "status": "done", "backup_id": backup_id})

            # Step 5: 注册到数据库
            self.registry.register(manifest)
            result["steps"].append({"name": "register", "status": "done"})

            # Step 6: 安装依赖
            self._install_dependencies(manifest.get("dependencies", []))
            result["steps"].append({"name": "install_deps", "status": "done"})

            result["success"] = True
            logger.info(f"插件 {manifest['name']} 安装成功")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"插件安装失败: {e}")
            # 自动回滚
            if backup_id:
                self._rollback(backup_id, manifest.get("name", "unknown"))
                result["steps"].append({"name": "rollback", "status": "done"})

        return result

    # ============ 激活 ============
    def activate(self, plugin_name: str, app=None) -> Dict[str, Any]:
        """
        激活插件

        流程：加载模块 → 注册路由 → 启动服务 → 更新状态

        Args:
            plugin_name: 插件名称
            app: FastAPI app 实例（可选，默认使用 self._app）

        Returns:
            激活结果字典
        """
        result = {"success": False, "plugin": plugin_name, "error": None}

        try:
            # 使用传入的 app 或存储的 app
            app_instance = app or self._app

            # 获取插件信息
            plugin_info = self.registry.get(plugin_name)
            if not plugin_info:
                raise ValueError(f"插件 {plugin_name} 未注册")

            # 加载插件模块
            plugin_module = self._load_plugin_module(plugin_name)

            # 调用 on_activate 钩子
            if hasattr(plugin_module, "on_activate"):
                context = {"app": app_instance, "config": plugin_info.get("config", {})}
                plugin_module.on_activate(context)

            # 注册路由（如果是 API 插件）
            if plugin_info.get("type") == "api" and app_instance:
                self._register_routes(plugin_name, plugin_module, app_instance)

            # 更新状态
            self.registry.update_status(plugin_name, "active")
            self._active_plugins[plugin_name] = plugin_module

            result["success"] = True
            logger.info(f"插件 {plugin_name} 激活成功")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"插件激活失败: {e}")

        return result

    # ============ 停用 ============
    def deactivate(self, plugin_name: str, app=None) -> Dict[str, Any]:
        """
        停用插件

        流程：调用钩子 → 移除路由 → 停止服务 → 更新状态
        """
        result = {"success": False, "plugin": plugin_name, "error": None}

        try:
            plugin_module = self._active_plugins.get(plugin_name)

            # 调用 on_deactivate 钩子
            if plugin_module and hasattr(plugin_module, "on_deactivate"):
                plugin_module.on_deactivate()

            # 移除路由
            if app:
                self._unregister_routes(plugin_name, app)

            # 更新状态
            self.registry.update_status(plugin_name, "inactive")
            self._active_plugins.pop(plugin_name, None)

            result["success"] = True
            logger.info(f"插件 {plugin_name} 已停用")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"插件停用失败: {e}")

        return result

    # ============ 卸载 ============
    def uninstall(self, plugin_name: str, keep_data: bool = False) -> Dict[str, Any]:
        """
        卸载插件

        流程：停用 → 清理 → 删除 → 注销
        """
        result = {"success": False, "plugin": plugin_name, "error": None}

        try:
            # 停用
            if plugin_name in self._active_plugins:
                self.deactivate(plugin_name)

            # 调用 on_uninstall 钩子
            plugin_module = self._load_plugin_module(plugin_name)
            if hasattr(plugin_module, "on_uninstall"):
                plugin_module.on_uninstall()

            # 删除文件
            plugin_path = self.plugins_dir / plugin_name
            if plugin_path.exists():
                shutil.rmtree(plugin_path)

            # 注销
            self.registry.unregister(plugin_name)

            result["success"] = True
            logger.info(f"插件 {plugin_name} 已卸载")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"插件卸载失败: {e}")

        return result

    # ============ 列表 ============
    def list_plugins(self, status: Optional[str] = None) -> List[dict]:
        """列出所有插件"""
        return self.registry.list_all(status)

    # ============ 获取单个插件 ============
    def get_plugin(self, plugin_name: str) -> Optional[dict]:
        """获取插件信息"""
        return self.registry.get(plugin_name)

    # ============ 健康检查 ============
    def health_check(self, plugin_name: str) -> Dict[str, Any]:
        """检查插件健康状态"""
        plugin_info = self.registry.get(plugin_name)
        if not plugin_info:
            return {"status": "not_found", "plugin": plugin_name}

        try:
            plugin_module = self._active_plugins.get(plugin_name)
            if plugin_module and hasattr(plugin_module, "health_check"):
                return plugin_module.health_check()

            # 默认检查
            plugin_path = self.plugins_dir / plugin_name
            return {
                "status": "ok" if plugin_path.exists() else "missing_files",
                "plugin": plugin_name,
                "active": plugin_name in self._active_plugins,
            }
        except Exception as e:
            return {"status": "error", "plugin": plugin_name, "error": str(e)}

    def auto_activate_installed(self) -> Dict[str, Any]:
        """自动激活所有已安装的插件（服务器启动时调用）"""
        results = {"activated": [], "failed": []}
        installed = self.list_plugins("installed")

        for plugin in installed:
            name = plugin["name"]
            result = self.activate(name)
            if result["success"]:
                results["activated"].append(name)
            else:
                results["failed"].append({"name": name, "error": result["error"]})

        # 也激活之前已激活但服务器重启的插件
        active = self.list_plugins("active")
        for plugin in active:
            name = plugin["name"]
            if name not in self._active_plugins:
                result = self.activate(name)
                if result["success"]:
                    results["activated"].append(name)
                else:
                    results["failed"].append({"name": name, "error": result["error"]})

        logger.info(f"自动激活完成: 成功={len(results['activated'])}, 失败={len(results['failed'])}")
        return results

    # ============ 内部方法 ============

    def _validate_manifest(self, manifest: dict) -> Any:
        """验证 manifest.json"""
        required = ["name", "version", "type", "display_name"]
        for field in required:
            if field not in manifest:
                raise ValueError(f"manifest 缺少必填字段: {field}")

        # 验证类型
        valid_types = ["api", "service", "ui", "llm", "storage", "theme"]
        if manifest["type"] not in valid_types:
            raise ValueError(f"无效的插件类型: {manifest['type']}，支持: {valid_types}")

        # 验证版本格式
        if not re.match(r"^\d+\.\d+\.\d+", manifest["version"]):
            raise ValueError(f"版本号格式错误: {manifest['version']}，要求语义化版本 x.y.z")

        # 验证名称格式
        if not re.match(r"^[a-z0-9-]+$", manifest["name"]):
            raise ValueError(f"插件名称只能包含小写字母、数字和连字符")

    def _check_dependencies(self, manifest: dict) -> Any:
        """检查依赖冲突"""
        # 检查是否已安装同名插件
        existing = self.registry.get(manifest["name"])
        if existing and existing.get("status") in ["installed", "active"]:
            raise ValueError(f"插件 {manifest['name']} 已安装")

        # 检查伏羲版本兼容性
        fuxi_version_req = manifest.get("fuxi_version", ">=1.0.0")
        # TODO: 实际检查伏羲版本

    def _create_backup(self, plugin_name: str) -> str:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{plugin_name}_{timestamp}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # 备份当前插件目录（如果存在）
        plugin_path = self.plugins_dir / plugin_name
        if plugin_path.exists():
            shutil.copytree(plugin_path, backup_path / "plugin")

        # 备份数据库
        db_path = Path(self.registry.db_path)
        if db_path.exists():
            shutil.copy2(db_path, backup_path / "plugins.db")

        logger.info(f"备份创建成功: {backup_id}")
        return backup_id

    def _copy_plugin(self, source: str, plugin_name: str) -> Path:
        """复制插件到目标目录"""
        # 清理路径（处理 Windows 编码问题）
        source = source.strip().replace("\u200b", "").replace("\xa0", "")
        source_path = Path(source).resolve()
        dest = (self.plugins_dir / plugin_name).resolve()

        logger.info(f"[COPY] source={source}, resolved={source_path}")
        logger.info(f"[COPY] dest={dest}")
        logger.info(f"[COPY] source.exists={source_path.exists()}, source.is_dir={source_path.is_dir()}")
        logger.info(f"[COPY] same_path={source_path == dest}")

        # 检查源和目标是否相同
        if source_path == dest:
            logger.info(f"[COPY] 源和目标相同，跳过复制")
            return dest

        if dest.exists():
            shutil.rmtree(dest)

        if not source_path.exists():
            raise ValueError(f"插件路径不存在: {source}")

        # 检查源路径是否在目标目录内（避免复制到自身）
        try:
            source_path.relative_to(dest)
            logger.info(f"[COPY] 源路径在目标目录内，跳过复制")
            return dest
        except ValueError:
            pass  # 源不在目标内，正常复制

        if source_path.is_dir():
            shutil.copytree(source_path, dest)
        elif source_path.is_file():
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest / source_path.name)
        else:
            raise ValueError(f"插件路径既不是文件也不是目录: {source}")

        logger.info(f"插件文件复制完成: {dest}")
        return dest

    def _install_dependencies(self, dependencies: List[str]) -> Any:
        """安装插件依赖"""
        if not dependencies:
            return

        for dep in dependencies:
            try:
                subprocess.run(["pip", "install", dep, "-q"], capture_output=True, timeout=120, check=False)
                logger.info(f"依赖安装成功: {dep}")
            except Exception as e:
                logger.warning(f"依赖安装失败 {dep}: {e}")

    def _load_plugin_module(self, plugin_name: str) -> Any:
        """动态加载插件模块"""
        # 尝试多个入口文件
        entry_points = [
            self.plugins_dir / plugin_name / "src" / "main.py",
            self.plugins_dir / plugin_name / "src" / "__init__.py",
            self.plugins_dir / plugin_name / "main.py",
        ]

        for plugin_path in entry_points:
            if plugin_path.exists():
                spec = importlib.util.spec_from_file_location(f"fuxi_plugin_{plugin_name}", str(plugin_path))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module

        raise FileNotFoundError(f"插件入口文件不存在，已尝试: {entry_points}")

    def _register_routes(self, plugin_name: str, module, app) -> Any:
        """注册插件路由"""
        if hasattr(module, "register_routes"):
            module.register_routes(app)
            logger.info(f"插件 {plugin_name} 路由已注册")

    def _unregister_routes(self, plugin_name: str, app) -> Any:
        """移除插件路由"""
        prefix = f"/api/plugins/{plugin_name}"
        app.routes = [r for r in app.routes if not hasattr(r, "path") or not r.path.startswith(prefix)]
        logger.info(f"插件 {plugin_name} 路由已移除")

    def _rollback(self, backup_id: str, plugin_name: str) -> Any:
        """回滚到备份状态"""
        backup_path = self.backup_dir / backup_id

        try:
            # 恢复插件目录
            plugin_backup = backup_path / "plugin"
            plugin_dest = self.plugins_dir / plugin_name
            if plugin_backup.exists():
                if plugin_dest.exists():
                    shutil.rmtree(plugin_dest)
                shutil.copytree(plugin_backup, plugin_dest)

            # 恢复数据库
            db_backup = backup_path / "plugins.db"
            if db_backup.exists():
                shutil.copy2(db_backup, self.registry.db_path)

            logger.info(f"已回滚插件 {plugin_name} 到备份 {backup_id}")
        except Exception as e:
            logger.error(f"回滚失败: {e}")


# ============ 全局实例 ============
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager(app=None) -> PluginManager:
    """获取插件管理器全局实例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    if app is not None:
        _plugin_manager._app = app
    return _plugin_manager
