"""
示例插件 - 主入口
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/api/plugins/example/hello")
async def hello_handler():
    """示例接口 - 返回问候语"""
    return {
        "success": True,
        "message": "你好！这是示例插件的接口",
        "data": {
            "plugin": "example-plugin",
            "version": "1.0.0",
            "timestamp": "2026-07-31"
        }
    }

def on_installed(data):
    """插件安装事件处理"""
    print(f"示例插件已安装: {data}")
