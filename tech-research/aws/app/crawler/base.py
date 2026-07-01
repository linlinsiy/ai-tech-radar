"""
L0 采集基类模块

定义所有采集器的统一接口。支持 RSS 采集和网页采集两种模式。
每个采集器需要实现 fetch 方法，返回标准化文章列表。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import hashlib
from datetime import datetime
from urllib.parse import urlparse

from logging_config import get_logger

logger = get_logger("crawler.base")


@dataclass
class RawArticle:
    """
    采集到的原始文章数据结构

    类变量：
        source_code: 数据源编码
        title: 原始标题
        url: 原文链接
        _url_hash: URL SHA-256 哈希（自动计算）
        author: 作者
        publish_time: 原文发布时间
        crawl_time: 抓取时间
        raw_html: 原始 HTML（网页采集模式）
        raw_summary: RSS 自带摘要
        content_hash: 内容指纹，后续阶段计算
    """
    source_code: str
    title: str
    url: str
    _url_hash: str = field(default="", init=False, repr=True)
    author: Optional[str] = None
    publish_time: Optional[datetime] = None
    crawl_time: datetime = field(default_factory=datetime.now)
    raw_html: Optional[str] = None
    raw_summary: Optional[str] = None
    content_hash: Optional[str] = None

    def __post_init__(self):
        """自动计算 url_hash"""
        if not self._url_hash:
            object.__setattr__(
                self, "_url_hash",
                hashlib.sha256(self.url.encode("utf-8")).hexdigest()
            )

    @property
    def url_hash(self) -> str:
        """URL SHA-256 哈希，用于去重"""
        return self._url_hash

    @url_hash.setter
    def url_hash(self, value: str):
        """设置 URL 哈希（通常由 __post_init__ 自动计算）"""
        object.__setattr__(self, "_url_hash", value)

    def compute_content_hash(self, content: str):
        """计算内容指纹"""
        self.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()


class BaseCrawler(ABC):
    """
    采集器抽象基类

    类变量：
        source_code: 数据源编码
        source_name: 数据源名称
        domain: 采集域名，用于白名单校验
        access_url: RSS/API/网页地址
    """

    def __init__(self, source: Dict[str, str]):
        """
        初始化采集器

        入参：
            source: 数据源配置字典，含 code/name/access_url/domain/fetch_method
        """
        self.source_code = source["code"]
        self.source_name = source["name"]
        self.access_url = source.get("access_url", "")
        self.domain = source.get("domain", "")

    @abstractmethod
    def fetch(self) -> List[RawArticle]:
        """
        执行采集，返回文章列表

        出参：RawArticle 列表，采集失败返回空列表
        """
        ...

    def validate_domain(self, url: str, allowed_domains: List[str]) -> bool:
        """
        校验 URL 域名是否在白名单内

        入参：
            url: 目标 URL
            allowed_domains: 允许的域名列表
        出参：是否在白名单内
        """
        if not allowed_domains:
            return True
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(allowed in domain for allowed in allowed_domains)


class CrawlerFactory:
    """
    采集器工厂

    根据数据源配置创建对应的采集器实例。
    """

    @staticmethod
    def create(source: Dict[str, str]) -> BaseCrawler:
        """
        根据数据源配置创建采集器

        入参：
            source: 数据源配置字典，fetch_method 决定类型
        出参：BaseCrawler 子类实例
        """
        method = source.get("fetch_method", "rss")
        if method == "rss":
            from crawler.rss_crawler import RSSCrawler
            return RSSCrawler(source)
        elif method == "web":
            from crawler.web_crawler import WebCrawler
            return WebCrawler(source)
        elif method == "api":
            from crawler.api_crawler import APICrawler
            return APICrawler(source)
        else:
            logger.warning("未知采集方式: %s, 使用 RSS 兜底", method)
            from crawler.rss_crawler import RSSCrawler
            return RSSCrawler(source)
