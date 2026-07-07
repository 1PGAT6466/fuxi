# 伏羲 v1.50 器官层信号协议对齐报告

> 生成时间：2026-07-06 | 仓库路径：`E:\easyclaw\伏羲-v1.44\repo`
>
> **背景**：第三轮代码质量扫描发现 signal_layer 与顶层 organ 文件间存在大量重复代码。本报告验证各器官是否遵循统一信号协议，并给出重构建议。

---

## 一、器官模块清单（12 个器官）

| # | 器官 ID | 名称 | Emoji | 器官类 | 文件 |
|---|---------|------|-------|--------|------|
| 1 | `gallbladder` | 胆·决断 | 🫀 | `GallbladderAgent` | `gallbladder.py` |
| 2 | `heart` | 心·节律 | 🫀 | `HeartAgent` | `heart.py` |
| 3 | `kidney` | 肾·精炼 | 🫘 | `KidneyAgent` | `kidney.py` |
| 4 | `limbs` | 四肢·行功 | 💪 | `LimbsAgent` | `limbs.py` |
| 5 | `liver` | 肝·免疫 | 🛡️ | `LiverAgent` | `liver.py` |
| 6 | `lung` | 肺·呼吸 | 🫁 | `LungAgent` | `lung.py` |
| 7 | `nose` | 鼻·嗅探 | 👃 | `NoseAgent` | `nose.py` |
| 8 | `sanjiao` | 三焦·通道 | 🌊 | `SanJiaoAgent` | `sanjiao.py` |
| 9 | `skeleton` | 骨骼 | 🦴 | `SkeletonAgent` | `skeleton.py` |
| 10 | `skin` | 皮肤·屏障 | 🧖 | `SkinAgent` | `skin.py` |
| 11 | `small_intestine` | 小肠·分清 | 🫒 | `SmallIntestineAgent` | `small_intestine.py` |
| 12 | `spleen` | 脾·存储 | 🩸 | `SpleenAgent` | `spleen.py` |

---

## 二、统一接口协议合规检查

目标协议方法：

```python
async def process_signal(signal: Signal) -> SignalResponse
async def get_status() -> dict
```

### 2.1 合规结果总览

| 器官 | `process_signal` | `get_status` | 继承 `OrganBase` | `stats()` | 心跳订阅 | 自有事件循环 | 合规评级 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| gallbladder | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| heart | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| kidney | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | 🔵 已分层重构 |
| limbs | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ 无 | ⚠️ 不合规 |
| liver | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| lung | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| nose | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| sanjiao | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| **skeleton** | ❌ | ❌ | **❌** | ✅ | ✅ | ✅ | 🔴 严重不合规 |
| skin | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| small_intestine | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |
| spleen | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ 不合规 |

### 2.2 关键发现

1. **所有器官均未实现 `process_signal` 和 `get_status` 接口。**
   - 当前架构中，各器官通过 `meridian.subscribe()` 注册独立信号处理器，而非统一路由。
   - `meridian.py` 中的 `get_symbol_status()` 期望各器官实现 `get_status()`，但当前无任何器官实现。

2. **SkeletonAgent 是唯一未继承 `OrganBase` 的器官**，完全手动实现，缺少：
   - `OrganMetadata` 易学元数据（八卦、五行、天干、九宫）
   - `get_wuxing_info()`、`get_bagua_info()`、`get_stem_hour_info()`
   - `alive()` 方法
   - 基类的 `_stats` 追踪

3. **LimbsAgent 无自有事件循环**（无 `start_*ing()` / `_*_loop()`），缺少自主心跳发送能力。

---

## 三、signal_layer.py vs 顶层 .py 重复代码分析

### 3.1 文件结构概况

所有器官均存在 **一对关系**（顶层 `.py` + 子目录 `signal_layer.py`），其中 **skin** 的两个文件几乎完全一致，其余器官的顶层文件 ≈ signal_layer 文件 + 少量差异。

| 器官 | 顶层大小 | signal_layer 大小 | MD5 相同？ | 差异 |
|------|---------|-------------------|-----------|------|
| gallbladder | 7,061 B | 6,801 B | ❌ | 顶层多了 `asyncio` 导入、`FAKE-ASYNC` 注释、heartbeat 标记 async |
| heart | 7,770 B | 7,162 B | ❌ | 同上 |
| kidney | 11,742 B | 7,741 B | ❌ | 顶层是旧版单体实现，signal_layer 是重构后的分层版本 |
| limbs | 5,726 B | 5,651 B | ❌ | 同上 pattern |
| liver | 8,996 B | 8,562 B | ❌ | 同上 pattern |
| lung | 10,243 B | 9,722 B | ❌ | 同上 pattern |
| nose | 9,249 B | 8,728 B | ❌ | 同上 pattern |
| sanjiao | 6,928 B | 6,494 B | ❌ | 同上 pattern |
| skeleton | 7,824 B | 7,476 B | ❌ | 同上 pattern |
| skin | 10,132 B | 9,903 B | ❌ | 几乎一致（仅 import 路径和 async 标记差异） |
| small_intestine | 8,849 B | 8,589 B | ❌ | 同上 pattern |
| spleen | 9,880 B | 9,476 B | ❌ | 同上 pattern |

