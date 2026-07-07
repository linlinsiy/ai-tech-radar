"""
L2 基础分析编排

对去重后的文章执行 LLM 摘要、分类、评分。
并发控制（≤3）、JSON 解析容错、失败不阻塞。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any
import json

from crawler.base import RawArticle
from llm.client import LLMClient
from llm.prompts import PromptRegistry

from logging_config import get_logger
logger = get_logger("processor.l2_analysis")


class L2Analyzer:
    """
    L2 基础分析器

    方法：
        analyze_batch: 批量分析文章（并发 ≤ max_concurrency）
        _analyze_single: 单篇文章分析

    类变量：
        llm: LLMClient 实例
        prompts: PromptRegistry 实例
        max_concurrency: 最大并发数
        categories: 技术分类候选列表
    """

    def __init__(
        self, llm: LLMClient, prompts: PromptRegistry,
        max_concurrency: int = 3, model_name: str = "gpt-4o-mini"
    ):
        """
        初始化 L2 分析器

        入参：
            llm: LLM 客户端
            prompts: Prompt 注册表
            max_concurrency: 最大并发数
        """
        self.llm = llm
        self.prompts = prompts
        self.max_concurrency = max_concurrency
        self.model_name = model_name
        # 从 prompt 配置获取分类候选列表
        tmpl = prompts.get("l2_summary")
        self.categories = (tmpl or {}).get("categories", "")
        self.term_glossary = (tmpl or {}).get("term_glossary", "")

    def analyze_batch(
        self, articles: List[RawArticle]
    ) -> List[Dict[str, Any]]:
        """
        批量分析文章

        入参：
            articles: 待分析的文章列表（已去重）
        出参：分析结果列表，每项含 article 字段和 analysis 字段
        """
        if not articles:
            return []

        logger.info("开始 L2 分析: articles=%d, concurrency=%d",
                     len(articles), self.max_concurrency)
        results: List[Dict] = []
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = {
                executor.submit(self._analyze_single, article): article
                for article in articles
            }
            for future in as_completed(futures):
                article = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                    else:
                        failed += 1
                except Exception as e:
                    logger.error("L2 分析异常: url=%s, %s", article.url, str(e))
                    failed += 1

        logger.info(
            "L2 分析完成: total=%d, success=%d, failed=%d",
            len(articles), len(results), failed
        )
        return results

    def _analyze_single(self, article: RawArticle) -> Optional[Dict]:
        """
        单篇文章 L2 分析

        入参：
            article: RawArticle 实例
        出参：{"article": RawArticle, "analysis": {...}}，失败返回 None
        """
        logger.info("L2 分析: %s", article.url_hash[:16])

        # 准备输入文本
        input_text = article.raw_summary or article.title or ""
        if len(input_text) < 50 and article.raw_html:
            from processor.parser import ContentParser
            input_text = ContentParser.extract_text(article.raw_html)[:3000]

        # 渲染 Prompt
        system, user, version, _model_name = self.prompts.render(
            "l2_summary",
            title=article.title,
            summary=input_text,
            categories=self.categories,
            term_glossary=self.term_glossary,
        )
        if not system or not user:
            logger.warning("L2 Prompt 渲染失败: %s", article.url_hash[:16])
            return None

        # 调用 LLM
        result = self.llm.call(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=self.model_name,
            temperature=0.3,
            max_tokens=2048,
            response_json=True,
        )

        if not result.get("success"):
            logger.warning("L2 LLM 调用失败: %s", article.url_hash[:16])
            return None

        # 解析 JSON 响应
        parsed = self.llm.parse_json_response(result)
        if parsed is None:
            logger.warning("L2 JSON 解析失败: %s", article.url_hash[:16])
            return None

        # 组装分析结果
        scores = self._extract_scores(parsed)
        value_score = sum(scores.values()) / len(scores) if scores else 0.0

        standard_terms = self._normalize_standard_terms(parsed.get("standard_terms", []))
        source_language = parsed.get("source_language") or self._detect_source_language(
            f"{article.title}\n{input_text}"
        )
        if source_language not in ("en", "zh", "mixed", "unknown"):
            source_language = self._detect_source_language(f"{article.title}\n{input_text}")

        analysis = {
            "title_cn": str(parsed.get("title_cn") or article.title or "").strip(),
            "source_language": source_language,
            "summary_cn": parsed.get("summary_cn", parsed.get("summary", "")),
            "category": parsed.get("category", ""),
            "keywords": self._ensure_list(parsed.get("keywords", [])),
            "tech_tags": self._ensure_list(parsed.get("tech_tags", [])),
            "companies": self._ensure_list(parsed.get("companies", [])),
            "standard_terms": standard_terms,
            "score_tech_depth": scores.get("tech_depth", 5.0),
            "score_engineering": scores.get("engineering", 5.0),
            "score_trend": scores.get("trend", 5.0),
            "score_credibility": scores.get("credibility", 5.0),
            "score_timeliness": scores.get("timeliness", 5.0),
            "value_score": round(value_score, 2),
            "model_name": result.get("model", ""),
            "prompt_version": version,
        }

        return {"article": article, "analysis": analysis}

    @staticmethod
    def _ensure_list(value) -> List[str]:
        """将 LLM 返回的字符串或数组统一为字符串数组。"""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            normalized = value.replace("，", ",").replace("；", ",").replace(";", ",")
            return [v.strip() for v in normalized.split(",") if v.strip()]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _normalize_standard_terms(value) -> List[Dict[str, Any]]:
        """标准化术语映射，兼容模型返回字符串或对象数组。"""
        if not value:
            return []
        items = value if isinstance(value, list) else [value]
        terms = []
        for item in items[:10]:
            if isinstance(item, dict):
                aliases = item.get("aliases", [])
                if isinstance(aliases, str):
                    aliases = L2Analyzer._ensure_list(aliases)
                term = {
                    "term": str(item.get("term") or item.get("en") or "").strip(),
                    "abbr": str(item.get("abbr") or "").strip(),
                    "zh": str(item.get("zh") or item.get("zh_cn") or "").strip(),
                    "aliases": [str(a).strip() for a in aliases if str(a).strip()],
                }
                if term["term"] or term["zh"]:
                    terms.append(term)
            elif isinstance(item, str) and item.strip():
                terms.append({"term": item.strip(), "abbr": "", "zh": "", "aliases": []})
        return terms

    @staticmethod
    def _detect_source_language(text: str) -> str:
        """粗略识别原文语言，用于知识库标签和展示。"""
        if not text:
            return "unknown"
        chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
        if chinese and latin > chinese * 2:
            return "mixed"
        if chinese:
            return "zh"
        if latin:
            return "en"
        return "unknown"

    @staticmethod
    def _extract_scores(parsed: Dict) -> Dict[str, float]:
        """
        从 LLM 响应中提取五维度评分

        入参：
            parsed: LLM JSON 响应
        出参：{tech_depth, engineering, trend, credibility, timeliness}
        """
        score_keys = {
            "tech_depth": ["tech_depth", "score_tech_depth", "技术深度"],
            "engineering": ["engineering", "score_engineering", "工程参考价值"],
            "trend": ["trend", "score_trend", "趋势重要性"],
            "credibility": ["credibility", "score_credibility", "来源可信度"],
            "timeliness": ["timeliness", "score_timeliness", "时效性"],
        }
        result = {}
        for key, candidates in score_keys.items():
            value = 5.0  # 默认中等
            for c in candidates:
                if c in parsed:
                    try:
                        v = float(parsed[c])
                        if 1.0 <= v <= 10.0:
                            value = v
                            break
                    except (ValueError, TypeError):
                        pass
            result[key] = value
        return result

