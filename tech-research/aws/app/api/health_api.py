"""
AWS 侧健康检查端点

GET /health

检查亚马逊云侧各组件连通性：
- 数据源可达性（对各源域名发起 HTTP HEAD 检测）
- 外部模型 API 连通性
- 内部导入端点连通性
"""
import os
import logging
import time
import asyncio
from datetime import datetime
from typing import Optional

import httpx

from config import AWSConfig

from logging_config import get_logger
logger = get_logger("health_api")

# 健康检查 timeout（秒）
CHECK_TIMEOUT = 10


async def _check_data_sources(config: AWSConfig) -> dict:
    """
    检查数据源可达性

    入参：config AWSConfig 实例
    出参：{total, reachable, unreachable, details}
    """
    sources = config.get_data_sources()
    reachable = 0
    unreachable = 0
    details = []
    proxy = config.proxy_url
    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT, follow_redirects=True, proxy=proxy) as client:
        for src in sources:
            domain = src.get("domain", "")
            access_url = src.get("access_url", "")
            url = access_url or f"https://{domain}" if domain else ""
            if not url:
                unreachable += 1
                details.append({
                    "code": src["code"],
                    "status": "unreachable",
                    "error": "no URL configured"
                })
                continue
            try:
                start = time.time()
                resp = await client.head(url)
                latency_ms = int((time.time() - start) * 1000)
                if resp.status_code < 500:
                    reachable += 1
                    details.append({
                        "code": src["code"],
                        "status": "reachable",
                        "latency_ms": latency_ms
                    })
                else:
                    unreachable += 1
                    details.append({
                        "code": src["code"],
                        "status": "unreachable",
                        "http_status": resp.status_code
                    })
            except Exception as e:
                unreachable += 1
                details.append({
                    "code": src["code"],
                    "status": "unreachable",
                    "error": f"{type(e).__name__}: {str(e)}"[:200]
                })
    return {
        "total": len(sources),
        "reachable": reachable,
        "unreachable": unreachable,
        "details": details,
    }


async def _check_external_llm(config: AWSConfig) -> dict:
    """
    检查外部模型 API 连通性

    入参：config AWSConfig 实例
    出参：{reachable, models, latency_ms}
    """
    base_url = os.environ.get("OPENAI_BASE_URL", config.get(option="l2_model.base_url", fallback="https://api.openai.com/v1"))
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return {"status": "misconfigured", "error": "OPENAI_API_KEY not set"}

    try:
        import openai
        client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=CHECK_TIMEOUT)
        start = time.time()
        models = client.models.list()
        latency_ms = int((time.time() - start) * 1000)
        model_ids = [m.id for m in models.data[:10]]
        return {
            "status": "healthy",
            "models": model_ids,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": f"{type(e).__name__}: {str(e)}"[:200]}


async def _check_import_endpoint(config: AWSConfig) -> dict:
    """
    检查内部导入端点连通性

    入参：config AWSConfig 实例
    出参：{url, status, latency_ms}
    """
    url = config.get(option="import_endpoint.url", fallback="")
    if not url:
        return {"status": "misconfigured", "error": "import_endpoint.url not set"}
    # 从导入端点 URL 中提取 base URL（scheme://host:port）用于健康检查
    from urllib.parse import urlparse
    parsed = urlparse(url)
    health_url = f"{parsed.scheme}://{parsed.netloc}/health"

    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT) as client:
            start = time.time()
            resp = await client.get(health_url)
            latency_ms = int((time.time() - start) * 1000)
            return {
                "status": "reachable" if resp.status_code == 200 else "degraded",
                "url": url,
                "latency_ms": latency_ms,
                "http_status": resp.status_code,
            }
    except Exception as e:
        return {"status": "unreachable", "url": url, "error": f"{type(e).__name__}: {str(e)}"[:200]}


async def health_check(config = None):
    """
    健康检查端点（用于 FastAPI 路由注册）

    入参：config 可选 AWSConfig 实例
    出参：各组件状态汇总
    """
    if config is None:
        try:
            config = AWSConfig.get_instance()
        except Exception:
            from config import AWSConfig as Cfg
            config = Cfg()

   
    checks = {}

    # 数据源检查
    try:
        checks["data_sources"] = await _check_data_sources(config)
    except Exception as e:
        checks["data_sources"] = {"status": "error", "error": f"{type(e).__name__}: {str(e)}"[:200]}

    # 外部 LLM 检查
    try:
        checks["external_llm"] = await _check_external_llm(config)
    except Exception as e:
        checks["external_llm"] = {"status": "error", "error": f"{type(e).__name__}: {str(e)}"[:200]}

    # 导入端点检查
    try:
        checks["import_endpoint"] = await _check_import_endpoint(config)
    except Exception as e:
        checks["import_endpoint"] = {"status": "error", "error": f"{type(e).__name__}: {str(e)}"[:200]}

    overall = "healthy" if all(
        c.get("status") in ("healthy", "reachable", "pending")
        for c in checks.values()
    ) else "degraded"

    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }
