"""Source plans shared by production and staged validation collection."""

from typing import Any, Dict, Iterable, List, Optional


SERVER_RECOMMENDED = "server_recommended"
PRIMARY_RESILIENT = "primary_resilient"
CONFIGURED = "configured"
SUPPORTED_STRATEGIES = (CONFIGURED, SERVER_RECOMMENDED, PRIMARY_RESILIENT)


SERVER_COVERAGE_RULES = (
    {
        "alias": "karpathy",
        "sources": {"36kr-ai", "tmtpost"},
        "keywords": ("大模型训练", "scaling law", "karpathy", "大模型优化"),
    },
    {
        "alias": "tencent-cloud-security",
        "sources": {"36kr-ai", "tmtpost"},
        "keywords": (
            "漏洞", "后门", "安全事件", "数据泄露", "ai安全", "cve", "cnvd",
        ),
    },
    {
        "alias": "google-research",
        "sources": {"arxiv-cs-ai", "pyimagesearch"},
        "keywords": ("大模型研究", "google", "gemini", "多模态"),
    },
    {
        "alias": "langchain-blog",
        "sources": {"aliyun-ai-dev", "csdn-ai"},
        "keywords": ("langchain", "agent框架", "rag", "向量数据库", "agent开发"),
    },
    {
        "alias": "infoq-en",
        "sources": {"36kr-ai", "tmtpost"},
        "keywords": ("海外技术", "工程实践", "架构设计"),
    },
    {
        "alias": "importai",
        "sources": {"ai-weekly", "36kr-ai"},
        "keywords": ("ai周报", "行业动态", "全球ai事件"),
    },
)


SERVER_CSDN_SOURCE = {
    "code": "csdn-ai",
    "name": "CSDN AI频道",
    "type": "tech_community",
    "category": "生成式AI应用",
    "domain": "blog.csdn.net",
    "enabled": "true",
}


SERVER_RECOMMENDED_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "36kr-ai": {
        "access_url": "https://36kr.com/information/AI/",
        "domain": "36kr.com",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'article-item')]"
            "//a[contains(@class, 'article-item-title')]/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'article-item')]"
            "//a[contains(@class, 'article-item-title')]/text()"
        ),
        "include_keywords": "",
    },
    "aliyun-ai-dev": {
        "access_url": "https://developer.aliyun.com/group/ai",
        "domain": "developer.aliyun.com",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'article-card')]"
            "//a[contains(@class, 'title')]/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'article-card')]"
            "//a[contains(@class, 'title')]/@title"
        ),
        "include_keywords": (
            "大模型,LLM,AI Agent,RAG,向量数据库,模型训练,多模态,微调,"
            "Agent,MCP,Spring AI,编程,框架,安全"
        ),
    },
    "csdn-ai": {
        "access_url": "https://blog.csdn.net/nav/ai",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'CommunityItem')]//h4/a/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'CommunityItem')]//h4/a/text()"
        ),
        "include_keywords": "",
    },
    "tmtpost": {
        "access_url": "https://www.tmtpost.com/column/100041",
        "domain": "www.tmtpost.com",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'post-list')]//h3/a/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'post-list')]//h3/a/text()"
        ),
        "include_keywords": "",
    },
    "tencent-cloud-ai": {
        "access_url": "https://cloud.tencent.com/developer/section/1005",
        "domain": "cloud.tencent.com",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'article-item')]"
            "//a[@class='item-title']/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'article-item')]"
            "//a[@class='item-title']/text()"
        ),
        "include_keywords": (
            "AI,人工智能,大模型,深度学习,机器学习,智能体,开源,Agent,MCP,"
            "Spring AI,编程,框架,安全,企业级"
        ),
    },
    "01caijing-home": {
        "access_url": "https://www.01caijing.com/ai",
        "domain": "www.01caijing.com",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'news-list')]//h3/a/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'news-list')]//h3/a/@title"
        ),
        "include_keywords": (
            "AI,大模型,人工智能,金融科技,智能投研,智能风控,监管科技,"
            "银行数字化,证券AI,保险科技,数字金融,数据要素"
        ),
    },
    "10jqka-news": {
        "access_url": "https://www.10jqka.com.cn/ai/",
        "domain": "www.10jqka.com.cn",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'news_list')]//h2/a/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'news_list')]//h2/a/text()"
        ),
        "include_keywords": (
            "AI,人工智能,大模型,金融科技,智能投研,智能风控,量化,监管科技"
        ),
    },
    "oschina-ai": {
        "access_url": "https://www.oschina.net/ai",
        "domain": "www.oschina.net",
        "fetch_method": "web",
        "list_link_xpath": (
            "//div[contains(@class, 'news-item')]//h2/a/@href"
        ),
        "list_title_xpath": (
            "//div[contains(@class, 'news-item')]//h2/a/@title"
        ),
        "include_keywords": "",
    },
}


