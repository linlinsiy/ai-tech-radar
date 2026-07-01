"""
内部侧 - 任务状态查询 API
"""
import logging
from fastapi import APIRouter
from api.task_tracker import TaskTracker

logger = logging.getLogger("task_api")
router = APIRouter()


@router.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务执行状态

    入参：
        task_id: 任务 ID（通常为 batch_no）
    出参：任务状态、进度、各阶段耗时
    """
    task = TaskTracker.get(task_id)
    if task is None:
        return {"code": 404, "message": "task_not_found", "data": None}

    return {"code": 0, "message": "ok", "data": task}


@router.get("/api/v1/tasks")
async def list_tasks(limit: int = 20):
    """
    列出最近任务

    入参：
        limit: 返回条数，默认 20
    出参：任务列表
    """
    tasks = TaskTracker.list_recent(limit)
    return {"code": 0, "message": "ok", "data": {"tasks": tasks, "count": len(tasks)}}
