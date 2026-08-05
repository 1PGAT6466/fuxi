"""
伏羲插件分析器
分析插件代码，识别集成点，生成集成方案

核心能力：
1. AST 解析：解析 Python 代码结构
2. 依赖分析：识别插件依赖的模块和函数
3. 集成点识别：找到插件与伏羲核心的交互点
4. 冲突检测：检查插件是否与现有代码冲突
5. 集成方案生成：输出可执行的集成方案

作者: AI助手
日期: 2026-07-17
"""

import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CodeSymbol:
    """代码符号（类/函数/变量）"""

    name: str
    type: str  # class/function/variable
    file_path: str
    line_number: int
    docstring: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)


@dataclass
class IntegrationPoint:
    """集成点"""

    type: str  # route/event/hook/service/config
    name: str
    description: str
    file_path: str
    line_number: int
    confidence: float  # 0-1，置信度
    action: str  # register/inject/modify/extend
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictInfo:
    """冲突信息"""

    type: str  # route/name/dependency/resource
    severity: str  # low/medium/high/critical
    description: str
    existing: str
    new: str
    resolution: str  # skip/replace/merge/ask


@dataclass
class AnalysisResult:
    """分析结果"""

    plugin_name: str
    plugin_type: str
    symbols: List[CodeSymbol] = field(default_factory=list)
    integration_points: List[IntegrationPoint] = field(default_factory=list)
    conflicts: List[ConflictInfo] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    complexity_score: float = 0.0  # 0-10
    risk_level: str = "low"  # low/medium/high/critical
    recommendations: List[str] = field(default_factory=list)


