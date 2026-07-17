"""
L3 深度洞察编排

对达到统一 rank_score 门槛且有 full_content 的文章执行深度分析。
需要先获取文章全文，再调用高质量模型生成五维度洞察。
并发 ≤ 1，确保高质量模型调用不冲突。
"""
import logging
from typing import List, Dict, Optional, Any

from crawler.base import RawArticle
from llm.client import LLMClient
from llm.prompts import PromptRegistry
from processor.parser import ContentParser
from crawler.browser_fetcher import BrowserFetcher

from logging_config import get_logger
logger = get_logger("deep.insight")


def _rank_score(analysis: Dict[str, Any]) -> float:
    value = analysis.get("rank_score")
    if value is None:
        value = analysis.get("value_score")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class L3Analyzer:
    """
    L3 深度洞察分析器

    方法：
        should_trigger: 判断是否触发 L3
        analyze: 对单篇文章执行深度洞察

    类变量：
        llm: LLMClient 实例（高质量模型）
        prompts: PromptRegistry 实例
        min_score: 触发最低评分阈值
        require_full_content: 是否要求原文全文
    """

    def __init__(
        self, llm: LLMClient, prompts: PromptRegistry,
        min_score: float = 8.0, require_full_content: bool = True,
        model_name: str = "gpt-4o", browser_fallback: bool = False,
        browser_timeout_seconds: int = 45,
        browser_executable_path: str = "",
        allow_content_fetch: bool = True,
    ):
        """
        初始化 L3 分析器

        入参：
            llm: LLM 客户端
            prompts: Prompt 注册表
            min_score: 触发最低评分
            require_full_content: 是否要求原文全文
        """
        self.llm = llm
        self.prompts = prompts
        self.min_score = min_score
        self.require_full_content = require_full_content
        self.model_name = model_name
        self.browser_fallback = browser_fallback
        self.allow_content_fetch = allow_content_fetch
        self.browser_fetcher = BrowserFetcher(
            browser_timeout_seconds,
            executable_path=browser_executable_path,
        )

    def should_trigger(
        self, l2_result: Dict[str, Any]
    ) -> bool:
        """
        判断是否触发 L3 深度洞察

        条件：rank_score >= min_score 且正文满足要求

        入参：
            l2_result: L2 分析结果 {"article": RawArticle, "analysis": {...}}
        出参：是否触发
        """
        analysis = l2_result.get("analysis", {})
        article = l2_result.get("article")

        score = _rank_score(analysis)
        if score < self.min_score:
            logger.info("L3 不触发: rank_score=%.1f < %.1f", score, self.min_score)
            return False

        if self.require_full_content:
            # 检查是否已有全文，若无则尝试获取
            if article and not article.raw_html:
                if not self.allow_content_fetch:
                    logger.info("L3 不触发: 验证分析禁止重新采集全文")
                    return False
                logger.info("L3 尝试获取全文: %s", article.url)
                html = ContentParser.fetch_full_content(article.url)
                if not html and self.browser_fallback:
                    html = self.browser_fetcher.fetch_html(article.url)
                if html:
                    article.raw_html = html
                else:
                    logger.info("L3 不触发: 无法获取全文")
                    return False

        logger.info("L3 触发: rank_score=%.1f, url=%s",
                     score, article.url if article else "N/A")
        return True

    def analyze(
        self, l2_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        执行单篇文章深度洞察

        入参：
            l2_result: L2 分析结果
        出参：{"article": RawArticle, "insight": {...}}，失败返回 None
        """
        article = l2_result.get("article")
        analysis = l2_result.get("analysis", {})

        if not article:
            self._last_failure_reason = "article_missing"
            return None

        # 获取全文内容
        full_text = ""
        try:
            if article.raw_html:
                full_text = ContentParser.extract_main_content(article.raw_html)
            if not full_text:
                full_text = analysis.get("summary_cn", "") or article.raw_summary or ""

        except Exception:
            full_text = analysis.get("summary_cn", "") or article.raw_summary or ""


        # 渲染 Prompt
        system, user, version, _model_name = self.prompts.render(
            "l3_deep_insight",
            title=article.title,
            full_content=full_text,
        )
        if not system or not user:
            logger.warning("L3 Prompt 渲染失败")
            self._last_failure_reason = "prompt_unavailable"
            return None

        # 调用 LLM（高质量模型，并发 1）
        result = self.llm.call(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=self.model_name,
            temperature=0.3,
            max_tokens=8192,
            response_json=True,
        )

        if not result.get("success"):
            logger.warning("L3 LLM 调用失败")
            self._last_failure_reason = "llm_failed"
            return None

        parsed = self.llm.parse_json_response(result)
        if parsed is None:
            logger.warning("L3 JSON 解析失败")
            self._last_failure_reason = "parse_failed"
            return None

        insight = {
            "technical_background": parsed.get("technical_background", ""),
            "core_problem": parsed.get("core_problem", ""),
            "technical_solution": parsed.get("technical_solution", ""),
            "impact_analysis": parsed.get("impact_analysis", ""),
            "reference_value": parsed.get("reference_value", ""),
            "model_name": result.get("model", ""),
            "prompt_version": version,
        }

        # 设置 content_hash（从 full_text 计算）
        if full_text:
            article.compute_content_hash(full_text)

        self._last_failure_reason = ""
        return {"article": article, "insight": insight}

    def analyze_eligible(
        self, l2_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        筛选高价值文章并执行深度分析（串行，并发 ≤ 1）

        入参：
            l2_results: L2 分析结果列表
        出参：深度洞察结果列表
        """
        insights, _outcomes = self.analyze_eligible_with_outcomes(l2_results)
        return insights

    def analyze_eligible_with_outcomes(
        self, l2_results: List[Dict[str, Any]]
    ) -> tuple:
        """Run selected L3 candidates and return article-level result reasons."""
        insights = []
        outcomes = []
        for result in l2_results:
            article = result.get("article")
            base = {
                "url_hash": article.url_hash if article else "",
                "source_code": article.source_code if article else "",
            }
            if not self.should_trigger(result):
                outcomes.append({**base, "reason": self._trigger_reason(result)})
                continue
            try:
                insight = self.analyze(result)
                if insight:
                    insights.append(insight)
                    outcomes.append({**base, "reason": "success"})
                else:
                    outcomes.append({
                        **base,
                        "reason": getattr(self, "_last_failure_reason", "llm_failed"),
                    })
            except Exception as e:
                logger.exception("L3 分析异常")
                outcomes.append({**base, "reason": "llm_failed"})
                continue

        logger.info("L3 分析完成: triggered=%d", len(insights))
        return insights, outcomes

    def _trigger_reason(self, l2_result: Dict[str, Any]) -> str:
        analysis = l2_result.get("analysis", {})
        article = l2_result.get("article")
        score = _rank_score(analysis)
        if score < self.min_score:
            return "score_below_threshold"
        if self.require_full_content and article and not article.raw_html:
            return "full_content_failed"
        return "not_triggered"