PRIMARY_RESILIENT_VARIANTS: Dict[str, List[Dict[str, Any]]] = {
    "deepmind-blog": [
        {
            "_variant_name": "official-rss",
            "access_url": "https://deepmind.google/blog/rss.xml",
            "domain": "deepmind.google",
            "fetch_method": "rss",
            "timeout_seconds": "60",
            "include_keywords": "",
        },
        {
            "_variant_name": "official-web",
            "access_url": "https://deepmind.google/blog/",
            "domain": "deepmind.google",
            "fetch_method": "web",
            "list_selector": "article a[href*='/blog/']",
            "article_url_pattern": r"deepmind\.google/blog/[^/]+/?$",
            "include_keywords": "",
        },
    ],
    "huggingface-blog": [
        {
            "_variant_name": "official-rss",
            "access_url": "https://huggingface.co/blog/feed.xml",
            "domain": "huggingface.co",
            "fetch_method": "rss",
            "timeout_seconds": "60",
            "include_keywords": "",
        },
        {
            "_variant_name": "official-web",
            "access_url": "https://huggingface.co/blog",
            "domain": "huggingface.co",
            "fetch_method": "web",
            "list_selector": "a[href^='/blog/']",
            "article_url_pattern": r"huggingface\.co/blog/[^/]+/?$",
            "include_keywords": "",
        },
    ],
    "langchain-blog": [
        {
            "_variant_name": "official-rss-current",
            "access_url": "https://www.langchain.com/blog/rss.xml",
            "domain": "www.langchain.com",
            "fetch_method": "rss",
            "timeout_seconds": "60",
        },
        {
            "_variant_name": "official-rss-legacy",
            "access_url": "https://blog.langchain.dev/rss.xml",
            "domain": "www.langchain.com",
            "fetch_method": "rss",
            "timeout_seconds": "60",
        },
    ],
    "36kr-ai": [
        {
            "_variant_name": "verified-ai-channel",
            "access_url": "https://36kr.com/information/AI/",
            "domain": "36kr.com",
            "fetch_method": "web",
            "list_selector": "a[href*='/p/']",
            "article_url_pattern": r"/p/\d+",
            "include_keywords": "",
        },
    ],
    "aliyun-ai-dev": [
        {
            "_variant_name": "configured-ai-group",
            "access_url": "https://developer.aliyun.com/group/ai",
            "domain": "developer.aliyun.com",
            "fetch_method": "web",
            "include_keywords": (
                "大模型,LLM,AI Agent,RAG,向量数据库,模型训练,多模态,微调,"
                "Agent,MCP,Spring AI,编程,框架,安全"
            ),
        },
    ],
    "tmtpost": [
        {
            "_variant_name": "existing-rss",
            "access_url": "https://www.tmtpost.com/feed",
            "domain": "www.tmtpost.com",
            "fetch_method": "rss",
            "timeout_seconds": "60",
        },
    ],
    "tencent-cloud-ai": [
        {
            "_variant_name": "existing-ai-column",
            "access_url": "https://cloud.tencent.com/developer/column/102946",
            "domain": "cloud.tencent.com",
            "fetch_method": "web",
        },
        {
            "_variant_name": "developer-home-keyword-fallback",
            "access_url": "https://cloud.tencent.com/developer",
            "domain": "cloud.tencent.com",
            "fetch_method": "web",
            "include_keywords": (
                "AI,人工智能,大模型,智能体,Agent,MCP,RAG,机器学习,深度学习"
            ),
        },
    ],
    "01caijing-home": [
        {
            "_variant_name": "existing-home-filtered",
            "access_url": "https://www.01caijing.com/",
            "domain": "www.01caijing.com",
            "fetch_method": "web",
        },
    ],
    "10jqka-news": [
        {
            "_variant_name": "existing-news-filtered",
            "access_url": "https://news.10jqka.com.cn/",
            "domain": "news.10jqka.com.cn",
            "fetch_method": "web",
        },
    ],
    "oschina-ai": [
        {
            "_variant_name": "official-ai-rss",
            "access_url": "https://www.oschina.net/news/rss/ai",
            "domain": "www.oschina.net",
            "fetch_method": "rss",
            "timeout_seconds": "60",
        },
        {
            "_variant_name": "news-keyword-fallback",
            "access_url": "https://www.oschina.net/news",
            "domain": "www.oschina.net",
            "fetch_method": "web",
            "include_keywords": "AI,人工智能,大模型,Agent,MCP,RAG,机器学习,开源",
            "article_url_pattern": r"/news/\d+",
        },
    ],
}


