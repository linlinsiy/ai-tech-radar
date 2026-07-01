"""
AWS 侧 - 数据源健康检查 Job

aiRadarHealthCheckJob: 每 30 分钟检查各数据源可达性，
写入 app.log，不可达数据源记录到 error.log。
"""
import logging
from typing import Dict, List, Any
import requests
from datetime import datetime

from config import AWSConfig

from logging_config import get_logger
logger = get_logger("jobs.health_check")


def check_single_source(source: Dict[str, str], timeout: int = 15) -> Dict:
    """
    检查单个数据源可达性

    入参：
        source: 数据源配置
        timeout: 超时秒数
    出参：{"code": "...", "name": "...", "reachable": bool, "latency_ms": float, "error": str}
    """
    code = source["code"]
    name = source["name"]
    url = source.get("access_url", "")

    if not url:
        logger.debug("[%s] access_url 为空，跳过检查", code)
        return {"code": code, "name": name, "reachable": True, "latency_ms": 0, "error": ""}

    try:
        start = datetime.now()
        resp = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "AI-Radar-HealthCheck/1.0"},
        )
        elapsed = (datetime.now() - start).total_seconds() * 1000
        reachable = resp.status_code < 500
        return {
            "code": code,
            "name": name,
            "reachable": reachable,
            "latency_ms": round(elapsed, 1),
            "error": "" if reachable else f"HTTP {resp.status_code}",
        }
    except requests.Timeout:
        return {"code": code, "name": name, "reachable": False, "latency_ms": timeout * 1000, "error": "timeout"}
    except Exception as e:
        return {"code": code, "name": name, "reachable": False, "latency_ms": 0, "error": str(e)[:200]}


def handle_health_check_job(params: str = "") -> Dict[str, Any]:
    """
    XXL-Job JobHandler: aiRadarHealthCheckJob

    入参：
        params: 调度参数（预留）
    出参：健康检查统计
    """
    config = AWSConfig()
    sources = config.get_data_sources()

    logger.info("====== 数据源健康检查开始 ======")
    logger.info("检查 %d 个数据源...", len(sources))

    results = []
    reachable_count = 0
    unreachable_sources = []

    for source in sources:
        result = check_single_source(source)
        results.append(result)
        if result["reachable"]:
            reachable_count += 1
        else:
            unreachable_sources.append(result["code"])
            logger.error(
                "[%s] 数据源不可达: %s",
                result["code"], result["error"]
            )

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": len(sources),
        "reachable": reachable_count,
        "unreachable": len(sources) - reachable_count,
        "unreachable_sources": unreachable_sources,
    }

    logger.info(
        "健康检查完成: reachable=%d/%d, unreachable=%s",
        reachable_count, len(sources),
        unreachable_sources if unreachable_sources else "无"
    )

    return summary
