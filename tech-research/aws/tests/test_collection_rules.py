import os
import sys
import unittest
from datetime import datetime, timedelta


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, APP_DIR)

from crawler.discovery_crawler import SearchDiscoveryCrawler
from crawler.web_crawler import WebCrawler
from processor.l2_analysis import L2Analyzer


class CollectionRuleTests(unittest.TestCase):
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

    def test_search_result_shapes_are_normalized(self):
        parsed = SearchDiscoveryCrawler._parse_results({
            "webPages": {"value": [{"name": "A", "url": "https://example.com/a", "snippet": "S"}]}
        })
        self.assertEqual(parsed[0]["title"], "A")
        self.assertEqual(parsed[0]["url"], "https://example.com/a")


if __name__ == "__main__":
    unittest.main()
