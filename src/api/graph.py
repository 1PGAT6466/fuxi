# 兼容层 - 知识图谱路由
from fastapi import APIRouter, Query, Request

router = APIRouter(tags=["知识图谱"])

@router.get("/api/graph")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def graph(entity: str = Query(""), request: Request = None):
    """知识图谱查询"""
    from src.db.data_store import load_graph
    try:
        data = load_graph()
        nodes = data.get("nodes", {})
        edges = data.get("edges", [])
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if entity:
            filtered_nodes = {k: v for k, v in nodes.items() if entity.lower() in k.lower()}
            result = {"nodes": filtered_nodes, "edges": edges}
        else:
            result = {"nodes": nodes, "edges": edges}
        if _wants_v2:
            from src.api.response import success
            return success(data=result, message="知识图谱数据")
        return result
    except Exception as e:
        result = {"nodes": {}, "edges": [], "error": str(e)}
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import error
            return error("知识图谱查询失败", status_code=500, detail=str(e))
        return result
