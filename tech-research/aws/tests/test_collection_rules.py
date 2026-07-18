import os
import sys
import asyncio
import threading
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, APP_DIR)

from crawler.discovery_crawler import SearchDiscoveryCrawler
from crawler.browser_fetcher import BrowserFetcher
from crawler.base import RawArticle
from crawler.site_discovery_crawler import SiteDiscoveryCrawler
from crawler.source_strategies import (
    CONFIGURED,
    PRIMARY_RESILIENT,
    SERVER_RECOMMENDED,
    build_source_plans,
    match_server_coverage_aliases,
)
from crawler.web_crawler import WebCrawler
from crawler.rss_crawler import RSSCrawler
from exporter.import_client import ImportClient
from processor.collection_snapshot import CollectionSnapshotStore
from deep.candidate_selector import L3CandidateSelector
from deep.insight import L3Analyzer
from api.jobs_api import (
    CollectJobRequest,
    ValidationAnalyzeRequest,
    ValidationCollectRequest,
    list_analysis_snapshots,
    trigger_collect,
    trigger_validation_analysis,
    trigger_validation_collect,
)
from config import AWSConfig
from jobs.collect_job import CollectOrchestrator
from jobs.validation_job import (
    ValidationAnalysisService,
    ValidationCollectionService,
    ValidationStore,
)
from processor.candidate_pool import CandidatePoolPlanner
from processor.l2_analysis import L2Analyzer
from processor.title_router import TitleRouter


class FakePrompts:
    def get(self, name):
        return {"categories": "大模型基础技术,Agent与智能体,行业动态"}

    def render(self, name, **kwargs):
        return "system", "user", "test-v1", ""


class FakeLLM:
    def __init__(self, parsed):
        self.parsed = parsed

    def call(self, **kwargs):
        return {"success": True, "model": "fake-model"}

    def parse_json_response(self, result):
        return self.parsed


