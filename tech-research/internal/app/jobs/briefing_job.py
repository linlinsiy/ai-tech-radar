"""Internal L4 topic selection and L5 briefing generation job."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from config import InternalConfig
from db.models import Article, ArticleAnalysis, BriefingDraft, DeepInsight, Source, get_session
from jobs.briefing_selector import BriefingSelector, CATEGORY_ORDER
from kb.markdown_gen import generate_briefing

logger = logging.getLogger("jobs.briefing")


def _query_articles(session, start_date: datetime, end_date: datetime) -> List[Dict]:
    """Load all qualified period candidates; L4, rather than SQL LIMIT, selects topics."""
    from sqlalchemy import desc

    rows = (
        session.query(Article, ArticleAnalysis, Source)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .join(Source, Article.source_id == Source.id)
        .filter(Article.publish_time >= start_date)
        .filter(Article.publish_time <= end_date)
        .filter(ArticleAnalysis.analysis_status == "success")
        .order_by(desc(ArticleAnalysis.value_score))
        .all()
    )

    result = []
    for article, analysis, source in rows:
        result.append({
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "publish_time": article.publish_time,
            "source_code": source.source_code,
            "source_name": source.source_name,
            "source_type": source.source_type or "",
            "source_domain": source.domain or "",
            "category": analysis.category or "其他AI相关",
            "sub_category": analysis.sub_category or "",
            "info_type": analysis.info_type or "其他",
            "briefing_focus": analysis.briefing_focus or "",
            "summary_cn": analysis.summary_cn or "",
            "keywords": analysis.keywords or "",
            "tech_tags": analysis.tech_tags or [],
            "companies": analysis.companies or [],
            "score_tech_depth": float(analysis.score_tech_depth or 0),
            "score_engineering": float(analysis.score_engineering or 0),
            "score_trend": float(analysis.score_trend or 0),
            "score_credibility": float(analysis.score_credibility or 0),
            "score_timeliness": float(analysis.score_timeliness or 0),
            "value_score": float(analysis.value_score or 0),
        })
    return result


def _query_insights(session, start_date: datetime, end_date: datetime) -> List[Dict]:
    rows = (
        session.query(DeepInsight, Article)
        .join(Article, DeepInsight.article_id == Article.id)
        .filter(Article.publish_time >= start_date)
        .filter(Article.publish_time <= end_date)
        .filter(DeepInsight.analysis_status == "success")
        .all()
    )
    return [
        {
            "id": insight.id,
            "article_id": article.id,
            "title": article.title,
            "url": article.url,
            "technical_background": insight.technical_background or "",
            "core_problem": insight.core_problem or "",
            "technical_solution": insight.technical_solution or "",
            "impact_analysis": insight.impact_analysis or "",
            "reference_value": insight.reference_value or "",
        }
        for insight, article in rows
    ]


def _call_internal_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call the internal OpenAI-compatible model with a 300-second timeout and no retry."""
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


def _format_topics(topics: List[Dict]) -> str:
    blocks = []
    for index, topic in enumerate(topics, 1):
        primary = topic["primary"]
        article_lines = []
        for article in topic["articles"]:
            published = (
                article["publish_time"].strftime("%Y-%m-%d")
                if article.get("publish_time") else "日期未知"
            )
            article_lines.append(
                f"- {article['source_name']}｜{published}｜{article['info_type']}\n"
                f"  标题：{article['title']}\n"
                f"  摘要：{article['summary_cn'][:500]}\n"
                f"  简报重点：{article.get('briefing_focus') or article['summary_cn'][:200]}\n"
                f"  链接：{article['url']}"
            )
        blocks.append(
            f"主题 {index}：{topic['title']}\n"
            f"一级分类：{topic['category']}\n"
            f"内容类型：{topic['lane']}\n"
            f"报告排序分：{topic['report_rank_score']:.2f}\n"
            f"主来源：{primary['source_name']}\n"
            f"重大事件豁免：{'是' if topic['must_include'] else '否'}\n"
            f"关联资讯：\n" + "\n".join(article_lines)
        )
    return "\n\n".join(blocks)


