import os
import sys
import unittest
from datetime import datetime, timedelta


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, APP_DIR)

from crawler.discovery_crawler import SearchDiscoveryCrawler
from crawler.site_discovery_crawler import SiteDiscoveryCrawler
from crawler.web_crawler import WebCrawler
from config import AWSConfig
from processor.l2_analysis import L2Analyzer


class CollectionRuleTests(unittest.TestCase):
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
