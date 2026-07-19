"""Staged entry points over the shared production collection pipeline."""

import json
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from config import AWSConfig
from crawler.base import RawArticle
from crawler.source_strategies import (
    CONFIGURED,
    SERVER_RECOMMENDED,
    match_server_coverage_aliases,
)
from jobs.collect_job import CollectOrchestrator
from logging_config import get_logger
from processor.parser import ContentParser
from processor.collection_audit import CollectionAudit
from processor.collection_snapshot import CollectionSnapshotStore


logger = get_logger("jobs.validation")


class ValidationStore:
    """Atomic local JSON storage below data/validation."""

    SAFE_BATCH_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

    def __init__(self, data_dir: str):
        self.root_dir = os.path.join(data_dir, "validation")
        self.collection_dir = os.path.join(self.root_dir, "collections")
        self.analysis_dir = os.path.join(self.root_dir, "analyses")

    def save_collection(self, batch_no: str, payload: Dict[str, Any]) -> str:
        return self._save(self.collection_dir, f"{batch_no}.json", payload)

    def load_collection(self, batch_no: str) -> Dict[str, Any]:
        self._validate_batch_no(batch_no)
        path = os.path.join(self.collection_dir, f"{batch_no}.json")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"采集验证批次不存在: {batch_no}")
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_analysis(self, batch_no: str, payload: Dict[str, Any]) -> str:
        return self._save(self.analysis_dir, f"{batch_no}.json", payload)

    @classmethod
    def _validate_batch_no(cls, batch_no: str) -> None:
        if not batch_no or not cls.SAFE_BATCH_PATTERN.fullmatch(batch_no):
            raise ValueError("collection_batch_no 格式无效")

    @staticmethod
    def _save(directory: str, filename: str, payload: Dict[str, Any]) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, filename)
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(temp_path, path)
        return os.path.abspath(path)


