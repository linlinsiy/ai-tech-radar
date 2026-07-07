"""
编排主流程 - aiRadarCollectJob

XXL-Job JobHandler 实现，串联采集分析全流程：
L0 采集 → L1 解析去重 → L2 基础分析 → L3 深度洞察 → 受控导入
各阶段失败独立处理，不阻塞其他文章。
"""
import logging
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any

from config import AWSConfig
from crawler.base import CrawlerFactory, RawArticle
from processor.parser import ContentParser
from processor.dedup import DedupManager
from processor.l2_analysis import L2Analyzer
from deep.insight import L3Analyzer
from exporter.import_client import ImportClient
from llm.client import LLMClient
from llm.prompts import PromptRegistry
from logging_config import get_logger

logger = get_logger("jobs.collect")


class CollectOrchestrator:
    """
    采集分析全流程编排器

    方法：
        run: 执行完整流程，返回各阶段统计

    类变量：
        config: AWSConfig 实例
        dedup: DedupManager 实例
        l2: L2Analyzer 实例
        l3: L3Analyzer 实例
        importer: ImportClient 实例
    """

    def __init__(self, config: AWSConfig):
        """
        初始化编排器

        入参：
            config: AWS 配置管理器
        """
        self.config = config
        self.dedup = DedupManager(
            cache_path=f"{config.data_dir}/interim/processed_hashes.json"
        )

        # 初始化 LLM 客户端：L2 / L3 使用不同超时时间
        api_key = self._get_api_key()
        self.l2_llm = LLMClient(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL"),  # 临时：本地测试指向内部大模型
            max_retries=2,
            timeout=config.l2_model["timeout_seconds"],
        )
        self.l3_llm = LLMClient(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL"),  # 临时：本地测试指向内部大模型
            max_retries=2,
            timeout=config.l3_model["timeout_seconds"],
        )

        # 初始化 Prompt 注册表
        self.prompts = PromptRegistry()

        # 初始化分析器
        self.l2 = L2Analyzer(
            self.l2_llm, self.prompts,
            max_concurrency=config.l2_model["max_concurrency"],
            model_name=config.l2_model["model"]
        )
        self.l3 = L3Analyzer(
            self.l3_llm, self.prompts,
            min_score=config.deep_insight_min_score,
            require_full_content=config.deep_insight_require_full_content,
            model_name=config.l3_model["model"]
        )

        # 初始化导入客户端
        retry_cfg = config.import_retry_config
        self.importer = ImportClient(
            endpoint_url=config.import_endpoint_url,
            timeout=retry_cfg["timeout_seconds"],
            retry_max=retry_cfg["retry_max"],
            backoff_seconds=retry_cfg["backoff_seconds"],
        )

    def _get_api_key(self) -> str:
        """获取 API Key（从环境变量）"""
        import os
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            logger.warning("OPENAI_API_KEY 未设置")
        return key

    def _persist_failed_import_payload(
        self,
        payload: Dict[str, Any],
        import_result: Dict[str, Any],
        stats: Dict[str, Any],
    ) -> Dict[str, str]:
        """导入失败时保存请求体，便于人工调用内部导入接口重试。"""
        batch_no = payload.get("batch", {}).get("batch_no") or stats.get("batch_no") or "unknown"
        retry_dir = os.path.join(self.config.data_dir, "failed_imports")
        os.makedirs(retry_dir, exist_ok=True)

        payload_path = os.path.join(retry_dir, f"{batch_no}.payload.json")
        meta_path = os.path.join(retry_dir, f"{batch_no}.meta.json")

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        metadata = {
            "batch_no": batch_no,
            "saved_at": datetime.now().isoformat(),
            "endpoint_url": self.config.import_endpoint_url,
            "reason": import_result.get("error", "unknown"),
            "import_result": import_result,
            "stats": stats,
            "payload_file": payload_path,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)

        logger.error("导入失败结果已持久化: payload=%s, meta=%s", payload_path, meta_path)
        return {"payload_file": payload_path, "meta_file": meta_path}

    def run(
        self,
        scope: str = "all",
        sources: List[str] = None,
        from_date: str = None,
        to_date: str = None,
        task_type: str = "scheduled",
    ) -> Dict[str, Any]:
        """
        执行采集分析全流程

        入参：
            scope: all / sources / timerange / rerun
            sources: 数据源编码列表（scope=sources 时使用）
            from_date: 开始日期（scope=timerange 时使用）
            to_date: 结束日期（scope=timerange 时使用）
        出参：执行统计 {batch_no, phase_stats: {...}, ...}
        """
        start_time = time.time()
        batch_no = f"IMP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        logger.info("====== 采集分析任务开始 ======")
        logger.info("batch_no=%s, scope=%s", batch_no, scope)

        stats = {
            "batch_no": batch_no,
            "scope": scope,
            "L0_collect": {"total": 0, "sources": 0, "errors": 0},
            "L1_dedup": {"total": 0, "new": 0, "skipped": 0},
            "L2_analysis": {"total": 0, "success": 0, "failed": 0},
            "L3_insight": {"triggered": 0, "success": 0},
            "import": {"status": "pending"},
        }

        # === L0: 采集 ===
        all_articles: List[RawArticle] = []
        data_sources = self.config.get_data_sources()
        if sources:
            data_sources = [s for s in data_sources if s["code"] in sources]

        stats["L0_collect"]["sources"] = len(data_sources)

        for source in data_sources:
            try:
                crawler = CrawlerFactory.create(source)
                articles = crawler.fetch()
                all_articles.extend(articles)
                logger.info("[%s] 采集 %d 篇", source["code"], len(articles))
            except Exception as e:
                logger.error("[%s] 采集异常: %s", source["code"], str(e))
                stats["L0_collect"]["errors"] += 1

        stats["L0_collect"]["total"] = len(all_articles)
        logger.info("L0 采集完成: total_articles=%d", len(all_articles))

        # === 日期过滤（独立于 scope，与 sources 可任意组合） ===
        if from_date or to_date:
            fd = datetime.fromisoformat(from_date) if from_date else None
            td = datetime.fromisoformat(to_date) if to_date else None
            if td:
                td = td.replace(hour=23, minute=59, second=59)
            filtered = []
            for art in all_articles:
                if art.publish_time is None:
                    filtered.append(art)
                elif (fd is None or art.publish_time >= fd) and (td is None or art.publish_time <= td):
                    filtered.append(art)
            all_articles = filtered
            logger.info("日期过滤: %d 篇 -> %d 篇 (from=%s, to=%s)",
                        stats["L0_collect"]["total"], len(all_articles), from_date or "-", to_date or "-")

        # === L1: 去重 ===
        new_articles = self.dedup.filter_duplicates(all_articles)
        stats["L1_dedup"]["total"] = len(all_articles)
        stats["L1_dedup"]["new"] = len(new_articles)
        stats["L1_dedup"]["skipped"] = len(all_articles) - len(new_articles)

        if not new_articles:
            logger.info("无新文章，流程结束")
            return stats

        # === L2: 基础分析 ===
        l2_results = self.l2.analyze_batch(new_articles)
        stats["L2_analysis"]["total"] = len(new_articles)
        stats["L2_analysis"]["success"] = len(l2_results)
        stats["L2_analysis"]["failed"] = len(new_articles) - len(l2_results)

        # === L3: 深度洞察 ===
        l3_results = []
        if l2_results:
            l3_results = self.l3.analyze_eligible(l2_results)
            stats["L3_insight"]["triggered"] = len(l3_results)
            stats["L3_insight"]["success"] = len(l3_results)

                # 对所有文章计算 content_hash（基于 raw_summary + raw_html）
                # 对所有文章计算 content_hash（基于 raw_summary + raw_html）
        for r in l2_results:
            art = r["article"]
            if not art.content_hash:
                hash_source = art.raw_summary or ""
                if art.raw_html:
                    hash_source = (hash_source + "\n" + art.raw_html)[:8000]
                if not hash_source:
                    hash_source = art.url or ""
                if hash_source:
                    art.compute_content_hash(hash_source)

