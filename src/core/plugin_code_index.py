"""
伏羲代码索引
使用 ChromaDB 建立代码库的向量索引，支持语义搜索

作者: AI助手
日期: 2026-07-17
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CodeIndex:
    """代码索引 - 使用 ChromaDB 建立代码向量索引"""

    def __init__(self, fuxi_root: str = ".", chromadb_path: str = "data/code_index"):
        """
        初始化代码索引

        Args:
            fuxi_root: 伏羲根目录
            chromadb_path: ChromaDB 存储路径
        """
        self.fuxi_root = Path(fuxi_root)
        self.chromadb_path = Path(chromadb_path)
        self._collection = None
        self._embedder = None

    # ============ 公开接口 ============

    def build_index(self, force: bool = False) -> Dict[str, Any]:
        """
        构建代码索引

        Args:
            force: 是否强制重建

        Returns:
            构建结果
        """
        result = {"success": False, "files_indexed": 0, "symbols_indexed": 0, "errors": []}

        try:
            # 检查是否需要重建
            if not force and self._index_exists():
                logger.info("索引已存在，跳过构建")
                result["success"] = True
                return result

            # 初始化 ChromaDB
            self._init_chromadb()

            # 扫描代码
            src_dir = self.fuxi_root / "src"
            if not src_dir.exists():
                raise FileNotFoundError(f"源码目录不存在: {src_dir}")

            # 索引文件
            for py_file in src_dir.rglob("*.py"):
                try:
                    self._index_file(py_file)
                    result["files_indexed"] += 1
                except (SyntaxError, UnicodeDecodeError, OSError) as e:
                    # SyntaxError - 代码语法错误
                    # UnicodeDecodeError - 文件编码问题
                    # OSError - 文件读取失败
                    result["errors"].append(f"{py_file.name}: {str(e)}")

            # 索引符号
            result["symbols_indexed"] = self._index_symbols()

            result["success"] = True
            logger.info(f"索引构建完成: {result['files_indexed']} 文件, " f"{result['symbols_indexed']} 符号")

        except (FileNotFoundError, ImportError, OSError, ValueError) as e:
            # FileNotFoundError - 源码目录不存在
            # ImportError - chromadb 未安装
            # OSError - 文件系统错误
            # ValueError - ChromaDB 配置错误
            logger.error(f"索引构建失败: {e}", exc_info=True)
            result["errors"].append(str(e))

        return result

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        语义搜索代码

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        results = []

        try:
            if not self._collection:
                self._init_chromadb()

            # 执行搜索
            search_results = self._collection.query(query_texts=[query], n_results=top_k)

            # 解析结果
            if search_results and search_results["documents"]:
                for i, doc in enumerate(search_results["documents"][0]):
                    metadata = search_results["metadatas"][0][i] if search_results["metadatas"] else {}
                    distance = search_results["distances"][0][i] if search_results["distances"] else 0

                    results.append(
                        {
                            "content": doc,
                            "metadata": metadata,
                            "distance": distance,
                            "relevance": 1 - distance,  # 转换为相关度
                        }
                    )

        except (ValueError, KeyError, TypeError) as e:
            # ValueError - ChromaDB 查询参数错误
            # KeyError - 结果字典键缺失
            # TypeError - 返回数据类型错误
            logger.error(f"搜索失败: {e}", exc_info=True)

        return results

    def get_symbol_info(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """
        获取符号信息

        Args:
            symbol_name: 符号名称

        Returns:
            符号信息
        """
        try:
            if not self._collection:
                self._init_chromadb()

            # 搜索符号
            results = self._collection.query(
                query_texts=[symbol_name], n_results=1, where={"type": {"$in": ["class", "function"]}}
            )

            if results and results["documents"] and results["documents"][0]:
                return {
                    "content": results["documents"][0][0],
                    "metadata": results["metadatas"][0][0] if results["metadatas"] else {},
                    "distance": results["distances"][0][0] if results["distances"] else 0,
                }

        except (ValueError, KeyError, TypeError) as e:
            # ValueError - ChromaDB 查询参数错误
            # KeyError - 结果字典键缺失
            # TypeError - 返回数据类型错误
            logger.error(f"获取符号信息失败: {e}", exc_info=True)

        return None

    # ============ 内部方法 ============

    def _index_exists(self) -> bool:
        """检查索引是否存在"""
        return self.chromadb_path.exists() and any(self.chromadb_path.iterdir())

    def _init_chromadb(self):
        """初始化 ChromaDB"""
        try:
            import chromadb

            # 创建持久化客户端
            client = chromadb.PersistentClient(path=str(self.chromadb_path))

            # 获取或创建集合
            self._collection = client.get_or_create_collection(
                name="code_index", metadata={"description": "伏羲代码索引"}
            )

            logger.info(f"ChromaDB 初始化完成: {self.chromadb_path}")

        except ImportError:
            logger.error("chromadb 未安装，请执行: pip install chromadb")
            raise
        except (OSError, ValueError, RuntimeError) as e:
            # OSError - 数据目录权限/磁盘问题
            # ValueError - ChromaDB 配置参数错误
            # RuntimeError - ChromaDB 运行时错误
            logger.error(f"ChromaDB 初始化失败: {e}", exc_info=True)
            raise

    def _index_file(self, file_path: Path):
        """索引单个文件"""
        try:
            content = file_path.read_text(encoding="utf-8")

            # 提取文件摘要
            summary = self._extract_file_summary(content, file_path)

            # 添加到索引
            self._collection.add(
                documents=[summary],
                metadatas=[{"type": "file", "path": str(file_path), "name": file_path.name, "size": len(content)}],
                ids=[f"file:{file_path}"],
            )

        except (UnicodeDecodeError, OSError, ValueError) as e:
            # UnicodeDecodeError - 文件编码不是UTF-8
            # OSError - 文件读取失败
            # ValueError - ChromaDB add() 参数错误
            logger.debug(f"索引文件失败 {file_path}: {e}")

    def _index_symbols(self) -> int:
        """索引符号"""
        import ast

        count = 0
        src_dir = self.fuxi_root / "src"

        for py_file in src_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))

                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                        # 提取符号信息
                        symbol_info = self._extract_symbol_info(node, py_file, content)

                        # 添加到索引
                        self._collection.add(
                            documents=[symbol_info["docstring"] or symbol_info["name"]],
                            metadatas=[
                                {
                                    "type": symbol_info["type"],
                                    "name": symbol_info["name"],
                                    "file": str(py_file),
                                    "line": symbol_info["line"],
                                }
                            ],
                            ids=[f"{symbol_info['type']}:{py_file}:{symbol_info['name']}"],
                        )

                        count += 1

            except (SyntaxError, UnicodeDecodeError, OSError, ValueError) as e:
                # SyntaxError - 代码语法错误
                # UnicodeDecodeError - 文件编码问题
                # OSError - 文件读取失败
                # ValueError - ChromaDB add() 参数错误
                logger.debug(f"索引符号失败 {py_file}: {e}")

        return count

    def _extract_file_summary(self, content: str, file_path: Path) -> str:
        """提取文件摘要"""
        lines = content.split("\n")

        # 提取模块文档
        docstring = ""
        if lines and lines[0].startswith('"""'):
            end_idx = content.find('"""', 3)
            if end_idx > 0:
                docstring = content[3:end_idx].strip()

        # 提取主要类和函数
        import ast

        try:
            tree = ast.parse(content)
            symbols = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append(f"class {node.name}")
                elif isinstance(node, ast.FunctionDef):
                    symbols.append(f"def {node.name}")

            symbol_str = ", ".join(symbols[:10])  # 最多10个
        except SyntaxError:
            # SyntaxError - AST 解析失败（非 Python 代码或语法错误）
            symbol_str = ""

        return f"{file_path.name}: {docstring}\n符号: {symbol_str}"

    def _extract_symbol_info(self, node: Any, file_path: Path, content: str) -> Dict[str, Any]:
        """提取符号信息"""
        import ast

        name = node.name
        symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"
        docstring = ast.get_docstring(node)
        line = node.lineno

        return {"name": name, "type": symbol_type, "docstring": docstring, "line": line, "file": str(file_path)}
