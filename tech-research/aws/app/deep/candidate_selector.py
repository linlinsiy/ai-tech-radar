"""Balanced candidate selection before expensive L3 analysis."""

import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Set, Tuple

from logging_config import get_logger

logger = get_logger("deep.candidate_selector")

MAJOR_EVENT_TYPES = {"模型发布", "产品发布", "开源项目", "政策监管"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_values(value: Any) -> List[str]:
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
    terms = {word for word in normalized.split() if len(word) >= 2}
    chinese = "".join(ch for ch in normalized if "\u4e00" <= ch <= "\u9fff")
    terms.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return terms


class L3CandidateSelector:
    """Collapse repeated topics and balance L3 candidates across sources."""

    def __init__(self, config: Dict[str, Any], min_score: float):
        self.config = config
        self.min_score = min_score
        self.enabled = bool(config.get("enabled", True))
        self.max_candidates = max(1, int(config.get("max_candidates_per_batch", 36)))
        self.max_per_source = max(1, int(config.get("max_candidates_per_source", 3)))
        self.max_source_ratio = float(config.get("max_source_ratio", 0.2))
        self.max_category_ratio = float(config.get("max_category_ratio", 0.35))
        self.similarity_threshold = float(config.get("topic_similarity_threshold", 0.34))
        self.max_major_exceptions = max(0, int(config.get("max_major_event_exceptions", 0)))
        self.min_sources_for_balance = max(1, int(config.get("min_sources_for_balance", 3)))
        self.min_categories_for_balance = max(1, int(config.get("min_categories_for_balance", 2)))

    def select(self, l2_results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        eligible = [self._enrich(result) for result in l2_results if self._is_eligible(result)]
        eligible.sort(key=lambda item: item["l3_rank_score"], reverse=True)

        if not self.enabled:
            selected_results = [item["result"] for item in eligible]
            return selected_results, self._metadata(eligible, eligible, len(eligible))

        topics = self._cluster(eligible)
        source_total = len({topic["source_code"] for topic in topics})
        category_total = len({topic["category"] for topic in topics})
        source_balance_active = source_total >= self.min_sources_for_balance
        category_balance_active = category_total >= self.min_categories_for_balance
        balance_active = source_balance_active or category_balance_active
        source_limit = (
            max(1, min(self.max_per_source, math.ceil(self.max_candidates * self.max_source_ratio)))
            if source_balance_active else self.max_candidates
        )
        category_limit = (
            max(1, math.ceil(self.max_candidates * self.max_category_ratio))
            if category_balance_active else self.max_candidates
        )

        major_topics = [topic for topic in topics if topic["must_include"]]
        protected_major_topics = (
            major_topics if self.max_major_exceptions == 0
            else major_topics[: self.max_major_exceptions]
        )
        selection_capacity = max(self.max_candidates, len(protected_major_topics))

        selected: List[Dict[str, Any]] = []
        selected_ids = set()
        source_counts = Counter()
        category_counts = Counter()

        def add(topic: Dict[str, Any], bypass_limits: bool = False) -> bool:
            if topic["topic_id"] in selected_ids or len(selected) >= selection_capacity:
                return False
            source = topic["source_code"]
            category = topic["category"]
            if not bypass_limits and (
                source_counts[source] >= source_limit
                or category_counts[category] >= category_limit
            ):
                return False
            selected.append(topic)
            selected_ids.add(topic["topic_id"])
            source_counts[source] += 1
            category_counts[category] += 1
            return True

        for topic in protected_major_topics:
            add(topic, bypass_limits=True)

        self._round_robin(
            topics,
            selected_ids,
            source_counts,
            category_counts,
            source_limit,
            category_limit,
            add,
            enforce_category=True,
            capacity=selection_capacity,
        )
        if len(selected) < selection_capacity:
            self._round_robin(
                topics,
                selected_ids,
                source_counts,
                category_counts,
                source_limit,
                category_limit,
                add,
                enforce_category=False,
                capacity=selection_capacity,
            )

        metadata = self._metadata(eligible, selected, len(topics))
        metadata.update({
            "source_limit": source_limit,
            "category_limit": category_limit,
            "source_counts": dict(source_counts),
            "category_counts": dict(category_counts),
            "balance_active": balance_active,
            "source_balance_active": source_balance_active,
            "category_balance_active": category_balance_active,
            "major_event_count": len(major_topics),
            "protected_major_event_count": len(protected_major_topics),
        })
        logger.info(
            "L3 候选均衡完成: eligible=%d, topics=%d, selected=%d, sources=%d",
            len(eligible),
            len(topics),
            len(selected),
            len(source_counts),
        )
        return [topic["result"] for topic in selected], metadata

    def _round_robin(
        self,
        topics: List[Dict[str, Any]],
        selected_ids: Set[str],
        source_counts: Counter,
        category_counts: Counter,
        source_limit: int,
        category_limit: int,
        add,
        enforce_category: bool,
        capacity: int,
    ) -> None:
        while len(selected_ids) < capacity:
            remaining = [topic for topic in topics if topic["topic_id"] not in selected_ids]
            if not remaining:
                return
            sources = sorted(
                {topic["source_code"] for topic in remaining},
                key=lambda source: (
                    source_counts[source],
                    -max(
                        topic["l3_rank_score"]
                        for topic in remaining
                        if topic["source_code"] == source
                    ),
                ),
            )
            progressed = False
            for source in sources:
                if source_counts[source] >= source_limit:
                    continue
                candidate = next((
                    topic for topic in remaining
                    if topic["source_code"] == source
                    and (
                        not enforce_category
                        or category_counts[topic["category"]] < category_limit
                    )
                ), None)
                if candidate and add(candidate, bypass_limits=not enforce_category):
                    progressed = True
                if len(selected_ids) >= capacity:
                    return
            if not progressed:
                return

    def _is_eligible(self, result: Dict[str, Any]) -> bool:
        analysis = result.get("analysis", {})
        value_score = _number(analysis.get("value_score"))
        return (
            result.get("article") is not None
            and value_score >= self.min_score
            and (
                analysis.get("need_deep_analysis") is not False
                or self._is_major_analysis(analysis, value_score)
            )
        )

    @staticmethod
    def _is_major_analysis(analysis: Dict[str, Any], value_score: float) -> bool:
        info_type = str(analysis.get("info_type") or "其他")
        major_release = (
            info_type in MAJOR_EVENT_TYPES
            and _number(analysis.get("score_trend")) >= 9.0
            and _number(analysis.get("score_credibility")) >= 8.0
            and value_score >= 7.0
        )
        engineering_breakthrough = (
            info_type in {"技术方案", "工程实践", "模型发布", "产品发布"}
            and _number(analysis.get("score_engineering")) >= 9.0
            and _number(analysis.get("score_trend")) >= 8.5
            and _number(analysis.get("score_credibility")) >= 8.0
            and value_score >= 7.0
        )
        return major_release or engineering_breakthrough

    def _enrich(self, result: Dict[str, Any]) -> Dict[str, Any]:
        analysis = result.get("analysis", {})
        article = result["article"]
        value_score = _number(analysis.get("value_score"))
        rank_score = round(
            value_score * 0.5
            + _number(analysis.get("score_tech_depth")) * 0.2
            + _number(analysis.get("score_engineering")) * 0.2
            + _number(analysis.get("score_trend")) * 0.1,
            2,
        )
        title = str(analysis.get("title_cn") or article.title or "")
        must_include = self._is_major_analysis(analysis, value_score)
        terms = _title_terms(title)
        for field in ("keywords", "tech_tags", "companies"):
            terms.update(value.lower() for value in _string_values(analysis.get(field)))
        return {
            "topic_id": article.url_hash,
            "result": result,
            "title": title,
            "source_code": article.source_code or "unknown",
            "category": str(analysis.get("category") or "其他AI相关"),
            "value_score": value_score,
            "l3_rank_score": rank_score,
            "must_include": must_include,
            "terms": terms,
            "related_count": 1,
        }

    def _cluster(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        topics: List[Dict[str, Any]] = []
        for item in items:
            matched = next((
                topic for topic in topics
                if topic["category"] == item["category"]
                and self._similarity(topic["terms"], item["terms"]) >= self.similarity_threshold
            ), None)
            if matched:
                matched["terms"].update(item["terms"])
                matched["must_include"] = matched["must_include"] or item["must_include"]
                matched["related_count"] += 1
            else:
                topics.append(dict(item))
        return topics

    @staticmethod
    def _similarity(left: Set[str], right: Set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    @staticmethod
    def _metadata(
        eligible: List[Dict[str, Any]],
        selected: List[Dict[str, Any]],
        topic_count: int,
    ) -> Dict[str, Any]:
        return {
            "eligible": len(eligible),
            "topics": topic_count,
            "selected": len(selected),
            "excluded": max(0, len(eligible) - len(selected)),
            "selected_articles": [
                {
                    "url_hash": item["result"]["article"].url_hash,
                    "source_code": item["source_code"],
                    "category": item["category"],
                    "title": item["title"],
                    "value_score": item["value_score"],
                    "major_event": item["must_include"],
                    "related_count": item["related_count"],
                }
                for item in selected
            ],
        }
