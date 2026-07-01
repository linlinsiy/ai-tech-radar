"""
任务状态追踪服务

使用内存字典记录每个 batch 的处理状态，供调度平台轮询。
实际生产可替换为 Redis 或 MySQL。
"""
import logging
import threading
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("task_tracker")

# 全局任务状态存储
_tasks: Dict[str, Dict] = {}
_lock = threading.Lock()


class TaskTracker:
    """任务状态追踪器（线程安全的内存实现）"""

    @staticmethod
    def create(
        task_id: str,
        scope: str = "all",
        sources: list = None,
    ) -> Dict:
        """
        创建任务记录

        入参：
            task_id: 任务 ID
            scope: 任务范围
            sources: 数据源列表
        出参：任务状态字典
        """
        with _lock:
            task = {
                "task_id": task_id,
                "scope": scope,
                "status": "pending",
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
                "progress": {
                    "phase": "init",
                    "sources_total": len(sources) if sources else 0,
                    "sources_done": 0,
                    "articles_collected": 0,
                },
                "stats": {},
            }
            _tasks[task_id] = task
            logger.info("创建任务: %s", task_id)
            return task

    @staticmethod
    def update(task_id: str, **kwargs):
        """更新任务状态"""
        with _lock:
            if task_id in _tasks:
                _tasks[task_id].update(kwargs)

    @staticmethod
    def update_progress(task_id: str, **kwargs):
        """更新进度信息"""
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["progress"].update(kwargs)

    @staticmethod
    def mark_phase(task_id: str, phase: str):
        """标记当前阶段"""
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["progress"]["phase"] = phase

    @staticmethod
    def mark_completed(task_id: str, stats: Dict = None):
        """标记任务完成"""
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["completed_at"] = datetime.now().isoformat()
                if stats:
                    _tasks[task_id]["stats"] = stats

    @staticmethod
    def mark_failed(task_id: str, error: str = ""):
        """标记任务失败"""
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["error"] = error
                _tasks[task_id]["completed_at"] = datetime.now().isoformat()

    @staticmethod
    def get(task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return _tasks.get(task_id)

    @staticmethod
    def list_recent(limit: int = 20) -> list:
        """获取最近任务列表"""
        items = sorted(_tasks.values(), key=lambda t: t.get("started_at", ""), reverse=True)
        return items[:limit]