class CollectionRuleTests(unittest.TestCase):
    @staticmethod
    def _empty_stage_stats():
        return {
            "L0_discovery": {
                "triggered": False,
                "site_total": 0,
                "search_total": 0,
                "total": 0,
            },
            "L1_candidate_pool": {
                "total": 0,
                "new": 0,
                "skipped": 0,
                "initial_selected": 0,
                "deferred": 0,
                "refill_selected": 0,
                "source_counts": {},
            },
            "L1_dedup": {
                "total": 0,
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
        }

    @staticmethod
    def _l2_result(
        source: str,
        index: int,
        title: str = "",
        category: str = "大模型基础技术",
        info_type: str = "技术方案",
        score: float = 8.5,
        trend: float = 8.0,
    ):
        article = RawArticle(
            source_code=source,
            title=title or f"{source} 独立主题 {index}",
            url=f"https://{source}.example.com/article/{index}",
        )
        return {
            "article": article,
            "analysis": {
                "title_cn": article.title,
                "category": category,
                "info_type": info_type,
                "keywords": [f"keyword-{source}-{index}"],
                "tech_tags": [],
                "companies": [],
                "score_tech_depth": score,
                "score_engineering": score,
                "score_org_relevance": score,
                "score_trend": trend,
                "score_timeliness": 8.0,
                "rank_score": score,
                "value_score": score,
                "need_deep_analysis": True,
            },
        }

    def test_site_discovery_is_enabled_without_search_service(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        discovery = AWSConfig(config_dir).discovery_config
        self.assertTrue(discovery["enabled"])
        self.assertEqual(discovery["mode"], "site")
        self.assertFalse(discovery["search_enabled"])
        self.assertEqual(discovery["search_endpoint"], "")

    def test_timeliness_uses_publish_age(self):
        crawled = datetime(2026, 7, 15)
        self.assertEqual(L2Analyzer._timeliness_score(crawled, crawled), 10.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=2), crawled), 9.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=3), crawled), 8.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=7), crawled), 7.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=21), crawled), 5.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=30), crawled), 4.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=60), crawled), 3.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=180), crawled), 1.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=181), crawled), 0.0)
        self.assertEqual(L2Analyzer._timeliness_score(None, crawled), 0.0)

    def test_l2_accepts_zero_scores_and_normalizes_org_relevance_anchor(self):
        scores = L2Analyzer._extract_scores({
            "score_org_relevance": 7,
            "score_trend": 0,
            "score_tech_depth": 0,
        })

        self.assertEqual(scores["org_relevance"], 7.0)
        self.assertEqual(scores["trend"], 0.0)
        self.assertEqual(scores["tech_depth"], 0.0)
        self.assertEqual(
            L2Analyzer._extract_scores({"score_org_relevance": 5})["org_relevance"],
            3.0,
        )
        self.assertEqual(
            L2Analyzer._extract_scores({"score_org_relevance": 9})["org_relevance"],
            9.0,
        )
        self.assertEqual(L2Analyzer._extract_scores({})["org_relevance"], 0.0)

    def test_legacy_source_roles_remain_stable_for_import_compatibility(self):
        self.assertEqual(AWSConfig._default_selection_role("academic"), "research")
        self.assertEqual(AWSConfig._default_selection_role("industry_application"), "industry")
        self.assertEqual(AWSConfig._default_selection_role("tech_community"), "engineering")

    def test_validation_source_profile_keeps_semantic_routing_keywords(self):
        profile = ValidationCollectionService._safe_source_profile({
            "code": "mixed-source",
            "include_keywords": "AI,Agent",
            "exclude_keywords": "招聘",
            "api_key": "must-not-be-persisted",
        })

        self.assertEqual(profile["include_keywords"], "AI,Agent")
        self.assertEqual(profile["exclude_keywords"], "招聘")
        self.assertNotIn("api_key", profile)

    def test_l2_rank_score_uses_single_five_dimension_formula(self):
        parsed = {
            "title_cn": "统一评分测试",
            "summary_cn": "摘要",
            "category": "Agent与智能体",
            "sub_category": "Agent工程化落地",
            "info_type": "工程实践",
            "briefing_focus": "工程能力变化",
            "analysis_detail": {},
            "tech_depth": 2,
            "engineering": 8,
            "org_relevance": 10,
            "trend": 9,
            "timeliness": 1,
        }
        analyzer = L2Analyzer(
            FakeLLM(parsed),
            FakePrompts(),
            source_profiles={"official": {"type": "vendor_blog"}},
            deep_analysis_min_score=6.0,
        )
        article = RawArticle(
            source_code="official",
            title="统一评分测试",
            url="https://official.example/test",
            raw_summary="正文摘要",
            publish_time=datetime(2026, 7, 15),
            crawl_time=datetime(2026, 7, 15),
        )

        result = analyzer._analyze_single(article)

        self.assertEqual(result["analysis"]["rank_score"], 8.5)
        self.assertEqual(result["analysis"]["value_score"], 8.5)

    def test_title_router_keeps_low_confidence_and_has_no_importance_identity(self):
        llm = FakeLLM({
            "items": [{
                "index": 0,
                "ai_related": False,
                "predicted_category": "行业动态",
                "info_type_hint": "模型发布",
                "confidence": 0.4,
                "reason": "标题信息不足",
            }]
        })
        router = TitleRouter(
            llm,
            FakePrompts(),
            {"enabled": True, "min_confidence": 0.65},
            "fake-model",
            ["大模型基础技术", "Agent与智能体", "行业动态"],
        )
        article = RawArticle(
            source_code="mixed",
            title="GPT 新版本发布",
            url="https://mixed.example/release",
        )

        stats = router.route([article], {"mixed": {"semantic_routing": True}})

        self.assertIsNone(article.ai_related)
        self.assertEqual(article.route_method, "semantic")
        self.assertEqual(stats["low_confidence"], 1)
        self.assertFalse(hasattr(article, "possible_major_event"))

    def test_browser_fallback_detects_js_shell(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/list",
            "domain": "example.com",
            "_browser_fallback_enabled": "true",
        })
        self.assertTrue(crawler._needs_browser_fallback('<html><body><div id="app"></div></body></html>'))
        self.assertFalse(crawler._needs_browser_fallback("<html><body>" + "有效正文" * 200 + "</body></html>"))

    def test_access_challenge_is_detected_without_attempting_to_bypass_it(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/list",
            "domain": "example.com",
        })

        self.assertTrue(crawler._is_access_challenge(
            "<script>TTGCaptcha.render({showMode: 'mask'})</script>"
        ))
        crawler._record_access_challenge("https://example.com/article/1")

        self.assertTrue(crawler._detail_challenge_open)
        self.assertEqual(crawler.collection_diagnostics["access_challenges"], 1)

    def test_content_reject_keywords_skip_footer_like_nodes(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/list",
            "domain": "example.com",
            "detail_content_selector": ".article-content|main",
            "detail_content_reject_keywords": "关注阿里云,联系我们",
        })
        detail = crawler._parse_detail_page(
            "<html><body><div class='article-content'>关注阿里云 联系我们</div>"
            "<main>这是可用于评分的正文内容，包含完整的技术说明。</main></body></html>"
        )

        self.assertIn("可用于评分", detail["summary"])
        self.assertNotIn("关注阿里云", detail["summary"])

    def test_web_crawler_follows_configured_next_page_link(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/list",
            "domain": "example.com",
            "list_selector": "article a",
            "next_page_selector": "a[rel='next']",
            "max_pages": "2",
        })
        pages = {
            "https://example.com/list": (
                "<article><a href='/article/1'>AI工程文章一</a></article>"
                "<a rel='next' href='/list?page=2'>下一页</a>"
            ),
            "https://example.com/list?page=2": (
                "<article><a href='/article/2'>AI工程文章二</a></article>"
            ),
        }
        with patch.object(crawler, "_request_html", side_effect=lambda url: pages.get(url)):
            candidates = crawler.discover_candidates()

        self.assertEqual([item.url for item in candidates], [
            "https://example.com/article/1",
            "https://example.com/article/2",
        ])

    def test_rss_detail_fetch_uses_the_shared_web_detail_reader(self):
        crawler = RSSCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/feed.xml",
            "domain": "example.com",
            "rss_detail_fetch": "true",
        })
        article = RawArticle(
            source_code="test",
            title="InfoQ 技术实践文章",
            url="https://example.com/article/1",
        )
        with patch("crawler.web_crawler.WebCrawler.fetch_candidates", return_value=[article]) as fetch:
            result = crawler.fetch_candidates([article])

        self.assertEqual(result, [article])
        fetch.assert_called_once()
        self.assertTrue(crawler.collection_diagnostics["rss_detail_fetch"])

    def test_underfilled_primary_variant_continues_to_fallback(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        orchestrator = CollectOrchestrator(AWSConfig(config_dir), initialize_analysis=False)

        class StubCrawler:
            def __init__(self, article_count):
                self.article_count = article_count
                self.last_http_status = 200
                self.last_effective_url = "https://example.com"
                self.last_error = ""
                self.collection_diagnostics = {"feed_entries": article_count}

            def discover_candidates(self):
                return [RawArticle(
                    source_code="test-source",
                    title=f"AI工程候选文章{i}",
                    url=f"https://example.com/article/{self.article_count}-{i}",
                ) for i in range(self.article_count)]

        plans = [{
            "source_code": "test-source",
            "source_name": "Test Source",
            "category": "AI基础设施",
            "variants": [
                {"code": "test-source", "name": "Test Source", "_variant_name": "primary", "_minimum_candidates": "3"},
                {"code": "test-source", "name": "Test Source", "_variant_name": "fallback", "_minimum_candidates": "3"},
            ],
        }]
        with patch("jobs.collect_job.build_source_plans", return_value=plans), patch(
            "jobs.collect_job.CrawlerFactory.create",
            side_effect=[StubCrawler(1), StubCrawler(4)],
        ):
            result = orchestrator.collect_stage(strategy=PRIMARY_RESILIENT)

        source = result["source_results"][0]
        self.assertEqual(source["selected_variant"], "fallback")
        self.assertEqual(source["article_count"], 4)
        self.assertEqual(source["attempts"][0]["status"], "underfilled")

    def test_browser_fetcher_accepts_system_browser_path(self):
        path = os.path.join("C:\\", "Program Files", "Browser", "browser.exe")
        fetcher = BrowserFetcher(executable_path=path)
        self.assertEqual(fetcher.executable_path, path)

    def test_web_candidate_discovery_does_not_fetch_details(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/list",
            "domain": "example.com",
            "_candidate_limit": "100",
            "_detail_limit": "50",
        })
        with patch.object(crawler, "_collect_candidates", return_value=[{
            "title": "AI 平台工程能力更新",
            "url": "https://example.com/article/1",
            "summary": "列表摘要",
            "author": "",
            "publish_time": datetime(2026, 7, 15),
        }]), patch.object(crawler, "_build_article") as detail_fetch:
            candidates = crawler.discover_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].raw_html)
        detail_fetch.assert_not_called()

    def test_web_list_selector_can_target_anchor_directly(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/ai",
            "domain": "example.com",
            "list_selector": "a[href*='/p/']",
            "article_url_pattern": r"/p/\d+",
        })
        parsed = crawler._parse_list_page(
            '<html><body><a href="/p/123456">重大模型正式发布</a></body></html>',
            crawler.access_url,
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["url"], "https://example.com/p/123456")

    def test_server_xpath_parser_is_strict_and_extracts_candidates(self):
        crawler = WebCrawler({
            "code": "test",
            "name": "test",
            "access_url": "https://example.com/ai",
            "domain": "example.com",
            "list_link_xpath": "//div[@class='article-item']/a/@href",
            "list_title_xpath": "//div[@class='article-item']/a/text()",
            "xpath_strict": "true",
        })
        parsed = crawler._parse_list_page(
            '<div class="article-item"><a href="/article/1">AI工程平台升级</a></div>',
            crawler.access_url,
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["title"], "AI工程平台升级")

        no_match = crawler._parse_list_page(
            '<a href="/article/2">普通兜底链接不会被严格模式采用</a>',
            crawler.access_url,
        )
        self.assertEqual(no_match, [])

    def test_http_collect_runs_sync_job_outside_event_loop_thread(self):
        event_loop_thread = threading.get_ident()

        def fake_collect(_params):
            return {"worker_thread": threading.get_ident()}

        with patch("jobs.collect_job.handle_collect_job", side_effect=fake_collect):
            response = asyncio.run(trigger_collect(CollectJobRequest()))

        self.assertNotEqual(response["data"]["worker_thread"], event_loop_thread)

    def test_validation_endpoints_run_sync_jobs_outside_event_loop_thread(self):
        event_loop_thread = threading.get_ident()

        def fake_job(_params):
            return {"worker_thread": threading.get_ident()}

        with patch("jobs.validation_job.handle_validation_collect", side_effect=fake_job):
            collect_response = asyncio.run(
                trigger_validation_collect(ValidationCollectRequest())
            )
        with patch("jobs.validation_job.handle_validation_analysis", side_effect=fake_job):
            analysis_response = asyncio.run(trigger_validation_analysis(
                ValidationAnalyzeRequest(collection_batch_no="VAL-COL-test")
            ))

        self.assertNotEqual(collect_response["data"]["worker_thread"], event_loop_thread)
        self.assertNotEqual(analysis_response["data"]["worker_thread"], event_loop_thread)

    def test_validation_source_strategies_keep_their_distinct_behavior(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        sources = AWSConfig(config_dir).get_data_sources()

        server = build_source_plans(
            sources,
            SERVER_RECOMMENDED,
            requested_codes=["36kr-ai", "csdn-ai"],
        )
        server_by_code = {item["source_code"]: item for item in server}
        self.assertEqual(set(server_by_code), {"36kr-ai", "csdn-ai"})
        self.assertEqual(
            server_by_code["36kr-ai"]["variants"][0]["xpath_strict"],
            "true",
        )

        resilient = build_source_plans(
            sources,
            PRIMARY_RESILIENT,
            requested_codes=["deepmind-blog", "oschina-ai"],
        )
        resilient_by_code = {item["source_code"]: item for item in resilient}
        self.assertEqual(
            resilient_by_code["deepmind-blog"]["variants"][0]["fetch_method"],
            "rss",
        )
        self.assertEqual(
            resilient_by_code["oschina-ai"]["variants"][0]["access_url"],
            "https://www.oschina.net/news/rss/ai",
        )

        self.assertEqual(
            match_server_coverage_aliases(
                "36kr-ai", "Karpathy谈大模型训练与Scaling Law"
            ),
            ["karpathy"],
        )
        self.assertEqual(
            match_server_coverage_aliases(
                "openai-blog", "Karpathy谈大模型训练与Scaling Law"
            ),
            [],
        )

        configured = build_source_plans(
            [{
                "code": "configured-source",
                "name": "Configured Source",
                "fetch_method": "rss",
            }],
            CONFIGURED,
        )
        self.assertNotIn("timeout_seconds", configured[0]["variants"][0])

    def test_validation_store_round_trip_and_rejects_unsafe_batch_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ValidationStore(temp_dir)
            payload = {"batch_no": "VAL-COL-test", "articles": []}
            path = store.save_collection("VAL-COL-test", payload)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(store.load_collection("VAL-COL-test"), payload)
            with self.assertRaises(ValueError):
                store.load_collection("../outside")

    def test_formal_analysis_snapshot_round_trip_preserves_raw_content(self):
        article = RawArticle(
            source_code="source-a",
            title="AI工程平台升级",
            url="https://example.com/article/1",
            raw_html="<article>可复用的正文内容</article>",
            raw_summary="列表摘要",
            predicted_category="AI基础设施",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CollectionSnapshotStore(temp_dir)
            path = store.save(
                "IMP-20260717-120000",
                {"scope": "all"},
                {"source-a": {"code": "source-a", "name": "Source A"}},
                [article],
            )
            loaded = store.load_latest()
            restored = CollectionSnapshotStore.article_from_dict(loaded["articles"][0])
            self.assertTrue(os.path.isfile(path))

        self.assertEqual(loaded["batch_no"], "IMP-20260717-120000")
        self.assertEqual(restored.url_hash, article.url_hash)
        self.assertEqual(restored.raw_html, article.raw_html)

    def test_formal_analysis_snapshot_can_load_named_batch_and_list_metadata(self):
        article = RawArticle(
            source_code="source-a",
            title="AI工程平台升级",
            url="https://example.com/article/1",
            raw_html="正文",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CollectionSnapshotStore(temp_dir)
            store.save(
                "IMP-20260701-120000",
                {"scope": "timerange", "from_date": "2026-06-01", "to_date": "2026-06-30"},
                {"source-a": {"code": "source-a"}},
                [article],
            )
            store.save(
                "IMP-20260718-120000",
                {"scope": "all"},
                {"source-a": {"code": "source-a"}},
                [article],
            )
            selected = store.load("IMP-20260701-120000")
            snapshots = store.list_snapshots()

        self.assertEqual(selected["batch_no"], "IMP-20260701-120000")
        self.assertEqual([item["batch_no"] for item in snapshots], [
            "IMP-20260718-120000", "IMP-20260701-120000",
        ])
        self.assertEqual(snapshots[1]["from_date"], "2026-06-01")
        with self.assertRaises(ValueError):
            store.load("../outside")

    def test_snapshot_list_api_returns_selectable_metadata(self):
        class FakeConfig:
            data_dir = "test-data"

        with patch("config.AWSConfig", return_value=FakeConfig()), patch(
            "processor.collection_snapshot.CollectionSnapshotStore.list_snapshots",
            return_value=[{"batch_no": "IMP-month", "article_count": 100}],
        ):
            response = asyncio.run(list_analysis_snapshots())

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["snapshots"][0]["batch_no"], "IMP-month")

    def test_reanalysis_import_marks_insight_replacement_scope(self):
        payload = ImportClient("http://example.com/import").build_payload(
            batch_no="RERUN-20260717-120000",
            task_type="reanalysis",
            source_scope=["source-a"],
            articles=[],
            analyses=[],
            insights=[],
            replace_insights_for_analyses=True,
            replace_insight_article_url_hashes=["hash-a"],
        )

        self.assertTrue(payload["batch"]["replace_insights_for_analyses"])
        self.assertEqual(payload["batch"]["replace_insight_article_url_hashes"], ["hash-a"])

    def test_reanalysis_import_failure_persists_retry_payload(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        orchestrator = CollectOrchestrator(AWSConfig(config_dir))
        article = RawArticle(
            source_code="source-a",
            title="AI工程平台升级",
            url="https://source-a.example.com/article/1",
            raw_html="<article>正文</article>",
            crawl_time=datetime(2026, 7, 18),
        )
        l2_result = self._l2_result("source-a", 1, score=7.0)
        l2_result["article"] = article
        l2_result["analysis"].update({
            "summary_cn": "摘要",
            "sub_category": "",
            "briefing_focus": "重点",
            "analysis_detail": {},
            "standard_terms": [],
            "model_name": "test-model",
            "prompt_version": "test-v1",
        })
        analysis_run = {
            "l2_results": [l2_result],
            "discarded_l2_results": [],
            "l3_candidates": [],
            "l3_results": [],
            "stats": self._empty_stage_stats(),
        }
        payload = {
            "batch": {
                "batch_no": "RERUN-test",
                "replace_insights_for_analyses": True,
            }
        }
        snapshot = {
            "batch_no": "IMP-source",
            "articles": [CollectionSnapshotStore.article_to_dict(article)],
            "source_profiles": {"source-a": {"code": "source-a"}},
        }
        failure = {"success": False, "error": "network_error"}
        retry_files = {
            "payload_file": "data/failed_imports/RERUN-test.payload.json",
            "meta_file": "data/failed_imports/RERUN-test.meta.json",
        }

        with patch(
            "jobs.collect_job.CollectionSnapshotStore.load",
            return_value=snapshot,
        ) as load_snapshot, patch.object(
            orchestrator,
            "analyze_stage",
            return_value=analysis_run,
        ), patch.object(
            orchestrator.importer,
            "build_payload",
            return_value=payload,
        ), patch.object(
            orchestrator.importer,
            "import_batch",
            return_value=failure,
        ), patch.object(
            orchestrator,
            "_persist_failed_import_payload",
            return_value=retry_files,
        ) as persist:
            result = orchestrator._run_snapshot_reanalysis(
                "reanalysis",
                "IMP-20260701-120000",
                "monthly",
            )

        self.assertEqual(result["import"]["status"], "failed")
        self.assertEqual(result["import"]["retry_files"], retry_files)
        self.assertEqual(result["processing_limits"]["period"], "monthly")
        self.assertEqual(result["processing_limits"]["l3_max_candidates"], 50)
        load_snapshot.assert_called_once_with("IMP-20260701-120000")
        persist.assert_called_once_with(payload, failure, result)

    def test_snapshot_reanalysis_rejects_empty_requested_date_range(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        orchestrator = CollectOrchestrator(AWSConfig(config_dir))
        article = RawArticle(
            source_code="source-a",
            title="历史文章",
            url="https://source-a.example.com/article/1",
            publish_time=datetime(2026, 7, 1),
            raw_html="<article>正文</article>",
        )
        snapshot = {
            "batch_no": "IMP-source",
            "articles": [CollectionSnapshotStore.article_to_dict(article)],
            "source_profiles": {},
        }

        with patch(
            "jobs.collect_job.CollectionSnapshotStore.load",
            return_value=snapshot,
        ):
            with self.assertRaisesRegex(ValueError, "所选时间范围"):
                orchestrator._run_snapshot_reanalysis(
                    "reanalysis",
                    "IMP-source",
                    "weekly",
                    "2026-07-10",
                    "2026-07-16",
                )

    def test_validation_collection_delegates_to_shared_collection_stage(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        service = ValidationCollectionService(AWSConfig(config_dir))
        article = RawArticle(
            source_code="source-a",
            title="AI工程平台升级",
            url="https://example.com/article/1",
            raw_html="<article>" + ("正文" * 100) + "</article>",
        )
        shared_result = {
            "strategy": PRIMARY_RESILIENT,
            "articles": [article],
            "crawlers": {},
            "source_profiles": {},
            "source_results": [{
                "source_code": "source-a",
                "source_name": "Source A",
                "category": "AI基础设施",
                "status": "success",
                "article_count": 1,
                "selected_variant": "official-rss",
                "source_profile": {
                    "code": "source-a",
                    "name": "Source A",
                    "fetch_method": "rss",
                },
                "attempts": [],
            }],
            "data_sources": [],
            "source_count": 1,
            "error_count": 0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            service.store = ValidationStore(temp_dir)
            with patch.object(
                service.orchestrator,
                "collect_stage",
                return_value=shared_result,
            ) as collect_stage:
                result = service.run(
                    strategy=PRIMARY_RESILIENT,
                    sources=["source-a"],
                )

        self.assertEqual(result["article_count"], 1)
        collect_stage.assert_called_once_with(
            strategy=PRIMARY_RESILIENT,
            sources=["source-a"],
            from_date=None,
            to_date=None,
            hydrate_candidates=True,
            strict_sources=True,
        )

    def test_collection_only_orchestrator_does_not_initialize_llm(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        with patch("jobs.collect_job.LLMClient") as llm_client:
            orchestrator = CollectOrchestrator(
                AWSConfig(config_dir),
                initialize_analysis=False,
            )

        self.assertTrue(orchestrator.source_profiles)
        llm_client.assert_not_called()

    def test_validation_analysis_delegates_to_shared_analysis_stage(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        service = ValidationAnalysisService(AWSConfig(config_dir))
        article = RawArticle(
            source_code="source-a",
            title="AI工程平台升级",
            url="https://example.com/article/1",
            raw_html="<article>" + ("正文" * 100) + "</article>",
        )
        analysis_result = {
            "article": article,
            "analysis": {
                "category": "AI基础设施",
                "value_score": 8.0,
            },
        }
        shared_result = {
            "l2_results": [analysis_result],
            "discarded_l2_results": [],
            "l3_candidates": [analysis_result],
            "l3_results": [],
            "remaining_deferred": [],
            "stats": self._empty_stage_stats(),
        }
        manifest = {
            "strategy": PRIMARY_RESILIENT,
            "source_results": [],
            "articles": [{
                "source_code": article.source_code,
                "title": article.title,
                "url": article.url,
                "crawl_time": article.crawl_time.isoformat(),
                "raw_html": article.raw_html,
            }],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            service.store = ValidationStore(temp_dir)
            service.store.save_collection("VAL-COL-test", manifest)
            with patch.object(
                service.orchestrator,
                "analyze_stage",
                return_value=shared_result,
            ) as analyze_stage:
                result = service.run("VAL-COL-test")

        self.assertEqual(result["l2_success"], 1)
        _, kwargs = analyze_stage.call_args
        self.assertFalse(kwargs["use_history_cache"])
        self.assertFalse(kwargs["persist_processed"])
        self.assertFalse(kwargs["enable_discovery"])
        self.assertFalse(kwargs["allow_l3_content_fetch"])

    def test_production_run_uses_shared_collection_and_analysis_stages(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        orchestrator = CollectOrchestrator(AWSConfig(config_dir))
        collection_result = {
            "strategy": "configured",
            "articles": [],
            "crawlers": {},
            "source_profiles": {},
            "source_results": [],
            "data_sources": [],
            "source_count": 0,
            "error_count": 0,
        }
        analysis_result = {
            "l2_results": [],
            "discarded_l2_results": [],
            "l3_candidates": [],
            "l3_results": [],
            "remaining_deferred": [],
            "stats": self._empty_stage_stats(),
        }
        with patch.object(
            orchestrator,
            "collect_stage",
            return_value=collection_result,
        ) as collect_stage, patch.object(
            orchestrator,
            "analyze_stage",
            return_value=analysis_result,
        ) as analyze_stage, patch.object(
            orchestrator.importer,
            "build_payload",
            return_value={},
        ), patch.object(
            orchestrator.importer,
            "import_batch",
            return_value={"success": True},
        ), patch("jobs.collect_job.CollectionAudit"):
            result = orchestrator.run(task_type="manual_backfill")

        self.assertEqual(result["import"]["status"], "success")
        self.assertEqual(collect_stage.call_args.kwargs["strategy"], "configured")
        _, kwargs = analyze_stage.call_args
        self.assertTrue(kwargs["use_history_cache"])
        self.assertTrue(kwargs["persist_processed"])
        self.assertTrue(kwargs["enable_discovery"])
        self.assertTrue(kwargs["allow_l3_content_fetch"])

    def test_candidate_pool_keeps_fifty_per_source_for_initial_scoring(self):
        planner = CandidatePoolPlanner({
            "initial_scored_per_source": 50,
            "refill_max_per_category": 10,
        })
        articles = [
            RawArticle(
                source_code="source-a",
                title=f"AI 工程实践专题 {index}",
                url=f"https://source-a.example.com/{index}",
            )
            for index in range(60)
        ]

        selected, deferred, metadata = planner.prepare(articles, {
            "source-a": {"category": "AI基础设施"},
        })

        self.assertEqual(len(selected), 50)
        self.assertEqual(len(deferred), 10)
        self.assertEqual(metadata["source_counts"]["source-a"]["candidates"], 60)

    def test_candidate_refill_only_uses_category_gap_without_identity_exception(self):
        planner = CandidatePoolPlanner({
            "initial_scored_per_source": 1,
            "refill_max_per_category": 1,
        })
        release = RawArticle(
            source_code="source-a",
            title="重点模型正式发布",
            url="https://source-a.example.com/major",
            predicted_category="大模型基础技术",
        )
        agent = RawArticle(
            source_code="source-b",
            title="智能体工程实践",
            url="https://source-b.example.com/agent",
            predicted_category="Agent与智能体",
        )
        other = RawArticle(
            source_code="source-c",
            title="普通行业动态",
            url="https://source-c.example.com/other",
            predicted_category="行业动态",
        )

        selected, remaining = planner.select_refill(
            [release, agent, other], ["Agent与智能体"]
        )

        self.assertEqual([item.url for item in selected], [agent.url])
        self.assertEqual({item.url for item in remaining}, {release.url, other.url})

    def test_l3_candidates_select_highest_scores_without_source_quota(self):
        selector = L3CandidateSelector({
            "max_candidates_per_batch": 6,
            "topic_similarity_threshold": 0.95,
        }, min_score=8.0)
        results = (
            [self._l2_result("source-a", index, score=9.0 - index * 0.1) for index in range(5)]
            + [self._l2_result("source-b", index) for index in range(2)]
            + [self._l2_result("source-c", index) for index in range(2)]
        )

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 6)
        self.assertEqual(metadata["selection_mode"], "rank_only")
        self.assertEqual(metadata["source_counts"]["source-a"], 5)

    def test_l3_candidates_accept_per_run_capacity_override(self):
        selector = L3CandidateSelector({
            "max_candidates_per_batch": 50,
            "topic_similarity_threshold": 0.95,
        }, min_score=6.0)
        results = [
            self._l2_result("source-a", index, score=9.0 - index * 0.1)
            for index in range(4)
        ]

        selected, metadata = selector.select(results, max_candidates=2)

        self.assertEqual(len(selected), 2)
        self.assertEqual(metadata["capacity"], 2)

    def test_processing_limits_use_weekly_or_long_period_profiles(self):
        config_dir = os.path.abspath(os.path.join(APP_DIR, "..", "config"))
        config = AWSConfig(config_dir)

        weekly = config.processing_limits("2026-07-13", "2026-07-19", "auto")
        monthly = config.processing_limits("2026-06-01", "2026-06-30", "auto")
        quarterly = config.processing_limits(collection_period="quarterly")

        self.assertEqual(weekly["period"], "weekly")
        self.assertEqual(weekly["candidate_pool"]["candidate_limit_per_source"], 60)
        self.assertEqual(weekly["candidate_pool"]["initial_scored_per_source"], 30)
        self.assertEqual(weekly["l3_max_candidates"], 40)
        self.assertEqual(monthly["period"], "monthly")
        self.assertEqual(monthly["candidate_pool"]["candidate_limit_per_source"], 100)
        self.assertEqual(monthly["candidate_pool"]["initial_scored_per_source"], 50)
        self.assertEqual(monthly["l3_max_candidates"], 50)
        self.assertEqual(quarterly["period"], "quarterly")
        self.assertEqual(quarterly["l3_max_candidates"], 50)

    def test_validation_l3_does_not_refetch_missing_content(self):
        analyzer = L3Analyzer(
            llm=object(),
            prompts=object(),
            min_score=7.0,
            require_full_content=True,
            allow_content_fetch=False,
        )
        result = self._l2_result("source-a", 1, score=8.0)
        with patch("processor.parser.ContentParser.fetch_full_content") as fetch:
            self.assertFalse(analyzer.should_trigger(result))
        fetch.assert_not_called()

    def test_l3_candidates_collapse_same_topic_across_sources(self):
        selector = L3CandidateSelector({
            "max_candidates_per_batch": 4,
            "topic_similarity_threshold": 0.8,
        }, min_score=8.0)
        results = [
            self._l2_result("source-a", 1, title="GPT 新版本正式发布"),
            self._l2_result("source-b", 1, title="GPT 新版本正式发布"),
        ]

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 1)
        self.assertEqual(metadata["topics"], 1)
        self.assertEqual(metadata["selected_articles"][0]["related_count"], 2)

    def test_l3_high_score_releases_are_not_replaced_for_source_diversity(self):
        selector = L3CandidateSelector({
            "max_candidates_per_batch": 3,
            "topic_similarity_threshold": 0.95,
        }, min_score=8.0)
        results = [
            self._l2_result(
                "official", 1, title="模型 Alpha 发布", info_type="模型发布",
                score=9.2, trend=9.5,
            ),
            self._l2_result(
                "official", 2, title="模型 Beta 发布", info_type="模型发布",
                score=9.1, trend=9.3,
            ),
            self._l2_result(
                "official", 3, title="模型 Gamma 发布", info_type="模型发布",
                score=9.0, trend=9.2,
            ),
            self._l2_result("independent", 1, score=8.5),
        ]

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 3)
        self.assertEqual(metadata["source_counts"]["official"], 3)
        outcomes = {item["url_hash"]: item["reason"] for item in metadata["article_outcomes"]}
        self.assertIn("excluded_by_capacity", outcomes.values())

    def test_need_deep_analysis_hint_does_not_block_l3_selection(self):
        selector = L3CandidateSelector({
            "max_candidates_per_batch": 3,
            "topic_similarity_threshold": 0.95,
        }, min_score=6.0)
        result = self._l2_result("official", 1, score=7.0)
        result["analysis"]["need_deep_analysis"] = False

        selected, _ = selector.select([result])

        self.assertEqual(len(selected), 1)

    def test_need_deep_analysis_hint_does_not_block_l3_execution(self):
        analyzer = L3Analyzer(
            llm=object(),
            prompts=object(),
            min_score=6.0,
            require_full_content=False,
        )
        result = self._l2_result("official", 1, score=7.0)
        result["analysis"]["need_deep_analysis"] = False

        self.assertTrue(analyzer.should_trigger(result))

    def test_l3_high_score_releases_do_not_expand_batch_capacity(self):
        selector = L3CandidateSelector({
            "max_candidates_per_batch": 1,
            "topic_similarity_threshold": 0.95,
        }, min_score=7.0)
        results = [
            self._l2_result(
                "official", 1, title="模型 Alpha 正式发布", info_type="模型发布",
                score=9.2, trend=9.5,
            ),
            self._l2_result(
                "official", 2, title="模型 Beta 正式发布", info_type="模型发布",
                score=9.1, trend=9.4,
            ),
        ]

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 1)
        self.assertEqual(metadata["capacity"], 1)

    def test_search_result_shapes_are_normalized(self):
        parsed = SearchDiscoveryCrawler._parse_results({
            "webPages": {"value": [{"name": "A", "url": "https://example.com/a", "snippet": "S"}]}
        })
        self.assertEqual(parsed[0]["title"], "A")
        self.assertEqual(parsed[0]["url"], "https://example.com/a")

    def test_sitemap_urlset_and_index_are_parsed(self):
        urlset = b"""<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/blog/model-release</loc><lastmod>2026-07-14</lastmod></url>
        </urlset>"""
        nested, urls = SiteDiscoveryCrawler._parse_sitemap(urlset)
        self.assertEqual(nested, [])
        self.assertEqual(urls[0][0], "https://example.com/blog/model-release")
        self.assertEqual(urls[0][1], datetime(2026, 7, 14))

        index = b"""<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.com/post-sitemap.xml</loc></sitemap>
        </sitemapindex>"""
        nested, urls = SiteDiscoveryCrawler._parse_sitemap(index)
        self.assertEqual(nested, ["https://example.com/post-sitemap.xml"])
        self.assertEqual(urls, [])

    def test_site_discovery_filters_non_article_urls(self):
        self.assertTrue(SiteDiscoveryCrawler._looks_like_article(
            "https://openai.com/index/gpt-5-6"
        ))
        self.assertFalse(SiteDiscoveryCrawler._looks_like_article(
            "https://openai.com/blog/"
        ))
        self.assertFalse(SiteDiscoveryCrawler._looks_like_article(
            "https://openai.com/assets/logo.png"
        ))

    def test_sitemap_rejects_doctype(self):
        nested, urls = SiteDiscoveryCrawler._parse_sitemap(
            b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset />'
        )
        self.assertEqual((nested, urls), ([], []))


if __name__ == "__main__":
    unittest.main()
