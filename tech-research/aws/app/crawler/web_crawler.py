"""
L0 网页采集器

用于量子位等不能通过 RSS 访问的数据源，通过 HTTP 抓取网页后解析文章列表。
当前实现量子位（www.qbitai.com）的首页文章列表解析，支持分页。
其他非 RSS 数据源可扩展 _parse_list_* 和 _parse_detail_* 私有方法。
"""
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from crawler.base import BaseCrawler, RawArticle

from logging_config import get_logger
logger = get_logger("crawler.web")


# ============================================================
# 量子位首页文章列表解析器
# 解析 qbitai.com 首页文章列表，提取标题 / 链接 / 时间 / 作者
# 支持分页：/page/2, /page/3 ...
# ============================================================

def _parse_qbitai_list(html: str, source_code: str, max_pages: int = 3) -> List[Dict]:
    """
    解析量子位文章列表（首页 + 分页）

    入参：
        html: 首页 HTML
        source_code: 数据源编码
        max_pages: 最大翻页数
    出参：文章信息字典列表 {title, url, author, time_str}
    """
    articles: List[Dict] = []
    seen_urls: set = set()

    def parse_page(soup: BeautifulSoup) -> None:
        """解析单页文章"""
        # 轮播 / 焦点文章 — 含 h3 标题的 swiper 区域
        for slide in soup.select("div.swiper-slide a[href]"):
            url = slide.get("href", "")
            if not url or url in seen_urls:
                continue
            h_tag = slide.find(["h3", "h4"])
            title = h_tag.get_text(strip=True) if h_tag else ""
            if not title:
                img = slide.find("img")
                title = img.get("alt", "") if img else ""
            if title and url:
                seen_urls.add(url)
                articles.append({"title": title, "url": url, "author": "", "time_str": ""})

        # 常规文章列表 — h4 含 a 链接，后跟 span.time
        for h_tag in soup.select("h4 a[href]"):
            url = h_tag.get("href", "")
            title = h_tag.get_text(strip=True)
            if not url or not title or url in seen_urls:
                continue
            parent_h4 = h_tag.find_parent("h4")
            time_span = parent_h4.find_next("span", class_="time") if parent_h4 else None
            time_str = time_span.get_text(strip=True) if time_span else ""
            seen_urls.add(url)
            articles.append({"title": title, "url": url, "author": "", "time_str": time_str})

        # 兼容：a[href] 直属 div 的文章卡片
        for link in soup.select('a[href*="qbitai.com/20"]'):
            url = link.get("href", "")
            title = link.get_text(strip=True)
            if url in seen_urls or not title or len(title) < 5:
                continue
            seen_urls.add(url)
            articles.append({"title": title, "url": url, "author": "", "time_str": ""})

    try:
        soup = BeautifulSoup(html, "lxml")
        parse_page(soup)

        # 分页抓取
        for page_num in range(2, max_pages + 1):
            try:
                resp = requests.get(
                    f"https://www.qbitai.com/page/{page_num}",
                    timeout=15,
                    headers={"User-Agent": "AI-Radar-Bot/1.0"},
                )
                if resp.status_code == 200:
                    page_soup = BeautifulSoup(resp.text, "lxml")
                    parse_page(page_soup)
                else:
                    break
            except Exception:
                break
    except Exception as e:
        logger.error("[%s] 量子位列表解析失败: %s", source_code, str(e))

    return articles


def _parse_qbitai_relative_time(time_str: str) -> Optional[datetime]:
    """
    解析量子位相对时间格式为 datetime

    入参：
        time_str: 时间字符串，如 "1小时前", "2天前", "2024-05-27"
    出参：datetime 对象，解析失败返回 None
    """
    if not time_str:
        return None
    now = datetime.now()
    time_str = time_str.strip()

    # 绝对日期：YYYY-MM-DD 或 YYYY/MM/DD
    abs_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", time_str)
    if abs_match:
        return datetime(int(abs_match.group(1)), int(abs_match.group(2)), int(abs_match.group(3)))

    # 相对时间
    rel_patterns = [
        (r"(\d+)小时前", "hours"),
        (r"(\d+)分钟前", "minutes"),
        (r"(\d+)天前", "days"),
        (r"(\d+)周前", "weeks"),
        (r"昨天", "days"),
    ]
    for pattern, unit in rel_patterns:
        match = re.search(pattern, time_str)
        if match:
            if pattern == "昨天":
                return now - timedelta(days=1)
            value = int(match.group(1))
            if unit == "hours":
                return now - timedelta(hours=value)
            elif unit == "minutes":
                return now - timedelta(minutes=value)
            elif unit == "days":
                return now - timedelta(days=value)
            elif unit == "weeks":
                return now - timedelta(weeks=value)

    return None


