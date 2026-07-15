"""

受控导入接口

POST /api/v1/radar/import

接收亚马逊云侧加工的结构化成果，完成：

- 参数校验与幂等判断

- MySQL 写入（业务数据与批次运营统计）

- Markdown 文件生成

- EIPLite 知识库上传（待集成）

- kb_mapping 回写

"""

import json

import hashlib

import os

import logging

from datetime import datetime

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException

from pydantic import BaseModel, Field, validator

from db.models import (

    get_session, Source, ImportBatch, Article, ArticleAnalysis,

    DeepInsight, BriefingDraft, KbMapping, PipelineOperation

)

from config import InternalConfig

logger = logging.getLogger("import_api")

router = APIRouter()

# === Pydantic 请求模型（与 AWS 侧约定对齐） ===

class BatchInfo(BaseModel):

    """批次元数据"""

    batch_no: str = Field(..., description="批次号，唯一标识")

    task_type: str = Field("scheduled", description="scheduled / manual_backfill")

    source_scope: Optional[List[str]] = Field(None, description="本次涉及数据源编码列表")

class ArticleItem(BaseModel):

    """文章导入项"""

    url: str = Field(..., description="原文链接")

    source_code: str = Field(..., description="数据源编码，用于匹配 source_id")

    url_hash: str = Field(..., description="URL SHA-256 哈希")

    title: str = Field(..., description="原始标题")

    author: Optional[str] = Field(None, description="作者")

    publish_time: Optional[str] = Field(None, description="发布时间 ISO 8601")

    crawl_time: Optional[str] = Field(None, description="抓取时间 ISO 8601")

    raw_summary: Optional[str] = Field(None, description="原文摘要")

    full_content: Optional[str] = Field(None, description="完整原文")

    content_hash: Optional[str] = Field(None, description="内容 SHA-256 指纹")

class AnalysisItem(BaseModel):

    """分析结果导入项"""

    article_url_hash: str = Field(..., description="关联文章的 url_hash")

    source_language: Optional[str] = Field("unknown", description="原文语言：en / zh / mixed / unknown")

    title_cn: Optional[str] = Field(None, description="中文标题")

    summary_cn: str = Field(..., description="中文摘要")

    category: Optional[str] = Field(None, description="资讯一级分类")

    sub_category: Optional[str] = Field(None, description="资讯子分类")

    info_type: Optional[str] = Field(None, description="资讯类型")

    briefing_focus: Optional[str] = Field(None, description="简报表达重点")

    analysis_detail: Optional[Dict[str, Any]] = Field(None, description="结构化分析详情")

    keywords: Optional[List[str]] = Field(None, description="关键词列表")

    tech_tags: Optional[List[str]] = Field(None, description="技术标签")

    companies: Optional[List[str]] = Field(None, description="涉及厂商")

    standard_terms: Optional[List[Dict[str, Any]]] = Field(None, description="标准术语映射")

    score_tech_depth: Optional[float] = Field(None, ge=1.0, le=10.0, description="技术深度")

    score_engineering: Optional[float] = Field(None, ge=1.0, le=10.0, description="工程参考价值")

    score_trend: Optional[float] = Field(None, ge=1.0, le=10.0, description="趋势重要性")

    score_credibility: Optional[float] = Field(None, ge=1.0, le=10.0, description="来源可信度")

    score_timeliness: Optional[float] = Field(None, ge=1.0, le=10.0, description="时效性")

    value_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="综合价值评分")

    model_name: Optional[str] = Field(None, description="调用模型")

    prompt_version: Optional[str] = Field(None, description="Prompt 版本")

class InsightItem(BaseModel):

    """深度洞察导入项"""

    article_url_hash: str = Field(..., description="关联文章的 url_hash")

    technical_background: str = Field(..., description="技术背景")

    core_problem: str = Field(..., description="核心问题")

    technical_solution: str = Field(..., description="技术方案")

    impact_analysis: Optional[str] = Field(None, description="影响分析")

    reference_value: Optional[str] = Field(None, description="内部参考价值")

    model_name: Optional[str] = Field(None, description="调用模型")

    prompt_version: Optional[str] = Field(None, description="Prompt 版本")


class OperationMetrics(BaseModel):

    """单次采集分析批次的阶段运营统计"""

    batch_time: Optional[str] = Field(None, description="采集批次时间 ISO 8601")
    l1_article_count: int = Field(0, ge=0, description="L1 候选文章数")
    l1_source_distribution: Dict[str, int] = Field(default_factory=dict)
    l2_article_count: int = Field(0, ge=0, description="L2 筛选后文章数")
    l2_source_distribution: Dict[str, int] = Field(default_factory=dict)
    l2_category_distribution: Dict[str, int] = Field(default_factory=dict)
    l3_article_count: int = Field(0, ge=0, description="L3 入选文章数")
    l3_source_distribution: Dict[str, int] = Field(default_factory=dict)
    l3_category_distribution: Dict[str, int] = Field(default_factory=dict)
    stage_detail: Dict[str, Any] = Field(default_factory=dict)