def _format_insights(insights: List[Dict], selected_article_ids: set) -> str:
    selected = [item for item in insights if item["article_id"] in selected_article_ids]
    if not selected:
        return "本期入选主题无对应 L3 深度洞察。"
    return "\n\n".join(
        f"{index}. {item['title']}\n"
        f"技术背景：{item['technical_background'][:300]}\n"
        f"核心问题：{item['core_problem'][:300]}\n"
        f"技术方案：{item['technical_solution'][:500]}\n"
        f"影响与参考：{item['impact_analysis'][:250]} {item['reference_value'][:250]}"
        for index, item in enumerate(selected, 1)
    )


def _render_briefing_prompt(
    briefing_type: str,
    time_range: str,
    topics_text: str,
    insights_text: str,
) -> tuple:
    prompt_config = InternalConfig.get_instance().briefing_prompt_config
    system = prompt_config["system"].replace("\\n", "\n")
    template = prompt_config["prompt"].replace("\\n", "\n")
    if not system or not template:
        return "", "", prompt_config["version"]
    type_names = {
        "weekly": "AI技术趋势周报",
        "monthly": "AI技术趋势月报",
        "quarterly": "AI技术趋势季报",
        "topic": "AI技术趋势专题报告",
    }
    user = template.format(
        briefing_type=type_names.get(briefing_type, "AI技术趋势报告"),
        time_range=time_range,
        category_order="、".join(CATEGORY_ORDER),
        topics=topics_text,
        insights=insights_text,
    )
    return system, user, prompt_config["version"]


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
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as handle:
            json.dump(
                {"title": title, "generated_at": datetime.now().isoformat(), **metadata},
                handle,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
    except OSError as exc:
        logger.warning("L4 选题审计文件保存失败: %s", str(exc))


def handle_briefing_job(params: str = "") -> Dict[str, Any]:
    """Generate a weekly, monthly, quarterly or topic briefing without changing its API."""
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
    title_prefix = {
        "weekly": "AI技术趋势周报",
        "monthly": "AI技术趋势月报",
        "quarterly": "AI技术趋势季报",
        "topic": "AI技术趋势专题报告",
    }.get(briefing_type, "AI技术趋势专题报告")
    title = f"{title_prefix}（{time_range}）"

    logger.info("====== 简报生成任务开始 ======")
    logger.info("briefing_type=%s, time_range=%s", briefing_type, time_range)

    session = get_session()
    try:
        candidates = _query_articles(session, start_date, end_date)
        insights = _query_insights(session, start_date, end_date)
        if not candidates:
            return {"status": "skipped", "reason": "no_new_articles", "time_range": time_range}

        selector = BriefingSelector(InternalConfig.get_instance().briefing_selection_config)
        topics, selection_metadata = selector.select(candidates, briefing_type)
        if not topics:
            return {"status": "skipped", "reason": "no_qualified_articles", "time_range": time_range}

        selected_article_ids = {
            article["id"] for topic in topics for article in topic["articles"]
        }
        selected_insights = [
            insight for insight in insights if insight["article_id"] in selected_article_ids
        ]
        system_prompt, user_prompt, prompt_version = _render_briefing_prompt(
            briefing_type,
            time_range,
            _format_topics(topics),
            _format_insights(insights, selected_article_ids),
        )
        if not system_prompt or not user_prompt:
            return {"status": "failed", "reason": "briefing_prompt_unavailable"}

        content = _call_internal_llm(system_prompt, user_prompt)
        if not content:
            return {"status": "failed", "reason": "internal_llm_unavailable"}

        draft = BriefingDraft(
            briefing_type=briefing_type,
            title=title,
            content=content,
            time_range_start=start_date,
            time_range_end=end_date,
            related_article_ids=sorted(selected_article_ids),
            related_insight_ids=[item["id"] for item in selected_insights],
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
        selection_metadata["prompt_version"] = prompt_version
        _persist_selection_metadata(title, selection_metadata)
        logger.info(
            "简报生成成功: title=%s, candidates=%d, topics=%d, content_length=%d",
            title,
            len(candidates),
            len(topics),
            len(content),
        )
        return {
            "status": "success",
            "briefing_type": briefing_type,
            "title": title,
            "time_range": time_range,
            "articles_count": len(selected_article_ids),
            "insights_count": len(selected_insights),
            "content_length": len(content),
            "md_preview": content[:500] + "..." if len(content) > 500 else content,
        }
    except Exception as exc:
        session.rollback()
        logger.exception("简报生成失败")
        return {"status": "failed", "reason": str(exc)[:500]}
    finally:
        session.close()
