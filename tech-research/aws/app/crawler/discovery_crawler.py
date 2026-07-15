"""Optional search-API discovery for coverage gaps in configured sources."""

import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests

from crawler.base import RawArticle
from crawler.web_crawler import WebCrawler
from logging_config import get_logger

logger = get_logger("crawler.discovery")


CATEGORY_QUERY_TERMS = {
    "大模型基础技术": "AI foundation model LLM training inference model release",
    "Agent与智能体": "AI agent runtime tools memory multi-agent engineering",
    "多模态技术": "multimodal AI vision audio video model release",
    "AI基础设施": "AI infrastructure GPU inference serving MLOps engineering",
    "生成式AI应用": "generative AI enterprise application copilot product",
    "安全与伦理": "AI safety governance security regulation privacy",
    "开源生态": "open source AI model framework tool release",
    "行业动态": "AI industry product launch acquisition policy",
    "AI在金融领域应用": "AI financial services investment risk compliance fintech",
}

SOURCE_CATEGORY_ALIASES = {
    "金融应用": "AI在金融领域应用",
    "学术论文": "大模型基础技术",
    "周报与深度评论": "行业动态",
}


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


class SearchDiscoveryCrawler:
    """Discover article URLs, restricted to domains already configured for collection."""

    def __init__(self, config: Dict, sources: List[Dict[str, str]]):
        self.config = config
        self.sources = sources
        self.endpoint = str(config.get("search_endpoint") or "").strip()
        self.timeout = int(config.get("timeout_seconds", 20))
        self.max_queries = int(config.get("max_queries_per_run", 6))
        self.max_results = int(config.get("max_results_per_query", 8))
        self.query_param = str(config.get("query_param") or "q")
        self.count_param = str(config.get("count_param") or "count")
        self.api_key = str(config.get("api_key") or "")
        self.api_key_header = str(config.get("api_key_header") or "").strip()
        self.domain_sources = {
            str(source.get("domain") or "").lower(): source
            for source in sources
            if source.get("domain")
        }

    def discover(
        self,
        categories: Iterable[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[RawArticle]:
        if not self.endpoint:
            logger.info("自动资讯发现未配置 search_endpoint，跳过")
            return []

        results: List[RawArticle] = []
        seen_urls = set()
        for category in list(categories)[: self.max_queries]:
            query = self._build_query(category, from_date, to_date)
            for item in self._search(query):
                url = str(item.get("url") or "").strip()
                source = self._match_source(url)
                if not url or not source or url in seen_urls:
                    continue
                seen_urls.add(url)
                runtime_source = dict(source)
                runtime_source.update(self.config.get("browser_source_options", {}))
                crawler = WebCrawler(runtime_source)
                fetched = crawler.fetch_urls([{
                    "url": url,
                    "title": item.get("title") or url,
                    "summary": item.get("summary") or "",
                    "publish_time": _parse_datetime(item.get("published_at")),
                    "author": "",
                }])
                results.extend(fetched)

        logger.info("自动资讯发现完成: articles=%d", len(results))
        return results

    def _build_query(
        self,
        category: str,
        from_date: Optional[str],
        to_date: Optional[str],
    ) -> str:
        terms = CATEGORY_QUERY_TERMS.get(category, f"AI {category}")
        category_domains = [
            source.get("domain", "")
            for source in self.sources
            if SOURCE_CATEGORY_ALIASES.get(source.get("category"), source.get("category")) == category
            and source.get("domain")
        ]
        domains = category_domains or list(self.domain_sources.keys())[:8]
        site_clause = " OR ".join(f"site:{domain}" for domain in domains[:8])
        date_clause = " ".join(
            item for item in (
                f"after:{from_date}" if from_date else "",
                f"before:{to_date}" if to_date else "",
            ) if item
        )
        return f"({terms}) ({site_clause}) {date_clause}".strip()

    def _search(self, query: str) -> List[Dict[str, str]]:
        headers = {"Accept": "application/json"}
        if self.api_key and self.api_key_header:
            headers[self.api_key_header] = self.api_key
        params = {
            self.query_param: query,
            self.count_param: self.max_results,
        }
        try:
            response = requests.get(
                self.endpoint,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_results(response.json())[: self.max_results]
        except Exception as exc:
            logger.warning("自动资讯搜索失败: query=%s, error=%s", query[:120], str(exc))
            return []

    @staticmethod
    def _parse_results(payload: Dict) -> List[Dict[str, str]]:
        raw_items = []
        if isinstance(payload.get("webPages"), dict):
            raw_items = payload["webPages"].get("value", [])
        elif isinstance(payload.get("results"), list):
            raw_items = payload["results"]
        elif isinstance(payload.get("items"), list):
            raw_items = payload["items"]

        parsed = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            parsed.append({
                "url": item.get("url") or item.get("link") or "",
                "title": item.get("name") or item.get("title") or "",
                "summary": item.get("snippet") or item.get("description") or "",
                "published_at": (
                    item.get("datePublished")
                    or item.get("published_at")
                    or item.get("published")
                    or ""
                ),
            })
        return parsed

    def _match_source(self, url: str) -> Optional[Dict[str, str]]:
        domain = urlparse(url).netloc.lower().split(":", 1)[0]
        if not re.match(r"^[a-z0-9.-]+$", domain):
            return None
        for configured_domain, source in self.domain_sources.items():
            normalized = configured_domain.split(":", 1)[0]
            if domain == normalized or domain.endswith(f".{normalized}"):
                return source
        return None
