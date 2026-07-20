import os
import sys
import unittest
from datetime import datetime


APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, APP_DIR)

from jobs.briefing_render import (
    assemble_briefing,
    build_information_overview,
    build_signal_index,
    topic_marker,
    validate_briefing,
    validate_section,
)
from jobs.briefing_selector import BriefingSelector, _string_values


def article(
    article_id,
    source,
    category,
    info_type,
    rank_score=7.5,
    title=None,
):
    return {
        "id": article_id,
        "title": title or f"主题 {article_id}",
        "url": f"https://{source}.example/{article_id}",
        "publish_time": datetime(2026, 7, 1),
        "source_code": source,
        "source_name": source,
        "selection_role": "industry",
        "category": category,
        "sub_category": "",
        "info_type": info_type,
        "briefing_focus": f"主题 {article_id} 的核心变化。",
        "summary_cn": f"主题 {article_id} 的摘要。",
        "keywords": f"keyword-{article_id}",
        "tech_tags": [],
        "companies": [],
        "score_tech_depth": 7,
        "score_engineering": 8,
        "score_org_relevance": 8,
        "score_trend": 8,
        "score_timeliness": 9,
        "rank_score": rank_score,
        "value_score": rank_score,
        "insight_id": article_id,
        "technical_background": "背景",
        "core_problem": "核心事实",
        "technical_solution": "方案或变化",
        "impact_analysis": "影响",
        "reference_value": "边界",
    }