# === 组装导入请求 ===
        article_items = []
        for r in l2_results:
            art = r["article"]
            article_items.append({
                "url": art.url,
                "url_hash": art.url_hash,
                "source_code": art.source_code,
                "title": art.title,
                "author": art.author,
                "publish_time": art.publish_time.isoformat() if art.publish_time else None,
                "crawl_time": art.crawl_time.isoformat(),
                "raw_summary": art.raw_summary,
                "full_content": art.raw_html or art.raw_summary,  # L3 获取的全文，无 raw_html 时回退到 raw_summary
                "content_hash": art.content_hash,
            })

        analysis_items = []
        for r in l2_results:
            a = r["analysis"]
            analysis_items.append({
                "article_url_hash": r["article"].url_hash,
                "source_language": a.get("source_language", "unknown"),
                "title_cn": a.get("title_cn", r["article"].title),
                "summary_cn": a["summary_cn"],
                "category": a["category"],
                "keywords": a["keywords"] if isinstance(a["keywords"], list) else [],
                "tech_tags": a["tech_tags"] if isinstance(a["tech_tags"], list) else [],
                "companies": a["companies"] if isinstance(a["companies"], list) else [],
                "standard_terms": a.get("standard_terms", []),
                "score_tech_depth": a["score_tech_depth"],
                "score_engineering": a["score_engineering"],
                "score_trend": a["score_trend"],
                "score_credibility": a["score_credibility"],
                "score_timeliness": a["score_timeliness"],
                "value_score": a["value_score"],
                "model_name": a["model_name"],
                "prompt_version": a["prompt_version"],
            })

        insight_items = []
        for r in l3_results:
            ins = r["insight"]
            insight_items.append({
                "article_url_hash": r["article"].url_hash,
                "technical_background": ins["technical_background"],
                "core_problem": ins["core_problem"],
                "technical_solution": ins["technical_solution"],
                "impact_analysis": ins["impact_analysis"],
                "reference_value": ins["reference_value"],
                "model_name": ins["model_name"],
                "prompt_version": ins["prompt_version"],
            })

        payload = self.importer.build_payload(
            batch_no=batch_no,
            task_type=task_type,
            source_scope=[s["code"] for s in data_sources],
            articles=article_items,
            analyses=analysis_items,
            insights=insight_items,
        )

        # === 受控导入 ===
        import_result = self.importer.import_batch(payload)
        stats["import"]["status"] = "success" if import_result.get("success") else "failed"
        if import_result.get("error"):
            stats["import"]["error"] = import_result["error"]
        if not import_result.get("success"):
            stats["import"]["retry_files"] = self._persist_failed_import_payload(
                payload,
                import_result,
                stats,
            )

        elapsed = time.time() - start_time
        stats["elapsed_seconds"] = round(elapsed, 1)

        logger.info("====== 采集分析任务完成 ======")
        logger.info("batch_no=%s, elapsed=%.1fs, stats=%s",
                     batch_no, elapsed,
                     json.dumps(stats, ensure_ascii=False, default=str))

        return stats


def handle_collect_job(params: str = None) -> Dict[str, Any]:
    """
    XXL-Job JobHandler: aiRadarCollectJob

    入参：
        params: 调度参数 JSON 字符串，如 {"scope":"all"}
    出参：执行统计字典
    """
    scope = "all"
    sources = None
    from_date = None
    to_date = None
    task_type = "scheduled"

    if params:
        try:
            ps = json.loads(params) if isinstance(params, str) else params
            scope = ps.get("scope", "all")
            sources = ps.get("sources")
            # sources 可能是逗号分隔字符串（来自 XXL-Job 调度参数或 HTTP 接口），统一转为 list
            if sources and isinstance(sources, str):
                sources = [s.strip() for s in sources.split(",") if s.strip()]
            from_date = ps.get("from_date") or ps.get("from")
            to_date = ps.get("to_date") or ps.get("to")
            task_type = ps.get("task_type", "scheduled")
        except json.JSONDecodeError:
            logger.warning("调度参数 JSON 解析失败: %s", params)

    config = AWSConfig()
    orchestrator = CollectOrchestrator(config)
    stats = orchestrator.run(
        scope=scope,
        sources=sources,
        from_date=from_date,
        to_date=to_date,
        task_type=task_type,
    )
    return stats
