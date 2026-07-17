"""
Markdown 文件生成模块

根据设计文档定义的三类模板，从 MySQL 记录生成 EIPLite 知识库入库用的 Markdown 文件。

模板类型：
- article_summary: 文章摘要卡片
- deep_insight: 深度洞察卡片
- briefing: 简报文档
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger("kb.markdown_gen")

# === 文章摘要卡片模板 ===
ARTICLE_SUMMARY_TEMPLATE = """# {display_title}

**来源**：{source_name}
**原始标题**：{title}
**中文标题**：{title_cn}
**作者**：{author}
**发布时间**：{publish_time}
**原文链接**：{url}
**资讯分类**：{category}
**资讯子分类**：{sub_category}
**资讯类型**：{info_type}
**原文语言**：{source_language}
**统一排序分**：{rank_score}/10

## 中文摘要（辅助入口）
{summary_cn}

## 简报表达重点
{briefing_focus}

## 结构化分析详情
{analysis_detail}

## 标准术语映射
{standard_terms}

## 原文摘要
{raw_summary}

## 原文正文（主召回内容）
{full_content}
"""

# === 深度洞察卡片模板 ===
DEEP_INSIGHT_TEMPLATE = """# {title} — 深度洞察

**来源**：{source_name}
**原文链接**：{url}
**资讯分类**：{category}
**统一排序分**：{rank_score}/10

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


def _format_standard_terms(standard_terms: Optional[List[Dict[str, Any]]]) -> str:
    """格式化标准术语映射，供知识库中文和英文双入口召回。"""
    if not standard_terms:
        return "N/A"

    lines = []
    for item in standard_terms:
        if not isinstance(item, dict):
            text = str(item).strip()
            if text:
                lines.append(f"- {text}")
            continue

        term = str(item.get("term") or "").strip()
        abbr = str(item.get("abbr") or "").strip()
        zh = str(item.get("zh") or "").strip()
        aliases = item.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        aliases_text = "，".join(str(a).strip() for a in aliases if str(a).strip())

        head = term
        if abbr and abbr != term:
            head = f"{head} ({abbr})" if head else abbr
        if zh:
            head = f"{head} -> {zh}" if head else zh
        if aliases_text:
            head = f"{head}；别名：{aliases_text}"
        if head:
            lines.append(f"- {head}")

    return "\n".join(lines) if lines else "N/A"


def _format_analysis_detail(analysis_detail: Optional[Dict[str, Any]]) -> str:
    """格式化通用结构化分析详情，避免为不同资讯类型扩展固定列。"""
    if not analysis_detail:
        return "N/A"

    labels = {
        "problem_solved": "解决的问题",
        "what_changed": "发生的变化",
        "how_it_works": "大致做法",
        "business_context": "业务背景",
        "finance_scenario": "金融场景",
        "risk_or_governance": "风险与治理",
        "ecosystem_signal": "生态信号",
        "note": "补充说明",
    }
    lines = []
    for key, value in analysis_detail.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lines.append(f"- {labels.get(key, key)}：{text}")
    return "\n".join(lines) if lines else "N/A"


def generate_article_summary(
    title: str,
    source_name: str,
    url: str,
    summary_cn: str,
    title_cn: str = "",
    source_language: str = "unknown",
    sub_category: str = "",
    info_type: str = "",
    briefing_focus: str = "",
    analysis_detail: Optional[Dict[str, Any]] = None,
    standard_terms: Optional[List[Dict[str, Any]]] = None,
    raw_summary: str = "",
    full_content: str = "",
    category: Optional[str] = None,
    author: Optional[str] = None,
    publish_time=None,
    value_score: Optional[float] = None,
    rank_score: Optional[float] = None,
) -> str:
    """
    生成文章摘要卡片 Markdown

    入参：
        title: 文章标题
        source_name: 来源名称
        url: 原文链接
        summary_cn: 中文摘要
        title_cn: 中文标题
        source_language: 原文语言
        sub_category: 资讯子分类
        info_type: 资讯类型
        briefing_focus: 简报表达重点
        analysis_detail: 结构化分析详情
        standard_terms: 标准术语映射
        category: 资讯分类
        author: 作者
        publish_time: 发布时间
        value_score: 旧字段兼容评分
        rank_score: 统一排序评分
    出参：Markdown 格式文本
    """
    return ARTICLE_SUMMARY_TEMPLATE.format(
        display_title=title_cn or title,
        title=title,
        title_cn=title_cn or "N/A",
        source_name=source_name,
        author=author or "N/A",
        publish_time=_format_time(publish_time),
        url=url,
        category=category or "N/A",
        sub_category=sub_category or "N/A",
        info_type=info_type or "N/A",
        source_language=source_language or "unknown",
        rank_score=(
            f"{rank_score:.1f}" if rank_score is not None
            else f"{value_score:.1f}" if value_score is not None
            else "N/A"
        ),
        summary_cn=summary_cn,
        briefing_focus=briefing_focus or "N/A",
        analysis_detail=_format_analysis_detail(analysis_detail),
        standard_terms=_format_standard_terms(standard_terms),
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
    rank_score: Optional[float] = None,
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
        rank_score=(
            f"{rank_score:.1f}" if rank_score is not None
            else f"{value_score:.1f}" if value_score is not None
            else "N/A"
        ),
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
