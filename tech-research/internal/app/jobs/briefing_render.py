"""Pure Markdown assembly and completeness checks for L5 briefings."""

import re
from collections import Counter
from typing import Any, Dict, List


TOPIC_MARKER_PATTERN = re.compile(r"<!--\s*topic:([A-Za-z0-9_-]+)\s*-->")


def topic_marker(topic: Dict) -> str:
    return f"T{topic['topic_id']}"


def strip_markdown_fence(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def validate_section(category: str, topics: List[Dict], content: str) -> Dict[str, Any]:
    expected = [topic_marker(topic) for topic in topics]
    actual = TOPIC_MARKER_PATTERN.findall(content or "")
    missing_urls = []
    for topic in topics:
        if not any(article.get("url") and article["url"] in content for article in topic["articles"]):
            missing_urls.append(topic_marker(topic))
    errors = []
    if f"## {category}" not in content:
        errors.append("category_heading_missing")
    if Counter(actual) != Counter(expected):
        errors.append("topic_marker_mismatch")
    if missing_urls:
        errors.append("source_link_missing")
    return {
        "valid": not errors,
        "category": category,
        "expected_topic_ids": expected,
        "actual_topic_ids": actual,
        "missing_source_topic_ids": missing_urls,
        "errors": errors,
    }


def build_information_overview(topics: List[Dict]) -> str:
    lines = ["## 信息速览"]
    for topic in topics:
        primary = topic["primary"]
        focus = (primary.get("briefing_focus") or primary.get("summary_cn") or "").strip()
        focus = re.split(r"(?<=[。！？!?])", focus, maxsplit=1)[0][:180]
        lines.append(
            f"- 【{topic['category']}】[{topic['title']}]({primary['url']})：{focus}"
        )
    return "\n\n".join(lines)


def escape_table(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def build_signal_index(topics: List[Dict]) -> str:
    lines = [
        "## 信号源索引",
        "| 主题 | 主来源 | 补充来源 | 发布日期 | 链接 |",
        "|---|---|---|---|---|",
    ]
    for topic in topics:
        primary = topic["primary"]
        supplementary = "、".join(
            article["source_name"] for article in topic["articles"][1:]
        ) or "-"
        published = (
            primary["publish_time"].strftime("%Y-%m-%d")
            if primary.get("publish_time") else "日期未知"
        )
        lines.append(
            f"| {escape_table(topic['title'])} | {escape_table(primary['source_name'])} | "
            f"{escape_table(supplementary)} | {published} | [原文]({primary['url']}) |"
        )
    return "\n".join(lines)


def assemble_briefing(
    time_range: str,
    intro: str,
    topics: List[Dict],
    sections: List[str],
) -> str:
    parts = [
        f"# AI技术趋势雷达｜{time_range}",
        intro.strip(),
        build_information_overview(topics),
        *[section.strip() for section in sections],
        build_signal_index(topics),
    ]
    return "\n\n".join(part for part in parts if part)


def validate_briefing(topics: List[Dict], content: str, section_checks: List[Dict]) -> Dict:
    expected = [topic_marker(topic) for topic in topics]
    actual = TOPIC_MARKER_PATTERN.findall(content)
    overview_count = sum(1 for topic in topics if f"【{topic['category']}】[{topic['title']}]" in content)
    index_count = sum(1 for topic in topics if f"| {escape_table(topic['title'])} |" in content)
    source_urls = {
        article["url"]
        for topic in topics for article in topic["articles"] if article.get("url")
    }
    missing_urls = sorted(url for url in source_urls if url not in content)
    valid = (
        all(check["valid"] for check in section_checks)
        and Counter(actual) == Counter(expected)
        and overview_count == len(topics)
        and index_count == len(topics)
        and not missing_urls
    )
    return {
        "valid": valid,
        "l4_topic_count": len(topics),
        "overview_topic_count": overview_count,
        "body_topic_count": len(actual),
        "index_topic_count": index_count,
        "expected_topic_ids": expected,
        "actual_topic_ids": actual,
        "missing_source_urls": missing_urls,
        "section_checks": section_checks,
    }
