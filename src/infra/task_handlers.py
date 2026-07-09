"""
伏羲 v1.44 — 任务处理器
======================
定义各种任务类型的处理器函数
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def handle_file_process(payload: Dict[str, Any]) -> Dict[str, Any]:
    """处理文件上传任务"""
    from src.shaoyang.pipeline import ShaoyangPipeline
    from src.bagua.intent_bus import IntentBus
    
    file_path = payload["file_path"]
    file_name = payload["file_name"]
    source = payload.get("source", "upload")
    
    logger.info(f"开始处理文件: {file_name}")
    
    try:
        # 通过少阳处理
        intent_bus = IntentBus()
        pipeline = ShaoyangPipeline(intent_bus)
        result = await pipeline.digest(file_path, source=source)
        
        logger.info(f"文件处理完成: {file_name}, chunks: {len(result.chunks)}")
        
        return {
            "file_name": file_name,
            "chunks": len(result.chunks),
            "duration_ms": result.duration_ms,
            "status": "completed"
        }
    except Exception as e:
        logger.error(f"文件处理失败: {file_name}, 错误: {e}")
        raise

async def handle_eval_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """处理评测任务"""
    from src.services.eval_automation import get_eval_automation
    
    trigger = payload.get("trigger", "unknown")
    user = payload.get("user", "anonymous")
    
    logger.info(f"开始执行评测，触发方式: {trigger}, 用户: {user}")
    
    try:
        automation = get_eval_automation()
        result = await automation.run_daily_eval()
        
        logger.info(f"评测执行完成: {result}")
        
        return {
            "trigger": trigger,
            "user": user,
            "result": result,
            "status": "completed"
        }
    except Exception as e:
        logger.error(f"评测执行失败: {e}")
        raise

async def handle_kb_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    """处理知识库更新任务"""
    # 这里可以添加知识库更新的逻辑
    logger.info(f"知识库更新任务: {payload}")
    
    # 暂时返回成功
    return {
        "status": "completed",
        "message": "知识库更新任务完成"
    }