def _new_batch_no(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"


def _parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _article_to_dict(
    article: RawArticle,
    coverage_aliases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "source_code": article.source_code,
        "title": article.title,
        "url": article.url,
        "url_hash": article.url_hash,
        "author": article.author,
        "publish_time": article.publish_time.isoformat() if article.publish_time else None,
        "crawl_time": article.crawl_time.isoformat(),
        "raw_html": article.raw_html,
        "raw_summary": article.raw_summary,
        "content_hash": article.content_hash,
        "predicted_category": article.predicted_category,
        "ai_related": article.ai_related,
        "info_type_hint": article.info_type_hint,
        "route_confidence": article.route_confidence,
        "route_reason": article.route_reason,
        "route_method": article.route_method,
        "candidate_score": article.candidate_score,
        "coverage_aliases": coverage_aliases or [],
    }


def _article_from_dict(data: Dict[str, Any]) -> RawArticle:
    article = RawArticle(
        source_code=data["source_code"],
        title=data.get("title") or "Untitled",
        url=data["url"],
        author=data.get("author"),
        publish_time=_parse_optional_datetime(data.get("publish_time")),
        crawl_time=_parse_optional_datetime(data.get("crawl_time")) or datetime.now(),
        raw_html=data.get("raw_html"),
        raw_summary=data.get("raw_summary"),
        content_hash=data.get("content_hash"),
        predicted_category=data.get("predicted_category"),
        ai_related=data.get("ai_related"),
        info_type_hint=data.get("info_type_hint"),
        route_confidence=float(data.get("route_confidence") or 0),
        route_reason=data.get("route_reason"),
        route_method=data.get("route_method"),
        candidate_score=float(data.get("candidate_score") or 0),
    )
    if data.get("url_hash"):
        article.url_hash = data["url_hash"]
    return article


def _content_text(article: RawArticle) -> str:
    if article.raw_html:
        return ContentParser.extract_main_content(article.raw_html).strip()
    return ContentParser.extract_text(article.raw_summary or "").strip()


def _deduplicate_urls(articles: Iterable[RawArticle]) -> Tuple[List[RawArticle], int]:
    seen = set()
    result = []
    duplicates = 0
    for article in articles:
        if article.url_hash in seen:
            duplicates += 1
            continue
        seen.add(article.url_hash)
        result.append(article)
    return result, duplicates


class ValidationCollectionService:
    """Collect raw data only; no LLM, import, or production dedup side effects."""

    def __init__(self, config: AWSConfig):
        self.config = config
        self.store = ValidationStore(config.data_dir)
        self.orchestrator = CollectOrchestrator(config, initialize_analysis=False)

    @staticmethod
    def _safe_source_profile(source: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "code", "name", "type", "category", "domain", "access_url",
            "fetch_method", "_variant_name",
            "selection_role", "semantic_routing", "include_keywords",
            "exclude_keywords",
        }
        return {key: value for key, value in source.items() if key in allowed}

    def run(
        self,
        strategy: str,
        scope: str = "all",
        sources: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        task_type: str = "manual_backfill",
    ) -> Dict[str, Any]:
        started_at = datetime.now()
        batch_no = _new_batch_no("VAL-COL")
        logger.info(
            "====== 采集验证开始: batch_no=%s, strategy=%s ======",
            batch_no,
            strategy,
        )
        collection = self.orchestrator.collect_stage(
            strategy=strategy,
            sources=sources,
            from_date=from_date,
            to_date=to_date,
            hydrate_candidates=True,
            strict_sources=True,
        )
        all_articles = collection["articles"]
        source_results = []
        for source_result in collection["source_results"]:
            source_code = source_result["source_code"]
            source_articles = [
                article for article in all_articles
                if article.source_code == source_code
            ]
            source_results.append({
                **source_result,
                "content_available_count": sum(
                    1 for article in source_articles
                    if len(_content_text(article)) >= 100
                ),
                "source_profile": self._safe_source_profile(
                    source_result.get("source_profile") or {}
                ),
            })

        unique_articles, duplicate_count = _deduplicate_urls(all_articles)
        coverage_aliases = {}
        if strategy == SERVER_RECOMMENDED:
            coverage_aliases = {
                article.url_hash: match_server_coverage_aliases(
                    article.source_code,
                    article.title,
                    article.raw_summary or "",
                )
                for article in unique_articles
            }
        source_counts = dict(Counter(item.source_code for item in unique_articles))
        alias_counts = dict(Counter(
            alias
            for aliases in coverage_aliases.values()
            for alias in aliases
        ))
        stats = {
            "source_count": collection["source_count"],
            "success_sources": sum(1 for item in source_results if item["status"] == "success"),
            "partial_sources": sum(1 for item in source_results if item["status"] == "partial"),
            "empty_sources": sum(1 for item in source_results if item["status"] == "empty"),
            "failed_sources": sum(1 for item in source_results if item["status"] == "failed"),
            "article_count": len(unique_articles),
            "duplicate_url_count": duplicate_count,
            "content_available_count": sum(
                1 for article in unique_articles if len(_content_text(article)) >= 100
            ),
            "source_distribution": source_counts,
            "coverage_alias_distribution": alias_counts,
        }
        manifest = {
            "schema_version": "1.0",
            "batch_no": batch_no,
            "strategy": strategy,
            "request": {
                "scope": scope,
                "sources": sources or [],
                "from_date": from_date,
                "to_date": to_date,
                "task_type": task_type,
            },
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "source_results": source_results,
            "stats": stats,
            "articles": [
                _article_to_dict(article, coverage_aliases.get(article.url_hash, []))
                for article in unique_articles
            ],
        }
        result_file = self.store.save_collection(batch_no, manifest)
        logger.info(
            "====== 采集验证完成: batch_no=%s, articles=%d, file=%s ======",
            batch_no,
            len(unique_articles),
            result_file,
        )
        return {"batch_no": batch_no, "result_file": result_file, **stats}


class ValidationAnalysisService:
    """Run L2/L3 only against a saved validation collection batch."""

    def __init__(self, config: AWSConfig):
        self.config = config
        self.store = ValidationStore(config.data_dir)
        self.orchestrator = CollectOrchestrator(config)

    @staticmethod
    def _serialize_analysis(
        result: Dict[str, Any],
        coverage_aliases: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        article = result["article"]
        return {
            "article_url_hash": article.url_hash,
            "source_code": article.source_code,
            "title": article.title,
            "url": article.url,
            "publish_time": article.publish_time.isoformat() if article.publish_time else None,
            "coverage_aliases": (coverage_aliases or {}).get(article.url_hash, []),
            "analysis": result["analysis"],
        }

    @staticmethod
    def _serialize_insight(result: Dict[str, Any]) -> Dict[str, Any]:
        article = result["article"]
        return {
            "article_url_hash": article.url_hash,
            "source_code": article.source_code,
            "title": article.title,
            "url": article.url,
            "insight": result["insight"],
        }

    def run(self, collection_batch_no: str) -> Dict[str, Any]:
        manifest = self.store.load_collection(collection_batch_no)
        analysis_batch_no = _new_batch_no("VAL-ANA")
        started_at = datetime.now()
        articles = [_article_from_dict(item) for item in manifest.get("articles", [])]
        coverage_aliases = {
            item.get("url_hash", ""): item.get("coverage_aliases") or []
            for item in manifest.get("articles", [])
        }
        articles, url_duplicates = _deduplicate_urls(articles)

        source_profiles = {}
        for source_result in manifest.get("source_results", []):
            profile = source_result.get("source_profile") or {}
            if profile.get("code"):
                source_profiles[profile["code"]] = profile

        analysis_run = self.orchestrator.analyze_stage(
            articles,
            crawlers={},
            source_profiles=source_profiles,
            use_history_cache=False,
            persist_processed=False,
            enable_discovery=False,
            allow_l3_content_fetch=False,
        )
        stage_stats = analysis_run["stats"]
        l2_results = analysis_run["l2_results"]
        discarded = analysis_run["discarded_l2_results"]
        l3_candidates = analysis_run["l3_candidates"]
        l3_results = analysis_run["l3_results"]

        stats = {
            "collection_article_count": len(articles),
            "url_duplicate_count": url_duplicates,
            "candidate_pool": stage_stats["L1_candidate_pool"],
            "initial_analysis": stage_stats["L2_analysis"]["initial"],
            "refill_analysis": stage_stats["L2_analysis"]["refill"],
            "remaining_deferred": len(analysis_run["remaining_deferred"]),
            "l2_success": len(l2_results),
            "l2_discarded": len(discarded),
            "l2_source_distribution": dict(Counter(
                result["article"].source_code for result in l2_results
            )),
            "l2_category_distribution": dict(Counter(
                result.get("analysis", {}).get("category") or "其他AI相关"
                for result in l2_results
            )),
            "l3_selected": len(l3_candidates),
            "l3_success": len(l3_results),
            "l3_selection": stage_stats["L3_selection"],
            "pipeline_stage_stats": stage_stats,
            "coverage_alias_distribution": dict(Counter(
                alias
                for aliases in coverage_aliases.values()
                for alias in aliases
            )),
        }
        output = {
            "schema_version": "1.0",
            "analysis_batch_no": analysis_batch_no,
            "collection_batch_no": collection_batch_no,
            "collection_strategy": manifest.get("strategy"),
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "stats": stats,
            "analyses": [
                self._serialize_analysis(item, coverage_aliases) for item in l2_results
            ],
            "discarded_analyses": [
                self._serialize_analysis(item, coverage_aliases) for item in discarded
            ],
            "insights": [self._serialize_insight(item) for item in l3_results],
        }
        result_file = self.store.save_analysis(analysis_batch_no, output)
        logger.info(
            "====== 验证分析完成: collection=%s, analysis=%s, l2=%d, l3=%d ======",
            collection_batch_no,
            analysis_batch_no,
            len(l2_results),
            len(l3_results),
        )
        return {
            "analysis_batch_no": analysis_batch_no,
            "collection_batch_no": collection_batch_no,
            "result_file": result_file,
            **stats,
        }


def run_staged_collection(
    config: AWSConfig,
    scope: str = "all",
    sources: Optional[List[str]] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    task_type: str = "manual_backfill",
    collection_period: str = "auto",
) -> Dict[str, Any]:
    """Formal collection phase: capture hydrated source data without L2/L3/import."""
    batch_no = _new_batch_no("COL")
    limits = config.processing_limits(from_date, to_date, collection_period)
    orchestrator = CollectOrchestrator(config, initialize_analysis=False)
    audit = CollectionAudit(config.data_dir, batch_no)
    collection = orchestrator.collect_stage(
        strategy=CONFIGURED,
        sources=sources,
        from_date=from_date,
        to_date=to_date,
        hydrate_candidates=True,
        audit=audit,
        strict_sources=True,
        candidate_pool_config=limits["candidate_pool"],
    )
    articles, duplicate_count = _deduplicate_urls(collection["articles"])
    snapshot_path = CollectionSnapshotStore(config.data_dir).save(
        batch_no=batch_no,
        request={
            "scope": scope,
            "sources": sources or [],
            "from_date": from_date,
            "to_date": to_date,
            "task_type": task_type,
            "collection_period": collection_period,
            "resolved_collection_period": limits["period"],
        },
        source_profiles=collection["source_profiles"],
        articles=articles,
        update_latest=False,
    )
    stats = {
        "batch_no": batch_no,
        "scope": scope,
        "L0_collect": {
            "total": len(collection["articles"]),
            "sources": collection["source_count"],
            "errors": collection["error_count"],
        },
        "article_count": len(articles),
        "duplicate_url_count": duplicate_count,
        "source_distribution": dict(Counter(item.source_code for item in articles)),
        "processing_limits": limits,
        "collection_snapshot": {"path": snapshot_path, "article_count": len(articles)},
    }
    audit.save([
        {"source_code": item.source_code, "url": item.url, "title": item.title,
         "publish_time": item.publish_time, "status": "collected"}
        for item in articles
    ], stats)
    logger.info(
        "====== 分阶段正式采集完成: batch_no=%s, articles=%d, snapshot=%s ======",
        batch_no, len(articles), snapshot_path,
    )
    return {"batch_no": batch_no, "result_file": snapshot_path, **stats}


def run_staged_analysis(
    config: AWSConfig,
    collection_batch_no: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    task_type: str = "manual_backfill",
    collection_period: str = "auto",
) -> Dict[str, Any]:
    """Analyze a formal COL snapshot or reanalyze an existing analysis snapshot."""
    store = CollectionSnapshotStore(config.data_dir)
    snapshot = store.load(collection_batch_no)
    if not str(snapshot.get("batch_no") or "").startswith("COL-"):
        # Full collect and staged analysis both persist analysis snapshots. Reuse
        # the same formal rerun path rather than maintaining a second L2/L3 flow.
        return CollectOrchestrator(config)._run_snapshot_reanalysis(
            task_type="reanalysis",
            reanalysis_batch_no=collection_batch_no,
            collection_period=collection_period,
            from_date=from_date,
            to_date=to_date,
        )
    request = snapshot.get("request") or {}
    articles = [CollectionSnapshotStore.article_from_dict(item) for item in snapshot.get("articles", [])]
    articles = CollectOrchestrator._filter_by_date(articles, from_date, to_date)
    if not articles:
        raise ValueError("指定采集批次在所选时间范围内不包含可分析文章")
    effective_from = from_date or request.get("from_date")
    effective_to = to_date or request.get("to_date")
    period = collection_period if collection_period != "auto" else (
        "auto" if from_date or to_date else request.get("resolved_collection_period", "auto")
    )
    limits = config.processing_limits(effective_from, effective_to, period)
    batch_no = f"IMP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    orchestrator = CollectOrchestrator(config)
    audit = CollectionAudit(config.data_dir, batch_no)
    analysis_run = orchestrator.analyze_stage(
        articles,
        crawlers={},
        source_profiles=snapshot.get("source_profiles") or {},
        from_date=from_date,
        to_date=to_date,
        data_sources=config.get_data_sources(),
        # A named COL snapshot is an explicit replay input. Do not let a
        # previous weekly run suppress articles needed by a later monthly run.
        # Batch URL/content de-duplication still runs, and successful L2
        # results are still written back to the shared cache for future jobs.
        use_history_cache=False,
        persist_processed=True,
        enable_discovery=True,
        allow_l3_content_fetch=True,
        audit=audit,
        replay_snapshot=False,
        candidate_pool_config=limits["candidate_pool"],
        l3_max_candidates=limits["l3_max_candidates"],
    )
    l2_results = analysis_run["l2_results"]
    discarded = analysis_run["discarded_l2_results"]
    l3_candidates = analysis_run["l3_candidates"]
    l3_results = analysis_run["l3_results"]
    source_profiles = snapshot.get("source_profiles") or {}
    operation_metrics = {
        "batch_time": datetime.now().isoformat(),
        "l1_article_count": analysis_run["stats"]["L1_candidate_pool"]["total"],
        "l1_source_distribution": analysis_run["stats"]["L1_candidate_pool"].get("source_counts", {}),
        "l2_article_count": len(l2_results),
        "l2_source_distribution": dict(Counter(item["article"].source_code for item in l2_results)),
        "l2_category_distribution": dict(Counter(item["analysis"].get("category") or "其他AI相关" for item in l2_results)),
        "l3_article_count": len(l3_candidates),
        "l3_source_distribution": dict(Counter(item["article"].source_code for item in l3_candidates)),
        "l3_category_distribution": dict(Counter(item["analysis"].get("category") or "其他AI相关" for item in l3_candidates)),
        "stage_detail": {**analysis_run["stats"], "collection_batch_no": collection_batch_no,
                         "processing_limits": limits},
    }
    payload, import_result = orchestrator.import_analysis_results(
        batch_no, task_type, source_profiles, l2_results, discarded, l3_candidates,
        l3_results, operation_metrics, replace_existing_insights=True,
    )
    result = {
        "batch_no": batch_no,
        "collection_batch_no": collection_batch_no,
        "collection_article_count": len(snapshot.get("articles", [])),
        "analysis_article_count": len(articles),
        "from_date": from_date,
        "to_date": to_date,
        "l2_success": len(l2_results),
        "l2_discarded": len(discarded),
        "l3_selected": len(l3_candidates),
        "l3_success": len(l3_results),
        "processing_limits": limits,
        "stage_stats": analysis_run["stats"],
        "import": {"status": "success" if import_result.get("success") else "failed"},
    }
    if not import_result.get("success"):
        result["import"]["error"] = import_result.get("error", "unknown_error")
        result["import"]["retry_files"] = orchestrator._persist_failed_import_payload(
            payload, import_result, result,
        )
        return result
    analysis_path = store.save(
        batch_no=batch_no,
        request={**request, "collection_batch_no": collection_batch_no,
                 "from_date": from_date, "to_date": to_date,
                 "resolved_collection_period": limits["period"]},
        source_profiles=source_profiles,
        articles=[item["article"] for item in (l2_results + discarded)],
        update_latest=True,
    )
    result["analysis_snapshot"] = {"path": analysis_path, "article_count": len(l2_results) + len(discarded)}
    audit.save([], result)
    logger.info(
        "====== 分阶段正式分析完成: collection=%s, batch=%s, l2=%d, l3=%d ======",
        collection_batch_no, batch_no, len(l2_results), len(l3_results),
    )
    return result


def _parse_params(params: Any) -> Dict[str, Any]:
    if not params:
        return {}
    if isinstance(params, str):
        return json.loads(params)
    return dict(params)


def handle_validation_collect(params: Any = None) -> Dict[str, Any]:
    parsed = _parse_params(params)
    sources = parsed.get("sources")
    if isinstance(sources, str):
        sources = [item.strip() for item in sources.split(",") if item.strip()]
    return run_staged_collection(
        AWSConfig(),
        scope=parsed.get("scope", "all"),
        sources=sources,
        from_date=parsed.get("from_date") or parsed.get("from"),
        to_date=parsed.get("to_date") or parsed.get("to"),
        task_type=parsed.get("task_type", "manual_backfill"),
        collection_period=parsed.get("collection_period", "auto"),
    )


def handle_validation_analysis(params: Any = None) -> Dict[str, Any]:
    parsed = _parse_params(params)
    collection_batch_no = parsed.get("collection_batch_no") or parsed.get("batch_no")
    if not collection_batch_no:
        raise ValueError("collection_batch_no 不能为空")
    return run_staged_analysis(
        AWSConfig(),
        collection_batch_no=collection_batch_no,
        from_date=parsed.get("from_date") or parsed.get("from"),
        to_date=parsed.get("to_date") or parsed.get("to"),
        task_type=parsed.get("task_type", "manual_backfill"),
        collection_period=parsed.get("collection_period", "auto"),
    )
