"""
L0 RSS 采集器

基于 feedparser 解析 RSS/Atom Feed，返回标准化的 RawArticle 列表。
支持白名单域名校验和采集异常容错。
"""
import logging
import feedparser
import time
from typing import List, Dict, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from crawler.base import BaseCrawler, RawArticle

from logging_config import get_logger
logger = get_logger("crawler.rss")


class RSSCrawler(BaseCrawler):
    """
    RSS Feed 采集器

    解析标准 RSS 2.0 / Atom Feed，提取标题、链接、作者、发布时间、
    RSS 自带摘要等字段，组装为 RawArticle 列表。

    类变量：
        timeout: 请求超时秒数
        max_articles: 单次最大采集文章数
    """

    def __init__(self, source: Dict[str, str]):
        """
        初始化 RSS 采集器

        入参：
            source: 数据源配置字典
        """
        super().__init__(source)
        self.timeout = 30
        self.max_articles = 100

    def fetch(self) -> List[RawArticle]:
        """
        执行 RSS 采集

        出参：RawArticle 列表，采集失败返回空列表
        """
        if not self.access_url:
            logger.warning("[%s] access_url 为空，跳过采集", self.source_code)
            return []

        logger.info("[%s] 开始 RSS 采集: %s", self.source_code, self.access_url)

        try:
            feed = feedparser.parse(self.access_url)
        except Exception as e:
            logger.error("[%s] RSS 解析失败: %s", self.source_code, str(e))
            return []

        # 检查 feed 解析状态
        if feed.bozo and not feed.entries:
            logger.warning(
                "[%s] Feed 解析异常: %s",
                self.source_code,
                str(feed.bozo_exception)[:200] if feed.bozo_exception else "unknown"
            )
            if feed.bozo:
                # 有异常但仍有条目，继续处理
                pass

        articles = []
        for entry in feed.entries[:self.max_articles]:
            try:
                url = entry.get("link", "")
                if not url:
                    continue

                # 域名白名单校验
                if self.domain and self.domain not in urlparse(url).netloc:
                    logger.debug("[%s] 域名不匹配，跳过: %s", self.source_code, url)
                    continue

                # 解析发布时间
                publish_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    publish_time = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    publish_time = datetime(*entry.updated_parsed[:6])
                elif hasattr(entry, "published"):
                    try:
                        publish_time = parsedate_to_datetime(entry.published)
                    except Exception:
                        pass

                # 提取摘要（RSS description 或 summary）
                raw_summary = entry.get("summary") or entry.get("description") or ""


                # 提取全文（RSS content:encoded 或 Atom content）
                raw_html = None
                if hasattr(entry, "content") and entry.content:
                    # feedparser 将 content:encoded 标准化为 entry.content 列表
                    raw_html = entry.content[0].get("value", "") or None

                # 提取作者
                author = entry.get("author") or ""
                if not author and hasattr(entry, "authors"):
                    authors = entry.authors
                    if authors:
                        author = authors[0].get("name", "")

                article = RawArticle(
                    source_code=self.source_code,
                    title=entry.get("title", "Untitled"),
                    url=url,
                    author=author if author else None,
                    publish_time=publish_time,
                    raw_summary=raw_summary,
                    raw_html=raw_html,
                )
                articles.append(article)

            except Exception as e:
                logger.warning(
                    "[%s] 解析条目失败: %s, %s",
                    self.source_code,
                    entry.get("link", "unknown"),
                    str(e)
                )
                continue

        logger.info(
            "[%s] RSS 采集完成: collected=%d",
            self.source_code,
            len(articles)
        )
        return articles
