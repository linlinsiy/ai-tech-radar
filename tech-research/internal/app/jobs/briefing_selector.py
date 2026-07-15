"""L4 briefing topic selection with source, category and content-type balance."""

import json
import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Set, Tuple


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

ENGINEERING_TYPES = {"技术方案", "产品发布", "开源项目", "工程实践", "案例实践"}
RESEARCH_TYPES = {"模型发布", "研究论文"}
INDUSTRY_TYPES = {"行业动态", "投融资并购", "政策监管", "观点分析", "其他"}
MAJOR_EVENT_TYPES = {"模型发布", "产品发布", "开源项目", "政策监管"}


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
    """Select representative topics while keeping all constraints soft for major events."""

    def __init__(self, config: Dict):
        self.config = config
        self.similarity_threshold = float(config.get("topic_similarity_threshold", 0.34))
        self.max_articles_per_topic = int(config.get("max_articles_per_topic", 3))

    def select(self, articles: List[Dict], briefing_type: str) -> Tuple[List[Dict], Dict]:
        target = int(self.config.get(f"target_{briefing_type}", self.config.get("target_topic", 12)))
        minimum_score = float(self.config.get("min_value_score", 5.5))
        candidates = [self._enrich(article) for article in articles]
        candidates = [article for article in candidates if article["value_score"] >= minimum_score]
        candidates.sort(key=lambda item: item["report_rank_score"], reverse=True)

        topics = self._cluster(candidates)
        major_topics = [topic for topic in topics if topic["must_include"]]
        selection_capacity = max(target, len(major_topics))
        max_source = max(
            1,
            min(
                int(self.config.get("max_primary_topics_per_source", 2)),
                math.ceil(target * float(self.config.get("max_primary_source_ratio", 0.2))),
            ),
        )
        max_category = max(1, math.ceil(target * float(self.config.get("max_category_ratio", 0.35))))

        lane_targets = {
            "engineering": math.ceil(target * float(self.config.get("engineering_ratio", 0.55))),
            "research": math.ceil(target * float(self.config.get("research_ratio", 0.25))),
        }
        lane_targets["industry"] = max(
            0, target - lane_targets["engineering"] - lane_targets["research"]
        )

        selected: List[Dict] = []
        selected_ids = set()
        source_counts = Counter()
        category_counts = Counter()

        def add(topic: Dict, bypass_limits: bool = False) -> bool:
            topic_id = topic["topic_id"]
            if topic_id in selected_ids or len(selected) >= selection_capacity:
                return False
            source = topic["primary"]["source_code"]
            category = topic["category"]
            if not bypass_limits and (
                source_counts[source] >= max_source
                or category_counts[category] >= max_category
            ):
                return False
            selected.append(topic)
            selected_ids.add(topic_id)
            source_counts[source] += 1
            category_counts[category] += 1
            return True

        # Major official events are never dropped solely because a source reached its soft limit.
        for topic in major_topics:
            add(topic, bypass_limits=True)

        for lane, lane_target in lane_targets.items():
            current = sum(1 for topic in selected if topic["lane"] == lane)
            for topic in topics:
                if current >= lane_target:
                    break
                if topic["lane"] == lane and add(topic):
                    current += 1

        for topic in topics:
            add(topic)

        # If qualified material is sparse, relax balance limits rather than producing an undersized report.
        for topic in topics:
            add(topic, bypass_limits=True)

        selected.sort(key=lambda topic: (
            CATEGORY_ORDER.index(topic["category"])
            if topic["category"] in CATEGORY_ORDER else len(CATEGORY_ORDER),
            -topic["report_rank_score"],
        ))
        metadata = {
            "candidate_articles": len(candidates),
            "candidate_topics": len(topics),
            "selected_topics": len(selected),
            "target_topics": target,
            "selection_capacity": selection_capacity,
            "source_counts": dict(source_counts),
            "category_counts": dict(category_counts),
            "lane_counts": dict(Counter(topic["lane"] for topic in selected)),
            "major_event_topics": [
                topic["title"] for topic in selected if topic["must_include"]
            ],
            "topics": [
                {
                    "title": topic["title"],
                    "category": topic["category"],
                    "primary_source": topic["primary"]["source_name"],
                    "article_ids": [article["id"] for article in topic["articles"]],
                }
                for topic in selected
            ],
        }
        return selected, metadata

    def _enrich(self, article: Dict) -> Dict:
        enriched = dict(article)
        enriched["value_score"] = _number(article.get("value_score"))
        enriched["report_rank_score"] = round(
            _number(article.get("score_engineering")) * 0.35
            + _number(article.get("score_trend")) * 0.25
            + _number(article.get("score_credibility")) * 0.15
            + _number(article.get("score_timeliness")) * 0.15
            + _number(article.get("score_tech_depth")) * 0.10,
            2,
        )
        info_type = str(article.get("info_type") or "其他")
        if info_type in ENGINEERING_TYPES:
            enriched["lane"] = "engineering"
        elif info_type in RESEARCH_TYPES:
            enriched["lane"] = "research"
        else:
            enriched["lane"] = "industry"
        major_release = (
            info_type in MAJOR_EVENT_TYPES
            and _number(article.get("score_trend")) >= 9.0
            and _number(article.get("score_credibility")) >= 8.0
            and enriched["value_score"] >= 7.0
        )
        engineering_breakthrough = (
            info_type in ENGINEERING_TYPES
            and _number(article.get("score_engineering")) >= 9.0
            and _number(article.get("score_trend")) >= 8.5
            and _number(article.get("score_credibility")) >= 8.0
            and enriched["value_score"] >= 7.0
        )
        enriched["must_include"] = major_release or engineering_breakthrough
        enriched["terms"] = self._terms(enriched)
        return enriched

    def _cluster(self, articles: List[Dict]) -> List[Dict]:
        topics: List[Dict] = []
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
                matched["must_include"] = matched["must_include"] or article["must_include"]
            else:
                topics.append({
                    "topic_id": str(article["id"]),
                    "title": article["title"],
                    "category": article.get("category") or "其他AI相关",
                    "lane": article["lane"],
                    "primary": article,
                    "articles": [article],
                    "terms": set(article["terms"]),
                    "must_include": article["must_include"],
                    "report_rank_score": article["report_rank_score"],
                })
        return topics

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
