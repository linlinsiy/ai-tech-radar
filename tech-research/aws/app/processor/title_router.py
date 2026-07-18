"""Batch semantic routing for mixed-source article candidates."""

import json
from typing import Any, Dict, List

from crawler.base import RawArticle
from llm.client import LLMClient
from llm.prompts import PromptRegistry
from logging_config import get_logger


logger = get_logger("processor.title_router")


class TitleRouter:
    """Annotate mixed-source candidates without producing formal L2 scores."""

    def __init__(
        self,
        llm: LLMClient,
        prompts: PromptRegistry,
        config: Dict[str, Any],
        model_name: str,
        categories: List[str],
    ):
        self.llm = llm
        self.prompts = prompts
        self.enabled = bool(config.get("enabled", True))
        self.batch_size = max(1, int(config.get("batch_size", 20)))
        self.min_confidence = float(config.get("min_confidence", 0.65))
        self.max_tokens = max(512, int(config.get("max_tokens", 4096)))
        self.model_name = model_name
        self.categories = categories

    def route(
        self,
        articles: List[RawArticle],
        source_profiles: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        targets = [
            article for article in articles
            if self._needs_semantic_routing(source_profiles.get(article.source_code, {}))
        ]
        stats = {
            "enabled": self.enabled,
            "candidates": len(articles),
            "routed": 0,
            "ai_related": 0,
            "filtered": 0,
            "low_confidence": 0,
            "fallback": 0,
            "batches": 0,
        }
        if not self.enabled or not targets:
            return stats

        for offset in range(0, len(targets), self.batch_size):
            batch = targets[offset:offset + self.batch_size]
            stats["batches"] += 1
            if not self._route_batch(batch, source_profiles, stats):
                stats["fallback"] += len(batch)
                for article in batch:
                    article.route_method = "rule_fallback"
        logger.info(
            "标题语义路由完成: candidates=%d, targets=%d, routed=%d, related=%d, filtered=%d, low_confidence=%d, fallback=%d",
            stats["candidates"],
            len(targets),
            stats["routed"],
            stats["ai_related"],
            stats["filtered"],
            stats["low_confidence"],
            stats["fallback"],
        )
        return stats

    def _route_batch(
        self,
        articles: List[RawArticle],
        source_profiles: Dict[str, Dict[str, Any]],
        stats: Dict[str, Any],
    ) -> bool:
        items = []
        for index, article in enumerate(articles):
            source = source_profiles.get(article.source_code, {})
            items.append({
                "index": index,
                "title": article.title,
                "summary": (article.raw_summary or "")[:500],
                "source_name": source.get("name", article.source_code),
                "source_category": source.get("category", ""),
            })

        system, user, _version, _configured_model = self.prompts.render(
            "title_route",
            categories=",".join(self.categories),
            items=json.dumps(items, ensure_ascii=False),
        )
        if not system or not user:
            logger.warning("标题语义路由 Prompt 不可用，回退规则路由")
            return False
        result = self.llm.call(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=self.model_name,
            temperature=0.0,
            max_tokens=self.max_tokens,
            response_json=True,
        )
        if not result.get("success"):
            logger.warning("标题语义路由调用失败，回退规则路由")
            return False
        parsed = self.llm.parse_json_response(result)
        routed_items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(routed_items, list):
            logger.warning("标题语义路由返回格式无效，回退规则路由")
            return False

        by_index = {
            int(item["index"]): item
            for item in routed_items
            if isinstance(item, dict) and str(item.get("index", "")).isdigit()
        }
        if set(by_index) != set(range(len(articles))):
            logger.warning(
                "标题语义路由返回数量不一致: expected=%d, actual=%d",
                len(articles),
                len(by_index),
            )
            return False

        for index, article in enumerate(articles):
            routed = by_index[index]
            confidence = self._confidence(routed.get("confidence"))
            article.route_confidence = confidence
            article.route_reason = str(routed.get("reason") or "")[:300]
            article.route_method = "semantic"
            category = str(routed.get("predicted_category") or "").strip()
            if category in self.categories:
                article.predicted_category = category
            article.info_type_hint = str(routed.get("info_type_hint") or "").strip()
            stats["routed"] += 1
            if confidence < self.min_confidence:
                article.ai_related = None
                stats["low_confidence"] += 1
                continue
            article.ai_related = self._boolean(routed.get("ai_related"))
            if article.ai_related:
                stats["ai_related"] += 1
            else:
                stats["filtered"] += 1
        return True

    @staticmethod
    def _needs_semantic_routing(source: Dict[str, Any]) -> bool:
        configured = str(source.get("semantic_routing") or "").strip().lower()
        if configured:
            return configured in {"true", "1", "yes"}
        return bool(source.get("include_keywords") or source.get("exclude_keywords"))

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "是"}
