# 伏羲 v1.50 器官层信号总线 — 深度全链路追踪报告

> **追踪日期**: 2026-07-06  
> **仓库**: `E:\easyclaw\伏羲-v1.44\repo`  
> **追踪原则**: 每一个 "A 调用了 B" 必须有代码证据，不做假设。

---

## 目录

1. [Meridian 经络总线的完整实现](#1-meridian-经络总线的完整实现)
2. [信号协议：Signal / SymbolRequest / SymbolResponse](#2-信号协议signal--symbolrequest--symbolresponse)
3. [SymbolBase 基类：实际继承者](#3-symbolbase-基类实际继承者)
4. [meridian.publish() 和 meridian.subscribe() 全量调用点](#4-meridiansubscribe-全量调用点)
5. [meridian.heartbeat() 全量调用点](#5-meridianheartbeat-全量调用点)
6. [MeridianMonitor：谁启动的？](#6-meridianmonitor谁启动的)
7. [五行生克调度器：真的在运行吗？](#7-五行生克调度器真的在运行吗)
8. [GrowthEngine：实际调用点](#8-growthengine实际调用点)
9. [实际模块间调用关系图](#9-实际模块间调用关系图)

---

## 1. Meridian 经络总线的完整实现

**文件**: `src/hypothalamus/meridian.py` (305 行)

### 1.1 核心数据结构

```python
class Meridian:
    _subscriptions: Dict[str, Dict[str, List[Callable]]]  # {organ_id: {signal_type: [handler, ...]}}
    _organs: Dict[str, OrganInfo]         # 已注册器官
    _symbols: Dict[str, Dict]             # 四象注册表
    _history: List[Signal]                # 最近 500 条信号
    _pending: Dict[str, Signal]           # 等待回复的信号
    _replies: Dict[str, asyncio.Future]   # 回复等待器
    _queue: asyncio.PriorityQueue         # 异步优先级队列
    _services: Dict[str, Callable]        # 服务桥接注册表
```

### 1.2 信号注册（器官订阅）

```python
# 注册器官
meridian.register_organ(organ_id, name, emoji, description)
  → self._organs[organ_id] = OrganInfo(...)

# 器官订阅信号类型
meridian.subscribe(organ_id, signal_type, handler)
  → self._subscriptions[organ_id][signal_type].append(handler)
  → self._subscriptions[organ_id]["*"].append(handler)  # 通配符
```

### 1.3 信号路由（非阻塞投递）

```python
meridian.send(signal: Signal) → signal_id
  1. signal.timestamp = time.time()
  2. _add_to_history(signal)           # 写入历史（保留最近 500 条）
  3. _queue.put_nowait((priority, signal))  # 推入优先级队列
  4. source_organ.signals_sent += 1
  5. return signal.signal_id

# 分发由 _run_loop() 驱动：
async def _run_loop():
    while running:
        _, signal = await _queue.get()    # 按优先级出队
        await _dispatch(signal)           # 分发给订阅者
```

### 1.4 信号分发（目标匹配）

```python
async def _dispatch(signal):
    1. 解析 target:
       - "*" → 所有已注册器官
       - "organ1,organ2" → 逗号分隔多目标
       - "organ1" → 单一目标
    2. 对每个 target，获取 handlers:
       - self._subscriptions[organ_id][signal.signal_type]  # 精确匹配
       - self._subscriptions[organ_id]["*"]                 # 通配符
    3. 逐个调用 handler(signal):
       - asyncio.iscoroutinefunction → await handler(signal)
       - 否则 → handler(signal) 同步调用
```

### 1.5 请求-回复模式

```python
meridian.send_and_wait(signal, timeout=5.0)
  → 创建 asyncio.Future, 存入 self._replies[signal_id]
  → 调用 self.send(signal)
  → await future (timeout 后返回 None)

meridian.reply(original_signal, data)
  → 构造 REPLY 信号发回
  → 设置 self._replies[signal_id].set_result(data)
```

### 1.6 广播

```python
meridian.broadcast(source, signal_type, payload, priority)
  → self.send(Signal(target="*", ...))
```

### 1.7 生命周期

```python
await meridian.start()   → _running = True, _task = asyncio.create_task(_run_loop())
await meridian.stop()    → _running = False, _task.cancel()
```

### 1.8 服务桥接（v1.40 P3）

```python
meridian.register_service(key, fn)
meridian.call_service(key, *args, **kwargs)
meridian.call_service_async(key, *args, **kwargs)
```

### ⚠️ 关键发现：`send_raw` 方法不存在

`MeridianRhythm.pulse()` 和 `StemScheduler.schedule()` 调用了 `meridian.send_raw()`，但 `Meridian` 类上**没有** `send_raw` 方法。这会导致运行时的 `AttributeError`。

**实际方法只有**: `send()`, `send_and_wait()`, `reply()`, `broadcast()`

---

## 2. 信号协议：Signal / SymbolRequest / SymbolResponse

### 2.1 两个 Signal 类并存（设计冗余）

| 位置 | 类名 | 字段数 | 用途 |
|------|------|--------|------|
| `src/hypothalamus/meridian.py` | `Signal` (dataclass) | 10 个字段 | 器官间信号总线 |
| `src/infra/protocol.py` | `Signal` (dataclass) | 6 个字段 | 象间通信（未使用） |

**代码证据**: 全代码库中所有 `Signal(...)` 构造都来自 `meridian.py` 的 Signal，没有任何代码使用 `protocol.py` 的 Signal。

### 2.2 SymbolRequest / SymbolResponse — 完全孤立

`src/infra/protocol.py` 定义了 `SymbolRequest` 和 `SymbolResponse`：

```python
@dataclass
class SymbolRequest:
    source: str, target: str, method: str
    params: Dict, timeout_ms: int, request_id: str

@dataclass
class SymbolResponse:
    success: bool, data: Any, error: str
    duration_ms: float, request_id: str
```

**唯一导出位置**: `src/services/__init__.py:68`  
```python
from src.infra.protocol import SymbolRequest, SymbolResponse
```

**全量搜索**: 没有任何实际业务代码 `import` 或使用这些类。它们仅在测试和 `services/__init__.py` 中被提及。

### 2.3 协议调用关系图

```
src/infra/protocol.py [定义 SymboRequest, SymbolResponse, Signal(第二版), SignalType 枚举]
        │
        ├─→ src/services/__init__.py  [符号导出 → 对外兼容层]
        │        │
        │        └─→ ⚠️ 全代码库中无实际调用点
        │
        └─→ ⚠️ 孤立定义：定义存在但无消费代码
```

---

## 3. SymbolBase 基类：实际继承者

**文件**: `src/infra/symbol_base.py` (58 行)

### 3.1 SymbolBase 核心定义

```python
class SymbolBase:
    def __init__(self, meridian, symbol_id, name, emoji, description):
        meridian.register_symbol(symbol_id, name, self)  # 自动注册到经络
    async def heartbeat(self):                # 心跳上报
    def get_status(self) -> dict:              # 健康状态
```

### 3.2 实际继承者（4 个，全部为四象模块）

| 类名 | 文件 | SymbolBase 提供的功能 | 实际使用 |
|------|------|----------------------|---------|
| `ShaoyangPipeline` | `src/shaoyang/pipeline.py` | 经络注册 + `get_status()` | ✅ 继承并重写 |
| `TaiyangRetrieval` | `src/taiyang/retrieval.py` | 经络注册 + `get_status()` | ✅ 继承并重写 |
| `ShaoyinBrain` | `src/shaoyin/brain.py` | 经络注册 + `get_status()` | ✅ 继承并重写 |
| `TaiyinServer` | `src/taiyin/server.py` | 经络注册 + `get_status()` | ✅ 继承并重写 |

### 3.3 哪些器官继承了 SymbolBase？

**答案：0 个。** 所有器官（HeartAgent, LiverAgent, KidneyAgent 等）继承的是 `OrganBase`，而非 `SymbolBase`。

```
     SymbolBase                          OrganBase
     (四象基类)                          (器官基类)
         │                                   │
    ┌────┼────┬────┐                    ┌────┼────┬── ... ──┐
    │    │    │    │                    │    │    │          │
  Shao- Tai- Shao- Tai-            Heart- Liver- Kidney-  Spleen-
  yang  yang  yin  yin            Agent  Agent  Agent    Agent
  Pipe- Ret- Brain Server         (心)   (肝)   (肾)     (脾)
  line  rieval
```

**设计意义**: 四象是高层抽象（管道/检索/决策/接口），通过 SymbolBase 注册到经络；器官是底层执行者，通过 OrganBase 注册到经络。两者通过 Meridian 通信，但没有继承关系。

---

## 4. `meridian.subscribe()` 全量调用点

> 注意: 代码库中**没有** `meridian.publish()` 方法，实际的发布方法是 `meridian.send()`。

### 4.1 器官订阅 — 信号层 (signal_layer.py)

每个器官在 `__init__` 中进行信号层订阅：

| 器官 (organ_id) | 订阅的信号类型 | 信号层文件 |
|----------------|--------------|-----------|
| **heart** | `heartbeat`, `check_health`, `store_memory`, `recall`, `user_preference` | `organs/heart/signal_layer.py` |
| **kidney** | `heartbeat`, `filter`, `purge`, `detect_deficiency` | `organs/kidney/signal_layer.py` |
| **liver** | `filter_results`, `learn_feedback`, `detect_fever`, `heartbeat` | `organs/liver/signal_layer.py` |
| **lung** | `new_nutrition`, `collect_health`, `organ_heartbeat`, `breathe`, `heartbeat` | `organs/lung/signal_layer.py` |
| **spleen** | `nutrition_ready`, `pump_wiki`, `data_purged`, `heartbeat` | `organs/spleen/signal_layer.py` |
| **skeleton** | `query_relations`, `build_relations`, `heartbeat` | `organs/skeleton/signal_layer.py` |
| **limbs** | `search`, `table_query`, `heartbeat` | `organs/limbs/signal_layer.py` |
| **nose** | `sniff`, `heartbeat` | `organs/nose/signal_layer.py` |
| **skin** | `heartbeat`, `check_request`, `search_external` | `organs/skin/signal_layer.py` |
| **gallbladder** | `decide_route`, `heartbeat` | `organs/gallbladder/signal_layer.py` |
| **small_intestine** | `nutrition_raw`, `heartbeat` | `organs/small_intestine/signal_layer.py` |
| **sanjiao** | `data_read`, `data_write`, `stats_collect`, `heartbeat` | `organs/sanjiao/signal_layer.py` |

### 4.2 大脑订阅

| 模块 | 订阅 | 文件 |
|------|------|------|
| **brain** | `heartbeat`, `query` | `src/hypothalamus/brain.py:224-225` |

### 4.3 四象注册（通过 SymbolBase 自动注册）

| 象 | 注册方式 | 文件 |
|----|---------|------|
| **shaoyang** | `SymbolBase.__init__` → `meridian.register_symbol()` | `shaoyang/pipeline.py` |
| **taiyang** | `SymbolBase.__init__` → `meridian.register_symbol()` | `taiyang/retrieval.py` |
| **shaoyin** | `SymbolBase.__init__` → `meridian.register_symbol()` | `shaoyin/brain.py` |
| **taiyin** | `SymbolBase.__init__` → `meridian.register_symbol()` | `taiyin/server.py` |

### 4.4 旧版扁平器官文件（代码重复）

旧版扁平文件 `organs/heart.py`、`organs/kidney.py` 等包含**完全相同的订阅代码**。例如：

```
organs/heart/signal_layer.py:  subscribe("heartbeat") + 4 个业务信号
organs/heart.py:               subscribe("heartbeat") + 4 个业务信号  ← 完全重复
```

**实际生效路径**: Fuxi 通过 `from src.hypothalamus.organs.heart import HeartAgent` → `organs/heart/__init__.py` → `from .signal_layer import HeartAgent`，所以是 signal_layer 版本生效。

但旧版 `.py` 文件仍存在且包含相同逻辑 — 形成了代码冗余。

---

## 5. `meridian.heartbeat()` 全量调用点

### 5.1 器官心跳 — 注册时发一次心跳（信号层）

每个器官在 `__init__` 末尾调用一次：

| 器官 | 文件位置 | 行号 |
|------|---------|------|
| gallbladder | `organs/gallbladder/signal_layer.py` | 56 |
| heart | `organs/heart/signal_layer.py` | 57 |
| kidney | `organs/kidney/signal_layer.py` | 84 |
| limbs | `organs/limbs/signal_layer.py` | 46 |
| liver | `organs/liver/signal_layer.py` | 51 |
| lung | `organs/lung/signal_layer.py` | 59 |
| nose | `organs/nose/signal_layer.py` | 52 |
| sanjiao | `organs/sanjiao/signal_layer.py` | 52 |
| skeleton | `organs/skeleton/signal_layer.py` | 43 |
| small_intestine | `organs/small_intestine/signal_layer.py` | 53 |
| spleen | `organs/spleen/signal_layer.py` | 48 |

### 5.2 器官心跳 — 持续循环中的心跳

| 器官 | 循环方式 | 心跳位置 | 心跳频率 |
|------|---------|---------|---------|
| **heart** | `_beat_loop()` | `heart/signal_layer.py:146` | 每 10 秒 |
| **kidney** | `_filter_loop()` | `kidney/signal_layer.py:158` | 每次过滤循环 |
| **lung** | `_breath_loop()` | `lung/signal_layer.py:206` | 每次呼吸循环 |
| **liver** | `_filter_loop()` | `liver/signal_layer.py:145` | 每次过滤循环 |
| **nose** | `_sniff_loop()` | `nose/signal_layer.py:219` | 每次嗅探循环 |
| **spleen** | `_pump_loop()` | `spleen/signal_layer.py:205` | 每次泵循环 |
| **small_intestine** | `_sort_loop()` | `small_intestine/signal_layer.py:206` | 每次循环 |
| **sanjiao** | `_flow_loop()` | `sanjiao/signal_layer.py:145` | 每次循环 |
| **gallbladder** | `_decide_loop()` | `gallbladder/signal_layer.py:146` | 每次循环 |
| **brain** | `_pulse_loop()` | `brain.py:507` | 每 15 秒 |
| **skin** | `_guard_loop()` | `skin/signal_layer.py:81` | 每次循环 |

### 5.3 四象心跳（通过 SymbolBase）

```python
# SymbolBase.heartbeat() → meridian.heartbeat(symbol_id)
```

每个四象模块继承此方法，但**搜索证据表明**实际代码中只在 `__init__`（构造时 `SymbolBase.__init__` 自动注册到经络）和 `get_status()` 中涉及心跳状态查询，**没有发现四象模块有主动循环调用 `self.heartbeat()` 的代码**。

### 5.4 心跳汇总：13 个心跳源

| 序号 | 实体 | 类型 | 持续心跳？ |
|-----|------|------|-----------|
| 1 | brain | 器官 | ✅ 每 15s |
| 2 | heart | 器官 | ✅ 每 10s |
| 3 | kidney | 器官 | ✅ 循环中 |
| 4 | liver | 器官 | ✅ 循环中 |
| 5 | lung | 器官 | ✅ 循环中 |
| 6 | nose | 器官 | ✅ 循环中 |
| 7 | spleen | 器官 | ✅ 循环中 |
| 8 | skeleton | 器官 | ⚠️ 仅 init 时一次 |
| 9 | limbs | 器官 | ⚠️ 仅 init 时一次 |
| 10 | skin | 器官 | ✅ 循环中 |
| 11 | gallbladder | 器官 | ✅ 循环中 |
| 12 | small_intestine | 器官 | ✅ 循环中 |
| 13 | sanjiao | 器官 | ✅ 循环中 |

**注意**: `skeleton` 和 `limbs` 在 init 中发送了一次心跳后，没有持续的 heartbeat 循环。

---

## 6. MeridianMonitor：谁启动的？

**文件**: `src/infra/meridian_monitor.py`

### 6.1 监控器设计

```python
class MeridianMonitor:
    record_signal(...)     # 记录信号和延迟
    record_timeout(...)    # 记录超时
    get_health_report()    # 健康报告
    get_symbol_stats()     # 各象统计
    get_latency_percentiles()  # P50/P90/P95/P99

# 全局单例
_monitor = None
def get_monitor(): ...  # 懒加载单例
```

### 6.2 谁 import 了 MeridianMonitor？

| 位置 | 导入方式 | 是否实际使用？ |
|------|---------|--------------|
| `src/services/__init__.py:71` | `from src.infra.meridian_monitor import MeridianMonitor` | 仅符号导出 |
| `src/taiyin/growth_api.py:45` | `from src.infra.meridian_monitor import get_monitor` | ✅ 在 `get_symbols_status()` 中 |
| `src/taiyin/mcp_tools.py:62` | `from src.infra.meridian_monitor import get_monitor` | ✅ 在健康指标收集中 |
| `src/services/eval_automation.py:102` | `from src.infra.meridian_monitor import get_monitor` | ✅ 在评估自动化中 |

### 6.3 谁启动了它？

**答案：没有人主动启动。** `MeridianMonitor` 使用懒加载单例模式 (`get_monitor()` 首次调用时才实例化)。它被以下 API 端点通过 HTTP 请求触发首次实例化：

```
GET /api/symbols/status  → get_symbols_status() → get_monitor() → MeridianMonitor()
    (src/server.py:294)

一些 MCP 工具调用          → mcp_tools.py → get_monitor()
```

### 6.4 关键问题：`record_signal()` 从未被调用

`MeridianMonitor` 的核心方法 `record_signal()` 和 `record_timeout()` **在 `Meridian._dispatch()` 中没有任何钩子调用它们**。

**证据**: 
- `meridian.py` 没有任何 `import meridian_monitor` 或调用 `record_signal`
- `meridian.py` 的 `_dispatch()` 方法中没有任何监控记录调用
- 全代码库搜索 `record_signal(` 只有定义，没有调用

**结论**: `MeridianMonitor` 是一个**外观完备但实际未接入信号总线**的监控器。它可以被动查询数据，但不会自动记录任何信号流事件。

---

## 7. 五行生克调度器：真的在运行吗？

**目录**: `src/hypothalamus/balance/`

### 7.1 三个调度器

| 文件 | 类名 | 功能 | 是否被 import？ | 是否被启动？ |
|------|------|------|---------------|------------|
| `five_elements.py` | `FiveElementsBalance` | 五行生克平衡监控 | ✅ `fuxi.py:35` | ✅ `fuxi.py:152` `await self.five_elements.start()` |
| `stem_scheduler.py` | `StemScheduler` | 天干时序调度 | ✅ `fuxi.py:36` | ✅ `fuxi.py:153` `await self.stem_scheduler.start()` |
| `meridian_rhythm.py` | `MeridianRhythm` | 经络流注节律 | ✅ `fuxi.py:37` | ✅ `fuxi.py:154` `await self.rhythm.start()` |

### 7.2 启动链

```
Fuxi.born()
  ├→ meridian.start()                    # 经络引擎
  ├→ 创建四象模块
  ├→ 创建 12 个器官
  ├→ five_elements = FiveElementsBalance(fuxi_instance)
  │    └→ await five_elements.start()     # 只是设 _running=True，没有实际循环
  ├→ stem_scheduler = StemScheduler(fuxi_instance)
  │    └→ await stem_scheduler.start()    # 创建 asyncio task → _loop() 每 5 分钟
  ├→ rhythm = MeridianRhythm(meridian)
  │    └→ await rhythm.start()            # 创建 asyncio task → _loop() 每 2 分钟
  └→ 启动各器官的自主循环
```

### 7.3 运行时行为分析

| 调度器 | 实际运行循环？ | 频率 | 实际作用 |
|--------|-------------|------|---------|
| `FiveElementsBalance` | ❌ `start()` 仅设 `_running=True`，无 `_loop()` | — | **不主动运行**，需外部显式调用 `check_balance()` 或 `auto_balance()` |
| `StemScheduler` | ✅ `_loop()` → `schedule()` | 每 300s | 调用 `organ.meridian.send_raw()` ← **会报错** |
| `MeridianRhythm` | ✅ `_loop()` → `pulse()` | 每 120s | 调用 `meridian.send_raw()` ← **会报错** |

### ⚠️ 阻塞性 Bug

```python
# meridian_rhythm.py:78
self.meridian.send_raw(flow["organ_id"], "rhythm_pulse", {...})
# meridian_rhythm.py:89
self.meridian.send_raw(oid, "heartbeat", {"source": "rhythm"})

# stem_scheduler.py:96
organ.meridian.send_raw(oid, "stem_pulse", {...})
```

**这三处调用的 `send_raw()` 方法在 `Meridian` 类上不存在**。唯一的方法是 `send(Signal(...))`。这些会在运行时抛出 `AttributeError: 'Meridian' object has no attribute 'send_raw'`。

---

## 8. GrowthEngine：实际调用点

**文件**: `src/growth/engine.py`

### 8.1 GrowthEngine 定义

```python
class GrowthEngine:
    record_event(symbol, metric, value, context)   # 写入 JSONL 日志
    record_search(...)      # 代理 → record_event("taiyang", ...)
    record_decision(...)    # 代理 → record_event("shaoyin", ...)
    record_extraction(...)  # 代理 → record_event("shaoyang", ...)
    record_request(...)     # 代理 → record_event("taiyin", ...)
    evaluate(symbol)        # 读取 JSONL 文件计算统计
    evaluate_all()          # 评估所有四象
    get_stats() / get_overview()  # 概览
```

### 8.2 谁 import 了 GrowthEngine？

```python
src/growth/__init__.py         → from .engine import GrowthEngine    # 包导出
src/services/__init__.py:74    → from src.growth.engine import GrowthEngine  # 兼容层导出
```

### 8.3 GrowthEngine() 实例化在哪？

**只有测试代码**:

```python
tests/test_core_modules.py:133   → engine = GrowthEngine()
tests/test_integration_chain.py:143 → engine = GrowthEngine()
```

### 8.4 四个子 Growth 类 — 依赖 GrowthEngine

| 类 | 文件 | 依赖 GrowthEngine | 谁实例化它们？ |
|----|------|-------------------|-------------|
| `RetrievalGrowth` | `src/growth/retrieval_growth.py` | 构造函数接收 `engine` | ❌ 无实例化 |
| `DecisionGrowth` | `src/growth/decision_growth.py` | 构造函数接收 `engine` | ❌ 无实例化 |
| `ExtractionGrowth` | `src/growth/extraction_growth.py` | 构造函数接收 `engine` | ❌ 无实例化 |
| `ExperienceGrowth` | `src/growth/experience_growth.py` | 构造函数接收 `engine` | ❌ 无实例化 |

**全量搜索**: `RetrievalGrowth(`, `DecisionGrowth(`, `ExtractionGrowth(` — 搜索结果为 **0**。

### 8.5 GrowthRecordPoints — 延迟导入但实际记录

```python
# taiyang/retrieval.py:111
from src.growth.growth_recorder import GrowthRecordPoints
# shaoyin/brain.py:113
from src.growth.growth_recorder import GrowthRecordPoints
# taiyin/server.py:54,73,114,136
from src.growth.growth_recorder import GrowthRecordPoints
```

这些是在方法内部的**延迟导入**，`GrowthRecordPoints` 是独立于 `GrowthEngine` 的记录点系统。

### 8.6 GrowthEngine 总结

| 方面 | 状态 |
|------|------|
| 类定义 | ✅ 完整 |
| 兼容层导出 | ✅ `services/__init__.py` |
| Fuxi 中引用 | ❌ 未引用 |
| 生产代码实例化 | ❌ 仅测试中实例化 |
| 子 Growth 类实例化 | ❌ 4 个子类均未实例化 |
| 实际写入数据 | ❌ `record_event()` 从未被调用 |

**结论**: `GrowthEngine` 及其 4 个子模块是 **Phase 1 准备的骨架代码**，定义了完整接口，但**尚未接入系统**。唯一的成长数据记录路径是 `GrowthRecordPoints`（独立于 GrowthEngine）。

---

## 9. 实际模块间调用关系图

### 9.1 启动时关系图（Fuxi.born()）

```
                               ┌─────────────────────┐
                               │   Fuxi (fuxi.py)     │
                               │   伏羲生命体启动器      │
                               └──────┬──────────────┘
                                      │ self.meridian = Meridian()
                                      │
                        ┌─────────────┼─────────────────────┐
                        │             │                     │
                   ┌────▼────┐  ┌─────▼──────┐    ┌────────▼─────────┐
                   │ Meridian │  │  四象模块    │    │  12 个器官 + Brain │
                   │ 经络总线  │  │   (4个)     │    │  (OrganBase系列)   │
                   └────┬────┘  └─────┬──────┘    └────────┬─────────┘
                        │             │                     │
                        │     ┌───────┼───────┐             │
                        │     │       │       │             │
                        │  SymbolBase Shaoyang Taiyang...   │
                        │  register_symbol()                │
                        │                                   │
                        │  register_organ() + subscribe()   │
                        │◄──────────────────────────────────┘
                        │
                  ┌─────▼──────────────────┐
                  │  balance/ 平衡调度器      │
                  │  ├ FiveElementsBalance  │ ← start() 设 flag，无实际循环
                  │  ├ StemScheduler ⚠️     │ ← _loop() 调用 send_raw() [BUG]
                  │  └ MeridianRhythm ⚠️    │ ← _loop() 调用 send_raw() [BUG]
                  └────────────────────────┘
```

### 9.2 信号流转图

```
  发送端                             Meridian 经络                           接收端
  ──────                            ────────────                           ──────
                                                                           
  organ.send(Signal(                                                         
    source="brain",                  ┌─── _queue ───┐                       
    target="limbs",                  │ (Priority    │                       
    signal_type="search",     ────►  │  Queue)      │  ────► _dispatch()   
    payload={...}                    └──────────────┘         │            
  ))                                                          │            
                                          ┌───────────────────┤            
                                          │                   │            
                                     target == "limbs"   target == "*"     
                                          │                   │            
                                    ┌─────▼─────┐     ┌─────▼─────┐      
                                    │ handlers:  │     │ 全器官广播  │      
                                    │ search + * │     │           │      
                                    └─────┬─────┘     └─────┬─────┘      
                                          │                   │            
                                    ┌─────▼──────────────────▼──────┐     
                                    │ handler(signal) 异步/同步调用   │     
                                    └────────────────────────────────┘     
                                                                           
  活跃的发送端（send 调用）：                                                
  ├ heart._heal() → "alert" → brain                                         
  ├ kidney → "filtered"/"purged"/"deficiency_alert"                         
  ├ liver → "fever_alert"                                                   
  ├ lung → "nutrition"/"health_report"                                      
  ├ nose → "breath_quality"                                                 
  ├ spleen → "pumped"/"wiki_ingested"                                       
  ├ skeleton → "relations_updated"                                          
  ├ small_intestine → "nutrition_stock", "stock_low"                        
  └ fuxi.digest_file() → "digest" → stomach                                 
```

### 9.3 心跳信号流

```
  持续心跳源（有实际循环的）：
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ brain    │  │ heart    │  │ kidney   │  │ liver    │
  │ 每 15s   │  │ 每 10s   │  │ 循环内   │  │ 循环内   │
  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
       │              │             │             │
  ┌────┼──────────────┼─────────────┼─────────────┼────────┐
  │    │          meridian.heartbeat(organ_id)             │
  │    │     → _organs[organ_id].last_heartbeat = now      │
  │    │     → _organs[organ_id].alive = True              │
  └────┼───────────────────────────────────────────────────┘
       │
  ┌────┼──────────────┬──────────────┬──────────────┐
  │lung│ nose │ spleen│ small_intestine│ gallbladder  │ sanjiao │
  │循环│ 循环 │ 循环   │ 循环           │ 循环         │ 循环    │
  └────┴──────┴───────┴───────────────┴──────────────┴────────┘

  仅 init 时发送心跳（无持续循环）：
  ┌──────────┐  ┌──────────┐
  │ skeleton │  │  limbs   │
  │ 一次     │  │  一次    │
  └──────────┘  └──────────┘
```

### 9.4 GrowthEngine 实际关系图

```
  src/growth/
  ├── engine.py          GrowthEngine         ← 仅测试中实例化
  ├── retrieval_growth.py RetrievalGrowth     ← 未实例化
  ├── decision_growth.py  DecisionGrowth      ← 未实例化
  ├── extraction_growth.py ExtractionGrowth   ← 未实例化
  ├── experience_growth.py ExperienceGrowth   ← 未实例化
  └── growth_recorder.py  GrowthRecordPoints  ← ✅ 实际使用

  GrowthRecordPoints 使用点：
  ├── taiyang/retrieval.py   (延迟导入)
  ├── shaoyin/brain.py       (延迟导入)
  └── taiyin/server.py       (延迟导入，4 处)

  GrowthEngine 导入但未实例化：
  └── services/__init__.py   (兼容层符号导出)
```

### 9.5 MeridianMonitor 实际关系图

```
  src/infra/meridian_monitor.py
  │
  ├── get_monitor() 单例模式
  │
  ├── 由谁首次实例化？
  │   ├── taiyin/growth_api.py → get_symbols_status()
  │   ├── taiyin/mcp_tools.py  → 健康指标收集
  │   └── services/eval_automation.py
  │
  ├── 由谁调用 record_signal()？
  │   └── ❌ 无人调用 — 监控器未接入 Meridian._dispatch()
  │
  └── 实际可用功能：
      └── get_health_report()   ✅ (被动查询，数据全为 0)
      └── get_latency_percentiles()  ✅ (空数据)
      └── get_symbol_stats()    ✅ (空数据)
```

---

## 总结：发现问题清单

### 🔴 阻塞性 Bug

1. **`send_raw()` 不存在**: `MeridianRhythm.pulse()` 和 `StemScheduler.schedule()` 调用 `meridian.send_raw()` 会在运行时抛 `AttributeError`。这两个调度器虽然被 `fuxi.py` 启动，但首次脉冲就会崩溃。

### 🟡 设计缺陷

2. **`FiveElementsBalance` 未实际运行**: `start()` 只设置 flag，没有 `_loop()` 或后台任务。除非外部主动调用 `check