def _merge_source(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    merged.update(override)
    merged["referer"] = merged.get("referer") or merged.get("access_url", "")
    merged.setdefault("timeout_seconds", "30")
    merged.setdefault("request_interval_seconds", "2")
    return merged


def build_source_plans(
    base_sources: Iterable[Dict[str, Any]],
    strategy: str,
    requested_codes: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Return logical sources and ordered endpoint variants for one validation run."""
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(
            f"不支持的采集策略: {strategy}; 可选值: {', '.join(SUPPORTED_STRATEGIES)}"
        )

    sources = [dict(source) for source in base_sources]
    by_code = {source["code"]: source for source in sources}
    if strategy == SERVER_RECOMMENDED and "csdn-ai" not in by_code:
        sources.append(dict(SERVER_CSDN_SOURCE))

    requested = set(requested_codes or [])
    plans = []
    for source in sources:
        code = source["code"]
        if requested and code not in requested:
            continue

        if strategy == CONFIGURED:
            configured = dict(source)
            configured["_variant_name"] = "configured-source"
            variants = [configured]
        elif strategy == SERVER_RECOMMENDED:
            override = SERVER_RECOMMENDED_OVERRIDES.get(code, {})
            variant = _merge_source(source, {
                "_variant_name": "server-xpath" if override else "configured-source",
                "xpath_strict": "true" if override.get("list_link_xpath") else "false",
                **override,
            })
            variants = [variant]
        else:
            configured_variants = PRIMARY_RESILIENT_VARIANTS.get(code)
            variants = (
                [_merge_source(source, item) for item in configured_variants]
                if configured_variants else
                [_merge_source(source, {"_variant_name": "configured-source"})]
            )

        plans.append({
            "source_code": code,
            "source_name": source.get("name", code),
            "category": source.get("category", ""),
            "variants": variants,
        })
    return plans


def match_server_coverage_aliases(
    source_code: str,
    title: str,
    summary: str = "",
) -> List[str]:
    """Record the server proposal's keyword substitutions without forging provenance."""
    text = f"{title or ''} {summary or ''}".lower()
    return [
        rule["alias"]
        for rule in SERVER_COVERAGE_RULES
        if source_code in rule["sources"]
        and any(keyword.lower() in text for keyword in rule["keywords"])
    ]
