#!/usr/bin/env python3
"""
标记伏羲 v1.50 代码库中的 fake async 函数。
规则：
1. 扫描所有 async def 函数（顶层/类层级，排除嵌套在其他函数内的）
2. 检查函数体内是否有 await 调用（排除嵌套 async 函数内部的 await）
3. 如果没有 await → 标记为 FAKE-ASYNC
4. 如果只有 `return await xxx()` 作为唯一含 await 的语句 → 也算 fake async

只做标记，不改任何函数逻辑。
标记格式：在 async def 所在行前插入一行注释。
"""

import ast
import sys
import re
from pathlib import Path
from collections import defaultdict

COMMENT = "# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行"


def add_parent_refs(node, parent=None):
    node._parent = parent
    for child in ast.iter_child_nodes(node):
        add_parent_refs(child, node)


def find_nearest_func(node):
    cur = node
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
        cur = getattr(cur, '_parent', None)
    return None


def analyze_async_func(func_node):
    """
    分析一个 async def 函数。
    返回: (is_fake: bool, reason: str)
    """
    direct_awaits = []
    has_other_code = False

    def walk_body(node, depth=0):
        nonlocal has_other_code
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # 跳过嵌套函数
            if isinstance(child, ast.ClassDef):
                continue
            if isinstance(child, ast.Await):
                parent_func = find_nearest_func(child)
                if parent_func is func_node:
                    direct_awaits.append(child)
                continue
            if depth == 0:
                if isinstance(child, ast.Return):
                    if child.value is not None and not isinstance(child.value, ast.Await):
                        has_other_code = True
                elif isinstance(child, ast.Expr):
                    if not (isinstance(child.value, ast.Constant) and
                            isinstance(child.value.value, str)):
                        has_other_code = True
                elif isinstance(child, (ast.Pass, ast.Import, ast.ImportFrom)):
                    pass
                elif isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    has_other_code = True
                elif isinstance(child, ast.If):
                    has_other_code = True
                elif isinstance(child, (ast.For, ast.While, ast.Try, ast.With)):
                    has_other_code = True
                elif isinstance(child, (ast.Raise, ast.Assert)):
                    has_other_code = True
                elif isinstance(child, ast.Global):
                    pass
                else:
                    has_other_code = True
            walk_body(child, depth + 1)

    walk_body(func_node)

    if len(direct_awaits) == 0:
        return True, "无 await 调用"

    # 检查是否只有 return await xxx() 这一种 await
    if len(direct_awaits) == 1 and not has_other_code:
        await_node = direct_awaits[0]
        parent = getattr(await_node, '_parent', None)
        if isinstance(parent, ast.Return):
            return True, "仅 return await xxx()"

    return False, ""


def analyze_file(filepath):
    """返回: (source, [(lineno, func_name, reason), ...])"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source)
        add_parent_refs(tree)

        fake_funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                parent = getattr(node, '_parent', None)
                # 跳过嵌套在另一个函数内的
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                is_fake, reason = analyze_async_func(node)
                if is_fake:
                    fake_funcs.append((node.lineno, node.name, reason))

        return source, fake_funcs
    except SyntaxError:
        return None, []
    except Exception as e:
        print(f"  ⚠️ 解析错误 {filepath}: {e}", file=sys.stderr)
        return None, []


def mark_file(filepath):
    """直接在文件上标记（无 dry_run，一次性完成）"""
    source, fake_funcs = analyze_file(filepath)
    if source is None or not fake_funcs:
        return []

    lines = source.split('\n')
    changes = []

    # 从后往前插入，避免行号偏移
    for lineno, func_name, reason in sorted(fake_funcs, key=lambda x: x[0], reverse=True):
        line_idx = lineno - 1

        # 双重检查：确保前面没有已存在的标记
        if line_idx > 0 and COMMENT in lines[line_idx - 1]:
            continue

        lines.insert(line_idx, COMMENT)
        changes.append((lineno, func_name, reason))

    if changes:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    return changes


def syntax_check_one(fpath):
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return None
    except SyntaxError as e:
        return str(e)


def main():
    repo_root = Path(r"E:\easyclaw\伏羲-v1.44\repo")
    src_dir = repo_root / "src"
    target_dirs = ["services", "taiyin", "taiyang", "shaoyang"]

    all_files = []
    for d in target_dirs:
        dir_path = src_dir / d
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                all_files.append(py_file)

    print(f"🔍 扫描 {len(all_files)} 个 Python 文件...\n")

    total_fake = 0
    all_results = []

    for py_file in sorted(all_files, key=lambda p: p.name):
        rel = py_file.relative_to(repo_root)
        changes = mark_file(str(py_file))
        if changes:
            total_fake += len(changes)
            all_results.append((rel, changes))
            print(f"📄 src/{rel.relative_to('src')}  ({len(changes)} 个)")
            for lineno, func_name, reason in changes:
                print(f"    行 {lineno}: async def {func_name}() — {reason}")

    print(f"\n📊 总计 {total_fake} 个 fake async 函数（{len(all_results)} 个文件）")

    if total_fake == 0:
        print("✅ 没有需要标记的 fake async 函数")
        return

    # 语法检查所有修改过的文件
    print("\n🔧 语法检查已修改的文件...")
    errors = []
    for rel, changes in all_results:
        fpath = repo_root / rel
        err = syntax_check_one(str(fpath))
        if err:
            errors.append((rel, err))
            print(f"  ❌ src/{rel.relative_to('src')}: {err}")
        else:
            print(f"  ✅ src/{rel.relative_to('src')}")

    # 也检查所有目标目录的文件
    print("\n🔧 全量语法检查...")
    all_errs = []
    for pf in all_files:
        err = syntax_check_one(str(pf))
        if err:
            all_errs.append((pf.relative_to(repo_root), err))

    if all_errs:
        # 只显示我们没引入的错误
        ours = set(str(r) for r, _ in all_results)
        for rel, err in all_errs:
            label = " (既有)" if str(rel) not in ours else ""
            print(f"  ❌ src/{rel.relative_to('src')}: {err}{label}")
    else:
        print("  ✅ 全部通过")

    # 输出变更清单
    print("\n" + "=" * 60)
    print("📋 变更清单")
    print("=" * 60)
    for rel, changes in all_results:
        for lineno, func_name, reason in changes:
            print(f"  src/{rel.relative_to('src')}:{lineno} — async def {func_name}() — {reason}")

    print(f"\n✅ 任务完成！共标记 {total_fake} 个 fake async 函数")


if __name__ == "__main__":
    main()
