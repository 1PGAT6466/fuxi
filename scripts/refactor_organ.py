"""
refactor_organ.py — 通用器官分层重构脚本

用法: python refactor_organ.py <organ_name>

将指定器官重构为分层结构：
- signal_layer.py: 信号层
- business_layer.py: 业务层
- data_layer.py: 数据层
- utility_layer.py: 工具层
"""

import os
import sys
import shutil
from pathlib import Path


def refactor_organ(organ_name: str):
    """重构指定器官"""
    organs_dir = Path("src/hypothalamus/organs")
    organ_file = organs_dir / f"{organ_name}.py"
    organ_dir = organs_dir / organ_name
    
    if not organ_file.exists():
        print(f"[ERROR] {organ_file} not found")
        return False
    
    if organ_dir.exists():
        print(f"[SKIP] {organ_dir} already exists")
        return True
    
    # 创建器官目录
    organ_dir.mkdir(exist_ok=True)
    print(f"[OK] Created {organ_dir}")
    
    # 读取原始文件
    with open(organ_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 提取类名
    class_name = None
    for line in content.split("\n"):
        if "class " in line and "(OrganBase)" in line:
            class_name = line.split("class ")[1].split("(")[0].strip()
            break
    
    if not class_name:
        print(f"[ERROR] Could not find class name in {organ_file}")
        return False
    
    print(f"[OK] Found class: {class_name}")
    
    # 创建 __init__.py
    init_content = f'''"""
{organ_name}/ — 器官分层结构

分层结构：
├── signal_layer.py      # 信号层：处理经络信号
├── business_layer.py    # 业务层：核心处理逻辑
├── data_layer.py        # 数据层：数据持久化
└── utility_layer.py     # 工具层：辅助函数
"""

from .signal_layer import {class_name}

__all__ = ["{class_name}"]
'''
    
    with open(organ_dir / "__init__.py", "w", encoding="utf-8") as f:
        f.write(init_content)
    print(f"[OK] Created {organ_dir / '__init__.py'}")
    
    # 创建 signal_layer.py (将原始文件内容作为信号层)
    # 这里我们直接复制原始文件作为信号层，保持向后兼容
    shutil.copy(organ_file, organ_dir / "signal_layer.py")
    print(f"[OK] Created {organ_dir / 'signal_layer.py'}")
    
    # 创建空的 business_layer.py
    business_content = f'''"""
business_layer.py — {organ_name}业务层

职责：核心处理逻辑
"""

import logging
from typing import Dict

logger = logging.getLogger("{organ_name}.business")


class {class_name}BusinessLayer:
    """{class_name}业务层"""

    def __init__(self):
        pass
'''
    
    with open(organ_dir / "business_layer.py", "w", encoding="utf-8") as f:
        f.write(business_content)
    print(f"[OK] Created {organ_dir / 'business_layer.py'}")
    
    # 创建空的 data_layer.py
    data_content = f'''"""
data_layer.py — {organ_name}数据层

职责：数据持久化
"""

import logging
from typing import Dict, List

logger = logging.getLogger("{organ_name}.data")


class {class_name}DataLayer:
    """{class_name}数据层"""

    def __init__(self):
        pass
'''
    
    with open(organ_dir / "data_layer.py", "w", encoding="utf-8") as f:
        f.write(data_content)
    print(f"[OK] Created {organ_dir / 'data_layer.py'}")
    
    # 创建空的 utility_layer.py
    utility_content = f'''"""
utility_layer.py — {organ_name}工具层

职责：辅助函数
"""

import logging
from typing import Dict

logger = logging.getLogger("{organ_name}.utility")


class {class_name}UtilityLayer:
    """{class_name}工具层"""

    def __init__(self):
        pass
'''
    
    with open(organ_dir / "utility_layer.py", "w", encoding="utf-8") as f:
        f.write(utility_content)
    print(f"[OK] Created {organ_dir / 'utility_layer.py'}")
    
    # 更新原始文件为向后兼容入口
    compat_content = f'''"""
organs/{organ_name}.py — 器官分层重构

分层重构：v1.50
- 信号层（signal_layer.py）：处理经络信号
- 业务层（business_layer.py）：核心处理逻辑
- 数据层（data_layer.py）：数据持久化
- 工具层（utility_layer.py）：辅助函数

向后兼容：保留原有导入路径
"""

# 向后兼容：从新位置导入
from .{organ_name}.signal_layer import {class_name}

__all__ = ["{class_name}"]
'''
    
    with open(organ_file, "w", encoding="utf-8") as f:
        f.write(compat_content)
    print(f"[OK] Updated {organ_file} for backward compatibility")
    
    print(f"[SUCCESS] {organ_name} refactored successfully!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python refactor_organ.py <organ_name>")
        sys.exit(1)
    
    organ_name = sys.argv[1]
    success = refactor_organ(organ_name)
    sys.exit(0 if success else 1)