def _parse_qbitai_detail(html: str, source_code: str) -> Optional[Dict]:
    """
    解析量子位文章详情页，提取元数据和正文

    入参：
        html: 文章页 HTML
        source_code: 数据源编码
    出参：{title, author, publish_time, content} 字典，解析失败返回 None
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""

        author_el = soup.select_one("span.author a")
        author = author_el.get_text(strip=True) if author_el else ""

        time_el = soup.select_one("span.time")
        time_str = time_el.get_text(strip=True) if time_el else ""
        publish_time = _parse_qbitai_relative_time(time_str)

        content_div = soup.select_one("div.content")
        if content_div:
            for junk in content_div.select("script, style, .info, .tags_s, .swiper-container, .related-posts"):
                junk.decompose()
            content = content_div.get_text(separator="\n", strip=True)
            content = re.sub(r"\n{3,}", "\n\n", content)
        else:
            content = soup.get_text(separator="\n", strip=True)

        return {
            "title": title,
            "author": author,
            "publish_time": publish_time,
            "content": content,
        }
    except Exception as e:
        logger.error("[%s] 量子位详情页解析失败: %s", source_code, str(e))
        return None


class WebCrawler(BaseCrawler):
    """
    网页采集器

    通过 HTTP GET 获取网页，解析文章列表。
    当前已实现量子位（liangziwei）的解析，其他数据源可扩展。

    类变量：
        timeout: 请求超时秒数
        max_pages: 最大翻页数
        max_articles: 最大采集篇数
    """

    def __init__(self, source: Dict[str, str]):
        """
        初始化网页采集器

        入参：
            source: 数据源配置字典
        """
        super().__init__(source)
        self.timeout = 30
        self.max_pages = 3
        self.max_articles = 100

    def fetch(self) -> List[RawArticle]:
        """
        执行网页采集

        出参：RawArticle 列表

        根据 source_code 选择解析器：
            liangziwei → 解析 qbitai.com
            其他 → 返回空列表（需适配）
        """
        logger.info(
            "[%s] 网页采集: %s",
            self.source_code, self.access_url
        )

        try:
            resp = requests.get(
                self.access_url,
                timeout=self.timeout,
                headers={"User-Agent": "AI-Radar-Bot/1.0"},
            )
            resp.encoding = resp.apparent_encoding or "utf-8"
            resp.raise_for_status()
            logger.info("[%s] 网页获取成功", self.source_code)
        except Exception as e:
            logger.error("[%s] 网页获取失败: %s", self.source_code, str(e))
            return []

        articles: List[RawArticle] = []

        if self.source_code == "liangziwei":
            articles = self._fetch_qbitai(resp.text)
        else:
            logger.warning(
                "[%s] 网页解析未实现（source_code=%s），返回空列表",
                self.source_code, self.source_code
            )

        return articles

    def _fetch_qbitai(self, html: str) -> List[RawArticle]:
        """
        量子位采集流程：列表解析 → 详情抓取 → RawArticle 组装

        入参：
            html: 首页 HTML
        出参：RawArticle 列表
        """
        article_dicts = _parse_qbitai_list(html, self.source_code, self.max_pages)
        logger.info("[%s] 量子位列表解析：%d 篇", self.source_code, len(article_dicts))

        results: List[RawArticle] = []
        for ad in article_dicts[: self.max_articles]:
            author = ad.get("author", "")
            publish_time = _parse_qbitai_relative_time(ad.get("time_str", ""))

            # 若列表页无时间，则抓取详情页提取
            if publish_time is None and ad["url"]:
                try:
                    detail_resp = requests.get(
                        ad["url"], timeout=self.timeout,
                        headers={"User-Agent": "AI-Radar-Bot/1.0"},
                    )
                    detail_resp.encoding = detail_resp.apparent_encoding or "utf-8"
                    detail = _parse_qbitai_detail(detail_resp.text, self.source_code)
                    if detail:
                        author = author or detail.get("author", "")
                        publish_time = publish_time or detail.get("publish_time")
                except Exception:
                    pass

            publish_time = publish_time or datetime.now()

            article = RawArticle(
                source_code=self.source_code,
                title=ad["title"],
                url=ad["url"],
                author=author if author else None,
                publish_time=publish_time,
            )
            results.append(article)

        logger.info("[%s] 量子位采集完成：%d 篇", self.source_code, len(results))
        return results
