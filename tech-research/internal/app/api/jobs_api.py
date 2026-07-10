"""
内部侧手动触发任务接口。

用于绕过 XXL-Job，由本地 crontab 或人工通过 HTTP 触发简报生成。
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger("api.jobs")
router = APIRouter()


class BriefingJobRequest(BaseModel):
    """简报生成任务请求体"""

    briefing_type: str = Field(
        default="weekly",
        description="简报类型: weekly | monthly | quarterly | topic"
    )
    from_date: Optional[str] = Field(
        default=None,
        description="覆盖开始日期，格式 YYYY-MM-DD，可选"
    )
    to_date: Optional[str] = Field(
        default=None,
        description="覆盖结束日期，格式 YYYY-MM-DD，可选"
    )


@router.post("/api/v1/jobs/briefing")
async def trigger_briefing(request: BriefingJobRequest):
    """
    手动触发简报生成任务。

    入参：
        request: BriefingJobRequest
    出参：
        {success: bool, data: 执行统计} 或 {success: bool, error: str}
    """
    params_str = json.dumps(request.model_dump(), ensure_ascii=False)
    logger.info("手动触发简报生成: %s", params_str)

    try:
        from jobs.briefing_job import handle_briefing_job
        result = handle_briefing_job(params_str)
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception("简报生成执行异常")
        return {"success": False, "error": str(e)}