class ImportRequest(BaseModel):

    """受控导入请求体"""

    batch: BatchInfo

    articles: Optional[List[ArticleItem]] = Field(default_factory=list)

    analyses: Optional[List[AnalysisItem]] = Field(default_factory=list)

    insights: Optional[List[InsightItem]] = Field(default_factory=list)

    operation_metrics: Optional[OperationMetrics] = Field(
        None, description="可选的 L1/L2/L3 阶段运营统计"
    )

    @validator("batch")

    def validate_batch_no(cls, v):

        """校验 batch_no 不为空"""

        if not v.batch_no or not v.batch_no.strip():

            raise ValueError("batch_no 不能为空")

        return v

# === 响应模型 ===

def build_ok_response(data: Dict) -> Dict:

    """构建成功响应"""

    return {"code": 0, "message": "ok", "data": data}

def build_error_response(code: int, message: str, detail: Optional[str] = None):

    """构建错误响应，通过 HTTPException 抛出"""

    content = {"code": code, "message": message}

    if detail:

        content["detail"] = detail

    raise HTTPException(status_code=code, detail=content)

# === 核心导入逻辑 ===

def _parse_iso(s: Optional[str]) -> Optional[datetime]:

    """将 ISO 8601 字符串解析为 datetime，失败返回 None"""

    if not s:

        return None

    try:

        # 兼容 Z 后缀和时区

        s = s.replace("Z", "+00:00")

        if "+" in s or "T" in s:

            from datetime import timezone

            dt = datetime.fromisoformat(s)

            return dt.replace(tzinfo=None)  # MySQL 不存时区

        return datetime.fromisoformat(s)

    except (ValueError, TypeError):

        return None

@router.post("/api/v1/radar/import")

