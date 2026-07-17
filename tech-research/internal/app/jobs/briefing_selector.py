"""L4 topic aggregation and balanced selection using the shared rank score."""

import json
import math
import re
from collections import Counter
from typing import Dict, List, Set, Tuple


CATEGORY_ORDER = [
    "大模型基础技术",
    "Agent与智能体",
    "多模态技术",
    "AI基础设施",
    "生成式AI应用",
    "安全与伦理",
    "开源生态",
    "行业动态",
    "AI在金融领域应用",
    "其他AI相关",
]

ENGINEERING_TYPES = {"技术方案", "模型发布", "产品发布", "开源项目", "工程实践", "案例实践", "政策监管"}


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_values(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.lstrip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    normalized = str(value).replace("，", ",").replace("；", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _title_terms(title: str) -> Set[str]:
    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", (title or "").lower())
    words = {word for word in normalized.split() if len(word) >= 2}
    chinese = "".join(ch for ch in normalized if "\u4e00" <= ch <= "\u9fff")
    words.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return words


class BriefingSelector:
    """Aggregate successful L3 material and apply auditable soft quotas.

    The selector never recalculates article value and has no identity-based
    exceptions. Every topic uses the L2 ``rank_score`` and the same limits.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.similarity_threshold = float(config.get("topic_similarity_threshold", 0.34))
        self.max_articles_per_topic = int(config.get("max_articles_per_topic", 3))

    def select(self, articles: List[Dict], briefing_type: str) -> Tuple[List[Dict], Dict]:
        target = int(self.config.get(f"target_{briefing_type}", self.config.get("target_topic", 12)))
        minimum_score = float(self.config.get("min_rank_score", 6.5))

        enriched = [self._enrich(article) for article in articles]
        candidates = [
            article for article in enriched
            if article["rank_score"] >= minimum_score
        ]
        candidates.sort(key=lambda item: item["rank_score"], reverse=True)
        topics = self._cluster(candidates)

        source_values = {topic["primary"]["source_code"] for topic in topics}
        category_values = {topic["category"] for topic in topics}
        source_balance_active = len(source_values) >= int(
            self.config.get("min_sources_for_balance", 3)
        )
        category_balance_active = len(category_values) >= int(
            self.config.get("min_categories_for_balance", 2)
        )

        # Sparse periods keep every qualified topic. Quotas only narrow a pool
        # that is larger than the configured report target.
        if len(topics) <= target:
            selected = list(topics)
            outcomes = {
                topic["topic_id"]: "selected" for topic in topics
            }
        else:
            source_limit = max(
                1,
                math.ceil(target * float(self.config.get("max_primary_source_ratio", 0.15))),
            )
            dynamic_category_limit = math.ceil(target / max(1, len(category_values)))
            category_limit = max(
                1,
                min(
                    dynamic_category_limit,
                    math.ceil(target * float(self.config.get("max_category_ratio", 0.35))),
                ),
            )
            selected, outcomes = self._select_with_limits(
                topics,
                target,
                source_limit if source_balance_active else None,
                category_limit if category_balance_active else None,
            )

        selected.sort(key=self._display_order)
        source_counts = Counter(topic["primary"]["source_code"] for topic in selected)
        category_counts = Counter(topic["category"] for topic in selected)
        info_type_counts = Counter(topic["primary"]["info_type"] for topic in selected)
        engineering_count = sum(
            1 for topic in selected if topic["primary"]["info_type"] in ENGINEERING_TYPES
        )
        metadata = {
            "candidate_articles": len(candidates),
            "candidate_topics": len(topics),
            "selected_topics": len(selected),
            "target_topics": target,
            "shortfall_topics": max(0, target - len(selected)),
            "source_balance_active": source_balance_active,
            "category_balance_active": category_balance_active,
            "source_counts": dict(source_counts),
            "category_counts": dict(category_counts),
            "info_type_counts": dict(info_type_counts),
            "engineering_observation_ratio": round(
                engineering_count / len(selected), 4
            ) if selected else 0,
            "topic_outcomes": outcomes,
            "topics": [
                {
                    "topic_id": topic["topic_id"],
                    "title": topic["title"],
                    "category": topic["category"],
                    "rank_score": topic["rank_score"],
                    "primary_source": topic["primary"]["source_name"],
                    "article_ids": [article["id"] for article in topic["articles"]],
                }
                for topic in selected
            ],
        }
        return selected, metadata

    @staticmethod
    def _select_with_limits(
        topics: List[Dict],
        target: int,
        source_limit: int,
        category_limit: int,
    ) -> Tuple[List[Dict], Dict[str, str]]:
        selected = []
        source_counts = Counter()
        category_counts = Counter()
        outcomes = {}
        for topic in topics:
            if len(selected) >= target:
                outcomes[topic["topic_id"]] = "excluded_by_capacity"
                continue
            source = topic["primary"]["source_code"]
            category = topic["category"]
            if source_limit is not None and source_counts[source] >= source_limit:
                outcomes[topic["topic_id"]] = "excluded_by_source_balance"
                continue
            if category_limit is not None and category_counts[category] >= category_limit:
                outcomes[topic["topic_id"]] = "excluded_by_category_balance"
                continue
            selected.append(topic)
            source_counts[source] += 1
            category_counts[category] += 1
            outcomes[topic["topic_id"]] = "selected"
        return selected, outcomes

    def _enrich(self, article: Dict) -> Dict:
        enriched = dict(article)
        enriched["rank_score"] = _number(
            article.get("rank_score"), _number(article.get("value_score"))
        )
        enriched["terms"] = self._terms(enriched)
        return enriched

    def _cluster(self, articles: List[Dict]) -> List[Dict]:
        topics: List[Dict] = []
        article_outcomes = {}
        for article in articles:
            matched = None
            for topic in topics:
                if len(topic["articles"]) >= self.max_articles_per_topic:
                    continue
                if topic["category"] != article.get("category"):
                    continue
                if self._similarity(topic["terms"], article["terms"]) >= self.similarity_threshold:
                    matched = topic
                    break
            if matched:
                matched["articles"].append(article)
                matched["terms"].update(article["terms"])
                article_outcomes[str(article["id"])] = f"merged_into:{matched['topic_id']}"
            else:
                topic_id = str(article["id"])
                topics.append({
                    "topic_id": topic_id,
                    "title": article["title"],
                    "category": article.get("category") or "其他AI相关",
                    "primary": article,
                    "articles": [article],
                    "terms": set(article["terms"]),
                    "rank_score": article["rank_score"],
                })
                article_outcomes[str(article["id"])] = "topic_primary"
        for topic in topics:
            topic["article_outcomes"] = {
                str(article["id"]): article_outcomes[str(article["id"])]
                for article in topic["articles"]
            }
        return topics

    @staticmethod
    def _display_order(topic: Dict) -> Tuple[int, float]:
        category = topic["category"]
        category_index = CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else len(CATEGORY_ORDER)
        return category_index, -topic["rank_score"]

    @staticmethod
    def _terms(article: Dict) -> Set[str]:
        terms = _title_terms(article.get("title", ""))
        for field in ("keywords", "tech_tags", "companies"):
            terms.update(value.lower() for value in _string_values(article.get(field)))
        return {term for term in terms if term}

    @staticmethod
    def _similarity(left: Set[str], right: Set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)
