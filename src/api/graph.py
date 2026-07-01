# 兼容层 - 知识图谱路由
from fastapi import APIRouter, Query

router = APIRouter(tags=["知识图谱"])

@router.get("/api/graph")
async def graph(entity: str = Query("")):
    """知识图谱查询"""
    from src.db.data_store import load_graph
    try:
        data = load_graph()
        nodes = data.get("nodes", {})
        edges = data.get("edges", [])
        if entity:
            # 过滤相关节点
            filtered_nodes = {k: v for k, v in nodes.items() if entity.lower() in k.lower()}
            return {"nodes": filtered_nodes, "edges": edges}
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        return {"nodes": {}, "edges": [], "error": str(e)}
