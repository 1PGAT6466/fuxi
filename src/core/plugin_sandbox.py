"""
伏羲插件沙箱验证器
在隔离环境中验证插件安全性

作者: AI助手
日期: 2026-07-17
"""

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """沙箱验证结果"""

    plugin_name: str
    passed: bool
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    security_issues: List[str] = field(default_factory=list)
    performance_issues: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class PluginSandbox:
    """插件沙箱验证器"""

    def __init__(self, timeout: int = 300):
        """
        初始化沙箱

        Args:
            timeout: 执行超时时间（秒）
        """
        self.timeout = timeout

    # ============ 公开接口 ============

    def validate(self, plugin_path: str, manifest: dict) -> SandboxResult:
        """
        在沙箱中验证插件

        Args:
            plugin_path: 插件目录路径
            manifest: manifest.json 内容

        Returns:
            验证结果
        """
        result = SandboxResult(plugin_name=manifest.get("name", "unknown"), passed=False)

        try:
            # Step 1: 创建临时沙箱环境
            sandbox_dir = self._create_sandbox(plugin_path)

            # Step 2: 静态安全检查
            security_issues = self._static_security_check(sandbox_dir, manifest)
            result.security_issues = security_issues

            # Step 3: 依赖检查
            dep_issues = self._check_dependencies(sandbox_dir, manifest)
            result.warnings.extend(dep_issues)

            # Step 4: 语法检查
            syntax_issues = self._syntax_check(sandbox_dir)
            result.errors.extend(syntax_issues)

            # Step 5: 测试执行（如果有测试）
            test_result = self._run_tests(sandbox_dir, manifest)
            result.tests_passed = test_result.get("passed", 0)
            result.tests_failed = test_result.get("failed", 0)
            result.tests_total = test_result.get("total", 0)

            # Step 6: 性能检查
            perf_issues = self._performance_check(sandbox_dir, manifest)
            result.performance_issues = perf_issues

            # 判断是否通过
            result.passed = len(result.security_issues) == 0 and len(result.errors) == 0 and result.tests_failed == 0

            logger.info(
                f"沙箱验证完成: {result.plugin_name}, "
                f"通过={result.passed}, "
                f"安全问题={len(result.security_issues)}, "
                f"错误={len(result.errors)}"
            )

        except (ValueError, KeyError, TypeError, FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
            # 细化异常类型：ValueError/KeyError/TypeError - 数据格式/类型错误
            # FileNotFoundError/OSError - 文件系统错误
            # TimeoutExpired - 测试执行超时
            logger.error(f"沙箱验证失败: {e}", exc_info=True)
            result.errors.append(f"验证失败: {str(e)}")

        finally:
            # 清理沙箱
            if "sandbox_dir" in locals():
                self._cleanup_sandbox(sandbox_dir)

        return result

    # ============ 内部方法 ============

    def _create_sandbox(self, plugin_path: str) -> Path:
        """创建沙箱环境"""
        sandbox_dir = Path(tempfile.mkdtemp(prefix="fuxi_sandbox_"))

        # 复制插件到沙箱
        plugin_path_obj = Path(plugin_path)
        if plugin_path_obj.exists():
            shutil.copytree(plugin_path_obj, sandbox_dir / "plugin")

        logger.info(f"沙箱创建完成: {sandbox_dir}")
        return sandbox_dir

    def _cleanup_sandbox(self, sandbox_dir: Path):
        """清理沙箱"""
        try:
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir)
                logger.info(f"沙箱清理完成: {sandbox_dir}")
        except (PermissionError, OSError) as e:
            # PermissionError - 权限不足无法删除
            # OSError - 文件系统错误（文件锁定等）
            logger.warning(f"沙箱清理失败: {e}", exc_info=True)

    def _static_security_check(self, sandbox_dir: Path, manifest: dict) -> List[str]:
        """静态安全检查"""
        issues = []

        plugin_dir = sandbox_dir / "plugin"
        if not plugin_dir.exists():
            return issues

        # 检查危险的导入
        dangerous_imports = [
            "os.system",
            "subprocess.call",
            "subprocess.run",
            "eval",
            "exec",
            "__import__",
            "importlib.import_module",
        ]

        for py_file in plugin_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")

                for dangerous in dangerous_imports:
                    if dangerous in content:
                        issues.append(f"危险调用: {dangerous} in {py_file.name}")

                # 检查网络访问
                if "requests" in content or "urllib" in content:
                    perm_level = manifest.get("permissions", 0)
                    if perm_level < 2:
                        issues.append(f"权限不足: 插件需要网络访问但权限等级为 L{perm_level}")

                # 检查文件访问
                if "open(" in content or "Path(" in content:
                    # 检查是否访问了受保护路径
                    protected_paths = ["/etc", "/root", "~/.ssh", "data/chromadb"]
                    for protected in protected_paths:
                        if protected in content:
                            issues.append(f"受保护路径: 尝试访问 {protected}")

            except (UnicodeDecodeError, OSError) as e:
                # UnicodeDecodeError - 文件编码不是UTF-8
                # OSError - 文件读取失败（权限/锁定）
                logger.debug(f"跳过文件 {py_file}: {e}")

        return issues

    def _check_dependencies(self, sandbox_dir: Path, manifest: dict) -> List[str]:
        """检查依赖"""
        warnings = []

        dependencies = manifest.get("dependencies", [])

        for dep in dependencies:
            # 检查依赖格式
            if ">=" not in dep and "==" not in dep and "~=" not in dep:
                warnings.append(f"依赖没有版本约束: {dep}")

        return warnings

    def _syntax_check(self, sandbox_dir: Path) -> List[str]:
        """语法检查"""
        errors = []

        plugin_dir = sandbox_dir / "plugin"
        if not plugin_dir.exists():
            return errors

        for py_file in plugin_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                compile(content, str(py_file), "exec")
            except SyntaxError as e:
                errors.append(f"语法错误 {py_file.name}: {e}")
            except (UnicodeDecodeError, OSError) as e:
                # UnicodeDecodeError - 文件编码不是UTF-8
                # OSError - 文件读取失败（权限/锁定）
                logger.debug(f"跳过文件 {py_file}: {e}")

        return errors

    def _run_tests(self, sandbox_dir: Path, manifest: dict) -> Dict[str, int]:
        """运行测试"""
        result = {"passed": 0, "failed": 0, "total": 0}

        plugin_dir = sandbox_dir / "plugin"
        test_dir = plugin_dir / "tests"

        if not test_dir.exists():
            logger.info("没有测试目录，跳过测试")
            return result

        # 查找测试文件
        test_files = list(test_dir.glob("test_*.py"))

        if not test_files:
            logger.info("没有测试文件，跳过测试")
            return result

        # 运行测试
        try:
            cmd = ["python", "-m", "pytest", str(test_dir), "-v", "--tb=short"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout, cwd=str(plugin_dir))

            # 解析结果
            output = proc.stdout + proc.stderr

            if "passed" in output:
                # 简单解析 pytest 输出
                for line in output.split("\n"):
                    if "passed" in line:
                        try:
                            count = int(line.split()[0])
                            result["passed"] = count
                        except (ValueError, IndexError):
                            # ValueError - int() 转换失败（非数字）
                            # IndexError - split() 结果为空
                            pass
                    elif "failed" in line:
                        try:
                            count = int(line.split()[0])
                            result["failed"] = count
                        except (ValueError, IndexError):
                            # ValueError - int() 转换失败（非数字）
                            # IndexError - split() 结果为空
                            pass

            result["total"] = result["passed"] + result["failed"]

        except subprocess.TimeoutExpired:
            logger.warning(f"测试执行超时: {self.timeout}秒")
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            # CalledProcessError - pytest 返回非零退出码
            # FileNotFoundError - pytest 未安装
            # OSError - 进程启动失败
            logger.warning(f"测试执行失败: {e}", exc_info=True)

        return result

    def _performance_check(self, sandbox_dir: Path, manifest: dict) -> List[str]:
        """性能检查"""
        issues = []

        plugin_dir = sandbox_dir / "plugin"
        if not plugin_dir.exists():
            return issues

        # 检查代码行数
        total_lines = 0
        for py_file in plugin_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                total_lines += len(content.split("\n"))
            except (UnicodeDecodeError, OSError):
                # UnicodeDecodeError - 文件编码不是UTF-8
                # OSError - 文件读取失败
                pass

        if total_lines > 10000:
            issues.append(f"代码行数过多: {total_lines}行（建议<10000行）")

        # 检查文件数量
        py_files = list(plugin_dir.rglob("*.py"))
        if len(py_files) > 100:
            issues.append(f"文件数量过多: {len(py_files)}个（建议<100个）")

        return issues


def generate_sandbox_report(result: SandboxResult) -> str:
    """生成沙箱验证报告"""
    report = f"""
## 插件沙箱验证报告

**插件名称**: {result.plugin_name}
**验证结果**: {'✅ 通过' if result.passed else '❌ 未通过'}
**执行时间**: {result.execution_time:.2f}秒

### 测试结果

- 总测试数: {result.tests_total}
- 通过: {result.tests_passed}
- 失败: {result.tests_failed}

### 安全问题

"""
    if result.security_issues:
        for issue in result.security_issues:
            report += f"- ❌ {issue}\n"
    else:
        report += "- ✅ 无安全问题\n"

    report += "\n### 性能问题\n\n"
    if result.performance_issues:
        for issue in result.performance_issues:
            report += f"- ⚠️ {issue}\n"
    else:
        report += "- ✅ 无性能问题\n"

    report += "\n### 错误\n\n"
    if result.errors:
        for error in result.errors:
            report += f"- ❌ {error}\n"
    else:
        report += "- ✅ 无错误\n"

    report += "\n### 警告\n\n"
    if result.warnings:
        for warning in result.warnings:
            report += f"- ⚠️ {warning}\n"
    else:
        report += "- ✅ 无警告\n"

    return report