class PluginAnalyzer:
    """插件分析器"""

    def __init__(self, fuxi_root: str = "."):
        self.fuxi_root = Path(fuxi_root)
        self._fuxi_symbols: Dict[str, CodeSymbol] = {}
        self._fuxi_routes: List[Dict[str, Any]] = []
        self._fuxi_hooks: List[str] = []
        self._fuxi_events: List[str] = []

    # ============ 公开接口 ============

    def analyze_plugin(self, plugin_path: str, manifest: dict) -> AnalysisResult:
        """
        分析插件

        Args:
            plugin_path: 插件目录路径
            manifest: manifest.json 内容

        Returns:
            分析结果
        """
        result = AnalysisResult(
            plugin_name=manifest.get("name", "unknown"), plugin_type=manifest.get("type", "unknown")
        )

        try:
            # Step 1: 扫描伏羲核心代码（如果还没扫描）
            if not self._fuxi_symbols:
                self._scan_fuxi_core()

            # Step 2: 解析插件代码
            plugin_path_obj = Path(plugin_path)
            if not plugin_path_obj.exists():
                raise FileNotFoundError(f"插件路径不存在: {plugin_path}")

            # Step 3: AST 解析插件代码
            for py_file in plugin_path_obj.rglob("*.py"):
                symbols = self._parse_python_file(py_file)
                result.symbols.extend(symbols)

            # Step 4: 识别集成点
            result.integration_points = self._identify_integration_points(result.symbols, manifest)

            # Step 5: 检测冲突
            result.conflicts = self._detect_conflicts(result.symbols, manifest)

            # Step 6: 分析依赖
            result.dependencies = self._analyze_dependencies(result.symbols)

            # Step 7: 分析导出
            result.exports = self._analyze_exports(result.symbols)

            # Step 8: 计算复杂度
            result.complexity_score = self._calculate_complexity(result.symbols)

            # Step 9: 评估风险
            result.risk_level = self._assess_risk(result)

            # Step 10: 生成建议
            result.recommendations = self._generate_recommendations(result)

            logger.info(
                f"插件分析完成: {result.plugin_name}, "
                f"符号={len(result.symbols)}, "
                f"集成点={len(result.integration_points)}, "
                f"冲突={len(result.conflicts)}"
            )

        except (SyntaxError, FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as e:
            # SyntaxError - 代码语法错误
            # FileNotFoundError - 插件路径或文件不存在
            # JSONDecodeError - manifest.json 解析失败
            # OSError - 文件读取失败
            # ValueError - 数据格式错误
            logger.error(f"插件分析失败: {e}", exc_info=True)
            result.risk_level = "critical"
            result.recommendations.append(f"分析失败: {str(e)}")

        return result

    # ============ 内部方法 ============

    def _scan_fuxi_core(self):
        """扫描伏羲核心代码，建立符号索引"""
        logger.info("扫描伏羲核心代码...")

        # 扫描 src/ 目录
        src_dir = self.fuxi_root / "src"
        if not src_dir.exists():
            logger.warning(f"源码目录不存在: {src_dir}")
            return

        for py_file in src_dir.rglob("*.py"):
            try:
                symbols = self._parse_python_file(py_file)
                for sym in symbols:
                    key = f"{sym.file_path}:{sym.name}"
                    self._fuxi_symbols[key] = sym
            except (SyntaxError, UnicodeDecodeError, OSError) as e:
                # SyntaxError - 代码语法错误
                # UnicodeDecodeError - 文件编码问题
                # OSError - 文件读取失败
                logger.debug(f"跳过文件 {py_file}: {e}")

        logger.info(f"伏羲核心扫描完成，共 {len(self._fuxi_symbols)} 个符号")

    def _parse_python_file(self, file_path: Path) -> List[CodeSymbol]:
        """解析 Python 文件，提取符号"""
        symbols = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append(
                        CodeSymbol(
                            name=node.name,
                            type="class",
                            file_path=str(file_path),
                            line_number=node.lineno,
                            docstring=ast.get_docstring(node),
                        )
                    )

                elif isinstance(node, ast.FunctionDef):
                    symbols.append(
                        CodeSymbol(
                            name=node.name,
                            type="function",
                            file_path=str(file_path),
                            line_number=node.lineno,
                            docstring=ast.get_docstring(node),
                        )
                    )

                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            symbols.append(
                                CodeSymbol(
                                    name=target.id, type="variable", file_path=str(file_path), line_number=node.lineno
                                )
                            )

        except SyntaxError as e:
            logger.warning(f"语法错误 {file_path}: {e}")
        except (UnicodeDecodeError, OSError, RecursionError) as e:
            # UnicodeDecodeError - 文件编码不是UTF-8
            # OSError - 文件读取失败
            # RecursionError - AST 递归深度超出
            logger.debug(f"解析失败 {file_path}: {e}")

        return symbols

    def _identify_integration_points(self, symbols: List[CodeSymbol], manifest: dict) -> List[IntegrationPoint]:
        """识别集成点"""
        points = []

        plugin_type = manifest.get("type", "")

        # 读取源文件内容用于深度分析
        source_contents = {}
        for sym in symbols:
            if sym.file_path not in source_contents:
                try:
                    source_contents[sym.file_path] = Path(sym.file_path).read_text(encoding="utf-8")
                except (UnicodeDecodeError, FileNotFoundError, OSError):
                    # UnicodeDecodeError - 文件编码不是UTF-8
                    # FileNotFoundError - 文件已被删除
                    # OSError - 文件读取权限问题
                    pass

        # 根据插件类型识别集成点
        if plugin_type == "api":
            # 查找路由定义：APIRouter、FastAPI、app.get/post/put/delete
            for sym in symbols:
                # 查找继承自APIPlugin的类
                if sym.type == "class" and any(
                    keyword in sym.name for keyword in ["API", "Router", "Route", "Endpoint"]
                ):
                    points.append(
                        IntegrationPoint(
                            type="route",
                            name=sym.name,
                            description=f"API路由类: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.85,
                            action="register",
                            details={"class_name": sym.name},
                        )
                    )

                # 查找有装饰器的函数（@router.get/post/put/delete）
                if sym.type == "function" and sym.docstring and "route" in sym.docstring.lower():
                    points.append(
                        IntegrationPoint(
                            type="route",
                            name=sym.name,
                            description=f"路由处理函数: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.75,
                            action="register",
                            details={"handler": sym.name},
                        )
                    )

        elif plugin_type == "service":
            # 查找服务类
            for sym in symbols:
                if sym.type == "class" and any(
                    keyword in sym.name for keyword in ["Service", "Worker", "Task", "Scheduler", "Monitor"]
                ):
                    points.append(
                        IntegrationPoint(
                            type="service",
                            name=sym.name,
                            description=f"后台服务: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.8,
                            action="inject",
                            details={"class_name": sym.name},
                        )
                    )

                # 查找后台任务函数
                if sym.type == "function" and any(
                    keyword in sym.name for keyword in ["background", "async", "periodic", "schedule"]
                ):
                    points.append(
                        IntegrationPoint(
                            type="service",
                            name=sym.name,
                            description=f"后台任务: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.7,
                            action="register",
                            details={"function_name": sym.name},
                        )
                    )

        elif plugin_type == "llm":
            # 查找 LLM 提供者
            for sym in symbols:
                if sym.type == "class" and any(
                    keyword in sym.name for keyword in ["LLM", "Provider", "Model", "Chat", "Embedding"]
                ):
                    points.append(
                        IntegrationPoint(
                            type="llm_provider",
                            name=sym.name,
                            description=f"LLM提供者: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.85,
                            action="register",
                            details={"class_name": sym.name},
                        )
                    )

        elif plugin_type == "storage":
            # 查找存储提供者
            for sym in symbols:
                if sym.type == "class" and any(
                    keyword in sym.name for keyword in ["Storage", "Backend", "Store", "Database", "VectorDB"]
                ):
                    points.append(
                        IntegrationPoint(
                            type="storage",
                            name=sym.name,
                            description=f"存储提供者: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.85,
                            action="register",
                            details={"class_name": sym.name},
                        )
                    )

        elif plugin_type == "ui":
            # 查找 UI 组件
            for sym in symbols:
                if sym.type == "class" and any(
                    keyword in sym.name for keyword in ["Component", "View", "Page", "Widget"]
                ):
                    points.append(
                        IntegrationPoint(
                            type="ui_component",
                            name=sym.name,
                            description=f"UI组件: {sym.name}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.8,
                            action="register",
                            details={"class_name": sym.name},
                        )
                    )

        # 通用：查找事件处理器
        for sym in symbols:
            if sym.type == "function" and sym.name.startswith("on_"):
                event_type = sym.name[3:]  # 去掉 "on_" 前缀
                # 与 FuxiPlugin 基类的方法区分
                if event_type not in ["install", "activate", "deactivate", "uninstall"]:
                    points.append(
                        IntegrationPoint(
                            type="event",
                            name=sym.name,
                            description=f"事件处理器: {event_type}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.7,
                            action="register",
                            details={"event_type": event_type},
                        )
                    )

        # 通用：查找钩子实现
        # 与 plugin_hooks.py 中的 valid_hooks 保持一致
        valid_hooks = [
            "pre_install",
            "post_install",
            "pre_activate",
            "post_activate",
            "pre_deactivate",
            "post_deactivate",
            "pre_uninstall",
            "post_uninstall",
        ]
        for sym in symbols:
            if sym.type == "function" and sym.name in valid_hooks:
                points.append(
                    IntegrationPoint(
                        type="hook",
                        name=sym.name,
                        description=f"生命周期钩子: {sym.name}",
                        file_path=sym.file_path,
                        line_number=sym.line_number,
                        confidence=0.95,
                        action="register",
                        details={"hook_name": sym.name},
                    )
                )

        # 通用：查找 register_routes 函数
        for sym in symbols:
            if sym.type == "function" and sym.name == "register_routes":
                points.append(
                    IntegrationPoint(
                        type="route",
                        name=sym.name,
                        description=f"路由注册函数: {sym.name}",
                        file_path=sym.file_path,
                        line_number=sym.line_number,
                        confidence=0.9,
                        action="register",
                        details={"handler": sym.name},
                    )
                )

        # 通用：查找 health_check 函数
        for sym in symbols:
            if sym.type == "function" and sym.name == "health_check":
                points.append(
                    IntegrationPoint(
                        type="health",
                        name=sym.name,
                        description=f"健康检查函数: {sym.name}",
                        file_path=sym.file_path,
                        line_number=sym.line_number,
                        confidence=0.85,
                        action="register",
                        details={"handler": sym.name},
                    )
                )

        # 通用：查找配置类/函数
        for sym in symbols:
            if sym.type == "class" and any(keyword in sym.name for keyword in ["Config", "Settings", "Configuration"]):
                points.append(
                    IntegrationPoint(
                        type="config",
                        name=sym.name,
                        description=f"配置类: {sym.name}",
                        file_path=sym.file_path,
                        line_number=sym.line_number,
                        confidence=0.7,
                        action="inject",
                        details={"class_name": sym.name},
                    )
                )

        # 通用：从 manifest 路由声明中识别集成点
        manifest_routes = manifest.get("routes", [])
        for route in manifest_routes:
            route_path = route.get("path", "/")
            route_method = route.get("method", "GET")
            handler_name = route.get("handler", "")

            # 查找对应的处理函数
            handler_found = False
            for sym in symbols:
                if sym.type == "function" and sym.name == handler_name:
                    points.append(
                        IntegrationPoint(
                            type="route",
                            name=handler_name,
                            description=f"路由处理: {route_method} {route_path}",
                            file_path=sym.file_path,
                            line_number=sym.line_number,
                            confidence=0.95,
                            action="register",
                            details={"method": route_method, "path": route_path, "handler": handler_name},
                        )
                    )
                    handler_found = True
                    break

            # 如果没找到处理函数，从 manifest 中创建
            if not handler_found and handler_name:
                points.append(
                    IntegrationPoint(
                        type="route",
                        name=handler_name,
                        description=f"路由处理: {route_method} {route_path} (需创建)",
                        file_path="",
                        line_number=0,
                        confidence=0.8,
                        action="create",
                        details={"method": route_method, "path": route_path, "handler": handler_name},
                    )
                )

        return points

    def _detect_conflicts(self, symbols: List[CodeSymbol], manifest: dict) -> List[ConflictInfo]:
        """检测冲突"""
        conflicts = []

        plugin_name = manifest.get("name", "")

        # 检查名称冲突
        for sym in symbols:
            # 使用完整路径作为key，避免误匹配
            key = f"src:{sym.name}"
            if key in self._fuxi_symbols:
                existing = self._fuxi_symbols[key]
                # 只有当类型相同时才认为是真正冲突
                if existing.type == sym.type:
                    conflicts.append(
                        ConflictInfo(
                            type="name",
                            severity="medium",
                            description=f"符号名冲突: {sym.name}",
                            existing=f"{existing.file_path}:{existing.line_number}",
                            new=f"{sym.file_path}:{sym.line_number}",
                            resolution="rename",
                        )
                    )

        # 检查路由冲突
        if manifest.get("type") == "api":
            for route in manifest.get("routes", []):
                route_path = route.get("path", "")
                full_path = f"/api/plugins/{plugin_name}{route_path}"
                # 检查是否与现有路由冲突
                for existing_route in self._fuxi_routes:
                    if existing_route.get("path") == full_path:
                        conflicts.append(
                            ConflictInfo(
                                type="route",
                                severity="high",
                                description=f"路由路径冲突: {full_path}",
                                existing=f"{existing_route.get('file', 'unknown')}:{existing_route.get('line', '?')}",
                                new=f"manifest.routes",
                                resolution="rename",
                            )
                        )

        return conflicts

    def _analyze_dependencies(self, symbols: List[CodeSymbol]) -> List[str]:
        """分析依赖"""
        deps = set()

        for sym in symbols:
            if sym.dependencies:
                deps.update(sym.dependencies)

        return sorted(list(deps))

    def _analyze_exports(self, symbols: List[CodeSymbol]) -> List[str]:
        """分析导出"""
        exports = []

        for sym in symbols:
            if sym.type in ["class", "function"]:
                exports.append(sym.name)

        return exports

    def _calculate_complexity(self, symbols: List[CodeSymbol]) -> float:
        """计算复杂度评分（0-10）"""
        if not symbols:
            return 0.0

        # 基于符号数量和类型计算
        class_count = sum(1 for s in symbols if s.type == "class")
        func_count = sum(1 for s in symbols if s.type == "function")
        var_count = sum(1 for s in symbols if s.type == "variable")

        # 加权计算
        score = class_count * 3 + func_count * 1 + var_count * 0.5

        # 归一化到 0-10
        return min(10.0, score / 10)

    def _assess_risk(self, result: AnalysisResult) -> str:
        """评估风险等级"""
        risk_score = 0

        # 冲突数量
        risk_score += len(result.conflicts) * 2

        # 复杂度
        risk_score += result.complexity_score

        # 集成点数量
        risk_score += len(result.integration_points) * 0.5

        # 权限等级（从manifest获取）
        # 权限等级越高，风险越大
        # L0: 0, L1: 2, L2: 4, L3: 6
        # TODO: 从manifest中读取权限等级

        if risk_score >= 15:
            return "critical"
        elif risk_score >= 10:
            return "high"
        elif risk_score >= 5:
            return "medium"
        else:
            return "low"

    def _generate_recommendations(self, result: AnalysisResult) -> List[str]:
        """生成建议"""
        recommendations = []

        if result.conflicts:
            recommendations.append(f"发现 {len(result.conflicts)} 个冲突，需要解决后再集成")

        if result.complexity_score > 7:
            recommendations.append("插件复杂度较高，建议分步集成")

        if result.risk_level in ["high", "critical"]:
            recommendations.append("风险等级较高，建议人工审查后再集成")

        if not result.integration_points:
            recommendations.append("未识别到集成点，可能是纯工具库插件")

        if result.integration_points:
            recommendations.append(f"识别到 {len(result.integration_points)} 个集成点，可自动集成")

        return recommendations


# ============ 工具函数 ============


def quick_analyze(plugin_path: str, fuxi_root: str = ".") -> AnalysisResult:
    """
    快速分析插件

    Args:
        plugin_path: 插件目录路径
        fuxi_root: 伏羲根目录

    Returns:
        分析结果
    """
    manifest_path = Path(plugin_path) / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json 不存在: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    analyzer = PluginAnalyzer(fuxi_root)
    return analyzer.analyze_plugin(plugin_path, manifest)


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python plugin_analyzer.py <插件目录> [伏羲根目录]")
        sys.exit(1)

    plugin_path = sys.argv[1]
    fuxi_root = sys.argv[2] if len(sys.argv) > 2 else "."

    logging.basicConfig(level=logging.INFO)

    try:
        result = quick_analyze(plugin_path, fuxi_root)

        print(f"\n{'='*50}")
        print(f"插件分析结果: {result.plugin_name}")
        print(f"{'='*50}")
        print(f"类型: {result.plugin_type}")
        print(f"符号数量: {len(result.symbols)}")
        print(f"集成点: {len(result.integration_points)}")
        print(f"冲突: {len(result.conflicts)}")
        print(f"复杂度: {result.complexity_score:.2f}/10")
        print(f"风险等级: {result.risk_level}")

        if result.integration_points:
            print(f"\n{'='*50}")
            print("集成点:")
            for point in result.integration_points:
                print(f"  [{point.type}] {point.name} (置信度: {point.confidence})")
                print(f"    {point.description}")

        if result.conflicts:
            print(f"\n{'='*50}")
            print("冲突:")
            for conflict in result.conflicts:
                print(f"  [{conflict.severity}] {conflict.description}")
                print(f"    现有: {conflict.existing}")
                print(f"    新增: {conflict.new}")
                print(f"    建议: {conflict.resolution}")

        if result.recommendations:
            print(f"\n{'='*50}")
            print("建议:")
            for rec in result.recommendations:
                print(f"  - {rec}")

    except (FileNotFoundError, json.JSONDecodeError, SyntaxError, OSError) as e:
        # FileNotFoundError - manifest.json 或插件路径不存在
        # JSONDecodeError - manifest.json 格式错误
        # SyntaxError - 代码语法错误
        # OSError - 文件读取失败
        print(f"分析失败: {e}")
        sys.exit(1)
