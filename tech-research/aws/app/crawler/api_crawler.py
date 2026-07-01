"""
L0 API 采集器（骨架）

用于通过 REST API 获取文章列表的数据源。
首期提供骨架，后续按具体 API 规范适配。
"""
import logging
from typing import List, Dict
from crawler.base import BaseCrawler, RawArticle

from logging_config import get_logger
logger = get_logger("crawler.api")


class APICrawler(BaseCrawler):
    """
    API 采集器

    通过 HTTP API 获取文章列表。
    首期提供骨架实现。

    类变量：
        timeout: 请求超时秒数
    """

    def __init__(self, source: Dict[str, str]):
        """
        初始化 API 采集器

        入参：
            source: 数据源配置字典
        """
        super().__init__(source)
        self.timeout = 30

    def fetch(self) -> List[RawArticle]:
        """
        执行 API 采集

        出参：RawArticle 列表

        TODO: 实现具体 API 调用逻辑
        """
        logger.info(
            "[%s] API 采集（骨架）: %s",
            self.source_code, self.access_url
        )
        logger.warning(
            "[%s] API 采集未实现，返回空列表（需按数据源适配）",
            self.source_code
        )
        return []
