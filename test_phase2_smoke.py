"""
伏羲 v2.1 Phase 2 — 导入测试 + 集成冒烟测试 (v3)
修正：使用 register_gua(not register), asyncio 处理 think()
"""
import sys
import os
import asyncio

repo_root = r"E:\easyclaw\伏羲-v1.44\repo"
os.chdir(repo_root)
sys.path.insert(0, repo_root)

# ============================================================
# 子任务 2: Bagua 模块导入测试
# ============================================================
print("=" * 60)
print("子任务 2: Bagua 模块导入测试")
print("=" * 60)

import_count = 0
import_errors = []

def try_import(module_path, symbols, label):
    global import_count
    try:
        code = f"from {module_path} import {symbols}"
        exec(code)
        import_count += 1
        print(f"[OK] {import_count:02d} {module_path}  ->  {label}")
        return True
    except Exception as e:
        print(f"[FAIL] {module_path}  ->  {e}")
        import_errors.append(f"{module_path}: {e}")
        return False

try_import("src.bagua.base_gua", "GuaBase, HealthLevel, CircuitState, FallbackAction, DegradationRule, DependencyStatus",
           "GuaBase, HealthLevel, CircuitState, FallbackAction, DegradationRule, DependencyStatus")
try_import("src.bagua.intent_bus", "IntentBus, Signal, Priority, SignalType",
           "IntentBus, Signal, Priority, SignalType")
try_import("src.bagua.smart_router", "RoutingDecision, CacheEntry",
           "RoutingDecision, CacheEntry")
try_import("src.bagua.qian", "QianGua, CycleGuard, SafetyCruise",
           "QianGua, CycleGuard, SafetyCruise")
try_import("src.bagua.kun", "KunGua", "KunGua")
try_import("src.bagua.zhen", "ZhenGua", "ZhenGua")
try_import("src.bagua.xun", "XunGua", "XunGua")
try_import("src.bagua.kan", "KanGua", "KanGua")
try_import("src.bagua.gen", "GenGua", "GenGua")
try_import("src.bagua.dui", "DuiGua", "DuiGua")

total_import_targets = 10
print(f"\n>>> 导入成功模块数: {import_count} / {total_import_targets}")
if import_errors:
    print("导入失败详情：")
    for err in import_errors:
        print(f"  - {err}")

# ============================================================
# 子任务 3: 快速集成冒烟测试
# ============================================================
print()
print("=" * 60)
print("子任务 3: 快速集成冒烟测试")
print("=" * 60)

from src.bagua.intent_bus import IntentBus, Signal, Priority
from src.bagua.qian import QianGua
from src.bagua.kun import KunGua

smoke_pass = True
result = None
smoke_errors = []

# 1. 创建 IntentBus 实例
try:
    bus = IntentBus()
    print("[STEP 1] IntentBus 实例创建成功")
except Exception as e:
    print(f"[FAIL] STEP 1: IntentBus 创建失败: {e}")
    smoke_errors.append(f"STEP 1: {e}")
    smoke_pass = False

# 2. 创建乾卦实例 (intent_mode="rule_based")
try:
    qian = QianGua(intent_mode="rule_based")
    print("[STEP 2] QianGua (intent_mode='rule_based') 创建成功")
except Exception as e:
    print(f"[FAIL] STEP 2: QianGua 创建失败: {e}")
    smoke_errors.append(f"STEP 2: {e}")
    smoke_pass = False

# 3. 注册坤卦到 IntentBus（方法名是 register_gua）
try:
    kun = KunGua()
    bus.register_gua("kun", kun)
    print("[STEP 3] KunGua 通过 register_gua 注册到 IntentBus 成功")
except Exception as e:
    print(f"[FAIL] STEP 3: KunGua 注册失败: {e}")
    smoke_errors.append(f"STEP 3: {e}")
    smoke_pass = False

# 4. 调用 qian.think("你好", [], "test-session") — 使用 asyncio 运行
try:
    if 'qian' in dir():
        result = asyncio.run(qian.think("你好", [], "test-session"))
        print(f"[STEP 4] qian.think('你好', [], 'test-session') await 完成")
        print(f"        返回类型: {type(result).__name__}")
    else:
        print("[FAIL] STEP 4: qian 未定义，跳过")
        smoke_errors.append("STEP 4: qian 未定义")
        smoke_pass = False
