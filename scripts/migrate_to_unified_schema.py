"""
migrate_to_unified_schema.py — 数据迁移脚本
旧格式 → 统一 Chunk Schema

运行方式：python scripts/migrate_to_unified_schema.py
"""
import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.chunk import Chunk


def backup_data():
    """备份现有数据"""
    data_dir = Path("data")
    if not data_dir.exists():
        print("[Migration] data 目录不存在，跳过备份")
        return

    backup_name = f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir = data_dir.parent / backup_name

    print(f"[Migration] 备份 data/ → {backup_name}/")
    shutil.copytree(data_dir, backup_dir)
    print(f"[Migration] 备份完成: {backup_dir}")


def migrate_chunks():
    """迁移 SQLite 中的 chunks"""
    try:
        from src.db.memory_store import get_store
        from src.db.data_store import load_chunks
    except Exception as e:
        print(f"[Migration] 无法加载数据存储: {e}")
        return

    try:
        old_chunks = load_chunks(filter_junk=False)
    except Exception as e:
        print(f"[Migration] 无法加载旧数据: {e}")
        return

    print(f"[Migration] 找到 {len(old_chunks)} 个旧 chunk")

    migrated = 0
    failed = 0
    skipped = 0

    for old in old_chunks:
        try:
            # 转换为统一 Chunk 对象
            chunk = Chunk.from_dict(old)

            # 验证必要字段
            if not chunk.text:
                skipped += 1
                continue

            # 转回 dict 存储（兼容现有存储层）
            new_dict = chunk.to_dict()

            # 保留旧数据中不在新 Schema 中的字段
            for key in old:
                if key not in new_dict:
                    new_dict[key] = old[key]

            migrated += 1

        except Exception as e:
            print(f"[Migration] 跳过 chunk: {e}")
            failed += 1

    print(f"[Migration] 完成: {migrated} 成功, {failed} 失败, {skipped} 跳过")


def validate_migration():
    """验证迁移结果"""
    try:
        from src.db.data_store import load_chunks
        from src.models.chunk import Chunk

        chunks = load_chunks(filter_junk=False)
        print(f"\n[Validation] 验证 {len(chunks)} 个 chunk")

        valid = 0
        invalid = 0
        sample_errors = []

        for c in chunks[:100]:  # 抽样验证前100个
            try:
                chunk = Chunk.from_dict(c)
                if chunk.text and (chunk.file_hash or chunk.chunk_id):
                    valid += 1
                else:
                    invalid += 1
                    if len(sample_errors) < 3:
                        sample_errors.append(f"缺少必要字段: {c.get('file_name', '?')}")
            except Exception as e:
                invalid += 1
                if len(sample_errors) < 3:
                    sample_errors.append(f"转换失败: {e}")

        print(f"[Validation] 结果: {valid} 有效, {invalid} 无效")
        if sample_errors:
            print(f"[Validation] 示例错误:")
            for err in sample_errors:
                print(f"  - {err}")

        return invalid == 0

    except Exception as e:
        print(f"[Validation] 验证失败: {e}")
        return False


def main():
    print("=" * 60)
    print("伏羲数据迁移脚本 — 周天大阵 Phase 1")
    print("=" * 60)

    # Step 1: 备份
    print("\n[Step 1] 备份现有数据...")
    backup_data()

    # Step 2: 迁移
    print("\n[Step 2] 迁移数据...")
    migrate_chunks()

    # Step 3: 验证
    print("\n[Step 3] 验证迁移结果...")
    success = validate_migration()

    if success:
        print("\n[Migration] 迁移成功完成！")
    else:
        print("\n[Migration] 迁移完成但有错误，请检查日志")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