async def handle_import(request: Request, body: ImportRequest):

    """

    受控导入接口

    入参：

        body: ImportRequest，含 batch / articles / analyses / insights

    出参：{"code": 0, "message": "ok", "data": {...}}

    幂等规则：

        - batch_no 已存在且成功 → 直接返回 200

        - url_hash 唯一索引去重

        - 同一 url_hash + 新 prompt_version → 覆盖更新分析结果

    """

    logger.info("收到导入请求: batch_no=%s, articles=%d, analyses=%d, insights=%d",

                body.batch.batch_no,

                len(body.articles),

                len(body.analyses),

                len(body.insights))

    session = get_session()

    try:

        # 1. 幂等检查 — batch 级别

        existing = session.query(ImportBatch).filter(

            ImportBatch.batch_no == body.batch.batch_no

        ).first()

        if existing and existing.import_status == "success":

            session.close()

            return build_ok_response({

                "batch_no": body.batch.batch_no,

                "import_status": "success",

                "note": "batch_already_exists",

            })

        # 2. 创建或更新批次记录

        if existing:

            batch = existing

            batch.article_count = len(body.articles)

            batch.source_scope = json.dumps(body.batch.source_scope or [])

        else:

            batch = ImportBatch(

                batch_no=body.batch.batch_no,

                task_type=body.batch.task_type,

                source_scope=json.dumps(body.batch.source_scope or []),

                article_count=len(body.articles),

            )

            session.add(batch)

        session.flush()  # 获取 batch.id

        # 2.1 写入阶段运营统计；可选字段保证旧版导入请求继续兼容。
        if body.operation_metrics:
            metrics = body.operation_metrics
            operation = session.query(PipelineOperation).filter(
                PipelineOperation.batch_no == body.batch.batch_no
            ).first()
            if operation is None:
                operation = PipelineOperation(
                    import_batch_id=batch.id,
                    batch_no=body.batch.batch_no,
                    batch_time=_parse_iso(metrics.batch_time) or datetime.now(),
                )
                session.add(operation)
            operation.import_batch_id = batch.id
            operation.batch_time = _parse_iso(metrics.batch_time) or operation.batch_time
            operation.l1_article_count = metrics.l1_article_count
            operation.l1_source_distribution = metrics.l1_source_distribution
            operation.l2_article_count = metrics.l2_article_count
            operation.l2_source_distribution = metrics.l2_source_distribution
            operation.l2_category_distribution = metrics.l2_category_distribution
            operation.l3_article_count = metrics.l3_article_count
            operation.l3_source_distribution = metrics.l3_source_distribution
            operation.l3_category_distribution = metrics.l3_category_distribution
            operation.stage_detail = metrics.stage_detail

        # 3. 写入 articles

        imported_articles = []

        failed_items = []

        url_hash_to_article_id = {}  # 供 analysis/insight 追溯

        for item in body.articles:

            try:

                # 去重检查

                existing_article = session.query(Article).filter(

                    Article.url_hash == item.url_hash

                ).first()

                if existing_article:

                    url_hash_to_article_id[item.url_hash] = existing_article.id

                    imported_articles.append({

                        "url_hash": item.url_hash,

                        "mysql_id": existing_article.id,

                        "status": "duplicate_skipped",

                    })

                    continue

                # 按 source_code 查找 source_id

                source_id = 1  # 默认兜底

                if item.source_code:

                    src = session.query(Source).filter(

                        Source.source_code == item.source_code

                    ).first()

                    if src:

                        source_id = src.id

                article = Article(

                    source_id=source_id,

                    title=item.title,

                    url=item.url,

                    url_hash=item.url_hash,

                    author=item.author,

                    publish_time=_parse_iso(item.publish_time),

                    crawl_time=_parse_iso(item.crawl_time),

                    raw_summary=item.raw_summary,

                    full_content=item.full_content,

                    content_hash=item.content_hash,

                    import_batch_id=batch.id,

                )

                session.add(article)

                session.flush()

                url_hash_to_article_id[item.url_hash] = article.id

                imported_articles.append({

                    "url_hash": item.url_hash,

                    "mysql_id": article.id,

                    "status": "imported",

                })

            except Exception as e:

                logger.warning("文章写入失败: url_hash=%s, %s", item.url_hash, str(e))

                failed_items.append({

                    "url_hash": item.url_hash,

                    "reason": "article_write_error",

                    "detail": str(e),

                })

        # 4. 写入 analyses

        for item in body.analyses:

            article_id = url_hash_to_article_id.get(item.article_url_hash)

            if not article_id:

                failed_items.append({

                    "article_url_hash": item.article_url_hash,

                    "reason": "article_not_found",

                    "detail": "article 未入库，analysis 跳过",

                })

                continue

            try:

                analysis_values = {
                    "summary_cn": item.summary_cn,
                    "category": item.category,
                    "sub_category": item.sub_category,
                    "info_type": item.info_type,
                    "briefing_focus": item.briefing_focus,
                    "analysis_detail": item.analysis_detail,
                    "keywords": ",".join(item.keywords) if item.keywords else None,
                    "tech_tags": item.tech_tags or None,
                    "companies": item.companies or None,
                    "score_tech_depth": item.score_tech_depth,
                    "score_engineering": item.score_engineering,
                    "score_trend": item.score_trend,
                    "score_credibility": item.score_credibility,
                    "score_timeliness": item.score_timeliness,
                    "value_score": item.value_score,
                    "model_name": item.model_name,
                    "prompt_version": item.prompt_version,
                    "analysis_status": "success",
                }
                analysis = session.query(ArticleAnalysis).filter(
                    ArticleAnalysis.article_id == article_id
                ).first()
                if analysis is None:
                    analysis = ArticleAnalysis(article_id=article_id, **analysis_values)
                    session.add(analysis)
                else:
                    for field, value in analysis_values.items():
                        setattr(analysis, field, value)

            except Exception as e:

                logger.error("分析结果写入失败: url_hash=%s, %s", item.article_url_hash, str(e))

                failed_items.append({

                    "article_url_hash": item.article_url_hash,

                    "reason": "analysis_write_error",

                    "detail": str(e),

                })

        # 5. 写入 insights

        for item in body.insights:

            article_id = url_hash_to_article_id.get(item.article_url_hash)

            if not article_id:

                failed_items.append({

                    "article_url_hash": item.article_url_hash,

                    "reason": "article_not_found",

                    "detail": "article 未入库，insight 跳过",

                })

                continue

            try:

                insight_values = {
                    "technical_background": item.technical_background,
                    "core_problem": item.core_problem,
                    "technical_solution": item.technical_solution,
                    "impact_analysis": item.impact_analysis,
                    "reference_value": item.reference_value,
                    "model_name": item.model_name,
                    "prompt_version": item.prompt_version,
                    "analysis_status": "success",
                }
                insight = session.query(DeepInsight).filter(
                    DeepInsight.article_id == article_id
                ).first()
                if insight is None:
                    insight = DeepInsight(article_id=article_id, **insight_values)
                    session.add(insight)
                else:
                    for field, value in insight_values.items():
                        setattr(insight, field, value)

            except Exception as e:

                logger.error("洞察写入失败: url_hash=%s, %s", item.article_url_hash, str(e))

                failed_items.append({

                    "article_url_hash": item.article_url_hash,

                    "reason": "insight_write_error",

                    "detail": str(e),

                })

        # 6. 计算导入统计

        success_count = len(imported_articles)

        failed_count = len(failed_items)

        batch.import_status = (

            "success" if failed_count == 0

            else "partial_success" if success_count > 0

            else "failed"

        )

        batch.success_count = success_count

        batch.failed_count = failed_count

        if failed_items:

            batch.error_summary = json.dumps(failed_items[:50])  # 最多保留前 50 条错误

        session.commit()

        # 7. 知识库上传（失败不阻塞导入）

        kb_stats = {"attempted": 0, "success": 0, "failed": 0}

        try:

            dataset_id = os.environ.get("EIPLITE_KB_DATASET_ID", "")

            if dataset_id:

                from kb.kb_client import create_kb_client

                from kb.markdown_gen import generate_article_summary, generate_deep_insight

                kb_client = create_kb_client()

                for item in body.articles:

                    article_id = url_hash_to_article_id.get(item.url_hash)

                    if not article_id:

                        continue

                    try:

                        matched = None

                        for a in body.analyses:

                            if a.article_url_hash == item.url_hash:

                                matched = a

                                break

                        src_name = item.source_code or "unknown"

                        md = generate_article_summary(

                            title=item.title, source_name=src_name, url=item.url,

                            title_cn=matched.title_cn if matched else "",

                            source_language=matched.source_language if matched else "unknown",

                            summary_cn=matched.summary_cn if matched else "",

                            sub_category=matched.sub_category if matched else "",

                            info_type=matched.info_type if matched else "",

                            briefing_focus=matched.briefing_focus if matched else "",

                            analysis_detail=matched.analysis_detail if matched else {},

                            standard_terms=matched.standard_terms if matched else [],

                            raw_summary=item.raw_summary or "",
                            full_content=item.full_content or "",

                            category=matched.category if matched else None,

                            author=item.author, publish_time=item.publish_time,

                            value_score=matched.value_score if matched else None,

                        )

                        standard_terms = matched.standard_terms if matched else []

                        term_tags = []

                        for term in standard_terms or []:

                            if isinstance(term, dict):

                                label = term.get("term") or term.get("zh")

                                if label:

                                    term_tags.append(str(label))

                        tags = {
                            "source": src_name,
                            "source_name": src_name,
                            "category": matched.category if matched else "",
                            "sub_category": matched.sub_category if matched else "",
                            "info_type": matched.info_type if matched else "",
                            "lang": "mixed",
                            "source_language": matched.source_language if matched else "unknown",
                            "title": item.title,
                            "title_cn": matched.title_cn if matched else "",
                            "standard_terms": term_tags,
                            "kb_type": "article_summary",
                        }

                        fname = f"{item.url_hash[:16]}_{item.title[:30]}.md"

                        kb_stats["attempted"] += 1

                        kb_file_id = kb_client.upload_file(content=md, filename=fname)

                        if kb_file_id:

                            mapping = KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type="article_summary", tags=tags, created_at=datetime.now())

                            session.add(mapping)

                            kb_stats["success"] += 1

                        else:

                            kb_stats["failed"] += 1

                    except Exception as kbe:

                        logger.warning("KB upload fail: %s %s", item.url_hash, str(kbe))

                        kb_stats["failed"] += 1

        except Exception as kbi:

            logger.warning("KB upload init error: %s", str(kbi))

        # 7. 知识库上传（失败不阻塞导入）

        # 提交知识库映射记录（tags 在此持久化）

        if kb_stats["success"] > 0:
            session.commit()


        result = {

            "batch_no": batch.batch_no,

            "article_count": len(body.articles),

            "success_count": success_count,

            "failed_count": failed_count,

            "imported_articles": imported_articles[:100],  # 限制返回量

        }

        if failed_items:

            result["failed_items"] = failed_items[:20]

        logger.info("导入完成: batch_no=%s, status=%s, success=%d, failed=%d",

                     batch.batch_no, batch.import_status, success_count, failed_count)

        return build_ok_response(result)

    except HTTPException:

        session.rollback()

        raise

    except Exception as e:

        session.rollback()

        logger.exception("导入异常: batch_no=%s", body.batch.batch_no)

        # 判断是否为数据库连接错误

        if "connection" in str(e).lower() or "connect" in str(e).lower():

            raise HTTPException(status_code=503, detail={

                "code": 503, "message": "service_unavailable", "detail": "internal service error"

            })

        raise HTTPException(status_code=500, detail={

            "code": 500, "message": "internal_error", "detail": str(e)[:500]

        })

    finally:

        session.close()