class BriefingSelectorTests(unittest.TestCase):
    def test_legacy_json_string_tags_are_normalized(self):
        self.assertEqual(["Agent", "RAG"], _string_values('["Agent", "RAG"]'))

    def setUp(self):
        self.config = {
            "target_weekly": 8,
            "target_topic": 8,
            "min_rank_score": 6.0,
            "topic_similarity_threshold": 0.34,
            "max_articles_per_topic": 3,
        }

    def test_selection_has_no_cap_when_caps_are_not_configured(self):
        candidates = [
            article(index, "aws", "AI基础设施", "研究论文", 9.5 - index * 0.1)
            for index in range(1, 7)
        ]
        categories = ["Agent与智能体", "开源生态", "生成式AI应用", "安全与伦理", "行业动态", "多模态技术"]
        for offset, category in enumerate(categories, 10):
            candidates.append(article(offset, f"source-{offset}", category, "工程实践", 8.0))

        selected, metadata = BriefingSelector(self.config).select(candidates, "weekly")

        self.assertEqual(len(selected), 8)
        self.assertEqual(metadata["source_counts"].get("aws", 0), 6)
        self.assertEqual(metadata["selection_mode"], "rank_with_upper_caps")
        self.assertNotIn("report_rank_score", selected[0])
        self.assertNotIn("must_include", selected[0])

    def test_source_cap_skips_excess_high_score_topics_without_low_score_backfill(self):
        config = {
            **self.config,
            "target_weekly": 3,
            "max_topics_per_source": 2,
            "max_topics_per_info_type": 0,
        }
        candidates = [
            article(1, "official", "大模型基础技术", "模型发布", 9.9, title="Alpha official release"),
            article(2, "official", "Agent与智能体", "模型发布", 9.8, title="Beta official release"),
            article(3, "official", "多模态技术", "模型发布", 9.7, title="Gamma official release"),
            article(4, "source-b", "行业动态", "行业动态", 8.0),
            article(5, "source-c", "开源生态", "开源项目", 7.9),
        ]

        selected, metadata = BriefingSelector(config).select(candidates, "weekly")

        self.assertEqual(metadata["source_counts"].get("official"), 2)
        self.assertEqual(len(selected), 3)
        self.assertEqual(selected[-1]["primary"]["source_code"], "source-b")
        self.assertEqual(metadata["topic_outcomes"]["3"], "excluded_by_source_cap")

    def test_info_type_cap_leaves_a_shortfall_instead_of_choosing_lower_score_type(self):
        config = {
            **self.config,
            "target_weekly": 4,
            "max_topics_per_source": 0,
            "max_topics_per_info_type": 1,
        }
        candidates = [
            article(1, "source-a", "大模型基础技术", "模型发布", 9.9, title="Alpha release"),
            article(2, "source-b", "Agent与智能体", "模型发布", 9.8, title="Beta release"),
            article(3, "source-c", "多模态技术", "模型发布", 9.7, title="Gamma release"),
        ]

        selected, metadata = BriefingSelector(config).select(candidates, "weekly")

        self.assertEqual(len(selected), 1)
        self.assertEqual(metadata["shortfall_topics"], 3)
        self.assertEqual(metadata["topic_outcomes"]["2"], "excluded_by_info_type_cap")

    def test_category_cap_skips_excess_topics_without_lowering_the_threshold(self):
        config = {
            **self.config,
            "target_weekly": 4,
            "max_topics_per_source": 0,
            "max_topics_per_info_type": 0,
            "max_topics_per_category": 2,
        }
        candidates = [
            article(1, "source-a", "Agent与智能体", "工程实践", 9.9, title="Alpha agent"),
            article(2, "source-b", "Agent与智能体", "产品发布", 9.8, title="Beta agent"),
            article(3, "source-c", "Agent与智能体", "模型发布", 9.7, title="Gamma agent"),
            article(4, "source-d", "AI基础设施", "工程实践", 8.0, title="Platform update"),
        ]

        selected, metadata = BriefingSelector(config).select(candidates, "weekly")

        self.assertEqual(len(selected), 3)
        self.assertEqual(metadata["category_counts"]["Agent与智能体"], 2)
        self.assertEqual(metadata["shortfall_topics"], 1)
        self.assertEqual(metadata["topic_outcomes"]["3"], "excluded_by_category_cap")

    def test_same_event_from_two_sources_is_one_topic(self):
        first = article(1, "source-a", "大模型基础技术", "模型发布", title="GPT 5.6 official model release")
        second = article(2, "source-b", "大模型基础技术", "行业动态", title="GPT 5.6 official model release details")

        selected, _ = BriefingSelector({**self.config, "target_weekly": 2}).select([first, second], "weekly")

        self.assertEqual(len(selected), 1)
        self.assertEqual(len(selected[0]["articles"]), 2)

    def test_l4_uses_l2_chinese_title_for_overview_and_signal_index(self):
        candidate = article(1, "source-a", "Agent与智能体", "工程实践", title="Build an agent gateway")
        candidate["title_cn"] = "构建智能体网关"
        candidate["original_title"] = candidate["title"]
        candidate["title"] = candidate["title_cn"]

        selected, _ = BriefingSelector({**self.config, "target_weekly": 1}).select([candidate], "weekly")
        overview = build_information_overview(selected)
        index = build_signal_index(selected)

        self.assertEqual(selected[0]["title"], "构建智能体网关")
        self.assertIn("构建智能体网关", overview)
        self.assertIn("构建智能体网关", index)
        self.assertEqual(selected[0]["primary"]["original_title"], "Build an agent gateway")

    def test_qualified_topics_do_not_expand_report_target(self):
        candidates = [
            article(1, "official", "大模型基础技术", "模型发布", 9.8, title="Alpha model official release"),
            article(2, "official", "AI基础设施", "产品发布", 9.7, title="Inference platform launch"),
        ]

        selected, metadata = BriefingSelector({**self.config, "target_weekly": 1}).select(candidates, "weekly")

        self.assertEqual(len(selected), 1)
        self.assertEqual(metadata["target_topics"], 1)

    def test_l5_assembly_validates_four_topic_counts_and_sources(self):
        primary = article(1, "source-a", "Agent与智能体", "工程实践")
        topic = {
            "topic_id": "1",
            "title": primary["title"],
            "category": primary["category"],
            "rank_score": primary["rank_score"],
            "primary": primary,
            "articles": [primary],
        }
        marker = topic_marker(topic)
        section = (
            f"## Agent与智能体\n\n<!-- topic:{marker} -->\n"
            f"### {topic['title']}\n正文。\n\n来源：[source-a]({primary['url']})"
        )
        section_check = validate_section("Agent与智能体", [topic], section)
        content = assemble_briefing(
            "2026-07-01 ~ 2026-07-31", "导语。", [topic], [section]
        )
        validation = validate_briefing([topic], content, [section_check])

        self.assertTrue(section_check["valid"])
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["l4_topic_count"], 1)
        self.assertEqual(validation["overview_topic_count"], 1)
        self.assertEqual(validation["body_topic_count"], 1)
        self.assertEqual(validation["index_topic_count"], 1)

    def test_l5_section_rejects_missing_marker_and_source(self):
        primary = article(1, "source-a", "Agent与智能体", "工程实践")
        topic = {
            "topic_id": "1",
            "title": primary["title"],
            "category": primary["category"],
            "rank_score": primary["rank_score"],
            "primary": primary,
            "articles": [primary],
        }

        check = validate_section("Agent与智能体", [topic], "## Agent与智能体\n正文")

        self.assertFalse(check["valid"])
        self.assertIn("topic_marker_mismatch", check["errors"])
        self.assertIn("source_link_missing", check["errors"])


if __name__ == "__main__":
    unittest.main()
