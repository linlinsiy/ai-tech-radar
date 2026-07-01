"""
Markdown 文件生成模块

根据设计文档定义的三类模板，从 MySQL 记录生成 EIPLite 知识库入库用的 Markdown 文件。

模板类型：
- article_summary: 文章摘要卡片
- deep_insight: 深度洞察卡片
- briefing: 简报文档
"""
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("kb.markdown_gen")

# === 文章摘要卡片模板 ===
ARTICLE_SUMMARY_TEMPLATE = """# {title}

**来源**：{source_name}
**作者**：{author}
**发布时间**：{publish_time}
**原文链接**：{url}
**技术分类**：{category}
**价值评分**：{value_score}/10

## AI 分析摘要
{summary_cn}

## 原文摘要
{raw_summary}

## 全文
{full_content}
"""

# === 深度洞察卡片模板 ===
DEEP_INSIGHT_TEMPLATE = """# {title} — 深度洞察

**来源**：{source_name}
**原文链接**：{url}
**技术分类**：{category}
**价值评分**：{value_score}/10

## 技术背景
{technical_background}

## 核心问题
{core_problem}

## 技术方案
{technical_solution}

## 影响分析
{impact_analysis}

## 内部参考价值
{reference_value}
"""

# === 简报文档模板 ===
BRIEFING_TEMPLATE = """# {title}

**覆盖时间**：{time_range_start} ~ {time_range_end}
**简报类型**：{briefing_type}

{briefing_content}
"""


def _format_time(dt) -> str:
    """格式化时间为字符串，None 返回 N/A"""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return str(dt)


def generate_article_summary(
    title: str,
    source_name: str,
    url: str,
    summary_cn: str,
    raw_summary: str = "",
    full_content: str = "",
    category: Optional[str] = None,
    author: Optional[str] = None,
    publish_time=None,
    value_score: Optional[float] = None,
) -> str:
    """
    生成文章摘要卡片 Markdown

    入参：
        title: 文章标题
        source_name: 来源名称
        url: 原文链接
        summary_cn: 中文摘要
        category: 技术分类
        author: 作者
        publish_time: 发布时间
        value_score: 价值评分
    出参：Markdown 格式文本
    """
    return ARTICLE_SUMMARY_TEMPLATE.format(
        title=title,
        source_name=source_name,
        author=author or "N/A",
        publish_time=_format_time(publish_time),
        url=url,
        category=category or "N/A",
        value_score=f"{value_score:.1f}" if value_score is not None else "N/A",
        summary_cn=summary_cn,
        raw_summary=raw_summary or "N/A",
        full_content=full_content or "N/A",
    )


def generate_deep_insight(
    title: str,
    source_name: str,
    url: str,
    category: Optional[str],
    value_score: Optional[float],
    technical_background: str,
    core_problem: str,
    technical_solution: str,
    impact_analysis: str = "",
    reference_value: str = "",
) -> str:
    """
    生成深度洞察卡片 Markdown

    入参：各字段对应 ai_radar_deep_insight 和关联表字段
    出参：Markdown 格式文本
    """
    return DEEP_INSIGHT_TEMPLATE.format(
        title=title,
        source_name=source_name,
        url=url,
        category=category or "N/A",
        value_score=f"{value_score:.1f}" if value_score is not None else "N/A",
        technical_background=technical_background,
        core_problem=core_problem,
        technical_solution=technical_solution,
        impact_analysis=impact_analysis or "N/A",
        reference_value=reference_value or "N/A",
    )


def generate_briefing(
    title: str,
    briefing_type: str,
    content: str,
    time_range_start=None,
    time_range_end=None,
) -> str:
    """
    生成简报文档 Markdown

    入参：
        title: 简报标题
        briefing_type: weekly / monthly / topic
        content: 简报正文
        time_range_start: 覆盖开始时间
        time_range_end: 覆盖结束时间
    出参：Markdown 格式文本
    """
    return BRIEFING_TEMPLATE.format(
        title=title,
        time_range_start=_format_time(time_range_start),
        time_range_end=_format_time(time_range_end),
        briefing_type=briefing_type,
        briefing_content=content,
    )
