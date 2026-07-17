"""Title-level candidate planning before article detail fetching and L2 scoring."""

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from crawler.base import RawArticle


CATEGORY_KEYWORDS = {
    "AI在金融领域应用": (
        "金融", "银行", "证券", "保险", "投研", "风控", "反欺诈", "量化", "财富管理",
        "fintech", "banking", "finance", "insurance", "trading",
    ),
    "Agent与智能体": ("agent", "智能体", "multi-agent", "工具调用", "workflow", "mcp"),
    "多模态技术": (
        "多模态", "视觉", "图像", "视频", "语音", "数字人", "vision", "image", "video", "speech",
    ),
    "AI基础设施": (
        "gpu", "芯片", "算力", "推理服务", "分布式训练", "数据库", "向量库", "inference",
        "serving", "cuda", "存储",
    ),
    "安全与伦理": (
        "安全", "合规", "监管", "对齐", "隐私", "版权", "攻击", "security", "safety", "alignment",
    ),
    "开源生态": ("开源", "open source", "github", "社区", "许可证", "生态"),
    "生成式AI应用": (
        "copilot", "代码生成", "内容生成", "企业应用", "rag", "知识库", "应用", "产品化",
    ),
    "大模型基础技术": (
        "大模型", "llm", "模型", "训练", "微调", "蒸馏", "moe", "attention", "上下文", "推理优化",
    ),
    "行业动态": ("融资", "并购", "发布", "政策", "市场", "厂商", "投资", "acquisition", "launch"),
}

AI_TERMS = (
    "ai", "人工智能", "大模型", "模型", "llm", "agent", "智能体", "机器学习", "深度学习",
    "生成式", "推理", "训练", "多模态", "rag", "copilot",
)

CANONICAL_CATEGORIES = set(CATEGORY_KEYWORDS) | {"其他AI相关"}


class CandidatePoolPlanner:
    """Build an initial detail-fetch set and a deferred category refill pool."""

    def __init__(self, config: Dict):
        self.candidate_limit = max(1, int(config.get("candidate_limit_per_source", 100)))
        self.initial_limit = max(1, int(config.get("initial_scored_per_source", 50)))
        self.refill_limit = max(0, int(config.get("refill_max_per_category", 10)))

    def prepare(
        self,
        candidates: List[RawArticle],
        source_profiles: Dict[str, Dict[str, str]],
    ) -> Tuple[List[RawArticle], List[RawArticle], Dict]:
        buckets = defaultdict(list)
        semantic_filtered = 0
        for article in candidates:
            self._annotate(article, source_profiles.get(article.source_code, {}))
            if article.ai_related is False:
                semantic_filtered += 1
                continue
            buckets[article.source_code].append(article)

        selected: List[RawArticle] = []
        deferred: List[RawArticle] = []
        source_counts = {}
        for source_code, items in buckets.items():
            discovered = self._rank_unique_titles(items)
            ranked = discovered[: self.candidate_limit]
            first = ranked[: self.initial_limit]
            rest = ranked[self.initial_limit:]
            selected.extend(first)
            deferred.extend(rest)
            source_counts[source_code] = {
                "discovered": len(discovered),
                "candidates": len(ranked),
                "candidate_cap_hit": len(discovered) >= self.candidate_limit,
                "initial_selected": len(first),
                "deferred": len(rest),
            }

        retained = selected + deferred
        return selected, deferred, {
            "candidate_count": sum(item["candidates"] for item in source_counts.values()),
            "initial_selected": len(selected),
            "deferred": len(deferred),
            "source_counts": source_counts,
            "predicted_category_counts": dict(Counter(
                article.predicted_category or "其他AI相关" for article in retained
            )),
            "semantic_filtered": semantic_filtered,
        }

    def select_refill(
        self,
        deferred: List[RawArticle],
        categories: Iterable[str],
    ) -> Tuple[List[RawArticle], List[RawArticle]]:
        wanted = [category for category in categories if category]
        selected: List[RawArticle] = []
        selected_hashes = set()
        for category in wanted:
            matches = [
                article for article in deferred
                if article.url_hash not in selected_hashes
                and article.predicted_category == category
            ]
            matches.sort(key=self._sort_key, reverse=True)
            for article in matches[: self.refill_limit]:
                selected.append(article)
                selected_hashes.add(article.url_hash)
        remaining = [article for article in deferred if article.url_hash not in selected_hashes]
        return selected, remaining

    def _annotate(self, article: RawArticle, source: Dict[str, str]) -> None:
        text = f"{article.title} {article.raw_summary or ''}".lower()
        if not article.predicted_category:
            article.predicted_category = self._predict_category(
                text,
                source.get("category", ""),
            )
        relevance = sum(1 for term in AI_TERMS if term in text)
        article.candidate_score = (
            relevance * 5.0
            + (2.0 if article.raw_summary else 0.0)
            + article.route_confidence * 5.0
        )

    @staticmethod
    def _predict_category(text: str, source_category: str) -> str:
        scores = {
            category: sum(1 for keyword in keywords if keyword in text)
            for category, keywords in CATEGORY_KEYWORDS.items()
        }
        best_category, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score > 0:
            return best_category
        if source_category in CANONICAL_CATEGORIES:
            return source_category
        return "其他AI相关"

    def _rank_unique_titles(self, articles: List[RawArticle]) -> List[RawArticle]:
        ranked = sorted(articles, key=self._sort_key, reverse=True)
        result = []
        seen_titles = set()
        for article in ranked:
            title_key = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", article.title.lower())
            if title_key and title_key in seen_titles:
                continue
            if title_key:
                seen_titles.add(title_key)
            result.append(article)
        return result

    @staticmethod
    def _sort_key(article: RawArticle):
        published = article.publish_time or datetime.min
        return article.candidate_score, published
