"""Internal L4 topic selection and deterministic L5 briefing assembly."""

import json
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import InternalConfig
from db.models import Article, ArticleAnalysis, BriefingDraft, DeepInsight, Source, get_session
from jobs.briefing_render import (
    assemble_briefing as _assemble_briefing,
    strip_markdown_fence as _strip_markdown_fence,
    topic_marker as _topic_marker,
    validate_briefing as _validate_briefing,
    validate_section as _validate_section,
)
from jobs.briefing_selector import BriefingSelector, CATEGORY_ORDER
from kb.markdown_gen import generate_briefing

logger = logging.getLogger("jobs.briefing")


def _query_articles(session, start_date: datetime, end_date: datetime) -> List[Dict]:
    """Load only period articles whose L2 and L3 analyses both succeeded."""
    from sqlalchemy import desc, func

    rows = (
        session.query(Article, ArticleAnalysis, Source, DeepInsight)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .join(Source, Article.source_id == Source.id)
        .join(DeepInsight, Article.id == DeepInsight.article_id)
        .filter(Article.publish_time >= start_date)
        .filter(Article.publish_time <= end_date)
        .filter(ArticleAnalysis.analysis_status == "success")
        .filter(DeepInsight.analysis_status == "success")
        .order_by(desc(func.coalesce(ArticleAnalysis.rank_score, ArticleAnalysis.value_score)))
        .all()
    )

    result = []
    for article, analysis, source, insight in rows:
        rank_score = analysis.rank_score
        if rank_score is None:
            rank_score = analysis.value_score
        result.append({
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "publish_time": article.publish_time,
            "source_code": source.source_code,
            "source_name": source.source_name,
            "source_type": source.source_type or "",
            "source_domain": source.domain or "",
            "selection_role": source.selection_role or "industry",
            "category": (
                "AI在金融领域应用"
                if analysis.category == "金融应用"
                else analysis.category or "其他AI相关"
            ),
            "sub_category": analysis.sub_category or "",
            "info_type": analysis.info_type or "其他",
            "briefing_focus": analysis.briefing_focus or "",
            "summary_cn": analysis.summary_cn or "",
            "keywords": analysis.keywords or "",
            "tech_tags": analysis.tech_tags or [],
            "companies": analysis.companies or [],
            "score_tech_depth": float(analysis.score_tech_depth or 0),
            "score_engineering": float(analysis.score_engineering or 0),
            "score_org_relevance": float(analysis.score_org_relevance or 0),
            "score_trend": float(analysis.score_trend or 0),
            "score_timeliness": float(analysis.score_timeliness or 0),
            "rank_score": float(rank_score or 0),
            "value_score": float(analysis.value_score or rank_score or 0),
            "insight_id": insight.id,
            "technical_background": insight.technical_background or "",
            "core_problem": insight.core_problem or "",
            "technical_solution": insight.technical_solution or "",
            "impact_analysis": insight.impact_analysis or "",
            "reference_value": insight.reference_value or "",
        })
    return result


def _call_internal_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call the internal OpenAI-compatible model with 300s timeout and no retry."""
    cfg = InternalConfig.get_instance().internal_llm_config
    if not cfg["base_url"] or not cfg["model"]:
        logger.warning("内部大模型未配置（base_url/model 为空），无法生成简报")
        return None

    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    if cfg.get("user_id"):
        headers["userid"] = cfg["user_id"]
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=300.0)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            logger.error("内部 LLM 返回空 choices: %s", str(data)[:200])
            return None
        content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        logger.info(
            "内部 LLM 调用成功: model=%s, tokens(prompt=%d, completion=%d)",
            cfg["model"],
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
        return content or None
    except httpx.TimeoutException:
        logger.warning("内部 LLM 超时: %s", url)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "内部 LLM 返回错误: status=%s, body=%s",
            exc.response.status_code,
            (exc.response.text or "")[:300],
        )
    except Exception as exc:
        logger.error("内部 LLM 请求异常: %s", str(exc))
    return None


def _format_topic_material(topic: Dict) -> str:
    article_blocks = []
    for article in topic["articles"]:
        published = (
            article["publish_time"].strftime("%Y-%m-%d")
            if article.get("publish_time") else "日期未知"
        )
        article_blocks.append(
            f"来源：{article['source_name']}｜{published}｜{article['info_type']}\n"
            f"标题：{article['title']}\n"
            f"L2摘要：{article['summary_cn'][:600]}\n"
            f"简报重点：{article.get('briefing_focus') or article['summary_cn'][:250]}\n"
            f"L3背景：{article['technical_background'][:500]}\n"
            f"L3核心事实或问题：{article['core_problem'][:500]}\n"
            f"L3方案或变化：{article['technical_solution'][:800]}\n"
            f"L3影响与边界：{article['impact_analysis'][:500]} {article['reference_value'][:500]}\n"
            f"链接：{article['url']}"
        )
    return (
        f"主题ID：{_topic_marker(topic)}\n"
        f"主题标题：{topic['title']}\n"
        f"统一排序分：{topic['rank_score']:.2f}\n"
        f"关联材料：\n" + "\n\n".join(article_blocks)
    )


def _briefing_type_name(briefing_type: str) -> str:
    return {
        "weekly": "AI技术趋势周报",
        "monthly": "AI技术趋势月报",
        "quarterly": "AI技术趋势季报",
        "topic": "AI技术趋势专题报告",
    }.get(briefing_type, "AI技术趋势报告")


def _render_section_prompt(
    briefing_type: str,
    time_range: str,
    category: str,
    topics: List[Dict],
) -> Tuple[str, str, str]:
    prompt_config = InternalConfig.get_instance().briefing_prompt_config
    system = prompt_config["system"].replace("\\n", "\n")
    template = prompt_config["section_prompt"].replace("\\n", "\n")
    if not system or not template:
        return "", "", prompt_config["version"]
    topic_ids = "、".join(_topic_marker(topic) for topic in topics)
    user = template.format(
        briefing_type=_briefing_type_name(briefing_type),
        time_range=time_range,
        category=category,
        topic_ids=topic_ids,
        topics="\n\n".join(_format_topic_material(topic) for topic in topics),
    )
    return system, user, prompt_config["version"]


def _render_intro_prompt(
    briefing_type: str,
    time_range: str,
    topics: List[Dict],
) -> Tuple[str, str]:
    prompt_config = InternalConfig.get_instance().briefing_prompt_config
    system = prompt_config["system"].replace("\\n", "\n")
    template = prompt_config["intro_prompt"].replace("\\n", "\n")
    category_counts = Counter(topic["category"] for topic in topics)
    summary = "、".join(
        f"{category}{category_counts[category]}个"
        for category in CATEGORY_ORDER if category_counts.get(category)
    )
    if not system or not template:
        return "", ""
    return system, template.format(
        briefing_type=_briefing_type_name(briefing_type),
        time_range=time_range,
        topic_count=len(topics),
        category_summary=summary,
    )


def _parse_date_param(value: Any, is_end: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        if is_end and "T" not in text and len(text) <= 10:
            parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
        return parsed
    except (TypeError, ValueError):
        logger.warning("简报日期参数解析失败: value=%s", value)
        return None


def _persist_selection_metadata(title: str, metadata: Dict):
    directory = os.path.join(InternalConfig.get_instance().data_dir, "briefing_selections")
    try:
        os.makedirs(directory, exist_ok=True)
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as handle:
            json.dump(
                {"title": title, "generated_at": datetime.now().isoformat(), **metadata},
                handle,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
    except OSError as exc:
        logger.warning("L4/L5 选题审计文件保存失败: %s", str(exc))


def _generate_sections(
    briefing_type: str,
    time_range: str,
    topics: List[Dict],
) -> Tuple[List[str], List[Dict], str]:
    grouped = defaultdict(list)
    for topic in topics:
        grouped[topic["category"]].append(topic)
    sections = []
    checks = []
    prompt_version = "unknown"
    for category in CATEGORY_ORDER:
        category_topics = grouped.get(category, [])
        if not category_topics:
            continue
        system_prompt, user_prompt, prompt_version = _render_section_prompt(
            briefing_type, time_range, category, category_topics
        )
        if not system_prompt or not user_prompt:
            checks.append({"valid": False, "category": category, "errors": ["prompt_unavailable"]})
            break
        content = _strip_markdown_fence(_call_internal_llm(system_prompt, user_prompt) or "")
        check = _validate_section(category, category_topics, content)
        checks.append(check)
        if not check["valid"]:
            logger.error("L5 分类生成校验失败: category=%s, errors=%s", category, check["errors"])
            break
        sections.append(content)
    return sections, checks, prompt_version


def handle_briefing_job(params: str = "") -> Dict[str, Any]:
    """Generate a briefing without changing the existing scheduler/API contract."""
    briefing_type = "weekly"
    from_date = None
    to_date = None
    if params:
        try:
            parsed_params = json.loads(params) if isinstance(params, str) else params
            briefing_type = parsed_params.get("briefing_type", "weekly")
            from_date = parsed_params.get("from_date") or parsed_params.get("from")
            to_date = parsed_params.get("to_date") or parsed_params.get("to")
        except (json.JSONDecodeError, AttributeError):
            logger.warning("简报调度参数解析失败: %s", params)

    now = datetime.now()
    start_date = _parse_date_param(from_date)
    end_date = _parse_date_param(to_date, is_end=True)
    if from_date and not start_date:
        return {"status": "failed", "reason": "invalid_from_date", "detail": "from_date must use YYYY-MM-DD or ISO datetime format"}
    if to_date and not end_date:
        return {"status": "failed", "reason": "invalid_to_date", "detail": "to_date must use YYYY-MM-DD or ISO datetime format"}
    if start_date and not end_date:
        end_date = now
    elif end_date and not start_date:
        start_date = end_date - timedelta(days=7)
    elif not start_date and not end_date:
        days = {"weekly": 7, "monthly": 30, "quarterly": 90}.get(briefing_type, 7)
        start_date, end_date = now - timedelta(days=days), now
    if start_date > end_date:
        return {"status": "failed", "reason": "invalid_time_range", "detail": "from_date must be earlier than or equal to to_date"}

    time_range = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
    title = f"{_briefing_type_name(briefing_type)}（{time_range}）"
    logger.info("====== 简报生成任务开始 ======")
    logger.info("briefing_type=%s, time_range=%s", briefing_type, time_range)

    session = get_session()
    try:
        candidates = _query_articles(session, start_date, end_date)
        if not candidates:
            return {"status": "skipped", "reason": "no_successful_l3_articles", "time_range": time_range}

        selector = BriefingSelector(InternalConfig.get_instance().briefing_selection_config)
        topics, selection_metadata = selector.select(candidates, briefing_type)
        logger.info(
            "L4 选题完成: successful_l3=%d, candidate_topics=%d, selected=%d, shortfall=%d, sources=%s, categories=%s",
            len(candidates),
            selection_metadata["candidate_topics"],
            len(topics),
            selection_metadata["shortfall_topics"],
            selection_metadata["source_counts"],
            selection_metadata["category_counts"],
        )
        if not topics:
            _persist_selection_metadata(title, selection_metadata)
            return {"status": "skipped", "reason": "no_qualified_l3_topics", "time_range": time_range}

        sections, section_checks, prompt_version = _generate_sections(
            briefing_type, time_range, topics
        )
        if len(sections) != len({topic["category"] for topic in topics}):
            selection_metadata.update({
                "prompt_version": prompt_version,
                "generation_status": "failed",
                "section_checks": section_checks,
            })
            _persist_selection_metadata(title, selection_metadata)
            return {"status": "failed", "reason": "briefing_section_validation_failed", "detail": section_checks}

        intro_system, intro_user = _render_intro_prompt(briefing_type, time_range, topics)
        if not intro_system or not intro_user:
            selection_metadata.update({"prompt_version": prompt_version, "generation_status": "failed", "reason": "intro_prompt_unavailable"})
            _persist_selection_metadata(title, selection_metadata)
            return {"status": "failed", "reason": "briefing_prompt_unavailable"}
        intro = _strip_markdown_fence(_call_internal_llm(intro_system, intro_user) or "")
        if not intro:
            selection_metadata.update({"prompt_version": prompt_version, "generation_status": "failed", "reason": "intro_unavailable"})
            _persist_selection_metadata(title, selection_metadata)
            return {"status": "failed", "reason": "internal_llm_unavailable"}

        content = _assemble_briefing(time_range, intro, topics, sections)
        validation = _validate_briefing(topics, content, section_checks)
        selection_metadata.update({
            "prompt_version": prompt_version,
            "generation_status": "success" if validation["valid"] else "failed",
            "generation_validation": validation,
        })
        if not validation["valid"]:
            _persist_selection_metadata(title, selection_metadata)
            return {"status": "failed", "reason": "briefing_completeness_validation_failed", "detail": validation}

        selected_article_ids = {
            article["id"] for topic in topics for article in topic["articles"]
        }
        selected_insight_ids = {
            article["insight_id"] for topic in topics for article in topic["articles"]
        }
        draft = BriefingDraft(
            briefing_type=briefing_type,
            title=title,
            content=content,
            time_range_start=start_date,
            time_range_end=end_date,
            related_article_ids=sorted(selected_article_ids),
            related_insight_ids=sorted(selected_insight_ids),
            review_status="pending",
        )
        session.add(draft)
        session.commit()

        generate_briefing(
            title=title,
            briefing_type=briefing_type,
            content=content,
            time_range_start=start_date,
            time_range_end=end_date,
        )
        _persist_selection_metadata(title, selection_metadata)
        logger.info(
            "简报生成成功: title=%s, successful_l3=%d, topics=%d, content_length=%d",
            title, len(candidates), len(topics), len(content),
        )
        return {
            "status": "success",
            "briefing_type": briefing_type,
            "title": title,
            "time_range": time_range,
            "articles_count": len(selected_article_ids),
            "insights_count": len(selected_insight_ids),
            "content_length": len(content),
            "md_preview": content[:500] + "..." if len(content) > 500 else content,
        }
    except Exception as exc:
        session.rollback()
        logger.exception("简报生成失败")
        return {"status": "failed", "reason": str(exc)[:500]}
    finally:
        session.close()
