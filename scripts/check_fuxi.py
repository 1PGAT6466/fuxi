import sys
sys.path.insert(0, '/home/feng-shaoxuan/kb-server')
from src.server import _fuxi_instance
print("fuxi:", _fuxi_instance)
if _fuxi_instance and _fuxi_instance.meridian:
    m = _fuxi_instance.meridian
    for oid, info in m._organs.items():
        alive = m.is_alive(oid)
        print(f"  {oid}: alive={alive} signals={info.signals_received}")
