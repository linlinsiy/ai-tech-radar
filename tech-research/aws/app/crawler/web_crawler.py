"""
L0 HTML 网页采集器

用于补充 RSS 不稳定或不可用的数据源。采集器仍输出 RawArticle，
因此后续 L1 去重、L2 分类评分、L3 深度分析和内部导入链路无需感知采集方式。
"""
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html

from crawler.base import BaseCrawler, RawArticle
from crawler.browser_fetcher import BrowserFetcher

from logging_config import get_logger
logger = get_logger("crawler.web")


BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

WEB_REQUEST_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}

COMMON_LIST_SELECTORS = [
    "article",
    ".article-item",
    ".post-item",
    ".news-item",
    ".list-item",
    ".feed-item",
    ".item",
    ".post",
    ".media",
    "li",
]

COMMON_CONTENT_SELECTORS = [
    "article",
    "main",
    "[role='main']",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".content",
    ".article",
    ".news-content",
    ".detail-content",
    ".main-content",
    "#content",
]

COMMON_TITLE_SELECTORS = ["h1", ".article-title", ".post-title", ".title"]
COMMON_AUTHOR_SELECTORS = [".author", ".article-author", ".post-author", ".name"]
COMMON_TIME_SELECTORS = ["time", ".time", ".date", ".publish-time", ".pub-time", ".article-time"]

JUNK_SELECTORS = (
    "script, style, nav, header, footer, aside, iframe, form, "
    ".share, .shares, .comment, .comments, .related, .recommend, "
    ".advert, .ad, .ads, .breadcrumb, .pagination"
)

BLOCKED_PATH_KEYWORDS = (
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/topic/",
    "/topics/",
    "/author/",
    "/about",
    "/login",
    "/register",
    "/search",
    "/video",
    "/live",
)

BLOCKED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".css",
    ".js",
    ".pdf",
    ".zip",
    ".rar",
)


