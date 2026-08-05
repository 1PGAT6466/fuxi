"""伏羲 - 工作流 API"""

from fastapi import APIRouter

router = APIRouter(tags=["工作流"])


@router.get("/api/workflows/")
async def list_workflows():
    return {"status": "success", "data": {"items": [], "total": 0}}


@router.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    return {"status": "success", "data": {"id": workflow_id, "name": "示例工作流", "steps": [], "status": "idle"}}


@router.post("/api/workflows/")
async def create_workflow(data: dict = None):
    return {"status": "success", "data": {"id": "wf_new", "name": "新建工作流", "steps": [], "status": "idle"}}


@router.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str):
    return {"status": "success", "data": {"execution_id": "exec_new", "status": "running"}}