### 3.2 重复代码模式分类

#### 模式 A：心跳处理器的 async/sync 不一致（全器官）

**顶层文件**（如 `gallbladder.py`）：
```python
import asyncio
# ...
meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

async def _handle_heartbeat(self, signal: Signal) -> None:  # <- async
    self.meridian.heartbeat(self.organ_id)
```

**signal_layer**（如 `gallbladder/signal_layer.py`）：
```python
# 无 asyncio 导入
meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

def _handle_heartbeat(self, signal: Signal) -> None:  # <- sync
    self.meridian.heartbeat(self.organ_id)
```

**问题**：两个版本的 `_handle_heartbeat` 实现完全相同，但顶层标记了 `async`（加了 `# FAKE-ASYNC` 注释），signal_layer 是纯 sync。这导致代码重复且行为不统一。

#### 模式 B：事件循环结构重复（11/12 器官）

所有器官的事件循环遵循相同模板：

```python
# 重复代码段 1：启动方法
def start_working(self) -> None:          # 各器官方法名不同
    if self._running:
        return
    self._running = True
    self._task = asyncio.create_task(self._xxx_loop())
    logger.info(f"[Xxx] xxx已启动 {emoji}")

# 重复代码段 2：停止方法
def stop_working(self) -> None:
    self._running = False
    if self._task:
        self._task.cancel()

# 重复代码段 3：循环主体
async def _xxx_loop(self) -> None:
    while self._running:
        try:
            await asyncio.sleep(self.XXX_INTERVAL)   # 各器官间隔不同
            self.meridian.heartbeat(self.organ_id)
            # 器官特定的核心逻辑
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Xxx] Loop error: {e}")
            await asyncio.sleep(10)
```

**影响范围**：gallbladder、heart、kidney、liver、lung、nose、sanjiao、skin、small_intestine、spleen、skeleton —— **全部 11/12 个**具有事件循环的器官重复此模式。

**方法名不统一表**：

| 器官 | 启动方法 | 循环方法 | 间隔常量 |
|------|---------|---------|---------|
| gallbladder | `start_working()` | `_decide_loop()` | 30s (硬编码) |
| heart | `start_beating()` | `_beat_loop()` | `BEAT_INTERVAL=10` |
| kidney | `start_filtering()` | `_filter_loop()` | `FILTER_INTERVAL=25` |
| liver | `start_filtering()` | `_filter_loop()` | 30s (硬编码) |
| lung | `start_breathing()` | `_breath_loop()` | `BREATH_INTERVAL=25` |
| nose | `start_sniffing()` | `_sniff_loop()` | `SNIFF_INTERVAL=25` |
| sanjiao | `start_working()` | `_channel_loop()` | 25s (硬编码) |
| skeleton | `start_scanning()` | `_scan_loop()` | `SCAN_INTERVAL=3600` |
| skin | `start_guarding()` | `_guard_loop()` | 30s (硬编码) |
| small_intestine | `start_working()` | `_sort_loop()` | `SORT_INTERVAL=15` |
| spleen | `start_working()` | `_store_loop()` | 30s (硬编码) |

#### 模式 C：meridian.register_organ() 参数格式不统一

```python
# 格式 1（gallbladder, skeleton 等）
self.meridian.register_organ(self.organ_id, self.md.name, self.md.emoji, self.md.description)

# 格式 2（skin）
meridian.register_organ(organ_id=self.organ_id, name="皮肤·屏障", emoji="🧖")

# 格式 3（heart, liver, kidney, lung, nose, limbs）
self.meridian.register_organ(self.organ_id, "心", "🫀", "核心监控：...")
```

#### 模式 D：皮肤 signal_layer.py 与 skin.py 几乎完全重复（最严重）

`skin/signal_layer.py` 与 `skin.py` 的差异仅在于：
- import 路径：`from ..organ_base` vs `from .organ_base`
- `_handle_heartbeat` 和 `start_guarding` 在顶层标记 `async`，在 signal_layer 是 sync
- 顶层多了 `# FAKE-ASYNC` 注释

