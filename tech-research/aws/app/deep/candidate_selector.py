"""Balanced L3 candidate selection using the shared L2 rank score."""

import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from logging_config import get_logger


logger = get_logger("deep.candidate_selector")


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
    """Collapse repeated topics and apply uniform source/category constraints."""

    def __init__(
        self,
        config: Dict[str, Any],
        min_score: float,
        source_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.config = config
        self.min_score = min_score
        self.source_profiles = source_profiles or {}
        self.enabled = bool(config.get("enabled", True))
        self.max_candidates = max(1, int(config.get("max_candidates_per_batch", 36)))
        self.max_category_ratio = float(config.get("max_category_ratio", 0.35))
        self.similarity_threshold = float(config.get("topic_similarity_threshold", 0.34))
        self.min_credibility = float(config.get("min_credibility_score", 6.5))
        self.min_sources_for_balance = max(1, int(config.get("min_sources_for_balance", 3)))
        self.min_categories_for_balance = max(1, int(config.get("min_categories_for_balance", 2)))
        self.source_role_ratios = {
            "engineering": float(config.get("engineering_source_ratio", 0.15)),
            "industry": float(config.get("industry_source_ratio", 0.10)),
            "research": float(config.get("research_source_ratio", 0.05)),
        }

    def select(
        self,
        l2_results: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        outcomes: Dict[str, Dict[str, Any]] = {}
        eligible = []
        for result in l2_results:
            reason = self._eligibility_reason(result)
            article = result.get("article")
            url_hash = article.url_hash if article else ""
            if reason:
                if url_hash:
                    outcomes[url_hash] = self._outcome(result, reason)
                continue
            item = self._enrich(result)
            eligible.append(item)
            outcomes[url_hash] = self._outcome(result, "eligible")

        eligible.sort(key=lambda item: item["rank_score"], reverse=True)
        topics = self._cluster(eligible, outcomes)
        capacity = min(self.max_candidates, len(topics))
        source_total = len({topic["source_code"] for topic in topics})
        category_total = len({topic["category"] for topic in topics})
        constraints_needed = len(topics) > self.max_candidates
        source_balance_active = (
            constraints_needed and source_total >= self.min_sources_for_balance
        )
        category_balance_active = (
            constraints_needed and category_total >= self.min_categories_for_balance
        )

        if not self.enabled or not constraints_needed:
            selected = topics[:capacity]
            source_limits = {}
            category_limit = capacity
        else:
            source_limits = {
                source: self._source_limit(source)
                for source in {topic["source_code"] for topic in topics}
            }
            category_limit = max(1, math.ceil(self.max_candidates * self.max_category_ratio))
            selected = self._select_balanced(
                topics,
                capacity,
                source_limits,
                category_limit,
                source_balance_active,
                category_balance_active,
            )

        selected_ids = {topic["topic_id"] for topic in selected}
        for topic in topics:
            reason = "selected" if topic["topic_id"] in selected_ids else "excluded_by_balance"
            outcomes[topic["topic_id"]] = self._outcome(topic["result"], reason)

        source_counts = Counter(topic["source_code"] for topic in selected)
        category_counts = Counter(topic["category"] for topic in selected)
        metadata = {
            "eligible": len(eligible),
            "topics": len(topics),
            "selected": len(selected),
            "excluded": max(0, len(eligible) - len(selected)),
            "capacity": self.max_candidates,
            "source_limits": source_limits,
            "category_limit": category_limit,
            "source_counts": dict(source_counts),
            "category_counts": dict(category_counts),
            "source_balance_active": source_balance_active,
            "category_balance_active": category_balance_active,
            "article_outcomes": list(outcomes.values()),
            "selected_articles": [
                {
                    "url_hash": topic["topic_id"],
                    "source_code": topic["source_code"],
                    "category": topic["category"],
                    "title": topic["title"],
                    "rank_score": topic["rank_score"],
                    "related_count": len(topic["member_hashes"]),
                }
                for topic in selected
            ],
        }
        logger.info(
            "L3 候选均衡完成: eligible=%d, topics=%d, selected=%d, sources=%d",
            len(eligible),
            len(topics),
            len(selected),
            len(source_counts),
        )
        return [topic["result"] for topic in selected], metadata

    def _select_balanced(
        self,
        topics: List[Dict[str, Any]],
        capacity: int,
        source_limits: Dict[str, int],
        category_limit: int,
        source_balance_active: bool,
        category_balance_active: bool,
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        selected_ids = set()
        source_counts = Counter()
        category_counts = Counter()

        while len(selected) < capacity:
            remaining = [
                topic for topic in topics if topic["topic_id"] not in selected_ids
            ]
            if not remaining:
                break
            sources = sorted(
                {topic["source_code"] for topic in remaining},
                key=lambda source: (
                    source_counts[source],
                    -max(
                        topic["rank_score"]
                        for topic in remaining
                        if topic["source_code"] == source
                    ),
                ),
            )
            progressed = False
            for source in sources:
                if (
                    source_balance_active
                    and source_counts[source] >= source_limits[source]
                ):
                    continue
                candidate = next((
                    topic for topic in remaining
                    if topic["source_code"] == source
                    and (
                        not category_balance_active
                        or category_counts[topic["category"]] < category_limit
                    )
                ), None)
                if not candidate:
                    continue
                selected.append(candidate)
                selected_ids.add(candidate["topic_id"])
                source_counts[source] += 1
                category_counts[candidate["category"]] += 1
                progressed = True
                if len(selected) >= capacity:
                    break
            if not progressed:
                break
        return selected

    def _eligibility_reason(self, result: Dict[str, Any]) -> str:
        article = result.get("article")
        analysis = result.get("analysis", {})
        if article is None:
            return "article_missing"
        if self._rank_score(analysis) < self.min_score:
            return "score_below_threshold"
        if analysis.get("need_deep_analysis") is False:
            return "deep_analysis_not_needed"
        if _number(analysis.get("score_credibility"), 0) < self.min_credibility:
            return "credibility_gate_failed"
        return ""

    def _enrich(self, result: Dict[str, Any]) -> Dict[str, Any]:
        analysis = result.get("analysis", {})
        article = result["article"]
        title = str(analysis.get("title_cn") or article.title or "")
        terms = _title_terms(title)
        for field in ("keywords", "tech_tags", "companies"):
            terms.update(value.lower() for value in _string_values(analysis.get(field)))
        return {
            "topic_id": article.url_hash,
            "result": result,
            "title": title,
            "source_code": article.source_code or "unknown",
            "category": str(analysis.get("category") or "其他AI相关"),
            "rank_score": self._rank_score(analysis),
            "terms": terms,
            "member_hashes": [article.url_hash],
        }

    def _cluster(
        self,
        items: List[Dict[str, Any]],
        outcomes: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        topics: List[Dict[str, Any]] = []
        for item in items:
            matched = next((
                topic for topic in topics
                if topic["category"] == item["category"]
                and self._similarity(topic["terms"], item["terms"])
                >= self.similarity_threshold
            ), None)
            if matched:
                matched["terms"].update(item["terms"])
                matched["member_hashes"].append(item["topic_id"])
                outcomes[item["topic_id"]] = self._outcome(
                    item["result"],
                    "merged_topic",
                )
            else:
                topics.append(dict(item))
        return topics

    def _source_limit(self, source_code: str) -> int:
        profile = self.source_profiles.get(source_code, {})
        role = str(profile.get("selection_role") or "engineering")
        ratio = self.source_role_ratios.get(role, self.source_role_ratios["engineering"])
        return max(1, math.ceil(self.max_candidates * ratio))

    @staticmethod
    def _rank_score(analysis: Dict[str, Any]) -> float:
        rank_score = analysis.get("rank_score")
        if rank_score is None:
            rank_score = analysis.get("value_score")
        return _number(rank_score)

    @staticmethod
    def _similarity(left: Set[str], right: Set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    @classmethod
    def _outcome(cls, result: Dict[str, Any], reason: str) -> Dict[str, Any]:
        article = result.get("article")
        analysis = result.get("analysis", {})
        return {
            "url_hash": article.url_hash if article else "",
            "source_code": article.source_code if article else "",
            "category": analysis.get("category") or "其他AI相关",
            "rank_score": cls._rank_score(analysis),
            "reason": reason,
        }
