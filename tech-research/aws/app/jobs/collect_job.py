"""
编排主流程 - aiRadarCollectJob

XXL-Job JobHandler 实现，串联采集分析全流程：
L0 采集 → L1 解析去重 → L2 基础分析 → L3 深度洞察 → 受控导入
各阶段失败独立处理，不阻塞其他文章。
"""
import logging
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from config import AWSConfig
from crawler.base import CrawlerFactory, RawArticle
from crawler.discovery_crawler import SearchDiscoveryCrawler
from crawler.site_discovery_crawler import SiteDiscoveryCrawler
from crawler.source_strategies import CONFIGURED, build_source_plans
from processor.parser import ContentParser
from processor.dedup import DedupManager
from processor.collection_audit import CollectionAudit
from processor.candidate_pool import CandidatePoolPlanner
from processor.l2_analysis import L2Analyzer
from processor.title_router import TitleRouter
from deep.candidate_selector import L3CandidateSelector
from deep.insight import L3Analyzer
from exporter.import_client import ImportClient
from llm.client import LLMClient
from llm.prompts import PromptRegistry
from logging_config import get_logger

logger = get_logger("jobs.collect")


class CollectOrchestrator:
    """
    采集分析全流程编排器

    方法：
        run: 执行完整流程，返回各阶段统计

    类变量：
        config: AWSConfig 实例
        dedup: DedupManager 实例
        l2: L2Analyzer 实例
        l3: L3Analyzer 实例
        importer: ImportClient 实例
    """

    def __init__(self, config: AWSConfig, initialize_analysis: bool = True):
        """
        初始化编排器

        入参：
            config: AWS 配置管理器
        """
        self.config = config
        self.dedup = DedupManager(
            cache_path=f"{config.data_dir}/interim/processed_hashes.json"
        )

        self.source_profiles = {
            source["code"]: source for source in config.get_data_sources()
        }
        if not initialize_analysis:
            return

        # 初始化 LLM 客户端：L2 / L3 使用不同超时时间
        api_key = self._get_api_key()
        self.l2_llm = LLMClient(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL"),  # 临时：本地测试指向内部大模型
            max_retries=config.l2_model["max_retries"],
            timeout=config.l2_model["timeout_seconds"],
        )
        self.l3_llm = LLMClient(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL"),  # 临时：本地测试指向内部大模型
            max_retries=config.l3_model["max_retries"],
            timeout=config.l3_model["timeout_seconds"],
        )

        # 初始化 Prompt 注册表
        self.prompts = PromptRegistry()

        # 初始化分析器
        self.l2 = L2Analyzer(
            self.l2_llm, self.prompts,
            max_concurrency=config.l2_model["max_concurrency"],
            model_name=config.l2_model["model"],
            source_profiles=self.source_profiles,
            deep_analysis_min_score=config.deep_insight_min_score,
        )
        self.title_router = TitleRouter(
            self.l2_llm,
            self.prompts,
            config.title_routing_config,
            model_name=config.l2_model["model"],
            categories=self.l2.allowed_categories,
        )
        self.l3 = L3Analyzer(
            self.l3_llm, self.prompts,
            min_score=config.deep_insight_min_score,
            require_full_content=config.deep_insight_require_full_content,
            model_name=config.l3_model["model"],
            browser_fallback=config.browser_fallback_config["enabled"],
            browser_timeout_seconds=config.browser_fallback_config["timeout_seconds"],
            browser_executable_path=config.browser_fallback_config["executable_path"],
        )
        self.l3_selector = L3CandidateSelector(
            config.l3_selection_config,
            min_score=config.deep_insight_min_score,
            source_profiles=self.source_profiles,
        )

        # 初始化导入客户端
        retry_cfg = config.import_retry_config
        self.importer = ImportClient(
            endpoint_url=config.import_endpoint_url,
            timeout=retry_cfg["timeout_seconds"],
            retry_max=retry_cfg["retry_max"],
            backoff_seconds=retry_cfg["backoff_seconds"],
        )

    def _get_api_key(self) -> str:
        """获取 API Key（从环境变量）"""
        import os
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            logger.warning("OPENAI_API_KEY 未设置")
        return key

    def _with_runtime_crawler_options(self, source: Dict[str, str]) -> Dict[str, str]:
        """向数据源配置注入全局浏览器降级参数，不改变原始配置。"""
        runtime = dict(source)
        browser = self.config.browser_fallback_config
        runtime["_browser_fallback_enabled"] = str(browser["enabled"]).lower()
        runtime["_browser_timeout_seconds"] = str(browser["timeout_seconds"])
        runtime["_browser_min_content_chars"] = str(browser["min_content_chars"])
        runtime["_browser_executable_path"] = browser["executable_path"]
        pool = self.config.candidate_pool_config
        runtime["_candidate_limit"] = str(pool["candidate_limit_per_source"])
        runtime["_detail_limit"] = str(pool["initial_scored_per_source"])
        return runtime

    def _filter_new_candidates(
        self,
        articles: List[RawArticle],
        seen_hashes: set,
        use_history_cache: bool = True,
    ) -> List[RawArticle]:
        """候选阶段只检查历史和批内 URL，不提前写入已处理缓存。"""
        result = []
        for article in articles:
            if article.url_hash in seen_hashes or (
                use_history_cache and self.dedup.is_duplicate(article)
            ):
                continue
            seen_hashes.add(article.url_hash)
            result.append(article)
        return result

    @staticmethod
    def _content_text(article: RawArticle) -> str:
        if article.raw_html:
            return ContentParser.extract_main_content(article.raw_html).strip()
        return ContentParser.extract_text(article.raw_summary or "").strip()

    def _hydrate_candidates(
        self,
        candidates: List[RawArticle],
        crawlers: Dict[str, Any],
    ) -> List[RawArticle]:
        """按来源读取已选候选的正文，RSS/API 候选保持原内容。"""
        grouped: Dict[str, List[RawArticle]] = {}
        for article in candidates:
            grouped.setdefault(article.source_code, []).append(article)

        hydrated = []
        for source_code, items in grouped.items():
            crawler = crawlers.get(source_code)
            if not crawler:
                hydrated.extend(items)
                continue
            try:
                hydrated.extend(crawler.fetch_candidates(items))
            except Exception as exc:
                logger.warning("[%s] 候选正文读取失败: %s", source_code, str(exc))
        return hydrated

    def _prepare_for_l2(
        self,
        articles: List[RawArticle],
        batch_content_hashes: set,
        use_history_cache: bool = True,
    ) -> Tuple[List[RawArticle], Dict[str, int]]:
        """检查正文充分性和正文精确重复，返回可正式评分文章。"""
        minimum = self.config.candidate_pool_config["min_scoring_content_chars"]
        prepared = []
        insufficient = 0
        content_duplicates = 0
        for article in articles:
            text = self._content_text(article)
            title_only = (
                not article.raw_html
                and text.strip() == (article.title or "").strip()
            )
            if title_only or len(text) < minimum:
                insufficient += 1
                continue
            article.compute_content_hash(text)
            if (
                article.content_hash in batch_content_hashes
                or (
                    use_history_cache
                    and self.dedup.is_content_duplicate(article)
                )
            ):
                content_duplicates += 1
                continue
            batch_content_hashes.add(article.content_hash)
            prepared.append(article)
        return prepared, {
            "content_insufficient": insufficient,
            "content_duplicates": content_duplicates,
        }

    def _analyze_selected(
        self,
        candidates: List[RawArticle],
        crawlers: Dict[str, Any],
        batch_content_hashes: set,
        use_history_cache: bool = True,
        persist_processed: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        hydrated = self._hydrate_candidates(candidates, crawlers)
        prepared, quality_stats = self._prepare_for_l2(
            hydrated,
            batch_content_hashes,
            use_history_cache=use_history_cache,
        )
        results = self.l2.analyze_batch(prepared)
        successful_hashes = {result["article"].url_hash for result in results}
        for article in prepared:
            if article.url_hash not in successful_hashes and article.content_hash:
                batch_content_hashes.discard(article.content_hash)
        if persist_processed:
            self.dedup.mark_processed_batch([result["article"] for result in results])
        return results, {
            "selected": len(candidates),
            "hydrated": len(hydrated),
            "scored": len(prepared),
            "success": len(results),
            "failed": len(prepared) - len(results),
            **quality_stats,
        }

    def _candidate_refill_gaps(self, l2_results: List[Dict[str, Any]]) -> List[str]:
        minimum = self.config.candidate_pool_config["refill_min_per_category"]
        counts = Counter(
            result.get("analysis", {}).get("category", "") for result in l2_results
        )
        return [
            category for category in self.l2.allowed_categories
            if category and category != "其他AI相关" and counts[category] < minimum
        ]

    @staticmethod
    def _filter_by_date(
        articles: List[RawArticle],
        from_date: str = None,
        to_date: str = None,
    ) -> List[RawArticle]:
        if not from_date and not to_date:
            return articles
        start = datetime.fromisoformat(from_date) if from_date else None
        end = datetime.fromisoformat(to_date) if to_date else None
        if end:
            end = end.replace(hour=23, minute=59, second=59)
        filtered = []
        for article in articles:
            published = article.publish_time.replace(tzinfo=None) if article.publish_time else None
            if published is None or (
                (start is None or published >= start)
                and (end is None or published <= end)
            ):
                filtered.append(article)
        return filtered

    def collect_stage(
        self,
        strategy: str = CONFIGURED,
        sources: Optional[List[str]] = None,
        from_date: str = None,
        to_date: str = None,
        hydrate_candidates: bool = False,
        audit: Optional[CollectionAudit] = None,
        strict_sources: bool = False,
    ) -> Dict[str, Any]:
        """Run the shared source collection stage without analysis or import."""
        configured_sources = self.config.get_data_sources()
        plans = build_source_plans(
            configured_sources,
            strategy,
            requested_codes=sources,
        )
        if sources and strict_sources:
            found = {plan["source_code"] for plan in plans}
            missing = sorted(set(sources) - found)
            if missing:
                raise ValueError(f"未知数据源: {', '.join(missing)}")

        articles: List[RawArticle] = []
        crawlers: Dict[str, Any] = {}
        source_profiles: Dict[str, Dict[str, Any]] = {}
        source_results: List[Dict[str, Any]] = []

        for plan in plans:
            attempts = []
            selected_articles: List[RawArticle] = []
            selected_source: Optional[Dict[str, Any]] = None
            selected_crawler = None

            for variant in plan["variants"]:
                runtime = self._with_runtime_crawler_options(variant)
                attempt = {
                    "variant": runtime.get("_variant_name", "configured-source"),
                    "access_url": runtime.get("access_url", ""),
                    "fetch_method": runtime.get("fetch_method", "rss"),
                    "status": "empty",
                    "candidate_count": 0,
                    "article_count": 0,
                    "http_status": None,
                    "effective_url": "",
                    "error": "",
                }
                try:
                    crawler = CrawlerFactory.create(runtime)
                    candidates = crawler.discover_candidates()
                    candidates = self._filter_by_date(candidates, from_date, to_date)
                    attempt["http_status"] = crawler.last_http_status
                    attempt["effective_url"] = crawler.last_effective_url
                    attempt["error"] = (crawler.last_error or "")[:500]
                    attempt["candidate_count"] = len(candidates)
                    if not candidates:
                        if attempt["error"] or (
                            attempt["http_status"] is not None
                            and attempt["http_status"] >= 400
                        ):
                            attempt["status"] = "failed"
                        attempts.append(attempt)
                        continue

                    if hydrate_candidates:
                        hydrated = crawler.fetch_candidates(candidates)
                        hydrated_by_hash = {
                            article.url_hash: article for article in hydrated
                        }
                        selected_articles = [
                            hydrated_by_hash.get(article.url_hash, article)
                            for article in candidates
                        ]
                    else:
                        selected_articles = candidates

                    attempt["article_count"] = len(selected_articles)
                    attempt["status"] = "success"
                    selected_source = runtime
                    selected_crawler = crawler
                    attempts.append(attempt)
                    break
                except Exception as exc:
                    attempt["status"] = "failed"
                    attempt["error"] = str(exc)[:500]
                    attempts.append(attempt)
                    logger.warning(
                        "[%s] 采集变体失败: variant=%s, error=%s",
                        plan["source_code"],
                        attempt["variant"],
                        str(exc),
                    )

            status = "success" if selected_articles else (
                "failed" if any(item["status"] == "failed" for item in attempts)
                else "empty"
            )
            articles.extend(selected_articles)
            if selected_source:
                source_profiles[plan["source_code"]] = selected_source
                crawlers[plan["source_code"]] = selected_crawler

            source_result = {
                "source_code": plan["source_code"],
                "source_name": plan["source_name"],
                "category": plan["category"],
                "status": status,
                "article_count": len(selected_articles),
                "selected_variant": (
                    selected_source.get("_variant_name") if selected_source else None
                ),
                "source_profile": selected_source or {},
                "attempts": attempts,
            }
            source_results.append(source_result)

            if audit:
                audit_source = selected_source or {
                    "code": plan["source_code"],
                    "name": plan["source_name"],
                    "category": plan["category"],
                    "fetch_method": attempts[-1]["fetch_method"] if attempts else "rss",
                }
                error = next(
                    (item["error"] for item in reversed(attempts) if item["error"]),
                    "",
                )
                audit.record_source(
                    audit_source,
                    len(selected_articles),
                    status,
                    error,
                    details={
                        "candidate_limit": self.config.candidate_pool_config[
                            "candidate_limit_per_source"
                        ],
                        "candidate_cap_hit": len(selected_articles) >= self.config.candidate_pool_config[
                            "candidate_limit_per_source"
                        ],
                        "selected_variant": source_result["selected_variant"],
                        "from_date": from_date,
                        "to_date": to_date,
                    },
                )

            logger.info(
                "[%s] 发现候选 %d 篇: strategy=%s, variant=%s",
                plan["source_code"],
                len(selected_articles),
                strategy,
                source_result["selected_variant"],
            )

        return {
            "strategy": strategy,
            "articles": articles,
            "crawlers": crawlers,
            "source_profiles": source_profiles,
            "source_results": source_results,
            "data_sources": [
                source_profiles.get(plan["source_code"], plan["variants"][0])
                for plan in plans
            ],
            "source_count": len(plans),
            "error_count": sum(
                1 for item in source_results if item["status"] == "failed"
            ),
        }

    def _coverage_gaps(self, l2_results: List[Dict[str, Any]]) -> List[str]:
        """识别分类覆盖不足或来源过度集中的方向，供一次性搜索补充。"""
        config = self.config.discovery_config
        minimum = config["min_articles_per_category"]
        categories = [
            category for category in self.l2.allowed_categories
            if category and category != "其他AI相关"
        ]
        category_counts = Counter(
            result.get("analysis", {}).get("category", "") for result in l2_results
        )
        gaps = [category for category in categories if category_counts[category] < minimum]

        source_counts = Counter(
            result["article"].source_code for result in l2_results if result.get("article")
        )
        total = sum(source_counts.values())
        concentration = max(source_counts.values(), default=0) / total if total else 1.0
        if concentration > config["max_primary_source_ratio"] and not gaps:
            gaps = sorted(categories, key=lambda item: category_counts[item])
        return gaps

    def analyze_stage(
        self,
        articles: List[RawArticle],
        crawlers: Optional[Dict[str, Any]] = None,
        source_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
        from_date: str = None,
        to_date: str = None,
        data_sources: Optional[List[Dict[str, Any]]] = None,
        use_history_cache: bool = True,
        persist_processed: bool = True,
        enable_discovery: bool = True,
        allow_l3_content_fetch: bool = True,
        audit: Optional[CollectionAudit] = None,
    ) -> Dict[str, Any]:
        """Run the shared candidate, L2 and L3 stages with explicit side effects."""
        crawlers = crawlers or {}
        data_sources = data_sources or []
        if source_profiles:
            self.source_profiles.update(source_profiles)
            self.l2.source_profiles.update(source_profiles)

        stage_stats = {
            "L1_candidate_pool": {
                "total": len(articles),
                "new": 0,
                "skipped": 0,
                "initial_selected": 0,
                "deferred": 0,
                "refill_selected": 0,
                "source_counts": {},
                "title_routing": {},
            },
            "L1_dedup": {
                "total": len(articles),
                "new": 0,
                "skipped": 0,
                "content_duplicates": 0,
            },
            "L2_analysis": {
                "total": 0,
                "success": 0,
                "failed": 0,
                "discarded": 0,
                "content_insufficient": 0,
                "initial": {},
                "refill": {},
            },
            "L3_selection": {
                "eligible": 0,
                "topics": 0,
                "selected": 0,
                "excluded": 0,
            },
            "L3_insight": {"triggered": 0, "success": 0},
            "L0_discovery": {
                "triggered": False,
                "site_total": 0,
                "search_total": 0,
                "total": 0,
            },
        }

        seen_hashes = set()
        new_candidates = self._filter_new_candidates(
            articles,
            seen_hashes,
            use_history_cache=use_history_cache,
        )
        stage_stats["L1_dedup"].update({
            "new": len(new_candidates),
            "skipped": len(articles) - len(new_candidates),
        })

        routing_stats = self.title_router.route(
            new_candidates,
            self.source_profiles,
        )
        stage_stats["L1_candidate_pool"]["title_routing"] = routing_stats

        planner = CandidatePoolPlanner(self.config.candidate_pool_config)
        initial_candidates, deferred_candidates, pool_stats = planner.prepare(
            new_candidates,
            self.source_profiles,
        )
        initial_deferred = list(deferred_candidates)
        stage_stats["L1_candidate_pool"].update({
            "total": pool_stats["candidate_count"],
            "new": pool_stats["candidate_count"],
            "skipped": len(articles) - pool_stats["candidate_count"],
            "initial_selected": pool_stats["initial_selected"],
            "deferred": pool_stats["deferred"],
            "source_counts": {
                source_code: detail["candidates"]
                for source_code, detail in pool_stats["source_counts"].items()
            },
            "source_stage_counts": pool_stats["source_counts"],
            "predicted_category_counts": pool_stats["predicted_category_counts"],
            "semantic_filtered": pool_stats["semantic_filtered"],
        })

        batch_content_hashes = set()
        l2_results, initial_stats = self._analyze_selected(
            initial_candidates,
            crawlers,
            batch_content_hashes,
            use_history_cache=use_history_cache,
            persist_processed=persist_processed,
        )
        stage_stats["L2_analysis"]["initial"] = initial_stats
        for key in ("scored", "success", "failed", "content_insufficient"):
            target = "total" if key == "scored" else key
            stage_stats["L2_analysis"][target] += initial_stats[key]
        stage_stats["L1_dedup"]["content_duplicates"] += initial_stats[
            "content_duplicates"
        ]

        refill_gaps = self._candidate_refill_gaps(l2_results)
        refill_candidates, deferred_candidates = planner.select_refill(
            deferred_candidates,
            refill_gaps,
        )
        stage_stats["L1_candidate_pool"]["refill_selected"] = len(refill_candidates)
        refill_hashes = {article.url_hash for article in refill_candidates}
        if refill_candidates:
            refill_results, refill_stats = self._analyze_selected(
                refill_candidates,
                crawlers,
                batch_content_hashes,
                use_history_cache=use_history_cache,
                persist_processed=persist_processed,
            )
            l2_results.extend(refill_results)
        else:
            refill_stats = {
                "selected": 0,
                "hydrated": 0,
                "scored": 0,
                "success": 0,
                "failed": 0,
                "content_insufficient": 0,
                "content_duplicates": 0,
            }
        stage_stats["L2_analysis"]["refill"] = refill_stats
        for key in ("scored", "success", "failed", "content_insufficient"):
            target = "total" if key == "scored" else key
            stage_stats["L2_analysis"][target] += refill_stats[key]
        stage_stats["L1_dedup"]["content_duplicates"] += refill_stats[
            "content_duplicates"
        ]

        if audit:
            audit.save_candidate_pool([{
                "source_code": article.source_code,
                "title": article.title,
                "url": article.url,
                "publish_time": article.publish_time,
                "ai_related": article.ai_related,
                "predicted_category": article.predicted_category,
                "info_type_hint": article.info_type_hint,
                "route_confidence": article.route_confidence,
                "route_reason": article.route_reason,
                "route_method": article.route_method,
                "status": (
                    "refill_selected" if article.url_hash in refill_hashes else "deferred"
                ),
            } for article in initial_deferred])

        discovery_config = self.config.discovery_config
        if enable_discovery and discovery_config["enabled"]:
            gaps = self._coverage_gaps(l2_results)
            if gaps:
                discovery_stats = stage_stats["L0_discovery"]
                discovery_stats["triggered"] = True
                mode = discovery_config.get("mode", "site")
                discovered = []
                if mode in ("site", "hybrid"):
                    site_discovery = SiteDiscoveryCrawler(discovery_config, data_sources)
                    site_articles = site_discovery.discover(gaps, from_date, to_date)
                    discovered.extend(site_articles)
                    discovery_stats["site_total"] = len(site_articles)

                expected = discovery_config["min_articles_per_category"] * len(gaps)
                if (
                    mode in ("search", "hybrid")
                    and discovery_config.get("search_enabled")
                    and len(discovered) < expected
                ):
                    search_discovery = SearchDiscoveryCrawler(
                        discovery_config,
                        data_sources,
                    )
                    search_articles = search_discovery.discover(
                        gaps,
                        from_date,
                        to_date,
                    )
                    discovered.extend(search_articles)
                    discovery_stats["search_total"] = len(search_articles)

                discovered = self._filter_by_date(discovered, from_date, to_date)
                discovered_new = self._filter_new_candidates(
                    discovered,
                    seen_hashes,
                    use_history_cache=use_history_cache,
                )
                discovered_prepared, discovered_quality = self._prepare_for_l2(
                    discovered_new,
                    batch_content_hashes,
                    use_history_cache=use_history_cache,
                )
                discovered_results = self.l2.analyze_batch(discovered_prepared)
                successful_hashes = {
                    result["article"].url_hash for result in discovered_results
                }
                for article in discovered_prepared:
                    if (
                        article.url_hash not in successful_hashes
                        and article.content_hash
                    ):
                        batch_content_hashes.discard(article.content_hash)
                if persist_processed:
                    self.dedup.mark_processed_batch([
                        result["article"] for result in discovered_results
                    ])
                l2_results.extend(discovered_results)
                discovery_stats["total"] = len(discovered)
                stage_stats["L1_dedup"]["total"] += len(discovered)
                stage_stats["L1_dedup"]["new"] += len(discovered_new)
                stage_stats["L1_dedup"]["skipped"] += (
                    len(discovered) - len(discovered_new)
                )
                stage_stats["L1_dedup"]["content_duplicates"] += discovered_quality[
                    "content_duplicates"
                ]
                stage_stats["L2_analysis"]["total"] += len(discovered_prepared)
                stage_stats["L2_analysis"]["success"] += len(discovered_results)
                stage_stats["L2_analysis"]["failed"] += (
                    len(discovered_prepared) - len(discovered_results)
                )
                stage_stats["L2_analysis"]["content_insufficient"] += discovered_quality[
                    "content_insufficient"
                ]

        discarded_l2_results = [
            result for result in l2_results if self._should_discard_analysis(result)
        ]
        l2_results = [
            result for result in l2_results if not self._should_discard_analysis(result)
        ]
        stage_stats["L2_analysis"]["discarded"] = len(discarded_l2_results)
        if discarded_l2_results:
            logger.info(
                "低价值非金融垂直场景文章已丢弃: discarded=%d",
                len(discarded_l2_results),
            )

        old_allow_content_fetch = self.l3.allow_content_fetch
        self.l3.allow_content_fetch = allow_l3_content_fetch
        try:
            l3_candidates, selection_stats = self.l3_selector.select(l2_results)
            l3_results, execution_outcomes = self.l3.analyze_eligible_with_outcomes(
                l3_candidates
            )
        finally:
            self.l3.allow_content_fetch = old_allow_content_fetch
        execution_by_hash = {
            item["url_hash"]: item["reason"] for item in execution_outcomes
        }
        for item in selection_stats.get("article_outcomes", []):
            if item.get("reason") == "selected" and item.get("url_hash") in execution_by_hash:
                item["reason"] = execution_by_hash[item["url_hash"]]
        stage_stats["L3_selection"] = selection_stats
        stage_stats["L3_insight"] = {
            "triggered": len(l3_candidates),
            "success": len(l3_results),
            "failure_reasons": dict(Counter(
                item["reason"]
                for item in execution_outcomes
                if item["reason"] != "success"
            )),
        }

        return {
            "l2_results": l2_results,
            "discarded_l2_results": discarded_l2_results,
            "l3_candidates": l3_candidates,
            "l3_results": l3_results,
            "remaining_deferred": deferred_candidates,
            "stats": stage_stats,
        }

    def _persist_failed_import_payload(
        self,
        payload: Dict[str, Any],
        import_result: Dict[str, Any],
        stats: Dict[str, Any],
    ) -> Dict[str, str]:
        """导入失败时保存请求体，便于人工调用内部导入接口重试。"""
        batch_no = payload.get("batch", {}).get("batch_no") or stats.get("batch_no") or "unknown"
        retry_dir = os.path.join(self.config.data_dir, "failed_imports")
        os.makedirs(retry_dir, exist_ok=True)

        payload_path = os.path.join(retry_dir, f"{batch_no}.payload.json")
        meta_path = os.path.join(retry_dir, f"{batch_no}.meta.json")

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        metadata = {
            "batch_no": batch_no,
            "saved_at": datetime.now().isoformat(),
            "endpoint_url": self.config.import_endpoint_url,
            "reason": import_result.get("error", "unknown"),
            "import_result": import_result,
            "stats": stats,
            "payload_file": payload_path,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)

        logger.error("导入失败结果已持久化: payload=%s, meta=%s", payload_path, meta_path)
        return {"payload_file": payload_path, "meta_file": meta_path}

    @staticmethod
    def _should_discard_analysis(result: Dict[str, Any]) -> bool:
        """丢弃低价值非金融垂直场景应用，避免进入 L3 和内部导入。"""
        analysis = result.get("analysis", {})
        category = str(analysis.get("category") or "").strip()
        try:
            configured_score = analysis.get("rank_score")
            if configured_score is None:
                configured_score = analysis.get("value_score")
            rank_score = float(configured_score or 0)
        except (TypeError, ValueError):
            rank_score = 0
        return category == "其他AI相关" and rank_score <= 5.0

    def run(
        self,
        scope: str = "all",
        sources: List[str] = None,
        from_date: str = None,
        to_date: str = None,
        task_type: str = "scheduled",
    ) -> Dict[str, Any]:
        """
        执行采集分析全流程

        入参：
            scope: all / sources / timerange / rerun
            sources: 数据源编码列表（scope=sources 时使用）
            from_date: 开始日期（scope=timerange 时使用）
            to_date: 结束日期（scope=timerange 时使用）
        出参：执行统计 {batch_no, phase_stats: {...}, ...}
        """
        start_time = time.time()
        batch_no = f"IMP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        audit = CollectionAudit(self.config.data_dir, batch_no)

        logger.info("====== 采集分析任务开始 ======")
        logger.info("batch_no=%s, scope=%s", batch_no, scope)

        batch_time = datetime.now()
        stats = {
            "batch_no": batch_no,
            "scope": scope,
            "L0_collect": {"total": 0, "sources": 0, "errors": 0},
            "L0_discovery": {"triggered": False, "site_total": 0, "search_total": 0, "total": 0},
            "L1_candidate_pool": {
                "total": 0, "new": 0, "skipped": 0,
                "initial_selected": 0, "deferred": 0, "refill_selected": 0,
                "source_counts": {},
            },
            "L1_dedup": {"total": 0, "new": 0, "skipped": 0, "content_duplicates": 0},
            "L2_analysis": {
                "total": 0, "success": 0, "failed": 0, "discarded": 0,
                "content_insufficient": 0, "initial": {}, "refill": {},
            },
            "L3_selection": {"eligible": 0, "topics": 0, "selected": 0, "excluded": 0},
            "L3_insight": {"triggered": 0, "success": 0},
            "import": {"status": "pending"},
        }

        collection = self.collect_stage(
            strategy=CONFIGURED,
            sources=sources,
            from_date=from_date,
            to_date=to_date,
            hydrate_candidates=False,
            audit=audit,
        )
        all_candidates = collection["articles"]
        source_crawlers = collection["crawlers"]
        data_sources = collection["data_sources"]
        stats["L0_collect"] = {
            "total": len(all_candidates),
            "sources": collection["source_count"],
            "errors": collection["error_count"],
        }
        logger.info("L1 候选发现完成: total_candidates=%d", len(all_candidates))

        analysis_run = self.analyze_stage(
            all_candidates,
            crawlers=source_crawlers,
            source_profiles=collection["source_profiles"],
            from_date=from_date,
            to_date=to_date,
            data_sources=data_sources,
            use_history_cache=True,
            persist_processed=True,
            enable_discovery=True,
            allow_l3_content_fetch=True,
            audit=audit,
        )
        stats.update(analysis_run["stats"])
        l2_results = analysis_run["l2_results"]
        discarded_l2_results = analysis_run["discarded_l2_results"]
        l3_candidates = analysis_run["l3_candidates"]
        l3_results = analysis_run["l3_results"]

        # 对所有文章计算清洗正文和 content_hash。
        for r in l2_results:
            art = r["article"]
            if not art.content_hash:
                hash_source = (
                    ContentParser.extract_main_content(art.raw_html)
                    if art.raw_html else art.raw_summary or ""
                )
                if not hash_source:
                    hash_source = art.url or ""
                if hash_source:
                    art.compute_content_hash(hash_source)

# === 组装导入请求 ===
        article_items = []
        for r in l2_results:
            art = r["article"]
            clean_content = (
                ContentParser.extract_main_content(art.raw_html)
                if art.raw_html else art.raw_summary
            )
            article_items.append({
                "url": art.url,
                "url_hash": art.url_hash,
                "source_code": art.source_code,
                "title": art.title,
                "author": art.author,
                "publish_time": art.publish_time.isoformat() if art.publish_time else None,
                "crawl_time": art.crawl_time.isoformat(),
                "raw_summary": art.raw_summary,
                "full_content": clean_content,
                "content_hash": art.content_hash,
            })

        analysis_items = []
        for r in l2_results:
            a = r["analysis"]
            analysis_items.append({
                "article_url_hash": r["article"].url_hash,
                "source_language": a.get("source_language", "unknown"),
                "title_cn": a.get("title_cn", r["article"].title),
                "summary_cn": a["summary_cn"],
                "category": a["category"],
                "sub_category": a.get("sub_category", ""),
                "info_type": a.get("info_type", ""),
                "briefing_focus": a.get("briefing_focus", ""),
                "analysis_detail": a.get("analysis_detail", {}),
                "keywords": a["keywords"] if isinstance(a["keywords"], list) else [],
                "tech_tags": a["tech_tags"] if isinstance(a["tech_tags"], list) else [],
                "companies": a["companies"] if isinstance(a["companies"], list) else [],
                "standard_terms": a.get("standard_terms", []),
                "score_tech_depth": a["score_tech_depth"],
                "score_engineering": a["score_engineering"],
                "score_org_relevance": a["score_org_relevance"],
                "score_trend": a["score_trend"],
                "score_credibility": a["score_credibility"],
                "score_timeliness": a["score_timeliness"],
                "rank_score": a["rank_score"],
                "value_score": a["value_score"],
                "model_name": a["model_name"],
                "prompt_version": a["prompt_version"],
            })

        insight_items = []
        for r in l3_results:
            ins = r["insight"]
            insight_items.append({
                "article_url_hash": r["article"].url_hash,
                "technical_background": ins["technical_background"],
                "core_problem": ins["core_problem"],
                "technical_solution": ins["technical_solution"],
                "impact_analysis": ins["impact_analysis"],
                "reference_value": ins["reference_value"],
                "model_name": ins["model_name"],
                "prompt_version": ins["prompt_version"],
            })

        operation_metrics = {
            "batch_time": batch_time.isoformat(),
            "l1_article_count": stats["L1_candidate_pool"]["total"],
            "l1_source_distribution": stats["L1_candidate_pool"]["source_counts"],
            "l2_article_count": len(l2_results),
            "l2_source_distribution": dict(Counter(
                result["article"].source_code for result in l2_results
            )),
            "l2_category_distribution": dict(Counter(
                result.get("analysis", {}).get("category") or "其他AI相关"
                for result in l2_results
            )),
            "l3_article_count": len(l3_candidates),
            "l3_source_distribution": dict(Counter(
                result["article"].source_code for result in l3_candidates
            )),
            "l3_category_distribution": dict(Counter(
                result.get("analysis", {}).get("category") or "其他AI相关"
                for result in l3_candidates
            )),
            "stage_detail": {
                "candidate_pool": stats["L1_candidate_pool"],
                "dedup": stats["L1_dedup"],
                "l2": stats["L2_analysis"],
                "l3_selection": stats["L3_selection"],
                "l3_insight": stats["L3_insight"],
            },
        }

        payload = self.importer.build_payload(
            batch_no=batch_no,
            task_type=task_type,
            source_scope=[s["code"] for s in data_sources],
            articles=article_items,
            analyses=analysis_items,
            insights=insight_items,
            operation_metrics=operation_metrics,
        )

        # === 受控导入 ===
        import_result = self.importer.import_batch(payload)
        stats["import"]["status"] = "success" if import_result.get("success") else "failed"
        if import_result.get("error"):
            stats["import"]["error"] = import_result["error"]
        if not import_result.get("success"):
            stats["import"]["retry_files"] = self._persist_failed_import_payload(
                payload,
                import_result,
                stats,
            )

        l3_candidate_hashes = {result["article"].url_hash for result in l3_candidates}
        l3_success_hashes = {result["article"].url_hash for result in l3_results}
        audit_articles = []
        for result in l2_results:
            article = result["article"]
            analysis = result["analysis"]
            audit_articles.append({
                "url": article.url,
                "source_code": article.source_code,
                "title": article.title,
                "publish_time": article.publish_time,
                "status": "analyzed",
                "category": analysis.get("category"),
                "info_type": analysis.get("info_type"),
                "rank_score": analysis.get("rank_score"),
                "l3_candidate": article.url_hash in l3_candidate_hashes,
                "l3_success": article.url_hash in l3_success_hashes,
            })
        for result in discarded_l2_results:
            article = result["article"]
            analysis = result["analysis"]
            audit_articles.append({
                "url": article.url,
                "source_code": article.source_code,
                "title": article.title,
                "publish_time": article.publish_time,
                "status": "discarded",
                "reason": "low_value_other_ai_vertical",
                "category": analysis.get("category"),
                "info_type": analysis.get("info_type"),
                "rank_score": analysis.get("rank_score"),
            })
        elapsed = time.time() - start_time
        stats["elapsed_seconds"] = round(elapsed, 1)
        audit.save(audit_articles, stats)

        logger.info("====== 采集分析任务完成 ======")
        logger.info("batch_no=%s, elapsed=%.1fs, stats=%s",
                     batch_no, elapsed,
                     json.dumps(stats, ensure_ascii=False, default=str))

        return stats


def handle_collect_job(params: str = None) -> Dict[str, Any]:
    """
    XXL-Job JobHandler: aiRadarCollectJob

    入参：
        params: 调度参数 JSON 字符串，如 {"scope":"all"}
    出参：执行统计字典
    """
    scope = "all"
    sources = None
    from_date = None
    to_date = None
    task_type = "scheduled"

    if params:
        try:
            ps = json.loads(params) if isinstance(params, str) else params
            scope = ps.get("scope", "all")
            sources = ps.get("sources")
            # sources 可能是逗号分隔字符串（来自 XXL-Job 调度参数或 HTTP 接口），统一转为 list
            if sources and isinstance(sources, str):
                sources = [s.strip() for s in sources.split(",") if s.strip()]
            from_date = ps.get("from_date") or ps.get("from")
            to_date = ps.get("to_date") or ps.get("to")
            task_type = ps.get("task_type", "scheduled")
        except json.JSONDecodeError:
            logger.warning("调度参数 JSON 解析失败: %s", params)

    config = AWSConfig()
    orchestrator = CollectOrchestrator(config)
    stats = orchestrator.run(
        scope=scope,
        sources=sources,
        from_date=from_date,
        to_date=to_date,
        task_type=task_type,
    )
    return stats