其余所有代码完全重复（共约 250 行），包括 `search_external()`、`_antenna_fetch()`、`_antenna_verify()`、`_antenna_cache`、`stats()` 等。

---

## 四、可提取到基类的公共方法清单

### 4.1 `OrganBase` 应新增方法

| 优先级 | 方法签名 | 来源模式 | 说明 |
|--------|---------|---------|------|
| **P0** | `start_loop(interval: float)` / `stop_loop()` | 模式 B (11/12) | 统一生命周期管理，子类只需覆盖 `_loop_tick()` |
| **P0** | `_loop_tick() -> None` （抽象方法） | 模式 B | 每轮循环执行的器官特有逻辑 |
| **P1** | `register_to_meridian(name, emoji, desc)` | 模式 C (12/12) | 统一经络注册，使用 `self.md` 元数据 |
| **P1** | `subscribe_heartbeat()` | 模式 A (12/12) | 统一心跳订阅 + 处理器 |
| **P1** | `send_heartbeat()` | 模式 A (12/12) | `self.meridian.heartbeat(self.organ_id)` |
| **P1** | `reply_ok(signal, data)` | 多处 | 包装 `self.meridian.reply(signal, {"ok": True, **data})` |
| **P1** | `reply_error(signal, error_msg)` | 多处 | 包装 `self.meridian.reply(signal, {"ok": False, "error": ...})` |
| **P2** | `send_to(organ, signal_type, payload, priority)` | 多处 | 包装 `self.meridian.send(Signal(...))` |
| **P2** | `alert_brain(message)` | heart/nose/liver | 向大脑发送 HIGH 优先级告警 |

### 4.2 提议的 `OrganBase` 增强实现

```python
class OrganBase:
    # ... 现有代码 ...

    # ── v1.50: 统一事件循环 ──
    
    LOOP_INTERVAL: float = 30  # 子类可覆盖

    def start_loop(self) -> None:
        """统一生命周期启动"""
        if getattr(self, '_running', False):
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._loop())

    def stop_loop(self) -> None:
        """统一生命周期停止"""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()

    async def _loop(self) -> None:
        """统一事件循环模板"""
        while self._running:
            try:
                await asyncio.sleep(self.LOOP_INTERVAL)
                self.meridian.heartbeat(self.organ_id)
                await self._loop_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.organ_id}] Loop error: {e}")
                await asyncio.sleep(10)

    async def _loop_tick(self) -> None:
        """子类覆盖：每轮执行的特有逻辑"""
        pass

    # ── v1.50: 统一经络交互 ──

    def register_to_meridian(self) -> None:
        """使用 self.md 统一注册"""
        self.meridian.register_organ(
            self.organ_id, self.md.name, self.md.emoji, self.md.description
        )

    def subscribe_heartbeat(self) -> None:
        """订阅心跳信号"""
        self.meridian.subscribe(self.organ_id, "heartbeat", self._on_heartbeat)

    def _on_heartbeat(self, signal: Signal) -> None:
        """统一心跳处理器"""
        self.meridian.heartbeat(self.organ_id)

    def reply_ok(self, signal: Signal, data: dict = None) -> None:
        """统一成功回复"""
        self.meridian.reply(signal, {"ok": True, **(data or {})})

    def reply_error(self, signal: Signal, error_msg: str) -> None:
        """统一错误回复"""
        self.meridian.reply(signal, {"ok": False, "error": error_msg})

    def send_to(self, target: str, signal_type: str, payload: dict = None,
                priority: SignalPriority = SignalPriority.NORMAL) -> None:
        """便捷发送信号"""
        self.meridian.send(Signal(
            source=self.organ_id, target=target,
            signal_type=signal_type, payload=payload or {},
            priority=priority,
        ))

    def alert_brain(self, message: str) -> None:
        """向大脑发送高优先级告警"""
        self.send_to("brain", "alert", {"message": message},
                     priority=SignalPriority.HIGH)
```

### 4.3 估算的重构收益

| 指标 | 当前 | 重构后 | 节省 |
|------|------|--------|------|
| `start_*`/`stop_*` 重复代码行数 | ~72 行 (6 行 × 12 器官) | 2 行 | **97%** |
| `_*_loop()` 重复代码行数 | ~120 行 (10 行 × 12) | 0 (基类提供) | **100%** |
| `_handle_heartbeat` 重复行数 | ~36 行 (3 行 × 12) | 0 | **100%** |
| `meridian.register_organ` 重复 | ~48 行 | 0 | **100%** |
| `asyncio.create_task` 分散调用 | 12 处 | 0 (统一) | **100%** |
| **总计可消除重复代码** | **~300 行** | — | — |
| 器官代码平均行数 | ~280 行 | ~120 行 | **57%** |

