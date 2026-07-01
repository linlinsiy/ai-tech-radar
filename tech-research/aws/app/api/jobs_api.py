"""
手动触发任务接口

提供绕过 XXL-Job 直接触发采集分析和健康检查的 HTTP 端点。
用于本地开发调试，以及 XXL-Job Admin 无法直连执行器时的替代方案。

接口：
    POST /api/v1/jobs/collect      手动触发采集分析
    POST /api/v1/jobs/health-check  手动触发健康检查
"""
import logging
import json
from typing import Optional
from pydantic import BaseModel, Field

from logging_config import get_logger
logger = get_logger("api.jobs")


# ============================================================
# 请求模型
# ============================================================

class CollectJobRequest(BaseModel):
    """
    采集分析任务请求体

    字段：
        scope: 采集范围，all | sources | timerange（默认 all）
        sources: 数据源编码列表，逗号分隔
        from_date: 开始日期 YYYY-MM-DD（可与 sources 组合使用）
        to_date: 结束日期 YYYY-MM-DD（可与 sources 组合使用）
        task_type: 任务类型（默认 manual_backfill）
    """
    scope: str = Field(
        default="all",
        description="采集范围: all | sources | timerange"
    )
    sources: Optional[str] = Field(
        default=None,
        description="数据源编码，逗号分隔，如 aws-ml-blog,arxiv-cs-ai"
    )
    from_date: Optional[str] = Field(
        default=None,
        description="开始日期 YYYY-MM-DD"
    )
    to_date: Optional[str] = Field(
        default=None,
        description="结束日期 YYYY-MM-DD"
    )
    task_type: str = Field(
        default="manual_backfill",
        description="任务类型: scheduled | manual_backfill"
    )


# ============================================================
# 路由处理函数
# ============================================================

async def trigger_collect(request: CollectJobRequest):
    """
    手动触发采集分析任务

    POST /api/v1/jobs/collect

    入参：
        request: CollectJobRequest, JSON 请求体
    出参：
        {success: bool, data: 各阶段执行统计} 或 {success: bool, error: str}

    调用示例：
        curl -X POST http://localhost:9003/api/v1/jobs/collect ^
             -H "Content-Type: application/json" ^
             -d "{\"scope\":\"all\"}"

        curl -X POST http://localhost:9003/api/v1/jobs/collect ^
             -H "Content-Type: application/json" ^
             -d "{\"scope\":\"all\",\"sources\":\"xin-zhi-yuan,aws-ml-blog\",\"from_date\":\"2026-06-20\",\"to_date\":\"2026-06-22\"}"
    """
    # 将请求模型转为 collect_job 接受的 JSON 参数字符串
    params = request.model_dump()
    # handle_collect_job 接受 JSON 字符串参数
    params_str = json.dumps(params, ensure_ascii=False)
    logger.info("手动触发采集分析: %s", params_str)

    try:
        from jobs.collect_job import handle_collect_job
        result = handle_collect_job(params_str)
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception("采集分析执行异常")
        return {"success": False, "error": str(e)}


async def trigger_health_check():
    """
    手动触发数据源健康检查

    POST /api/v1/jobs/health-check

    出参：
        {success: bool, data: 各数据源可达性汇总} 或 {success: bool, error: str}

    调用示例：
        curl -X POST http://localhost:9003/api/v1/jobs/health-check
    """
    logger.info("手动触发健康检查")

    try:
        from jobs.health_check_job import handle_health_check_job
        result = handle_health_check_job()
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception("健康检查执行异常")
        return {"success": False, "error": str(e)}
