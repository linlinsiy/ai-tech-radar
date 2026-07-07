"""
内部侧 - 简报生成 Job

aiRadarBriefingJob: 定时/手动触发，查 MySQL 近一周/月文章 + 洞察，
调用内部大模型生成简报，写 MySQL 元数据 + EIPLite 知识库。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from db.models import get_session, Article, ArticleAnalysis, DeepInsight, BriefingDraft
from config import InternalConfig
import httpx
import time
from kb.markdown_gen import generate_briefing

logger = logging.getLogger("jobs.briefing")


def _query_articles(session, start_date: datetime, end_date: datetime) -> List[Dict]:
    """
    查询时间范围内的文章及分析结果（按价值评分降序）

    入参：
        session: DB 会话
        start_date: 开始日期
        end_date: 结束日期
    出参：文章列表 [{"title": ..., "category": ..., "sub_category": ..., "summary_cn": ..., "value_score": ..., "url": ...}]
    """
    from sqlalchemy import desc

    articles = (
        session.query(Article, ArticleAnalysis)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .filter(Article.publish_time >= start_date)
        .filter(Article.publish_time <= end_date)
        .filter(ArticleAnalysis.analysis_status == "success")
        .order_by(desc(ArticleAnalysis.value_score))
        .limit(15)
        .all()
    )

    result = []
    for art, analysis in articles:
        result.append({
            "id": art.id,
            "title": art.title,
            "url": art.url,
            "category": analysis.category or "",
            "sub_category": analysis.sub_category or "",
            "info_type": analysis.info_type or "",
            "briefing_focus": analysis.briefing_focus or "",
            "summary_cn": analysis.summary_cn or "",
            "value_score": float(analysis.value_score) if analysis.value_score else 0,
        })
    return result


def _query_insights(session, start_date: datetime, end_date: datetime) -> List[Dict]:
    """
    查询时间范围内的深度洞察

    入参：
        session: DB 会话
        start_date: 开始日期
        end_date: 结束日期
    出参：洞察列表
    """
    from sqlalchemy import desc

    insights = (
        session.query(DeepInsight, Article)
        .join(Article, DeepInsight.article_id == Article.id)
        .filter(Article.publish_time >= start_date)
        .filter(Article.publish_time <= end_date)
        .filter(DeepInsight.analysis_status == "success")
        .all()
    )

    result = []
    for ins, art in insights:
        result.append({
            "id": ins.id,
            "title": art.title,
            "url": art.url,
            "technical_background": ins.technical_background,
            "core_problem": ins.core_problem,
            "technical_solution": ins.technical_solution,
            "impact_analysis": ins.impact_analysis or "",
            "reference_value": ins.reference_value or "",
        })
    return result


def _call_internal_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """
    调用内部大模型生成简报（OpenAI 兼容接口）

    入参：
        system_prompt: 系统指令
        user_prompt: 用户提示词
    出参：生成的简报正文，失败返回 None

    调用内部 Qwen3-32B-AWQ 模型的 chat/completions 接口，
    超时时间 300 秒，不进行失败重试，API Key 为可选。
    """
    cfg = InternalConfig.get_instance().internal_llm_config
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]
    model = cfg["model"]

    if not base_url or not model:
        logger.warning("内部大模型未配置（base_url/model 为空），无法生成简报")
        return None

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }

    timeout_seconds = 300.0
    max_retries = 0
    retry_backoff = (10, 30)

    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        except httpx.TimeoutException:
            logger.warning("内部 LLM 超时 (attempt %d/%d): %s",
                           attempt + 1, max_retries + 1, url)
            if attempt < max_retries:
                time.sleep(retry_backoff[min(attempt, len(retry_backoff) - 1)])
            continue
        except httpx.ConnectError as e:
            logger.warning("内部 LLM 连接失败 (attempt %d/%d): %s",
                           attempt + 1, max_retries + 1, e)
            if attempt < max_retries:
                time.sleep(retry_backoff[min(attempt, len(retry_backoff) - 1)])
            continue
        except Exception as e:
            logger.error("内部 LLM 请求异常: %s", e)
            return None

        if resp.status_code == 200:
            try:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    logger.info(
                        "内部 LLM 调用成功: model=%s, tokens(prompt=%d, completion=%d)",
                        model,
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )
                    return content
                logger.error("内部 LLM 返回空 choices: %s", str(data)[:200])
                return None
            except Exception as e:
                logger.error("内部 LLM 响应解析失败: %s", e)
                return None

        if resp.status_code == 503 and attempt < max_retries:
            logger.warning("内部 LLM 503 (attempt %d/%d): %s",
                           attempt + 1, max_retries + 1, resp.text[:200] if resp.text else "")
            time.sleep(retry_backoff[min(attempt, len(retry_backoff) - 1)])
            continue

        logger.error("内部 LLM 返回错误 (status=%d): %s",
                     resp.status_code, (resp.text or "")[:300])
        if attempt < max_retries:
            time.sleep(retry_backoff[min(attempt, len(retry_backoff) - 1)])
            continue
        return None

    return None


def _format_articles_list(articles: List[Dict]) -> str:
    """格式化文章列表为 LLM 输入文本"""
    lines = []
    for i, a in enumerate(articles, 1):
        category_text = a["category"]
        if a.get("sub_category"):
            category_text = f"{category_text}/{a['sub_category']}" if category_text else a["sub_category"]
        if a.get("info_type"):
            category_text = f"{category_text} · {a['info_type']}" if category_text else a["info_type"]
        focus = a.get("briefing_focus") or a["summary_cn"][:200]
        lines.append(
            f"{i}. 【{category_text}】{a['title']}\n"
            f"   评分: {a['value_score']:.1f}/10\n"
            f"   摘要: {a['summary_cn'][:200]}\n"
            f"   简报重点: {focus}\n"
            f"   链接: {a['url']}"
        )
    return "\n\n".join(lines)


def _format_insights_list(insights: List[Dict]) -> str:
    """格式化洞察列表为 LLM 输入文本"""
    if not insights:
        return "本周期无深度洞察文章。"
    lines = []
    for i, ins in enumerate(insights, 1):
        lines.append(
            f"{i}. {ins['title']}\n"
            f"   核心问题: {ins['core_problem'][:150]}\n"
            f"   方案: {ins['technical_solution'][:150]}\n"
            f"   参考价值: {ins['reference_value'][:150]}"
        )
    return "\n\n".join(lines)


def handle_briefing_job(params: str = "") -> Dict[str, Any]:
    """
    XXL-Job JobHandler: aiRadarBriefingJob

    入参：
        params: 调度参数 JSON，如 {"briefing_type":"weekly"}
    出参：生成统计

    流程：
        1. 解析调度参数，确定时间范围和简报类型
        2. 查 MySQL 获取文章和洞察
        3. 调用内部大模型生成简报正文
        4. 写入 ai_radar_briefing_draft 元数据
        5. 生成 Markdown 文件 → EIPLite 上传（待集成）
    """
    # 解析参数
    briefing_type = "weekly"
    if params:
        try:
            ps = json.loads(params) if isinstance(params, str) else params
            briefing_type = ps.get("briefing_type", "weekly")
        except json.JSONDecodeError:
            pass

    logger.info("====== 简报生成任务开始 ======")
    logger.info("briefing_type=%s", briefing_type)

    # 确定时间范围
    now = datetime.now()
    if briefing_type == "weekly":
        start_date = now - timedelta(days=7)
        title_prefix = "AI技术趋势周报"
    elif briefing_type == "monthly":
        start_date = now - timedelta(days=30)
        title_prefix = "AI技术趋势月报"
    else:
        start_date = now - timedelta(days=7)
        title_prefix = "AI技术趋势专题报告"

    end_date = now
    time_range_str = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"

    session = get_session()
    try:
        # 查询数据
        articles = _query_articles(session, start_date, end_date)
        insights = _query_insights(session, start_date, end_date)

        if not articles and not insights:
            logger.info("时间范围内无新文章，跳过简报生成")
            return {
                "status": "skipped",
                "reason": "no_new_articles",
                "time_range": time_range_str,
            }

        # 格式化输入
        articles_text = _format_articles_list(articles)
        insights_text = _format_insights_list(insights)

        # 构建 Prompt
        # TODO: 从配置文件加载 prompt 模板（当前硬编码占位）
        system_prompt = (
            "你是信息技术部架构委员会的技术简报编辑。基于近期外部 AI 技术资讯的分析结果，"
            "生成一份面向全公司或全部门阅读的 AI 技术趋势雷达文章。文章的主要作用是像雷达一样"
            "扫描并呈现外部 AI 技术资讯，帮助读者了解近期出现了哪些技术内容、它们解决什么问题、"
            "具体做了什么以及大致如何实现。风格要求：专业、精炼、客观，避免过度主观发挥，"
            "也避免写成项目建议书、风险清单或任务分解。"
        )
        type_cn = {"weekly": "周报", "monthly": "月报", "topic": "专题报告"}
        user_prompt = (
            f"请根据以下近期采集和分析的 AI 技术资讯，生成一份{type_cn.get(briefing_type, '技术趋势')}简报。\n\n"
            f"【覆盖时间】{time_range_str}\n\n"
            f"【收录文章（按价值评分降序前 {len(articles)} 篇）】\n{articles_text}\n\n"
            f"【深度洞察文章（{len(insights)} 篇）】\n{insights_text}\n\n"
            "请按以下结构组织简报，面向全公司/全部门统一阅读，不要按读者身份拆分栏目，"
            "不要写成具体决策事项、实施计划、风险清单或行动任务：\n"
            "1. 雷达概览（用 1-2 段客观概括本期收集到的资讯范围、主要技术类别和信息密度）\n"
            "2. 技术资讯分类摘要（正文主体，按技术类别组织，如大模型、Agent、RAG、推理优化、多模态、AI工程系统、安全与治理等；每类说明本期收集到哪些内容）\n"
            "3. 重点技术条目（选择高价值或有代表性的资讯逐条说明：分类、解决的问题、具体做了什么、大致怎么做的、关联原文链接）\n"
            "4. 共性问题与方法归纳（仅基于已收集资讯，归纳这些文章共同关注的问题和常见技术做法，不做过度推演）\n"
            "5. 信号源索引（标题、来源、评分、链接）\n\n"
            "格式：Markdown。正文以技术资讯事实和归纳为主，少写主观判断；涉及总结时必须能从输入文章中找到依据。"
        )

        # 调用内部大模型
        briefing_content = _call_internal_llm(system_prompt, user_prompt)
        if not briefing_content:
            return {"status": "failed", "reason": "internal_llm_unavailable"}

        # 写入 MySQL 元数据和正文
        title = f"{title_prefix}（{time_range_str}）"
        draft = BriefingDraft(
            briefing_type=briefing_type,
            title=title,
            content=briefing_content,
            time_range_start=start_date,
            time_range_end=end_date,
            related_article_ids=json.dumps([a["id"] for a in articles]),
            related_insight_ids=json.dumps([i.get("id", 0) for i in insights]),
            review_status="pending",
        )
        session.add(draft)
        session.commit()

        # 生成 Markdown 文件（供 EIPLite 上传）
        md_content = generate_briefing(
            title=title,
            briefing_type=briefing_type,
            content=briefing_content,
            time_range_start=start_date,
            time_range_end=end_date,
        )

        logger.info("简报生成成功: title=%s, content_length=%d", title, len(briefing_content))

        return {
            "status": "success",
            "briefing_type": briefing_type,
            "title": title,
            "time_range": time_range_str,
            "articles_count": len(articles),
            "insights_count": len(insights),
            "content_length": len(briefing_content),
            "md_preview": md_content[:500] + "..." if len(md_content) > 500 else md_content,
        }

    except Exception as e:
        session.rollback()
        logger.exception("简报生成失败")
        return {"status": "failed", "reason": str(e)[:500]}
    finally:
        session.close()

