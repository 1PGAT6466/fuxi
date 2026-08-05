"""
伏羲插件全自动集成管线
Phase 3: 安装 → 分析 → 生成 → 验证 → 集成 → 激活，全流程自动化

作者: AI助手
日期: 2026-07-17
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """管线步骤"""

    name: str
    status: str = "pending"  # pending/running/done/failed/skipped
    duration_ms: int = 0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """管线执行结果"""

    plugin_name: str
    success: bool
    steps: List[PipelineStep] = field(default_factory=list)
    total_duration_ms: int = 0
    error: Optional[str] = None
    integration_id: Optional[str] = None


class PluginAutoPipeline:
    """插件全自动集成管线"""

    def __init__(self, fuxi_root: str = "."):
        self.fuxi_root = Path(fuxi_root)
        self._plugin_manager = None
        self._analyzer = None
        self._integrator = None
        self._sandbox = None
        self._auto_integrator = None

    # ============ 懒加载 ============

    @property
    def plugin_manager(self):
        if self._plugin_manager is None:
            from src.core.plugin_manager import get_plugin_manager

            self._plugin_manager = get_plugin_manager()
        return self._plugin_manager

    @property
    def analyzer(self):
        if self._analyzer is None:
            from src.core.plugin_analyzer import PluginAnalyzer

            self._analyzer = PluginAnalyzer(str(self.fuxi_root))
        return self._analyzer

    @property
    def integrator(self):
        if self._integrator is None:
            from src.core.plugin_integrator import PluginIntegrator

            self._integrator = PluginIntegrator(str(self.fuxi_root))
        return self._integrator

    @property
    def sandbox(self):
        if self._sandbox is None:
            from src.core.plugin_sandbox import PluginSandbox

            self._sandbox = PluginSandbox()
        return self._sandbox

    @property
    def auto_integrator(self):
        if self._auto_integrator is None:
            from src.core.plugin_auto_integrator import PluginAutoIntegrator

            self._auto_integrator = PluginAutoIntegrator(str(self.fuxi_root))
        return self._auto_integrator

    # ============ 公开接口 ============

    def run_full_pipeline(
        self, plugin_path: str, manifest: dict, skip_sandbox: bool = False, auto_confirm: bool = True
    ) -> PipelineResult:
        """
        运行完整集成管线

        流程:
        1. 验证 manifest
        2. 安装插件
        3. 沙箱验证（可选）
        4. 分析插件
        5. 生成集成代码
        6. 执行集成
        7. 激活插件
        8. 健康检查

        Args:
            plugin_path: 插件目录路径
            manifest: manifest.json 内容
            skip_sandbox: 是否跳过沙箱验证
            auto_confirm: 是否自动确认

        Returns:
            管线执行结果
        """
        import time

        start_time = time.time()

        result = PipelineResult(plugin_name=manifest.get("name", "unknown"), success=False)

        try:
            # Step 1: 验证 manifest
            step1 = self._step_validate_manifest(manifest)
            result.steps.append(step1)
            if step1.status == "failed":
                result.error = step1.error
                return result

            # Step 2: 安装插件
            step2 = self._step_install_plugin(plugin_path, manifest)
            result.steps.append(step2)
            if step2.status == "failed":
                result.error = step2.error
                return result

            # Step 3: 沙箱验证（可选）
            if not skip_sandbox:
                step3 = self._step_sandbox_validate(plugin_path, manifest)
                result.steps.append(step3)
                if step3.status == "failed":
                    # 沙箱失败则卸载插件
                    self.plugin_manager.uninstall(manifest["name"])
                    result.error = step3.error
                    return result
            else:
                result.steps.append(PipelineStep(name="沙箱验证", status="skipped", details={"reason": "已跳过"}))

            # Step 4: 分析插件
            step4 = self._step_analyze_plugin(plugin_path, manifest)
            result.steps.append(step4)
            if step4.status == "failed":
                result.error = step4.error
                return result

            # Step 5: 生成集成代码
            analysis_result = step4.details.get("analysis_result")
            step5 = self._step_generate_code(analysis_result, plugin_path)
            result.steps.append(step5)
            if step5.status == "failed":
                result.error = step5.error
                return result

            # Step 6: 执行集成
            codes = step5.details.get("codes", [])
            step6 = self._step_execute_integration(manifest["name"], plugin_path, codes, auto_confirm)
            result.steps.append(step6)
            if step6.status == "failed":
                result.error = step6.error
                return result

            # Step 7: 激活插件
            step7 = self._step_activate_plugin(manifest["name"])
            result.steps.append(step7)
            if step7.status == "failed":
                result.error = step7.error
                return result

            # Step 8: 健康检查
            step8 = self._step_health_check(manifest["name"])
            result.steps.append(step8)

            # 判断整体结果
            failed_steps = [s for s in result.steps if s.status == "failed"]
            result.success = len(failed_steps) == 0
            result.integration_id = step6.details.get("backup_id")

        except Exception as e:
            result.error = str(e)
            logger.error(f"管线执行失败: {e}", exc_info=True)

        finally:
            result.total_duration_ms = int((time.time() - start_time) * 1000)

        return result

    # ============ 管线步骤 ============

    def _step_validate_manifest(self, manifest: dict) -> PipelineStep:
        """Step 1: 验证 manifest"""
        step = PipelineStep(name="验证 manifest")

        try:
            required = ["name", "version", "type"]
            for field in required:
                if field not in manifest:
                    raise ValueError(f"缺少必填字段: {field}")

            # 验证版本格式
            import re

            if not re.match(r"^\d+\.\d+\.\d+", manifest.get("version", "")):
                raise ValueError(f"版本号格式错误: {manifest.get('version')}")

            step.status = "done"
            step.details = {"manifest": manifest}

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_install_plugin(self, plugin_path: str, manifest: dict) -> PipelineStep:
        """Step 2: 安装插件"""
        step = PipelineStep(name="安装插件")

        try:
            result = self.plugin_manager.install(plugin_path, manifest)

            if result["success"]:
                step.status = "done"
                step.details = result
            else:
                # 如果已安装，尝试继续
                if "已安装" in str(result.get("error", "")):
                    step.status = "done"
                    step.details = {"note": "插件已安装，继续后续步骤"}
                else:
                    step.status = "failed"
                    step.error = result.get("error", "安装失败")

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_sandbox_validate(self, plugin_path: str, manifest: dict) -> PipelineStep:
        """Step 3: 沙箱验证"""
        step = PipelineStep(name="沙箱验证")

        try:
            result = self.sandbox.validate(plugin_path, manifest)

            if result.passed:
                step.status = "done"
                step.details = {
                    "security_issues": len(result.security_issues),
                    "performance_issues": len(result.performance_issues),
                }
            else:
                step.status = "failed"
                step.error = f"安全问题: {len(result.security_issues)}, 错误: {len(result.errors)}"

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_analyze_plugin(self, plugin_path: str, manifest: dict) -> PipelineStep:
        """Step 4: 分析插件"""
        step = PipelineStep(name="分析插件")

        try:
            analysis = self.analyzer.analyze_plugin(plugin_path, manifest)

            step.status = "done"
            step.details = {
                "analysis_result": analysis,
                "symbols_count": len(analysis.symbols),
                "integration_points": len(analysis.integration_points),
                "conflicts": len(analysis.conflicts),
                "complexity_score": analysis.complexity_score,
                "risk_level": analysis.risk_level,
            }

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_generate_code(self, analysis_result: Any, plugin_path: str) -> PipelineStep:
        """Step 5: 生成集成代码"""
        step = PipelineStep(name="生成集成代码")

        try:
            plan = self.integrator.generate_integration_plan(analysis_result)
            codes = self.integrator.generate_integration_code(plan, plugin_path)

            codes_dict = [
                {
                    "file_path": c.file_path,
                    "content": c.content,
                    "action": c.action,
                    "description": c.description,
                    "requires_confirmation": c.requires_confirmation,
                }
                for c in codes
            ]

            step.status = "done"
            step.details = {"codes": codes_dict, "plan_steps": len(plan.steps), "estimated_time": plan.estimated_time}

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_execute_integration(
        self, plugin_name: str, plugin_path: str, codes: List[Dict[str, Any]], auto_confirm: bool
    ) -> PipelineStep:
        """Step 6: 执行集成"""
        step = PipelineStep(name="执行集成")

        try:
            result = self.auto_integrator.execute_integration(
                plugin_name=plugin_name, plugin_path=plugin_path, codes=codes, auto_confirm=auto_confirm
            )

            if result.success:
                step.status = "done"
                step.details = {
                    "backup_id": result.backup_id,
                    "steps_completed": result.steps_completed,
                    "steps_failed": result.steps_failed,
                    "steps_skipped": result.steps_skipped,
                }
            else:
                step.status = "failed"
                step.error = result.error or f"失败步骤: {result.steps_failed}"

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_activate_plugin(self, plugin_name: str) -> PipelineStep:
        """Step 7: 激活插件"""
        step = PipelineStep(name="激活插件")

        try:
            result = self.plugin_manager.activate(plugin_name)

            if result["success"]:
                step.status = "done"
            else:
                # 如果已激活，继续
                if "已激活" in str(result.get("error", "")):
                    step.status = "done"
                else:
                    step.status = "failed"
                    step.error = result.get("error", "激活失败")

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step

    def _step_health_check(self, plugin_name: str) -> PipelineStep:
        """Step 8: 健康检查"""
        step = PipelineStep(name="健康检查")

        try:
            result = self.plugin_manager.health_check(plugin_name)

            if result.get("status") == "ok":
                step.status = "done"
                step.details = result
            else:
                step.status = "failed"
                step.error = f"健康检查状态: {result.get('status')}"

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step


def generate_pipeline_report(result: PipelineResult) -> str:
    """生成管线执行报告"""
    status_icon = "✅" if result.success else "❌"

    report = f"""
## 插件全自动集成报告

**插件名称**: {result.plugin_name}
**执行结果**: {status_icon} {'成功' if result.success else '失败'}
**总耗时**: {result.total_duration_ms}ms
**集成ID**: {result.integration_id or '无'}

### 执行步骤

"""
    for i, step in enumerate(result.steps, 1):
        icon = {"done": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⏳", "running": "🔄"}.get(step.status, "❓")

        duration = f" ({step.duration_ms}ms)" if step.duration_ms > 0 else ""
        report += f"{i}. {icon} {step.name}{duration}\n"

        if step.error:
            report += f"   错误: {step.error}\n"

    if result.error:
        report += f"\n### 错误信息\n\n{result.error}\n"

    return report
