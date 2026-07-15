"""Zero-key article discovery inside already configured source domains."""

import gzip
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from crawler.base import RawArticle
from crawler.discovery_crawler import SOURCE_CATEGORY_ALIASES
from crawler.web_crawler import WEB_REQUEST_HEADERS, WebCrawler
from logging_config import get_logger

logger = get_logger("crawler.site_discovery")


SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/news-sitemap.xml")
TRACKING_QUERY_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "spm"}
LISTING_HINTS = (
    "ai", "ml", "news", "blog", "research", "technology", "tech", "article",
    "fintech", "finance", "policy", "security", "agent", "model", "product",
)
NON_ARTICLE_SEGMENTS = {
    "about", "contact", "login", "register", "search", "tag", "tags", "author",
    "category", "categories", "topic", "topics", "video", "live", "events",
}
ASSET_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js",
    ".pdf", ".zip", ".rar", ".xml", ".json", ".ico", ".woff", ".woff2",
)


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
        if match:
            return datetime(*(int(part) for part in match.groups()))
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS
    ])
    return urlunparse(parsed._replace(fragment="", query=query))


class SiteDiscoveryCrawler:
    """Discover recent article URLs through robots, Sitemap and bounded link traversal."""

    def __init__(self, config: Dict, sources: List[Dict[str, str]]):
        self.config = config
        self.sources = sources
        self.timeout = int(config.get("timeout_seconds", 20))
        self.max_sources = int(config.get("max_sources_per_run", 9))
        self.max_pages = int(config.get("max_pages_per_source", 3))
        self.max_urls = int(config.get("max_urls_per_source", 12))
        self.max_depth = int(config.get("crawl_depth", 2))
        self.max_sitemaps = int(config.get("max_sitemaps_per_source", 5))
        self.recency_days = int(config.get("recency_days", 30))
        self.request_interval = float(config.get("request_interval_seconds", 0.2))
        self.session = requests.Session()

    def discover(
        self,
        categories: Iterable[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[RawArticle]:
        category_list = [str(category) for category in categories if category]
        selected_sources = self._select_sources(category_list)
        start = _parse_datetime(from_date) or datetime.now() - timedelta(days=self.recency_days)
        end = _parse_datetime(to_date)
        if end and len(str(to_date)) <= 10:
            end = end.replace(hour=23, minute=59, second=59)

        results: List[RawArticle] = []
        seen_urls = set()
        for source in selected_sources:
            candidates = self._discover_source(source, start, end)
            candidates = [item for item in candidates if item["url"] not in seen_urls]
            if not candidates:
                continue
            seen_urls.update(item["url"] for item in candidates)

            runtime_source = dict(source)
            runtime_source.update(self.config.get("browser_source_options", {}))
            runtime_source["max_articles"] = str(self.max_urls)
            runtime_source["request_interval_seconds"] = str(self.request_interval)
            crawler = WebCrawler(runtime_source)
            fetched = crawler.fetch_urls(candidates)
            results.extend(fetched)
            logger.info(
                "[%s] 站内自动发现: candidates=%d, fetched=%d",
                source.get("code", "unknown"),
                len(candidates),
                len(fetched),
            )

        logger.info(
            "站内自动发现完成: sources=%d, articles=%d",
            len(selected_sources),
            len(results),
        )
        return results

    def _select_sources(self, categories: List[str]) -> List[Dict[str, str]]:
        """Round-robin matching categories so one category cannot consume all source slots."""
        usable = [
            source for source in self.sources
            if source.get("access_url") and source.get("domain")
        ]
        buckets = {
            category: [
                source for source in usable
                if SOURCE_CATEGORY_ALIASES.get(source.get("category"), source.get("category")) == category
            ]
            for category in categories
        }
        for bucket in buckets.values():
            bucket.sort(key=lambda source: source.get("fetch_method") not in ("web", "html"))

        selected: List[Dict[str, str]] = []
        selected_codes = set()
        while len(selected) < self.max_sources and any(buckets.values()):
            for category in categories:
                bucket = buckets.get(category, [])
                while bucket:
                    source = bucket.pop(0)
                    code = source.get("code")
                    if code not in selected_codes:
                        selected.append(source)
                        selected_codes.add(code)
                        break
                if len(selected) >= self.max_sources:
                    break

        if not selected:
            selected = usable[: self.max_sources]
        return selected

    def _discover_source(
        self,
        source: Dict[str, str],
        start: datetime,
        end: Optional[datetime],
    ) -> List[Dict[str, object]]:
        origin = self._origin(source["access_url"])
        if not origin:
            return []

        robots, sitemap_urls = self._load_robots(origin)
        for path in SITEMAP_PATHS:
            sitemap_urls.append(urljoin(origin, path))

        sitemap_candidates = self._discover_from_sitemaps(
            sitemap_urls,
            source,
            robots,
            start,
            end,
        )
        candidates = list(sitemap_candidates)
        seen = {item["url"] for item in candidates}

        if len(candidates) < self.max_urls:
            for item in self._discover_from_links(source, robots):
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                candidates.append(item)
                if len(candidates) >= self.max_urls:
                    break
        return candidates[: self.max_urls]

    def _load_robots(self, origin: str) -> Tuple[RobotFileParser, List[str]]:
        robots_url = urljoin(origin, "/robots.txt")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        sitemap_urls: List[str] = []
        try:
            response = self._request(robots_url)
            if response is not None:
                text = response.text
                parser.parse(text.splitlines())
                for line in text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        value = line.split(":", 1)[1].strip()
                        if value:
                            sitemap_urls.append(urljoin(origin, value))
            else:
                parser.parse([])
        except Exception as exc:
            parser.parse([])
            logger.debug("robots.txt 解析失败: url=%s, error=%s", robots_url, str(exc))
        return parser, sitemap_urls

    def _discover_from_sitemaps(
        self,
        sitemap_urls: List[str],
        source: Dict[str, str],
        robots: RobotFileParser,
        start: datetime,
        end: Optional[datetime],
    ) -> List[Dict[str, object]]:
        queue = deque(dict.fromkeys(sitemap_urls))
        visited = set()
        entries: Dict[str, Optional[datetime]] = {}

        while queue and len(visited) < self.max_sitemaps:
            sitemap_url = queue.popleft()
            if sitemap_url in visited or not self._same_domain(sitemap_url, source.get("domain", "")):
                continue
            visited.add(sitemap_url)
            response = self._request(sitemap_url)
            if response is None:
                continue
            nested, urls = self._parse_sitemap(response.content)
            for nested_url in reversed(nested):
                if nested_url not in visited:
                    queue.appendleft(nested_url)
            for url, last_modified in urls:
                if not self._same_domain(url, source.get("domain", "")):
                    continue
                if not robots.can_fetch("*", url):
                    continue
                if last_modified and (last_modified < start or (end and last_modified > end)):
                    continue
                if self._looks_like_article(url):
                    normalized = _normalize_url(url)
                    previous = entries.get(normalized)
                    if normalized not in entries or (last_modified and (not previous or last_modified > previous)):
                        entries[normalized] = last_modified

        ordered_entries = sorted(
            entries.items(),
            key=lambda item: item[1] or datetime.min,
            reverse=True,
        )
        return [
            {
                "url": url,
                "title": self._title_from_url(url),
                "summary": "",
                "publish_time": None,
                "author": "",
            }
            for url, _last_modified in ordered_entries[: self.max_urls]
        ]

    def _discover_from_links(
        self,
        source: Dict[str, str],
        robots: RobotFileParser,
    ) -> List[Dict[str, object]]:
        access_url = source.get("access_url", "")
        parsed = urlparse(access_url)
        start_url = access_url if source.get("fetch_method") in ("web", "html") else self._origin(access_url)
        queue = deque([(start_url, 0)])
        visited_pages = set()
        candidates: List[Dict[str, object]] = []
        seen_candidates = set()

        while queue and len(visited_pages) < self.max_pages and len(candidates) < self.max_urls:
            page_url, depth = queue.popleft()
            page_url = _normalize_url(page_url)
            if page_url in visited_pages or not self._same_domain(page_url, source.get("domain", "")):
                continue
            if not robots.can_fetch("*", page_url):
                continue
            visited_pages.add(page_url)
            response = self._request(page_url)
            if response is None:
                continue
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type and "<html" not in response.text[:500].lower():
                continue

            soup = BeautifulSoup(response.text, "lxml")
            for link in soup.find_all("a", href=True):
                url = _normalize_url(urljoin(page_url, link.get("href", "").strip()))
                if not self._same_domain(url, source.get("domain", "")) or not robots.can_fetch("*", url):
                    continue
                title = link.get_text(" ", strip=True)
                if not title:
                    image = link.find("img")
                    title = image.get("alt", "").strip() if image else ""

                if self._looks_like_article(url) and len(title) >= 6:
                    if url not in seen_candidates:
                        seen_candidates.add(url)
                        candidates.append({
                            "url": url,
                            "title": title,
                            "summary": "",
                            "publish_time": None,
                            "author": "",
                        })
                        if len(candidates) >= self.max_urls:
                            break
                elif depth < self.max_depth and self._looks_like_listing(url, parsed.netloc):
                    queue.append((url, depth + 1))

            if self.request_interval > 0:
                time.sleep(self.request_interval)
        return candidates

    def _request(self, url: str) -> Optional[requests.Response]:
        try:
            response = self.session.get(
                url,
                headers=WEB_REQUEST_HEADERS,
                timeout=self.timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            return response
        except requests.RequestException as exc:
            logger.debug("站内发现请求失败: url=%s, error=%s", url, str(exc))
            return None

    @staticmethod
    def _parse_sitemap(content: bytes) -> Tuple[List[str], List[Tuple[str, Optional[datetime]]]]:
        if len(content) > 10 * 1024 * 1024:
            return [], []
        if content[:2] == b"\x1f\x8b":
            try:
                content = gzip.decompress(content)
            except OSError:
                return [], []
            if len(content) > 10 * 1024 * 1024:
                return [], []
        lowered = content[:2048].lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            return [], []
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return [], []

        nested: List[str] = []
        urls: List[Tuple[str, Optional[datetime]]] = []
        root_name = _local_name(root.tag)
        for node in root:
            values = {
                _local_name(child.tag): (child.text or "").strip()
                for child in node
            }
            location = values.get("loc", "")
            if not location:
                continue
            if root_name == "sitemapindex":
                nested.append(location)
            elif root_name == "urlset":
                urls.append((location, _parse_datetime(values.get("lastmod"))))
        return nested, urls

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}/"

    @staticmethod
    def _same_domain(url: str, configured_domain: str) -> bool:
        domain = urlparse(url).netloc.lower().split(":", 1)[0]
        configured = str(configured_domain or "").lower().split(":", 1)[0]
        return bool(configured and (domain == configured or domain.endswith(f".{configured}")))

    @staticmethod
    def _looks_like_article(url: str) -> bool:
        parsed = urlparse(url)
        path = unquote(parsed.path).lower().rstrip("/")
        if not path or path == "/" or path.endswith(ASSET_EXTENSIONS):
            return False
        segments = [segment for segment in path.split("/") if segment]
        if not segments or any(segment in NON_ARTICLE_SEGMENTS for segment in segments):
            return False
        last = segments[-1]
        if last in LISTING_HINTS or last in {"index", "home", "latest", "archive", "archives"}:
            return False
        return bool(
            re.search(r"/20\d{2}/(?:0?[1-9]|1[0-2])(?:/|$)", path)
            or re.search(r"(?:^|[-_/])\d{5,}(?:[-_/]|$)", path)
            or path.endswith((".html", ".htm"))
            or (len(segments) >= 2 and len(last) >= 6)
            or ("-" in last and len(last) >= 10)
        )

    @staticmethod
    def _looks_like_listing(url: str, original_netloc: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != original_netloc or parsed.path.lower().endswith(ASSET_EXTENSIONS):
            return False
        path = unquote(parsed.path).lower()
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) > 3:
            return False
        return not segments or any(hint in path for hint in LISTING_HINTS)

    @staticmethod
    def _title_from_url(url: str) -> str:
        path = unquote(urlparse(url).path.rstrip("/"))
        title = path.rsplit("/", 1)[-1]
        title = re.sub(r"\.(?:html?|aspx?)$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"[-_]+", " ", title).strip()
        return title or url
