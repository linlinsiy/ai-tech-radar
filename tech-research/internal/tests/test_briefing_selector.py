import os
import sys
import unittest
from datetime import datetime


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, APP_DIR)

from jobs.briefing_selector import BriefingSelector, _string_values


def article(article_id, source, category, info_type, engineering, trend=8, credibility=8, title=None):
    return {
        "id": article_id,
        "title": title or f"主题 {article_id}",
        "url": f"https://{source}.example/{article_id}",
        "publish_time": datetime(2026, 7, 1),
        "source_code": source,
        "source_name": source,
        "category": category,
        "sub_category": "",
        "info_type": info_type,
        "briefing_focus": "",
        "summary_cn": f"主题 {article_id} 的摘要",
        "keywords": f"keyword-{article_id}",
        "tech_tags": [],
        "companies": [],
        "score_tech_depth": 7,
        "score_engineering": engineering,
        "score_trend": trend,
        "score_credibility": credibility,
        "score_timeliness": 9,
        "value_score": 7.5,
    }


class BriefingSelectorTests(unittest.TestCase):
    def test_legacy_json_string_tags_are_normalized(self):
        self.assertEqual(["Agent", "RAG"], _string_values('["Agent", "RAG"]'))

    def setUp(self):
        self.config = {
            "target_weekly": 8,
            "target_topic": 8,
            "min_value_score": 5.5,
            "max_primary_topics_per_source": 2,
            "max_primary_source_ratio": 0.2,
            "max_category_ratio": 0.35,
            "engineering_ratio": 0.55,
            "research_ratio": 0.25,
            "topic_similarity_threshold": 0.34,
            "max_articles_per_topic": 3,
        }

    def test_selection_balances_source_and_prefers_engineering(self):
        candidates = [
            article(index, "aws", "AI基础设施", "研究论文", 5)
            for index in range(1, 7)
        ]
        categories = ["Agent与智能体", "开源生态", "生成式AI应用", "安全与伦理", "行业动态", "多模态技术"]
        for offset, category in enumerate(categories, 10):
            candidates.append(article(offset, f"source-{offset}", category, "工程实践", 9))

        selected, metadata = BriefingSelector(self.config).select(candidates, "weekly")
        self.assertEqual(len(selected), 8)
        self.assertLessEqual(metadata["source_counts"].get("aws", 0), 2)
        self.assertGreaterEqual(metadata["lane_counts"].get("engineering", 0), 5)

    def test_major_event_can_bypass_source_soft_limit(self):
        candidates = [
            article(1, "openai", "大模型基础技术", "工程实践", 9, title="Agent runtime engineering"),
            article(2, "openai", "Agent与智能体", "工程实践", 9, title="Agent memory platform"),
            article(3, "openai", "大模型基础技术", "模型发布", 8, trend=9, credibility=9, title="GPT 5.6 official release"),
        ]
        for index in range(4, 10):
            candidates.append(article(index, f"source-{index}", "行业动态", "行业动态", 7))

        selected, metadata = BriefingSelector(self.config).select(candidates, "weekly")
        titles = {topic["title"] for topic in selected}
        self.assertIn("GPT 5.6 official release", titles)
        self.assertIn("GPT 5.6 official release", metadata["major_event_topics"])

    def test_same_event_from_two_sources_is_one_topic(self):
        first = article(1, "source-a", "大模型基础技术", "模型发布", 8, title="GPT 5.6 official model release")
        second = article(2, "source-b", "大模型基础技术", "行业动态", 7, title="GPT 5.6 official model release details")
        selected, _ = BriefingSelector({**self.config, "target_weekly": 2}).select([first, second], "weekly")
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(selected[0]["articles"]), 2)


if __name__ == "__main__":
    unittest.main()
