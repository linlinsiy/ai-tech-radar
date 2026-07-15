import os
import sys
import asyncio
import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, APP_DIR)

from crawler.discovery_crawler import SearchDiscoveryCrawler
from crawler.browser_fetcher import BrowserFetcher
from crawler.base import RawArticle
from crawler.site_discovery_crawler import SiteDiscoveryCrawler
from crawler.web_crawler import WebCrawler
from deep.candidate_selector import L3CandidateSelector
from api.jobs_api import CollectJobRequest, trigger_collect
from config import AWSConfig
from processor.candidate_pool import CandidatePoolPlanner
from processor.l2_analysis import L2Analyzer


class CollectionRuleTests(unittest.TestCase):
    @staticmethod
    def _l2_result(
        source: str,
        index: int,
        title: str = "",
        category: str = "大模型基础技术",
        info_type: str = "技术方案",
        score: float = 8.5,
        trend: float = 8.0,
        credibility: float = 8.0,
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
                "score_trend": trend,
                "score_credibility": credibility,
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
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=3), crawled), 10.0)
        self.assertEqual(L2Analyzer._timeliness_score(crawled - timedelta(days=60), crawled), 8.0)
        self.assertEqual(L2Analyzer._timeliness_score(None, crawled), 5.0)

    def test_source_credibility_uses_type_or_override(self):
        self.assertEqual(L2Analyzer._source_credibility_score({"type": "academic"}), 9.0)
        self.assertEqual(
            L2Analyzer._source_credibility_score({"type": "tech_media", "credibility_score": "8.3"}),
            8.3,
        )

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

    def test_http_collect_runs_sync_job_outside_event_loop_thread(self):
        event_loop_thread = threading.get_ident()

        def fake_collect(_params):
            return {"worker_thread": threading.get_ident()}

        with patch("jobs.collect_job.handle_collect_job", side_effect=fake_collect):
            response = asyncio.run(trigger_collect(CollectJobRequest()))

        self.assertNotEqual(response["data"]["worker_thread"], event_loop_thread)

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

    def test_candidate_refill_includes_gaps_and_all_possible_major_events(self):
        planner = CandidatePoolPlanner({
            "initial_scored_per_source": 1,
            "refill_max_per_category": 1,
        })
        major = RawArticle(
            source_code="source-a",
            title="重点模型正式发布",
            url="https://source-a.example.com/major",
            predicted_category="大模型基础技术",
            possible_major_event=True,
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
            [major, agent, other], ["Agent与智能体"]
        )

        self.assertEqual({item.url for item in selected}, {major.url, agent.url})
        self.assertEqual([item.url for item in remaining], [other.url])

    def test_l3_candidates_are_round_robin_balanced_by_source(self):
        selector = L3CandidateSelector({
            "enabled": True,
            "max_candidates_per_batch": 6,
            "max_candidates_per_source": 2,
            "max_source_ratio": 1.0,
            "max_category_ratio": 1.0,
            "topic_similarity_threshold": 0.95,
            "max_major_event_exceptions": 0,
        }, min_score=8.0)
        results = (
            [self._l2_result("source-a", index, score=9.0 - index * 0.1) for index in range(5)]
            + [self._l2_result("source-b", index) for index in range(2)]
            + [self._l2_result("source-c", index) for index in range(2)]
        )

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 6)
        self.assertEqual(metadata["source_counts"], {
            "source-a": 2,
            "source-b": 2,
            "source-c": 2,
        })

    def test_l3_candidates_collapse_same_topic_across_sources(self):
        selector = L3CandidateSelector({
            "enabled": True,
            "max_candidates_per_batch": 4,
            "max_candidates_per_source": 2,
            "max_source_ratio": 1.0,
            "max_category_ratio": 1.0,
            "topic_similarity_threshold": 0.8,
            "max_major_event_exceptions": 0,
        }, min_score=8.0)
        results = [
            self._l2_result("source-a", 1, title="GPT 新版本正式发布"),
            self._l2_result("source-b", 1, title="GPT 新版本正式发布"),
        ]

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 1)
        self.assertEqual(metadata["topics"], 1)
        self.assertEqual(metadata["selected_articles"][0]["related_count"], 2)

    def test_l3_major_events_can_use_limited_exceptions(self):
        selector = L3CandidateSelector({
            "enabled": True,
            "max_candidates_per_batch": 3,
            "max_candidates_per_source": 1,
            "max_source_ratio": 1.0,
            "max_category_ratio": 1.0,
            "topic_similarity_threshold": 0.95,
            "max_major_event_exceptions": 2,
        }, min_score=8.0)
        results = [
            self._l2_result(
                "official", 1, title="模型 Alpha 发布", info_type="模型发布",
                score=9.2, trend=9.5, credibility=9.0,
            ),
            self._l2_result(
                "official", 2, title="模型 Beta 发布", info_type="模型发布",
                score=9.1, trend=9.3, credibility=9.0,
            ),
            self._l2_result("independent", 1, score=8.5),
        ]

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 3)
        self.assertEqual(metadata["source_counts"]["official"], 2)
        self.assertEqual(metadata["source_counts"]["independent"], 1)

    def test_l3_unlimited_major_events_expand_normal_batch_capacity(self):
        selector = L3CandidateSelector({
            "enabled": True,
            "max_candidates_per_batch": 1,
            "max_candidates_per_source": 1,
            "max_source_ratio": 1.0,
            "max_category_ratio": 1.0,
            "topic_similarity_threshold": 0.95,
            "max_major_event_exceptions": 0,
        }, min_score=7.0)
        results = [
            self._l2_result(
                "official", 1, title="模型 Alpha 正式发布", info_type="模型发布",
                score=9.2, trend=9.5, credibility=9.0,
            ),
            self._l2_result(
                "official", 2, title="模型 Beta 正式发布", info_type="模型发布",
                score=9.1, trend=9.4, credibility=9.0,
            ),
        ]

        selected, metadata = selector.select(results)

        self.assertEqual(len(selected), 2)
        self.assertEqual(metadata["protected_major_event_count"], 2)

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
