"""L3 candidate selection using topic deduplication and the shared rank score."""

import json
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
    """Collapse repeated topics and retain the highest-scoring candidates."""

    def __init__(
        self,
        config: Dict[str, Any],
        min_score: float,
        source_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.config = config
        self.min_score = min_score
        # Kept for constructor compatibility; source identity no longer affects selection.
        self.source_profiles = source_profiles or {}
        self.max_candidates = max(1, int(config.get("max_candidates_per_batch", 50)))
        self.similarity_threshold = float(config.get("topic_similarity_threshold", 0.34))
        self.topic_trend_boost_enabled = str(
            config.get("topic_trend_boost_enabled", False)
        ).lower() == "true"
        self.topic_trend_boost_min_sources = max(
            2, int(config.get("topic_trend_boost_min_sources", 2))
        )
        self.topic_trend_boost_score = min(
            10.0, max(0.0, _number(config.get("topic_trend_boost_score"), 10.0))
        )
        self.topic_trend_boost_min_org_relevance = _number(
            config.get("topic_trend_boost_min_org_relevance"), 6.0
        )
        self.topic_trend_boost_similarity_threshold = float(
            config.get("topic_trend_boost_similarity_threshold", self.similarity_threshold)
        )

    def select(
        self,
        l2_results: List[Dict[str, Any]],
        max_candidates: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        outcomes: Dict[str, Dict[str, Any]] = {}
        enriched = []
        for result in l2_results:
            article = result.get("article")
            if article is None:
                continue
            enriched.append(self._enrich(result))

        topic_trend_boosts = self._apply_topic_trend_boost(enriched)
        eligible = []
        for item in enriched:
            result = item["result"]
            reason = self._eligibility_reason(result)
            url_hash = item["topic_id"]
            if reason:
                if url_hash:
                    outcomes[url_hash] = self._outcome(result, reason)
                continue
            eligible.append(item)
            outcomes[url_hash] = self._outcome(result, "eligible")

        eligible.sort(key=self._sort_key, reverse=True)
        topics = self._cluster(eligible, outcomes)
        configured_capacity = max(1, int(max_candidates or self.max_candidates))
        capacity = min(configured_capacity, len(topics))
        selected = topics[:capacity]

        selected_ids = {topic["topic_id"] for topic in selected}
        for topic in topics:
            reason = "selected" if topic["topic_id"] in selected_ids else "excluded_by_capacity"
            outcomes[topic["topic_id"]] = self._outcome(topic["result"], reason)

        source_counts = Counter(topic["source_code"] for topic in selected)
        category_counts = Counter(topic["category"] for topic in selected)
        metadata = {
            "eligible": len(eligible),
            "topics": len(topics),
            "selected": len(selected),
            "excluded": max(0, len(eligible) - len(selected)),
            "capacity": configured_capacity,
            "selection_mode": "rank_only",
            "source_counts": dict(source_counts),
            "category_counts": dict(category_counts),
            "topic_trend_boosts": topic_trend_boosts,
            "article_outcomes": list(outcomes.values()),
            "selected_articles": [
                {
                    "url_hash": topic["topic_id"],
                    "source_code": topic["source_code"],
                    "category": topic["category"],
                    "title": topic["title"],
                    "rank_score": topic["rank_score"],
                    "related_count": len(topic["member_hashes"]),
                    "topic_trend_boosted": bool(
                        topic["result"].get("analysis", {}).get("analysis_detail", {})
                        .get("topic_trend_boost")
                    ),
                }
                for topic in selected
            ],
        }
        logger.info(
            "L3 候选排序完成: eligible=%d, topics=%d, selected=%d, sources=%d",
            len(eligible),
            len(topics),
            len(selected),
            len(source_counts),
        )
        return [topic["result"] for topic in selected], metadata

    def _eligibility_reason(self, result: Dict[str, Any]) -> str:
        article = result.get("article")
        analysis = result.get("analysis", {})
        if article is None:
            return "article_missing"
        if self._rank_score(analysis) < self.min_score:
            return "score_below_threshold"
        return ""

    def _enrich(self, result: Dict[str, Any]) -> Dict[str, Any]:
        analysis = result.get("analysis", {})
        article = result["article"]
        title = str(analysis.get("title_cn") or article.title or "")
        title_terms = _title_terms(title)
        terms = set(title_terms)
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
            "title_terms": title_terms,
            "member_hashes": [article.url_hash],
        }

    def _apply_topic_trend_boost(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Promote one eligible representative when independent sources corroborate a topic."""
        if not self.topic_trend_boost_enabled:
            return []

        topics: List[Dict[str, Any]] = []
        for item in sorted(items, key=self._sort_key, reverse=True):
            matched = next((
                topic for topic in topics
                if max(
                    self._similarity(topic["terms"], item["terms"]),
                    self._similarity(topic["title_terms"], item["title_terms"]),
                )
                >= self.topic_trend_boost_similarity_threshold
            ), None)
            if matched:
                matched["terms"].update(item["terms"])
                matched["title_terms"].update(item["title_terms"])
                matched["members"].append(item)
            else:
                topics.append({
                    "terms": set(item["terms"]),
                    "title_terms": set(item["title_terms"]),
                    "members": [item],
                })

        boosts = []
        for topic in topics:
            members = topic["members"]
            source_codes = sorted({item["source_code"] for item in members})
            if len(source_codes) < self.topic_trend_boost_min_sources:
                continue

            representative = max(members, key=self._sort_key)
            analysis = representative["result"].get("analysis", {})
            if not self._is_hard_event(analysis):
                continue
            if _number(analysis.get("score_org_relevance")) < self.topic_trend_boost_min_org_relevance:
                continue

            original_trend = _number(analysis.get("score_trend"))
            if original_trend >= self.topic_trend_boost_score:
                continue

            analysis["score_trend"] = self.topic_trend_boost_score
            rank_score = self._calculate_rank_score(analysis)
            analysis["rank_score"] = rank_score
            analysis["value_score"] = rank_score
            detail = analysis.get("analysis_detail")
            if not isinstance(detail, dict):
                detail = {}
                analysis["analysis_detail"] = detail
            original_trend_reason = str(detail.get("trend_reason") or "").strip()
            boost_reason = (
                "同一话题被多个独立来源提及，提升趋势重要性"
                f"（独立来源={len(source_codes)}，来源={','.join(source_codes)}，"
                f"{original_trend:.1f}分提升至{self.topic_trend_boost_score:.1f}分）"
            )
            detail["trend_reason"] = (
                f"{original_trend_reason}；{boost_reason}"
                if original_trend_reason else boost_reason
            )
            detail["topic_trend_boost"] = {
                "distinct_source_count": len(source_codes),
                "source_codes": source_codes,
                "original_trend_score": original_trend,
                "original_trend_reason": original_trend_reason,
                "trend_score": self.topic_trend_boost_score,
                "reason": "同一话题被多个独立来源提及，提升趋势重要性",
            }
            representative["rank_score"] = rank_score
            boosts.append({
                "representative_url_hash": representative["topic_id"],
                "representative_title": representative["title"],
                "distinct_source_count": len(source_codes),
                "source_codes": source_codes,
                "original_trend_score": original_trend,
                "trend_score": self.topic_trend_boost_score,
                "rank_score": rank_score,
            })

        if boosts:
            logger.info(
                "L3 跨来源话题趋势提升完成: topics=%d, representatives=%d",
                len(topics),
                len(boosts),
            )
        return boosts

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

    @classmethod
    def _sort_key(cls, item: Dict[str, Any]) -> Tuple[float, ...]:
        analysis = item.get("result", {}).get("analysis", {})
        return (
            item["rank_score"],
            _number(analysis.get("score_org_relevance")),
            _number(analysis.get("score_engineering")),
            _number(analysis.get("score_trend")),
            _number(analysis.get("score_tech_depth")),
            _number(analysis.get("score_timeliness")),
        )

    @staticmethod
    def _rank_score(analysis: Dict[str, Any]) -> float:
        rank_score = analysis.get("rank_score")
        if rank_score is None:
            rank_score = analysis.get("value_score")
        return _number(rank_score)

    @staticmethod
    def _calculate_rank_score(analysis: Dict[str, Any]) -> float:
        return round(
            _number(analysis.get("score_org_relevance")) * 0.35
            + _number(analysis.get("score_trend")) * 0.30
            + _number(analysis.get("score_engineering")) * 0.20
            + _number(analysis.get("score_tech_depth")) * 0.10
            + _number(analysis.get("score_timeliness")) * 0.05,
            2,
        )

    @staticmethod
    def _is_hard_event(analysis: Dict[str, Any]) -> bool:
        """Opinions and commentary cannot become hard events through re-reporting."""
        info_type = str(analysis.get("info_type") or "").lower()
        opinion_terms = ("观点", "评论", "访谈", "人物言论", "争议", "社论", "解读")
        return not any(term in info_type for term in opinion_terms)

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