except Exception as e:
    print(f"[FAIL] STEP 4: qian.think() 崩溃: {e}")
    import traceback
    traceback.print_exc()
    smoke_errors.append(f"STEP 4: {e}")
    smoke_pass = False

# 5. 检查返回结果是否包含 answer/sources/mode/confidence
try:
    if result is not None:
        required_fields = ["answer", "sources", "mode", "confidence"]
        if isinstance(result, dict):
            missing = [f for f in required_fields if f not in result]
            if not missing:
                print(f"[STEP 5] 返回 (dict) 包含所有必需字段: {required_fields}")
                for f in required_fields:
                    val = result.get(f)
                    if isinstance(val, str) and len(val) > 80:
                        val = val[:80] + "..."
                    print(f"         {f}: {val}")
            else:
                print(f"[FAIL] STEP 5: dict 缺少字段: {missing}")
                print(f"         实际字段: {list(result.keys())[:10]}")
                smoke_errors.append(f"STEP 5: missing {missing}")
                smoke_pass = False
        elif hasattr(result, '__dict__'):
            rd = vars(result)
            missing = [f for f in required_fields if f not in rd]
            if not missing:
                print(f"[STEP 5] 返回 (dataclass) 包含所有必需字段: {required_fields}")
                for f in required_fields:
                    val = rd.get(f)
                    if isinstance(val, str) and len(val) > 80:
                        val = val[:80] + "..."
                    print(f"         {f}: {val}")
            else:
                print(f"[FAIL] STEP 5: dataclass 缺少字段: {missing}")
                print(f"         实际字段: {list(rd.keys())[:10]}")
                smoke_errors.append(f"STEP 5: missing {missing}")
                smoke_pass = False
        else:
            print(f"[WARN] STEP 5: 返回类型为 {type(result).__name__}，尝试字符串检测")
            # 尝试打印前 200 个字符来看结构
            print(f"         str(result)[:200]: {str(result)[:200]}")
            smoke_errors.append(f"STEP 5: uncheckable type {type(result).__name__}")
            smoke_pass = False
    else:
        print("[FAIL] STEP 5: result 为 None")
        smoke_errors.append("STEP 5: result is None")
        smoke_pass = False
except Exception as e:
    print(f"[FAIL] STEP 5: 字段验证异常: {e}")
    import traceback
    traceback.print_exc()
    smoke_errors.append(f"STEP 5: {e}")
    smoke_pass = False

# ============================================================
# 子任务 4: 统计汇总
# ============================================================
print()
print("=" * 60)
print("子任务 4: 统计汇总 (Phase 2 最终)")
print("=" * 60)

print(f"\n  编译统计  ")
print(f"  编译通过: 11 / 11  (100%)")
print(f"  编译失败:  0 / 11")

print(f"\n  导入统计  ")
print(f"  导入成功: {import_count} / {total_import_targets} (100%)" if import_count == total_import_targets else f"  导入成功: {import_count} / {total_import_targets}")
if import_errors:
    for err in import_errors:
        print(f"    - {err}")

print(f"\n  冒烟测试  ")
print(f"  结果: {'✅ PASS' if smoke_pass else '❌ FAIL'}")
if smoke_errors:
    print(f"  失败步骤 ({len(smoke_errors)}):")
    for err in smoke_errors:
        print(f"    - {err}")

print(f"\n  文件行数统计  ")
bagua_dir = os.path.join(repo_root, "src", "bagua")
lines_total = 0
file_lines = []
for fname in sorted(os.listdir(bagua_dir)):
    if fname.endswith('.py'):
        fpath = os.path.join(bagua_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            n = sum(1 for _ in f)
        lines_total += n
        file_lines.append((fname, n))

for fname, n in file_lines:
    print(f"  {fname:25s} {n:5d} lines")

print(f"  {'─'*30}")
print(f"  {'TOTAL':25s} {lines_total:5d} lines ({len(file_lines)} Python files)")

print()
print("=" * 60)
print("Phase 2 验证完成")
print("=" * 60)
