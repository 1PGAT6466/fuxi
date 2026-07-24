import sys
sys.path.insert(0, '.')
from src.services.coreference_resolver import CoreferenceResolver
import asyncio

r = CoreferenceResolver()

# Debug 1: "功耗？" with PLC history
history_plc = [
    {'role': 'user', 'content': 'PLC-200 是什么？'},
    {'role': 'assistant', 'content': 'PLC-200 是一款高性能可编程逻辑控制器。'},
    {'role': 'user', 'content': '它的主要参数有哪些？'},
    {'role': 'assistant', 'content': 'PLC-200 支持 32 路 IO，工作温度 -20~70°C。'},
]
entities = r._extract_entities_from_history(history_plc)
print(f'plc entities: {entities}')
print(f'_needs("功耗？"): {r._needs_resolution("功耗？")}')

# Debug 2: multi-entity history
h2 = [
    {'role': 'user', 'content': '伺服电机和步进电机的区别？'},
    {'role': 'assistant', 'content': '伺服电机精度更高，步进电机成本更低。'},
    {'role': 'user', 'content': '伺服电机配套的驱动器推荐？'},
    {'role': 'assistant', 'content': '推荐 ACD-2000 系列驱动器，支持多种反馈。'},
]
entities2 = r._extract_entities_from_history(h2)
print(f'\nmotor entities: {entities2}')
for msg in reversed(h2):
    e = r._extract_key_entities(msg['content'])
    print(f'  {msg["role"]} "{msg["content"]}" -> {e}')

async def test():
    print(f'\nresolve("功耗？"): "{await r.resolve("功耗？", history_plc)}"')
    print(f'resolve("它的价格？"): "{await r.resolve("它的价格？", h2)}"')

asyncio.run(test())
