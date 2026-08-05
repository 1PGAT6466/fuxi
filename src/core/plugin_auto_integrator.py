"""
伏羲插件自动集成执行器
Phase 2: 根据集成计划自动执行代码修改

作者: AI助手
日期: 2026-07-17
"""

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IntegrationStep:
    """集成步骤"""

    name: str
    description: str
    action: str  # create/modify/delete/register
    target_file: str
    content: Optional[str] = None
    status: str = "pending"  # pending/running/done/failed/skipped
    error: Optional[str] = None
    requires_confirmation: bool = False


@dataclass
class IntegrationResult:
    """集成结果"""

    plugin_name: str
    success: bool
    steps_total: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    steps: List[IntegrationStep] = field(default_factory=list)
    backup_id: Optional[str] = None
    error: Optional[str] = None


class PluginAutoIntegrator:
    """插件自动集成执行器"""

    def __init__(self, fuxi_root: str = ".", backup_dir: str = ".fuxi/backups"):
        self.fuxi_root = Path(fuxi_root)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ============ 公开接口 ============

    def execute_integration(
        self, plugin_name: str, plugin_path: str, codes: List[Dict[str, Any]], auto_confirm: bool = False
    ) -> IntegrationResult:
        """
        执行集成

        Args:
            plugin_name: 插件名称
            plugin_path: 插件路径
            codes: 生成的代码列表
            auto_confirm: 是否自动确认（跳过需要确认的步骤）

        Returns:
            集成结果
        """
        result = IntegrationResult(plugin_name=plugin_name, success=False, steps_total=len(codes))

        try:
            # Step 1: 创建备份
            backup_id = self._create_backup(plugin_name)
            result.backup_id = backup_id

            # Step 2: 执行每个步骤
            for code in codes:
                step = IntegrationStep(
                    name=code.get("description", "未知操作"),
                    description=code.get("description", ""),
                    action=code.get("action", "create"),
                    target_file=code.get("file_path", ""),
                    content=code.get("content", ""),
                    requires_confirmation=code.get("requires_confirmation", False),
                )

                # 检查是否需要确认
                if step.requires_confirmation and not auto_confirm:
                    step.status = "skipped"
                    step.error = "需要人工确认"
                    result.steps_skipped += 1
                    result.steps.append(step)
                    continue

                # 执行步骤
                try:
                    self._execute_step(step)
                    step.status = "done"
                    result.steps_completed += 1
                except Exception as e:
                    step.status = "failed"
                    step.error = str(e)
                    result.steps_failed += 1
                    logger.error(f"步骤失败: {step.name} - {e}")

                result.steps.append(step)

            # Step 3: 判断整体结果
            result.success = result.steps_failed == 0

            logger.info(
                f"集成执行完成: {plugin_name}, "
                f"成功={result.steps_completed}, "
                f"失败={result.steps_failed}, "
                f"跳过={result.steps_skipped}"
            )

        except Exception as e:
            result.error = str(e)
            logger.error(f"集成执行失败: {e}")

            # 尝试回滚
            if result.backup_id:
                self._rollback(result.backup_id, plugin_name)

        return result

    def rollback(self, backup_id: str, plugin_name: str) -> bool:
        """
        回滚到备份状态

        Args:
            backup_id: 备份ID
            plugin_name: 插件名称

        Returns:
            是否成功
        """
        try:
            self._rollback(backup_id, plugin_name)
            return True
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            return False

    # ============ 内部方法 ============

    def _create_backup(self, plugin_name: str) -> str:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{plugin_name}_{timestamp}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # 备份关键目录
        dirs_to_backup = ["src/api", "src/core", "src/services"]
        for dir_name in dirs_to_backup:
            src = self.fuxi_root / dir_name
            if src.exists():
                dst = backup_path / dir_name
                dst.mkdir(parents=True, exist_ok=True)
                for py_file in src.glob("*.py"):
                    shutil.copy2(py_file, dst / py_file.name)

        logger.info(f"备份创建成功: {backup_id}")
        return backup_id

    def _execute_step(self, step: IntegrationStep):
        """执行单个步骤"""
        action = step.action
        target = step.target_file

        if action == "create":
            self._create_file(target, step.content)
        elif action == "modify":
            self._modify_file(target, step.content)
        elif action == "delete":
            self._delete_file(target)
        elif action == "register":
            self._register_component(target, step.content)
        else:
            raise ValueError(f"未知操作: {action}")

    def _create_file(self, file_path: str, content: str):
        """创建文件"""
        path = self.fuxi_root / file_path

        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        # 检查文件是否已存在
        if path.exists():
            # 备份现有文件
            backup_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup_path)
            logger.info(f"现有文件已备份: {backup_path}")

        # 写入新文件
        path.write_text(content, encoding="utf-8")
        logger.info(f"文件创建成功: {path}")

    def _modify_file(self, file_path: str, content: str):
        """修改文件"""
        path = self.fuxi_root / file_path

        if not path.exists():
            # 如果文件不存在，创建新文件
            self._create_file(file_path, content)
            return

        # 备份现有文件
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)

        # 写入修改后的内容
        path.write_text(content, encoding="utf-8")
        logger.info(f"文件修改成功: {path}")

    def _delete_file(self, file_path: str):
        """删除文件"""
        path = self.fuxi_root / file_path

        if not path.exists():
            logger.warning(f"文件不存在，跳过删除: {path}")
            return

        # 备份现有文件
        backup_path = path.with_suffix(path.suffix + ".deleted")
        shutil.copy2(path, backup_path)

        # 删除文件
        path.unlink()
        logger.info(f"文件删除成功: {path}")

    def _register_component(self, target: str, content: str):
        """注册组件到 routes.py 或其他配置文件"""
        # 解析目标文件
        if "routes.py" in target:
            self._register_to_routes(target, content)
        else:
            # 默认创建新文件
            self._create_file(target, content)

    def _register_to_routes(self, routes_file: str, content: str):
        """注册路由到 routes.py"""
        path = self.fuxi_root / routes_file

        if not path.exists():
            logger.warning(f"路由文件不存在: {path}")
            self._create_file(routes_file, content)
            return

        # 读取现有内容
        existing = path.read_text(encoding="utf-8")

        # 检查是否已注册
        if content.strip() in existing:
            logger.info(f"路由已存在，跳过注册")
            return

        # 备份
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)

        # 在文件末尾添加新路由
        new_content = existing.rstrip() + "\n\n" + content
        path.write_text(new_content, encoding="utf-8")
        logger.info(f"路由注册成功: {path}")

    def _rollback(self, backup_id: str, plugin_name: str):
        """回滚到备份状态"""
        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            raise FileNotFoundError(f"备份不存在: {backup_id}")

        # 恢复备份的目录
        for dir_name in ["src/api", "src/core", "src/services"]:
            src = backup_path / dir_name
            dst = self.fuxi_root / dir_name

            if src.exists():
                for py_file in src.glob("*.py"):
                    shutil.copy2(py_file, dst / py_file.name)

        logger.info(f"回滚完成: {backup_id}")


def generate_integration_report(result: IntegrationResult) -> str:
    """生成集成报告"""
    report = f"""
## 插件集成执行报告

**插件名称**: {result.plugin_name}
**执行结果**: {'✅ 成功' if result.success else '❌ 失败'}
**备份ID**: {result.backup_id or '无'}

### 执行统计

- 总步骤数: {result.steps_total}
- 完成: {result.steps_completed}
- 失败: {result.steps_failed}
- 跳过: {result.steps_skipped}

### 执行详情

"""
    for i, step in enumerate(result.steps, 1):
        status_icon = {"done": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⏳", "running": "🔄"}.get(
            step.status, "❓"
        )

        report += f"{i}. {status_icon} {step.name}\n"
        report += f"   文件: {step.target_file}\n"
        if step.error:
            report += f"   错误: {step.error}\n"

    if result.error:
        report += f"\n### 错误信息\n\n{result.error}\n"

    return report
