"""
受控导入客户端

将 AWS 侧加工的结构化成果打包为 JSON，POST 到内部受控导入接口。
支持重试、错误分类和部分失败处理。
"""
import json
import time
import logging
from typing import List, Dict, Any, Optional
import requests
from requests.exceptions import RequestException, Timeout

from logging_config import get_logger
logger = get_logger("exporter.import_client")


class ImportClient:
    """
    受控导入客户端

    组装 batch + articles + analyses + insights 请求体，
    发送到内部受控导入接口，处理重试和错误响应。

    类变量：
        endpoint_url: 内部导入接口地址
        timeout: 请求超时秒数
        retry_max: 最大重试次数
        backoff_seconds: 重试退避时间列表
    """

    def __init__(
        self,
        endpoint_url: str,
        timeout: int = 300,
        retry_max: int = 2,
        backoff_seconds: List[int] = None,
    ):
        """
        初始化导入客户端

        入参：
            endpoint_url: 内部导入接口完整 URL
            timeout: 请求超时秒数
            retry_max: 最大重试次数
            backoff_seconds: 退避时间列表，如 [10, 30]
        """
        self.endpoint_url = endpoint_url
        self.timeout = timeout  # modified to 300s for KB upload
        self.retry_max = retry_max
        self.backoff_seconds = backoff_seconds or [10, 30]

    def build_payload(
        self,
        batch_no: str,
        task_type: str,
        source_scope: List[str],
        articles: List[Dict[str, Any]],
        analyses: List[Dict[str, Any]],
        insights: List[Dict[str, Any]],
        operation_metrics: Optional[Dict[str, Any]] = None,
        collection_batch_no: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        strategy: Optional[str] = None,
        collection_period: Optional[str] = None,
        snapshot_path: Optional[str] = None,
        replace_insights_for_analyses: bool = False,
        replace_insight_article_url_hashes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        构建受控导入请求体

        入参：
            batch_no: 批次号
            task_type: scheduled / manual_backfill
            source_scope: 数据源编码列表
            articles: 文章数据列表（含 url_hash）
            analyses: 分析结果列表（含 article_url_hash）
            insights: 深度洞察列表（含 article_url_hash）
        出参：完整请求体字典
        """
        payload = {
            "batch": {
                "batch_no": batch_no,
                "task_type": task_type,
                "source_scope": source_scope,
                "collection_batch_no": collection_batch_no,
                "from_date": from_date,
                "to_date": to_date,
                "strategy": strategy,
                "collection_period": collection_period,
                "snapshot_path": snapshot_path,
            },
            "articles": articles,
            "analyses": analyses,
            "insights": insights,
        }
        if replace_insights_for_analyses:
            payload["batch"]["replace_insights_for_analyses"] = True
        if replace_insight_article_url_hashes:
            payload["batch"]["replace_insight_article_url_hashes"] = (
                replace_insight_article_url_hashes
            )
        if operation_metrics is not None:
            payload["operation_metrics"] = operation_metrics
        return payload

    def import_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行导入并处理重试

        入参：
            payload: 完整请求体
        出参：{"success": bool, "response": {...}, "error": str}
        """
        batch_no = payload.get("batch", {}).get("batch_no", "unknown")
        logger.info("开始导入: batch_no=%s, articles=%d, analyses=%d, insights=%d",
                     batch_no,
                     len(payload.get("articles", [])),
                     len(payload.get("analyses", [])),
                     len(payload.get("insights", [])))

        last_error = None
        for attempt in range(self.retry_max + 1):
            try:
                resp = requests.post(
                    self.endpoint_url,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 200:
                    result = resp.json()
                    code = result.get("code", -1)
                    message = result.get("message", "")

                    if code == 0:
                        data = result.get("data", {})
                        logger.info(
                            "导入成功: batch_no=%s, status=%s, success=%d, failed=%d",
                            batch_no,
                            data.get("import_status", "N/A"),
                            data.get("success_count", 0),
                            data.get("failed_count", 0),
                        )
                        return {"success": True, "response": result}

                    elif message == "batch_already_exists":
                        logger.info("批次已存在，幂等返回: batch_no=%s", batch_no)
                        return {"success": True, "response": result}

                    else:
                        logger.warning("导入接口返回非预期 code: %d, message=%s", code, message)

                elif resp.status_code == 400:
                    logger.error("导入参数校验失败: %s", resp.text[:500])
                    return {"success": False, "error": "validation_error", "response": resp.json() if resp.text else {}}

                elif resp.status_code == 413:
                    logger.error("请求体过大: 需拆分批次")
                    return {"success": False, "error": "payload_too_large", "detail": "request body too large"}

                elif resp.status_code == 503:
                    last_error = f"503 service_unavailable: {resp.text[:200]}"
                    logger.warning("导入服务不可用 (attempt %d): %s", attempt + 1, last_error)

                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning("导入异常响应 (attempt %d): %s", attempt + 1, last_error)

            except Timeout:
                last_error = "timeout"
                logger.warning("导入请求超时 (attempt %d)", attempt + 1)
            except RequestException as e:
                last_error = f"network_error: {str(e)[:200]}"
                logger.warning("导入网络异常 (attempt %d): %s", attempt + 1, str(e)[:200])

            # 重试退避
            if attempt < self.retry_max:
                wait = (
                    self.backoff_seconds[attempt]
                    if attempt < len(self.backoff_seconds)
                    else 60
                )
                logger.info("等待 %d 秒后重试...", wait)
                time.sleep(wait)

        logger.error("导入最终失败: batch_no=%s, error=%s", batch_no, last_error)
        return {"success": False, "error": last_error or "max_retries_exceeded"}
