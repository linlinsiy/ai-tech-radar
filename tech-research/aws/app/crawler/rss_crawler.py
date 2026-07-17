"""
L0 RSS 采集器

基于 feedparser 解析 RSS/Atom Feed，返回标准化的 RawArticle 列表。
支持白名单域名校验和采集异常容错。
"""
import logging
import feedparser
import time
import requests
from typing import List, Dict, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from crawler.base import BaseCrawler, RawArticle

from logging_config import get_logger
logger = get_logger("crawler.rss")


def _safe_int(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

RSS_REQUEST_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": (
        "application/rss+xml, application/atom+xml, application/xml, "
        "text/xml, text/html;q=0.8, */*;q=0.5"
    ),
}

ALLOWED_CONTENT_TYPES = (
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
    "application/rdf+xml",
    "text/html",
)


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
        self.source = dict(source)
        self.timeout = _safe_int(source.get("timeout_seconds"), 20)
        # 仅作为异常 Feed 的技术保护，不参与最终报告来源均衡。
        self.max_articles = _safe_int(
            source.get("_candidate_limit", source.get("max_articles")), 100
        )
        self.rss_detail_fetch = str(source.get("rss_detail_fetch", "false")).lower() == "true"

    def _request_feed(self, url: str):
        """请求 RSS URL，统一设置浏览器 UA、超时和重定向。"""
        response = requests.get(
            url,
            timeout=self.timeout,
            headers=RSS_REQUEST_HEADERS,
            allow_redirects=True,
        )
        self.last_http_status = response.status_code
        self.last_effective_url = response.url
        return response

    @staticmethod
    def _is_allowed_content_type(content_type: str) -> bool:
        """判断响应是否为可尝试解析的 RSS/Atom/XML/HTML 内容。"""
        normalized = (content_type or "").split(";")[0].strip().lower()
        return not normalized or normalized in ALLOWED_CONTENT_TYPES

    @staticmethod
    def _extract_feed_from_html(html: str, base_url: str) -> Optional[str]:
        """
        从 HTML 中提取 RSS 内容。

        支持两类情况：
        1. HTML 页面中直接嵌入了 RSS/Atom XML 片段；
        2. HTML 通过 <link rel="alternate" type="application/rss+xml"> 指向真实 feed。
        """
        if not html:
            return None

        lowered = html.lower()
        starts = [
            lowered.find("<?xml"),
            lowered.find("<rss"),
            lowered.find("<feed"),
        ]
        starts = [idx for idx in starts if idx >= 0]
        if starts:
            return html[min(starts):]

        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("link"):
            rel = " ".join(link.get("rel", [])).lower()
            link_type = (link.get("type") or "").lower()
            href = link.get("href")
            if not href:
                continue
            if "alternate" in rel and (
                "rss" in link_type or "atom" in link_type or "xml" in link_type
            ):
                return urljoin(base_url, href)
        return None

    @staticmethod
    def _parse_feed(content: str, response_headers: Optional[Dict[str, str]] = None):
        """使用 feedparser 容错解析；兼容旧 feedparser 版本的参数差异。"""
        try:
            return feedparser.parse(
                content,
                response_headers=response_headers or {},
                reject_unsafe_xml=False,
                resolve_entities=False,
            )
        except TypeError:
            logger.debug("当前 feedparser 版本不支持 reject_unsafe_xml/resolve_entities，使用兼容解析")
            return feedparser.parse(content, response_headers=response_headers or {})

    def _load_feed(self):
        """下载并解析 RSS/Atom 内容，兼容 text/html 中的 feed 链接或嵌入内容。"""
        resp = self._request_feed(self.access_url)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not self._is_allowed_content_type(content_type):
            logger.warning(
                "[%s] Content-Type 不在允许范围，仍尝试解析: %s",
                self.source_code,
                content_type or "unknown",
            )

        normalized_type = content_type.split(";")[0].strip().lower()
        content = resp.text
        feed_url = resp.url

        if normalized_type == "text/html":
            extracted = self._extract_feed_from_html(content, resp.url)
            if extracted and extracted.startswith(("http://", "https://")):
                logger.info("[%s] HTML 中发现 RSS 链接: %s", self.source_code, extracted)
                feed_resp = self._request_feed(extracted)
                feed_resp.raise_for_status()
                content = feed_resp.text
                feed_url = feed_resp.url
                content_type = feed_resp.headers.get("Content-Type", content_type)
            elif extracted:
                logger.info("[%s] HTML 中发现内嵌 RSS/Atom 内容", self.source_code)
                content = extracted
            else:
                logger.warning("[%s] text/html 响应中未发现 RSS/Atom 内容", self.source_code)

        return self._parse_feed(content, response_headers={"content-location": feed_url})

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
            feed = self._load_feed()
        except requests.Timeout:
            self.last_error = f"request timeout after {self.timeout}s"
            logger.error("[%s] RSS 请求超时: timeout=%ss", self.source_code, self.timeout)
            return []
        except requests.RequestException as e:
            self.last_error = str(e)
            logger.error("[%s] RSS 请求失败: %s", self.source_code, str(e))
            return []
        except Exception as e:
            self.last_error = str(e)
            logger.error("[%s] RSS 解析失败: %s", self.source_code, str(e))
            return []

        self.collection_diagnostics.update({
            "feed_entries": len(feed.entries),
            "feed_bozo": bool(feed.bozo),
        })

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

    def fetch_candidates(self, candidates: List[RawArticle]) -> List[RawArticle]:
        """对摘要型 RSS 按配置补读详情页，其他 RSS 保持原始内容。"""
        if not self.rss_detail_fetch or not candidates:
            return candidates

        from crawler.web_crawler import WebCrawler

        detail_source = dict(self.source)
        detail_source["fetch_method"] = "web"
        crawler = WebCrawler(detail_source)
        articles = crawler.fetch_candidates(candidates)
        self.collection_diagnostics["rss_detail_fetch"] = True
        self.collection_diagnostics["rss_detail"] = dict(crawler.collection_diagnostics)
        return articles
