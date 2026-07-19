"""L4 topic aggregation and selection using the shared rank score."""

import json
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
    """Aggregate successful L3 material and select the highest-scoring topics.

    The selector never recalculates article value. It applies only configured
    upper caps, never minimum quotas or low-score backfilling.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.similarity_threshold = float(config.get("topic_similarity_threshold", 0.34))
        self.max_articles_per_topic = int(config.get("max_articles_per_topic", 3))
        self.max_topics_per_source = int(config.get("max_topics_per_source", 0))
        self.max_topics_per_info_type = int(config.get("max_topics_per_info_type", 0))

    def select(self, articles: List[Dict], briefing_type: str) -> Tuple[List[Dict], Dict]:
        target = int(self.config.get(f"target_{briefing_type}", self.config.get("target_topic", 12)))
        minimum_score = float(self.config.get("min_rank_score", 6.0))

        enriched = [self._enrich(article) for article in articles]
        candidates = [
            article for article in enriched
            if article["rank_score"] >= minimum_score
        ]
        candidates.sort(key=lambda item: item["rank_score"], reverse=True)
        topics = self._cluster(candidates)
        selected, outcomes = self._select_with_upper_caps(topics, target)

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
            "selection_mode": "rank_with_upper_caps",
            "max_topics_per_source": self.max_topics_per_source,
            "max_topics_per_info_type": self.max_topics_per_info_type,
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

    def _select_with_upper_caps(self, topics: List[Dict], target: int) -> Tuple[List[Dict], Dict[str, str]]:
        """Select in score order; upper caps may leave the report below its target."""
        selected: List[Dict] = []
        outcomes: Dict[str, str] = {}
        source_counts: Counter = Counter()
        info_type_counts: Counter = Counter()

        for topic in topics:
            source_code = topic["primary"]["source_code"]
            info_type = topic["primary"]["info_type"] or "其他"
            if self.max_topics_per_source > 0 and source_counts[source_code] >= self.max_topics_per_source:
                outcomes[topic["topic_id"]] = "excluded_by_source_cap"
                continue
            if self.max_topics_per_info_type > 0 and info_type_counts[info_type] >= self.max_topics_per_info_type:
                outcomes[topic["topic_id"]] = "excluded_by_info_type_cap"
                continue
            if len(selected) >= target:
                outcomes[topic["topic_id"]] = "excluded_by_capacity"
                continue

            selected.append(topic)
            source_counts[source_code] += 1
            info_type_counts[info_type] += 1
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