def _split_keywords(value: str) -> List[str]:
    """解析逗号/分号分隔的关键词配置。"""
    if not value:
        return []
    normalized = value.replace("，", ",").replace("；", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _split_selectors(value: str, defaults: Iterable[str]) -> List[str]:
    """解析 CSS 选择器配置；多个选择器使用竖线分隔，避免和 CSS 逗号冲突。"""
    if not value:
        return list(defaults)
    return [item.strip() for item in value.split("|") if item.strip()]


def _safe_int(value: str, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _safe_float(value: str, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _normalize_url(url: str) -> str:
    """去掉 URL fragment，减少同页锚点导致的重复。"""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def _parse_datetime_text(text: str) -> Optional[datetime]:
    """兼容常见中文相对时间和绝对日期格式。"""
    if not text:
        return None

    raw = re.sub(r"\s+", " ", text).strip()
    now = datetime.now()

    relative_patterns = [
        (r"(\d+)\s*分钟前", "minutes"),
        (r"(\d+)\s*小时前", "hours"),
        (r"(\d+)\s*天前", "days"),
        (r"(\d+)\s*周前", "weeks"),
    ]
    for pattern, unit in relative_patterns:
        match = re.search(pattern, raw)
        if not match:
            continue
        value = int(match.group(1))
        if unit == "minutes":
            return now - timedelta(minutes=value)
        if unit == "hours":
            return now - timedelta(hours=value)
        if unit == "days":
            return now - timedelta(days=value)
        if unit == "weeks":
            return now - timedelta(weeks=value)

    if "昨天" in raw:
        return now - timedelta(days=1)
    if "前天" in raw:
        return now - timedelta(days=2)

    absolute_patterns = [
        r"(\d{4})-(\d{1,2})-(\d{1,2})[T\s](\d{1,2}):(\d{1,2})",
        r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})",
    ]
    for pattern in absolute_patterns:
        match = re.search(pattern, raw)
        if not match:
            continue
        parts = [int(p) for p in match.groups()]
        if len(parts) >= 5:
            return datetime(parts[0], parts[1], parts[2], parts[3], parts[4])
        return datetime(parts[0], parts[1], parts[2])

    return None


def _clean_text(text: str) -> str:
    """规整页面文本。"""
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class WebCrawler(BaseCrawler):
    """
    配置化 HTML 网页采集器。

    支持的数据源配置项：
    - fetch_method=web/html
    - list_selector、link_selector、title_selector、time_selector、author_selector
    - detail_content_selector、detail_title_selector、detail_time_selector、detail_author_selector
    - page_url_pattern：分页 URL 模板，使用 {page} 占位
    - max_pages、max_articles、timeout_seconds、request_interval_seconds
    - include_keywords、exclude_keywords：用于粗筛列表标题
    """

    def __init__(self, source: Dict[str, str]):
        super().__init__(source)
        self.source = source
        self.timeout = _safe_int(source.get("timeout_seconds", ""), 20)
        self.max_pages = _safe_int(source.get("max_pages", ""), 1)
        self.max_articles = _safe_int(
            source.get("_detail_limit", source.get("max_articles", "")), 30
        )
        self.candidate_limit = _safe_int(
            source.get("_candidate_limit", source.get("max_articles", "")),
            self.max_articles,
        )
        self.request_interval = _safe_float(source.get("request_interval_seconds", ""), 1.0)
        self.page_url_pattern = source.get("page_url_pattern", "").strip()
        self.next_page_selectors = _split_selectors(source.get("next_page_selector", ""), [])
        self.list_link_xpath = source.get("list_link_xpath", "").strip()
        self.list_title_xpath = source.get("list_title_xpath", "").strip()
        self.xpath_strict = str(source.get("xpath_strict", "false")).lower() == "true"
        self.article_url_pattern = source.get("article_url_pattern", "").strip()
        self._article_url_regex = None
        if self.article_url_pattern:
            try:
                self._article_url_regex = re.compile(self.article_url_pattern)
            except re.error as exc:
                logger.warning(
                    "[%s] article_url_pattern 无效，忽略该约束: %s",
                    self.source_code,
                    str(exc),
                )

        self.list_selectors = _split_selectors(source.get("list_selector", ""), [])
        self.link_selectors = _split_selectors(source.get("link_selector", ""), [])
        self.title_selectors = _split_selectors(source.get("title_selector", ""), [])
        self.time_selectors = _split_selectors(source.get("time_selector", ""), [])
        self.author_selectors = _split_selectors(source.get("author_selector", ""), [])

        self.detail_content_selectors = _split_selectors(
            source.get("detail_content_selector", ""),
            COMMON_CONTENT_SELECTORS,
        )
        self.detail_title_selectors = _split_selectors(
            source.get("detail_title_selector", ""),
            COMMON_TITLE_SELECTORS,
        )
        self.detail_time_selectors = _split_selectors(
            source.get("detail_time_selector", ""),
            COMMON_TIME_SELECTORS,
        )
        self.detail_author_selectors = _split_selectors(
            source.get("detail_author_selector", ""),
            COMMON_AUTHOR_SELECTORS,
        )
        self.include_keywords = _split_keywords(source.get("include_keywords", ""))
        self.exclude_keywords = _split_keywords(source.get("exclude_keywords", ""))
        self.detail_content_reject_keywords = _split_keywords(
            source.get("detail_content_reject_keywords", "")
        )

        self.browser_fallback_enabled = str(
            source.get("_browser_fallback_enabled", source.get("browser_fallback", "false"))
        ).lower() == "true"
        self.browser_min_content_chars = _safe_int(
            source.get("_browser_min_content_chars", ""), 300
        )
        self.browser_fetcher = BrowserFetcher(
            timeout_seconds=_safe_int(source.get("_browser_timeout_seconds", ""), 45),
            executable_path=source.get("_browser_executable_path", ""),
        )
        self.challenge_max_pages = max(
            1, _safe_int(source.get("challenge_max_pages", ""), 1)
        )
        self._prefer_browser_after_timeout = False
        self._detail_challenge_open = False
        self._last_access_challenge = False
        self.collection_diagnostics.update({
            "http_timeouts": 0,
            "browser_attempts": 0,
            "browser_successes": 0,
            "access_challenges": 0,
            "challenge_urls": [],
        })

        self.session = requests.Session()
        self.request_headers = dict(WEB_REQUEST_HEADERS)
        referer = source.get("referer", "").strip()
        if referer:
            self.request_headers["Referer"] = referer

    def fetch(self) -> List[RawArticle]:
        """执行 HTML 采集，返回标准 RawArticle 列表。"""
        candidates = self.discover_candidates()
        return self.fetch_candidates(candidates[: self.max_articles])

    def discover_candidates(self) -> List[RawArticle]:
        """只解析列表元数据，不请求文章详情页。"""
        if not self.access_url:
            logger.warning("[%s] access_url 为空，跳过网页采集", self.source_code)
            return []

        logger.info("[%s] 开始 HTML 候选发现: %s", self.source_code, self.access_url)

        candidates = self._collect_candidates()
        if not candidates:
            logger.warning("[%s] HTML 列表未解析到候选文章", self.source_code)
            return []

        results = [
            RawArticle(
                source_code=self.source_code,
                title=str(candidate.get("title") or "Untitled"),
                url=str(candidate.get("url") or ""),
                author=str(candidate.get("author") or "") or None,
                publish_time=(
                    candidate.get("publish_time")
                    if isinstance(candidate.get("publish_time"), datetime) else None
                ),
                raw_summary=str(candidate.get("summary") or "") or None,
            )
            for candidate in candidates[: self.candidate_limit]
            if candidate.get("url")
        ]
        logger.info("[%s] HTML 候选发现完成: %d 篇", self.source_code, len(results))
        return results

    def fetch_candidates(self, candidates: List[RawArticle]) -> List[RawArticle]:
        """读取已选候选的详情页正文。"""
        items = [{
            "title": article.title,
            "url": article.url,
            "author": article.author or "",
            "publish_time": article.publish_time,
            "summary": article.raw_summary or "",
        } for article in candidates]
        return self.fetch_urls(items)

    def _request_html(self, url: str) -> Optional[str]:
        """请求 HTML 页面，统一使用浏览器 UA。"""
        self._last_access_challenge = False
        html = None
        if not (self.browser_fallback_enabled and self._prefer_browser_after_timeout):
            try:
                resp = self.session.get(
                    url,
                    timeout=self.timeout,
                    headers=self.request_headers,
                    allow_redirects=True,
                )
                self.last_http_status = resp.status_code
                self.last_effective_url = resp.url
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                html = resp.text
            except requests.Timeout:
                self.last_error = f"request timeout after {self.timeout}s"
                self.collection_diagnostics["http_timeouts"] += 1
                if self.browser_fallback_enabled:
                    self._prefer_browser_after_timeout = True
                logger.warning("[%s] HTML 请求超时: %s", self.source_code, url)
            except requests.RequestException as e:
                self.last_error = str(e)
                logger.warning("[%s] HTML 请求失败: %s, %s", self.source_code, url, str(e))

        if html and self._is_access_challenge(html):
            self._record_access_challenge(url)
            return None

        if self.browser_fallback_enabled and self._needs_browser_fallback(html):
            logger.info("[%s] 启用浏览器降级采集: %s", self.source_code, url)
            self.collection_diagnostics["browser_attempts"] += 1
            rendered = self.browser_fetcher.fetch_html(url)
            if rendered and self._is_access_challenge(rendered):
                self._record_access_challenge(url)
                return None
            if rendered:
                self.last_error = ""
                self.collection_diagnostics["browser_successes"] += 1
                return rendered
        return html

    @staticmethod
    def _is_access_challenge(html: Optional[str]) -> bool:
        """识别验证码和访问挑战页；不尝试绕过站点访问控制。"""
        lowered = (html or "").lower()
        return any(marker in lowered for marker in (
            "ttgcaptcha",
            "captcha/index.js",
            "verify_center",
            "cf-chl-",
            "challenge-platform",
            "滑块验证",
        ))

    def _record_access_challenge(self, url: str) -> None:
        self._last_access_challenge = True
        self.last_error = "access challenge or captcha page"
        self.collection_diagnostics["access_challenges"] += 1
        challenge_urls = self.collection_diagnostics["challenge_urls"]
        if len(challenge_urls) < 3:
            challenge_urls.append(url)
        if self.collection_diagnostics["access_challenges"] >= self.challenge_max_pages:
            self._detail_challenge_open = True
        logger.warning(
            "[%s] 检测到验证码/访问挑战页，停止本批后续正文请求: %s",
            self.source_code,
            url,
        )

    def _needs_browser_fallback(self, html: Optional[str]) -> bool:
        """请求失败、正文过短或明显 JS 空壳时使用浏览器渲染。"""
        if not html:
            return True
        try:
            text = _clean_text(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
        except Exception:
            text = ""
        lowered = html.lower()
        js_shell = any(marker in lowered for marker in (
            "enable javascript",
            "please turn javascript on",
            "id=\"__next\"",
            "id=\"app\"></div>",
        ))
        return len(text) < self.browser_min_content_chars or js_shell

    def fetch_urls(self, candidates: List[Dict[str, object]]) -> List[RawArticle]:
        """抓取已发现的详情页 URL，不重新扫描列表页。"""
        results: List[RawArticle] = []
        for candidate in candidates:
            url = str(candidate.get("url") or "")
            if not self._is_allowed_article_url(url):
                continue
            if self._detail_challenge_open:
                # 保留候选元数据，后续批次可重试；本批不重复触发验证码页面。
                results.append(self._build_article_from_metadata(candidate))
                continue
            article = self._build_article(candidate)
            if article:
                results.append(article)
            if self.request_interval > 0:
                time.sleep(self.request_interval)
        return results

    def _build_article_from_metadata(self, candidate: Dict[str, object]) -> RawArticle:
        return RawArticle(
            source_code=self.source_code,
            title=str(candidate.get("title") or "Untitled"),
            url=str(candidate.get("url") or ""),
            author=str(candidate.get("author") or "") or None,
            publish_time=(
                candidate.get("publish_time")
                if isinstance(candidate.get("publish_time"), datetime) else None
            ),
            raw_summary=str(candidate.get("summary") or "") or None,
        )

    def _list_page_urls(self) -> List[str]:
        """生成列表页 URL。"""
        urls = [self.access_url]
        if self.page_url_pattern and self.max_pages > 1:
            for page in range(2, self.max_pages + 1):
                urls.append(self.page_url_pattern.format(page=page))
        return urls

    def _collect_candidates(self) -> List[Dict[str, object]]:
        """抓取列表页并解析候选文章。"""
        candidates: List[Dict[str, object]] = []
        seen_urls = set()

        page_urls = self._list_page_urls()
        seen_pages = set()
        page_index = 0
        while page_index < len(page_urls) and len(seen_pages) < self.max_pages:
            page_url = page_urls[page_index]
            page_index += 1
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            html = self._request_html(page_url)
            if not html:
                continue

            for item in self._parse_list_page(html, page_url):
                url = item["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(item)
                if len(candidates) >= self.candidate_limit:
                    return candidates

            for next_url in self._next_page_urls(html, page_url):
                if next_url not in seen_pages and next_url not in page_urls:
                    page_urls.append(next_url)

            if self.request_interval > 0:
                time.sleep(self.request_interval)

        return candidates

    def _next_page_urls(self, html: str, base_url: str) -> List[str]:
        """从已配置的“下一页”链接发现有限分页，避免只抓首页。"""
        if not self.next_page_selectors:
            return []
        soup = BeautifulSoup(html, "lxml")
        urls = []
        for selector in self.next_page_selectors:
            try:
                links = soup.select(selector)
            except Exception:
                logger.warning("[%s] next_page_selector 无效: %s", self.source_code, selector)
                continue
            for link in links:
                href = link.get("href", "")
                url = _normalize_url(urljoin(base_url, href)) if href else ""
                parsed = urlparse(url)
                if (
                    url and parsed.scheme in ("http", "https")
                    and (not self.domain or self.domain in parsed.netloc)
                ):
                    urls.append(url)
        return list(dict.fromkeys(urls))

    def _parse_list_page(self, html: str, base_url: str) -> List[Dict[str, object]]:
        """解析列表页候选文章。"""
        if self.list_link_xpath:
            xpath_candidates = self._parse_xpath_list_page(html, base_url)
            if xpath_candidates or self.xpath_strict:
                return xpath_candidates

        soup = BeautifulSoup(html, "lxml")
        candidates: List[Dict[str, object]] = []

        containers = []
        for selector in self.list_selectors:
            containers.extend(soup.select(selector))
        if not containers:
            for selector in COMMON_LIST_SELECTORS:
                containers.extend(soup.select(selector))

        for node in containers:
            item = self._candidate_from_node(node, base_url)
            if item:
                candidates.append(item)

        # 对结构不稳定页面兜底：直接扫描所有链接。
        if len(candidates) < min(5, self.candidate_limit):
            for item in self._candidate_from_links(soup, base_url):
                candidates.append(item)

        deduped: List[Dict[str, object]] = []
        seen = set()
        for item in candidates:
            url = item["url"]
            if url in seen:
                continue
            seen.add(url)
            deduped.append(item)
        return deduped

    def _parse_xpath_list_page(
        self,
        html: str,
        base_url: str,
    ) -> List[Dict[str, object]]:
        """解析验证策略提供的 XPath；正式源仍默认使用 CSS 选择器。"""
        try:
            tree = lxml_html.fromstring(html)
            href_values = tree.xpath(self.list_link_xpath)
            title_values = tree.xpath(self.list_title_xpath) if self.list_title_xpath else []
        except (ValueError, TypeError, etree.XPathError) as exc:
            logger.warning("[%s] XPath 解析失败: %s", self.source_code, str(exc))
            return []

        candidates = []
        for index, href_value in enumerate(href_values):
            if hasattr(href_value, "get"):
                href = href_value.get("href", "")
                node_title = href_value.get("title", "") or href_value.text_content()
            else:
                href = str(href_value or "")
                node_title = ""

            url = self._normalize_article_url(href, base_url)
            if not self._is_allowed_article_url(url):
                continue

            title_value = title_values[index] if index < len(title_values) else node_title
            if hasattr(title_value, "text_content"):
                title = title_value.text_content()
            else:
                title = str(title_value or "")
            title = _clean_text(title)
            if not self._is_allowed_title(title):
                continue

            candidates.append({
                "title": title,
                "url": url,
                "author": "",
                "publish_time": None,
                "summary": "",
            })

        deduped = []
        seen = set()
        for item in candidates:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            deduped.append(item)
        logger.info(
            "[%s] XPath 列表解析完成: links=%d, candidates=%d",
            self.source_code,
            len(href_values),
            len(deduped),
        )
        return deduped

    def _candidate_from_node(self, node, base_url: str) -> Optional[Dict[str, object]]:
        """从列表卡片节点中提取候选文章。"""
        if getattr(node, "name", "") == "a" and node.get("href"):
            link = node
        else:
            link = (
                self._select_first(node, self.link_selectors)
                if self.link_selectors else node.find("a", href=True)
            )
        if not link:
            return None

        url = self._normalize_article_url(link.get("href", ""), base_url)
        if not self._is_allowed_article_url(url):
            return None

        title = self._extract_title(node, link)
        if not self._is_allowed_title(title):
            return None

        time_text = self._select_text(node, self.time_selectors or COMMON_TIME_SELECTORS)
        author = self._select_text(node, self.author_selectors or COMMON_AUTHOR_SELECTORS)
        summary = self._extract_node_summary(node, title)

        return {
            "title": title,
            "url": url,
            "author": author,
            "publish_time": _parse_datetime_text(time_text),
            "summary": summary,
        }

    def _candidate_from_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, object]]:
        """直接扫描页面链接作为兜底候选。"""
        candidates: List[Dict[str, object]] = []
        for link in soup.find_all("a", href=True):
            url = self._normalize_article_url(link.get("href", ""), base_url)
            if not self._is_allowed_article_url(url):
                continue
            title = link.get_text(separator=" ", strip=True)
            if not title:
                image = link.find("img")
                title = image.get("alt", "").strip() if image else ""
            if not self._is_allowed_title(title):
                continue
            candidates.append({
                "title": title,
                "url": url,
                "author": "",
                "publish_time": None,
                "summary": "",
            })
        return candidates

    def _normalize_article_url(self, href: str, base_url: str) -> str:
        """转为绝对 URL 并去除 fragment。"""
        if not href:
            return ""
        return _normalize_url(urljoin(base_url, href.strip()))

    def _is_allowed_article_url(self, url: str) -> bool:
        """过滤明显不是文章详情页的链接。"""
        if not url:
            return False

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        if self.domain and self.domain not in parsed.netloc:
            return False

        path = parsed.path.lower()
        if not path or path == "/":
            return False
        if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS):
            return False
        if any(keyword in path for keyword in BLOCKED_PATH_KEYWORDS):
            return False
        if self._article_url_regex and not self._article_url_regex.search(url):
            return False
        if url.rstrip("/") == self.access_url.rstrip("/"):
            return False

        return True

    def _is_allowed_title(self, title: str) -> bool:
        """按标题质量和关键词粗筛候选文章。"""
        title = (title or "").strip()
        if len(title) < 6:
            return False

        normalized = title.lower()
        blocked_titles = {"首页", "更多", "登录", "注册", "关于我们", "加入我们", "联系我们"}
        if title in blocked_titles:
            return False
        if self.exclude_keywords and any(keyword.lower() in normalized for keyword in self.exclude_keywords):
            return False
        if self.include_keywords and not any(keyword.lower() in normalized for keyword in self.include_keywords):
            return False
        return True

    def _extract_title(self, node, link) -> str:
        """从列表卡片中提取标题。"""
        for selector in self.title_selectors:
            selected = node.select_one(selector)
            if selected:
                return selected.get_text(separator=" ", strip=True)

        for selector in ("h1", "h2", "h3", "h4", ".title"):
            selected = node.select_one(selector)
            if selected:
                title = selected.get_text(separator=" ", strip=True)
                if title:
                    return title

        title = link.get_text(separator=" ", strip=True)
        if title:
            return title

        image = link.find("img")
        return image.get("alt", "").strip() if image else ""

    @staticmethod
    def _select_first(node, selectors: Iterable[str]):
        """按选择器顺序返回第一个命中节点。"""
        for selector in selectors:
            if not selector:
                continue
            selected = node.select_one(selector)
            if selected:
                return selected
        return None

    @staticmethod
    def _select_text(node, selectors: Iterable[str]) -> str:
        """按选择器顺序提取第一个非空文本。"""
        for selector in selectors:
            if not selector:
                continue
            selected = node.select_one(selector)
            if selected:
                text = selected.get("datetime") or selected.get_text(separator=" ", strip=True)
                if text:
                    return text.strip()
        return ""

    @staticmethod
    def _extract_node_summary(node, title: str) -> str:
        """从列表卡片生成短摘要。"""
        text = node.get_text(separator="\n", strip=True)
        text = _clean_text(text)
        if title and text.startswith(title):
            text = text[len(title):].strip()
        return text[:500]

    def _build_article(self, candidate: Dict[str, object]) -> Optional[RawArticle]:
        """抓取详情页并组装 RawArticle。"""
        url = str(candidate["url"])
        detail_html = self._request_html(url)

        title = str(candidate.get("title") or "").strip()
        author = str(candidate.get("author") or "").strip()
        publish_time = candidate.get("publish_time")
        raw_summary = str(candidate.get("summary") or "").strip()
        raw_html = None

        if detail_html:
            detail = self._parse_detail_page(detail_html)
            title = detail.get("title") or title
            author = detail.get("author") or author
            publish_time = detail.get("publish_time") or publish_time
            raw_html = detail.get("content_html") or detail_html
            raw_summary = detail.get("summary") or raw_summary

        publish_time = publish_time if isinstance(publish_time, datetime) else None
        article = RawArticle(
            source_code=self.source_code,
            title=title,
            url=url,
            author=author or None,
            publish_time=publish_time,
            raw_summary=raw_summary or title,
            raw_html=raw_html,
        )
        return article

    def _parse_detail_page(self, html: str) -> Dict[str, object]:
        """解析详情页标题、作者、时间和正文。"""
        soup = BeautifulSoup(html, "lxml")

        title = self._select_meta(soup, ["og:title", "twitter:title"]) or self._select_text(
            soup,
            self.detail_title_selectors,
        )
        author = self._select_meta(soup, ["author", "article:author"]) or self._select_text(
            soup,
            self.detail_author_selectors,
        )
        time_text = self._select_meta(
            soup,
            ["article:published_time", "pubdate", "publishdate", "date"],
        ) or self._select_text(soup, self.detail_time_selectors)
        publish_time = _parse_datetime_text(time_text)

        content_node = self._select_content_node(soup)
        content_html = ""
        summary = ""
        if content_node:
            for junk in content_node.select(JUNK_SELECTORS):
                junk.decompose()
            content_html = str(content_node)
            summary = _clean_text(content_node.get_text(separator="\n", strip=True))[:1000]

        return {
            "title": title.strip() if title else "",
            "author": author.strip() if author else "",
            "publish_time": publish_time,
            "content_html": content_html,
            "summary": summary,
        }

    @staticmethod
    def _select_meta(soup: BeautifulSoup, names: Iterable[str]) -> str:
        """从 meta 标签提取内容。"""
        for name in names:
            selected = (
                soup.find("meta", attrs={"property": name})
                or soup.find("meta", attrs={"name": name})
                or soup.find("meta", attrs={"itemprop": name})
            )
            if selected and selected.get("content"):
                return selected.get("content", "").strip()
        return ""

    def _select_content_node(self, soup: BeautifulSoup):
        """选择正文节点，多个候选时取文本最长的节点。"""
        candidates = []
        for selector in self.detail_content_selectors:
            if not selector:
                continue
            candidates.extend(soup.select(selector))

        if not candidates and soup.body:
            candidates = [soup.body]

        best_node = None
        best_length = 0
        for node in candidates:
            text = _clean_text(node.get_text(separator="\n", strip=True))
            lowered = text.lower()
            if self.detail_content_reject_keywords and any(
                keyword.lower() in lowered
                for keyword in self.detail_content_reject_keywords
            ):
                continue
            if len(text) > best_length:
                best_node = node
                best_length = len(text)
        return best_node