---

## 五、协议接口演进建议

### 5.1 当前问题根源

当前系统通过 `meridian.subscribe(organ_id, signal_type, handler)` 实现了有效的信号路由，但没有统一的"信号入口"概念。每个器官自己决定订阅哪些信号，导致：

1. 无法统一查询"器官能否处理某种信号"
2. `meridian.get_symbol_status()` 调用了 `get_status()` 但无人实现
3. 没有 `process_signal` 作为单一入口

### 5.2 建议的接口协议

```python
class OrganBase:
    """器官基类 — v1.50 统一协议"""

    # ── 标准协议方法 ──

    async def process_signal(self, signal: Signal) -> SignalResponse:
        """统一信号处理入口（子类通常不需覆盖，由 _dispatch 自动路由）"""
        handlers = self._signal_handlers()
        handler = handlers.get(signal.signal_type)
        if handler:
            return await handler(signal)
        return SignalResponse(ok=False, error=f"unhandled signal: {signal.signal_type}")

    def _signal_handlers(self) -> Dict[str, Callable]:
        """子类覆盖：返回信号类型 -> 处理器的映射"""
        return {}

    async def get_status(self) -> dict:
        """标准状态查询接口"""
        return {
            "organ_id": self.organ_id,
            "name": self.md.name,
            "alive": self.alive(),
            "uptime": round(time.time() - self._born_at),
            "wuxing": self.get_wuxing_info(),
            "stats": self.stats(),
            "running": getattr(self, '_running', False),
        }
```

### 5.3 协议对齐分阶段计划

| 阶段 | 内容 | 影响范围 | 工时估算 |
|------|------|---------|---------|
| **Phase 0** | 清理重复文件，删除 11 个 `signal_layer.py`（或无用的顶层 .py） | 所有器官 | 0.5h |
| **Phase 1** | `OrganBase` 增加统一生命周期 + 经络交互方法 | `organ_base.py` | 1h |
| **Phase 2** | 所有器官迁移到基类 `start_loop()` + `_loop_tick()` | 11 个器官 | 2h |
| **Phase 3** | 实现 `get_status()` + `_signal_handlers()` | 11 个器官 | 1h |
| **Phase 4** | SkeletonAgent 继承 `OrganBase` | skeleton | 0.5h |
| **Phase 5** | 为 LimbsAgent 添加自主心跳事件循环 | limbs | 0.5h |
| **Phase 6** | 添加 `process_signal()` 统一入口 + 协议测试 | `organ_base.py` + tests | 1h |
| **总计** | | | **约 6.5h** |

---

## 六、重构优先级建议

### 🔴 严重（立即修复）

1. **SkeletonAgent 继承 OrganBase** — 当前是完全独立实现，缺少所有易学元数据和基础方法。
2. **删除 signal_layer.py 全部 11 个重复文件**（除 kidney/signal_layer.py 是真正的分层实现，应保留作为模板）。

### 🟡 高（本次迭代完成）

3. **`OrganBase` 增加统一生命周期方法**（`start_loop`/`stop_loop`/`_loop_tick`）
4. **统一 `register_organ` 调用**（消除 3 种不同参数格式）
5. **统一 `_handle_heartbeat` 实现**

### 🟢 中（下个迭代）

6. **实现 `get_status()` 接口**（所有 12 个器官）
7. **实现 `process_signal()` 统一入口**
8. **为 LimbsAgent 添加事件循环**

### 🔵 低（后续优化）

9. **`reply_ok`/`reply_error`/`send_to`/`alert_brain` 便捷方法**
10. **协议合规自动化测试**

---

## 七、附录：kidney 分层重构作为目标模板

Kidney 是唯一完成了四层分层的器官，其架构应作为其他器官重构的目标模板：

```
kidney/
├── __init__.py          # 导出 KidneyAgent
├── signal_layer.py      # 信号路由 + 经络交互 + 生命周期
├── business_layer.py    # 核心业务逻辑（无经络依赖）
├── data_layer.py        # 数据持久化（纯 I/O）
└── utility_layer.py     # 纯函数工具（无副作用，易测试）
```

**分层后的收益（以 kidney 为例）**：
- signal_layer: 120 行（vs 旧版单体 340 行）
- business_layer: 可独立测试，不依赖经络
- data_layer: 可 mock 测试
- utility_layer: 纯函数，单元测试覆盖率可达 100%
