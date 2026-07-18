"""
L2 基础分析编排

对去重后的文章执行 LLM 摘要、分类、评分。
并发控制（≤3）、JSON 解析容错、失败不阻塞。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any
import json
from datetime import datetime

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
        categories: 资讯一级分类候选列表
    """

    def __init__(
        self, llm: LLMClient, prompts: PromptRegistry,
        max_concurrency: int = 3, model_name: str = "gpt-4o-mini",
        source_profiles: Optional[Dict[str, Dict[str, str]]] = None,
        deep_analysis_min_score: float = 7.0,
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
        self.source_profiles = source_profiles or {}
        self.deep_analysis_min_score = deep_analysis_min_score
        # 从 prompt 配置获取分类候选列表
        tmpl = prompts.get("l2_summary")
        self.categories = (tmpl or {}).get("categories", "")
        self.allowed_categories = self._ensure_list(self.categories)
        self.sub_categories = (tmpl or {}).get("sub_categories", "")
        self.info_types = (tmpl or {}).get("info_types", "")
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

        # L2 同时读取摘要和有限正文片段，避免只凭列表摘要判断工程价值。
        input_text = self._prepare_input_text(article)
        source = self.source_profiles.get(article.source_code, {})
        timeliness = self._timeliness_score(article.publish_time, article.crawl_time)

        # 渲染 Prompt
        system, user, version, _model_name = self.prompts.render(
            "l2_summary",
            title=article.title,
            summary=input_text,
            categories=self.categories,
            sub_categories=self.sub_categories,
            info_types=self.info_types,
            term_glossary=self.term_glossary,
            source_name=source.get("name", article.source_code),
            source_type=source.get("type", "unknown"),
            source_domain=source.get("domain", ""),
            source_category=source.get("category", ""),
            fetch_method=source.get("fetch_method", "unknown"),
            publish_time=article.publish_time.isoformat() if article.publish_time else "unknown",
            crawl_time=article.crawl_time.isoformat(),
            content_length=len(input_text),
            timeliness_score=timeliness,
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

        standard_terms = self._normalize_standard_terms(parsed.get("standard_terms", []))
        source_language = parsed.get("source_language") or self._detect_source_language(
            f"{article.title}\n{input_text}"
        )
        if source_language not in ("en", "zh", "mixed", "unknown"):
            source_language = self._detect_source_language(f"{article.title}\n{input_text}")

        # 组装分析结果
        scores = self._extract_scores(parsed)
        # 时效性由可核验元数据确定，不接受模型猜测值。
        scores["timeliness"] = timeliness
        rank_score = (
            scores.get("org_relevance", 5.0) * 0.35
            + scores.get("trend", 5.0) * 0.30
            + scores.get("engineering", 5.0) * 0.20
            + scores.get("tech_depth", 5.0) * 0.10
            + scores.get("timeliness", 5.0) * 0.05
        )
        need_deep_analysis = parsed.get("need_deep_analysis")
        if need_deep_analysis is None:
            need_deep_analysis = rank_score >= self.deep_analysis_min_score

        analysis = {
            "title_cn": str(parsed.get("title_cn") or article.title or "").strip(),
            "source_language": source_language,
            "summary_cn": parsed.get("summary_cn", parsed.get("summary", "")),
            "category": self._normalize_category(parsed.get("category", "")),
            "sub_category": str(parsed.get("sub_category") or "").strip(),
            "info_type": str(parsed.get("info_type") or "").strip(),
            "briefing_focus": str(parsed.get("briefing_focus") or "").strip(),
            "analysis_detail": self._ensure_dict(parsed.get("analysis_detail")),
            "keywords": self._ensure_list(parsed.get("keywords", [])),
            "tech_tags": self._ensure_list(parsed.get("tech_tags", [])),
            "companies": self._ensure_list(parsed.get("companies", [])),
            "standard_terms": standard_terms,
            "score_tech_depth": scores.get("tech_depth", 5.0),
            "score_engineering": scores.get("engineering", 5.0),
            "score_org_relevance": scores.get("org_relevance", 5.0),
            "score_trend": scores.get("trend", 5.0),
            "score_timeliness": scores.get("timeliness", 5.0),
            "rank_score": round(rank_score, 2),
            # 兼容旧导入字段；新批次不再计算独立 value_score。
            "value_score": round(rank_score, 2),
            "need_deep_analysis": self._ensure_bool(need_deep_analysis),
            "model_name": result.get("model", ""),
            "prompt_version": version,
        }

        return {"article": article, "analysis": analysis}

    @staticmethod
    def _prepare_input_text(article: RawArticle) -> str:
        """组合摘要和正文样本，控制输入长度且保留文章开头技术信息。"""
        from processor.parser import ContentParser

        summary = ContentParser.extract_text(article.raw_summary or "").strip()
        full_sample = ""
        if article.raw_html:
            full_sample = ContentParser.extract_main_content(article.raw_html)[:3500].strip()
        parts = [part for part in (summary[:1200], full_sample) if part]
        return "\n\n".join(parts) or article.title or ""

    @staticmethod
    def _timeliness_score(
        publish_time: Optional[datetime], crawl_time: Optional[datetime]
    ) -> float:
        """按采集时文章年龄确定时效性，未知发布时间不获得时效性加分。"""
        if not publish_time:
            return 0.0
        reference = crawl_time or datetime.now()
        published = publish_time.replace(tzinfo=None)
        reference = reference.replace(tzinfo=None)
        age_days = max(0, (reference - published).days)
        if age_days == 0:
            return 10.0
        if age_days <= 2:
            return 9.0
        if age_days <= 4:
            return 8.0
        if age_days <= 7:
            return 7.0
        if age_days <= 14:
            return 6.0
        if age_days <= 21:
            return 5.0
        if age_days <= 30:
            return 4.0
        if age_days <= 60:
            return 3.0
        if age_days <= 90:
            return 2.0
        if age_days <= 180:
            return 1.0
        return 0.0

    @staticmethod
    def _ensure_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "是")
        return bool(value)

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
    def _ensure_dict(value) -> Dict[str, Any]:
        """将 LLM 返回的对象统一为字典，非对象内容保留为 note。"""
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            return {"note": value.strip()}
        return {}

    def _normalize_category(self, value) -> str:
        """将模型返回的分类约束到候选一级分类，避免垂直行业应用污染金融分类查询。"""
        raw = str(value or "").strip()
        fallback = "其他AI相关" if "其他AI相关" in self.allowed_categories else ""
        if not raw:
            return fallback
        if raw in self.allowed_categories:
            return raw

        synonyms = {
            "大语言模型": "大模型基础技术",
            "LLM": "大模型基础技术",
            "AI Agent": "Agent与智能体",
            "智能体": "Agent与智能体",
            "多模态": "多模态技术",
            "部署与推理": "AI基础设施",
            "数据与评测": "AI基础设施",
            "安全与对齐": "安全与伦理",
            "开源": "开源生态",
            "金融AI": "AI在金融领域应用",
            "金融应用": "AI在金融领域应用",
        }
        for key, target in synonyms.items():
            if key in raw and target in self.allowed_categories:
                return target

        non_finance_vertical_terms = (
            "医学", "医疗", "化学", "物理", "科学", "科研", "教育", "制造", "政务"
        )
        if any(term in raw for term in non_finance_vertical_terms):
            return fallback

        for candidate in self.allowed_categories:
            if candidate and (candidate in raw or raw in candidate):
                return candidate

        return fallback

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
        从 LLM 响应中提取多维度评分

        入参：
            parsed: LLM JSON 响应
        出参：评分维度字典
        """
        score_keys = {
            "tech_depth": ["tech_depth", "score_tech_depth", "技术深度"],
            "engineering": ["engineering", "score_engineering", "工程参考价值"],
            "org_relevance": [
                "org_relevance", "score_org_relevance", "组织相关性"
            ],
            "trend": ["trend", "score_trend", "趋势重要性"],
            "timeliness": ["timeliness", "score_timeliness", "时效性"],
        }
        result = {}
        for key, candidates in score_keys.items():
            value = 0.0  # 缺失评分不获得默认中等分
            minimum = 0.0
            for c in candidates:
                if c in parsed:
                    try:
                        v = float(parsed[c])
                        if minimum <= v <= 10.0:
                            value = v
                            break
                    except (ValueError, TypeError):
                        pass
            result[key] = value
        # 组织相关性使用固定锚点，避免模型评分再次集中在 7-8 分，
        # 同时保留“应知信号”和“可直接迁移工程实践”的区分粒度。
        anchors = (0.0, 1.0, 3.0, 6.0, 7.0, 8.0, 9.0, 10.0)
        raw_org_score = result["org_relevance"]
        result["org_relevance"] = max(
            anchor for anchor in anchors if anchor <= raw_org_score
        )
        return result

