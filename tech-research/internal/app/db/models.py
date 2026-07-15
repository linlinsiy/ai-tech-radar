"""
内部侧 MySQL 连接与模型定义模块

使用 SQLAlchemy ORM 定义 8 张核心表的模型，
提供连接池管理和事务支持。
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, BigInteger, String, Text, DateTime,
    Integer, Numeric, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from config import InternalConfig

Base = declarative_base()


class Source(Base):
    """数据源主数据 - ai_radar_source"""
    __tablename__ = "ai_radar_source"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    source_code = Column(String(64), nullable=False, unique=True, comment="数据源编码")
    source_name = Column(String(128), nullable=False, comment="数据源名称")
    source_type = Column(String(64), comment="数据源分类")
    access_url = Column(String(512), comment="RSS/API/网页地址")
    domain = Column(String(128), comment="访问域名")
    enabled = Column(Integer, nullable=False, default=1, comment="是否启用")


class ImportBatch(Base):
    """导入批次 - ai_radar_import_batch"""
    __tablename__ = "ai_radar_import_batch"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    batch_no = Column(String(64), nullable=False, unique=True, comment="批次号")
    task_type = Column(String(64), comment="任务类型")
    source_scope = Column(String(512), comment="数据源列表 JSON")
    article_count = Column(Integer, nullable=False, default=0, comment="文章数量")
    success_count = Column(Integer, nullable=False, default=0, comment="成功数量")
    failed_count = Column(Integer, nullable=False, default=0, comment="失败数量")
    import_status = Column(String(32), nullable=False, default="pending", comment="导入状态")
    error_summary = Column(Text, comment="错误摘要")


class PipelineOperation(Base):
    """各采集分析阶段运营统计 - ai_radar_pipeline_operation"""
    __tablename__ = "ai_radar_pipeline_operation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    import_batch_id = Column(BigInteger, nullable=False, unique=True, comment="导入批次 ID")
    batch_no = Column(String(64), nullable=False, unique=True, comment="批次号")
    batch_time = Column(DateTime, nullable=False, comment="采集批次时间")
    l1_article_count = Column(Integer, nullable=False, default=0, comment="L1 候选文章数")
    l1_source_distribution = Column(JSON, comment="L1 来源数量分布")
    l2_article_count = Column(Integer, nullable=False, default=0, comment="L2 筛选后文章数")
    l2_source_distribution = Column(JSON, comment="L2 来源数量分布")
    l2_category_distribution = Column(JSON, comment="L2 分类数量分布")
    l3_article_count = Column(Integer, nullable=False, default=0, comment="L3 入选文章数")
    l3_source_distribution = Column(JSON, comment="L3 来源数量分布")
    l3_category_distribution = Column(JSON, comment="L3 分类数量分布")
    stage_detail = Column(JSON, comment="候选、补采、失败等扩展阶段指标")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class Article(Base):
    """外部文章 - ai_radar_article"""
    __tablename__ = "ai_radar_article"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    source_id = Column(BigInteger, nullable=False, comment="来源 ID")
    title = Column(String(512), nullable=False, comment="原始标题")
    url = Column(String(1024), nullable=False, comment="原文链接")
    url_hash = Column(String(64), nullable=False, unique=True, comment="URL SHA-256")
    author = Column(String(128), comment="作者")
    publish_time = Column(DateTime, comment="发布时间")
    crawl_time = Column(DateTime, comment="抓取时间")
    raw_summary = Column(Text, comment="原文摘要")
    full_content = Column(Text, comment="完整原文")
    content_hash = Column(String(64), comment="内容指纹")
    import_batch_id = Column(BigInteger, nullable=False, comment="导入批次 ID")


class ArticleAnalysis(Base):
    """文章分析结果 - ai_radar_article_analysis"""
    __tablename__ = "ai_radar_article_analysis"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    article_id = Column(BigInteger, nullable=False, unique=True, comment="文章 ID")
    summary_cn = Column(Text, nullable=False, comment="中文摘要")
    category = Column(String(128), comment="资讯一级分类")
    sub_category = Column(String(128), comment="资讯子分类")
    info_type = Column(String(64), comment="资讯类型")
    briefing_focus = Column(Text, comment="简报表达重点")
    analysis_detail = Column(JSON, comment="按资讯类型存放的结构化分析详情")
    keywords = Column(String(512), comment="关键词")
    tech_tags = Column(JSON, comment="技术标签")
    companies = Column(JSON, comment="涉及厂商")
    score_tech_depth = Column(Numeric(3, 1), comment="技术深度")
    score_engineering = Column(Numeric(3, 1), comment="工程参考价值")
    score_trend = Column(Numeric(3, 1), comment="趋势重要性")
    score_credibility = Column(Numeric(3, 1), comment="来源可信度")
    score_timeliness = Column(Numeric(3, 1), comment="时效性")
    value_score = Column(Numeric(4, 2), comment="综合价值评分")
    model_name = Column(String(128), comment="调用模型")
    prompt_version = Column(String(64), comment="Prompt 版本")
    analysis_status = Column(String(32), nullable=False, default="success", comment="分析状态")


class DeepInsight(Base):
    """深度洞察 - ai_radar_deep_insight"""
    __tablename__ = "ai_radar_deep_insight"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    article_id = Column(BigInteger, nullable=False, unique=True, comment="文章 ID")
    technical_background = Column(Text, nullable=False, comment="技术背景")
    core_problem = Column(Text, nullable=False, comment="核心问题")
    technical_solution = Column(Text, nullable=False, comment="技术方案")
    impact_analysis = Column(Text, comment="影响分析")
    reference_value = Column(Text, comment="内部参考价值")
    model_name = Column(String(128), comment="调用模型")
    prompt_version = Column(String(64), comment="Prompt 版本")
    analysis_status = Column(String(32), nullable=False, default="success", comment="分析状态")


class BriefingDraft(Base):
    """简报草稿 - ai_radar_briefing_draft"""
    __tablename__ = "ai_radar_briefing_draft"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    briefing_type = Column(String(32), nullable=False, comment="简报类型")
    title = Column(String(256), nullable=False, comment="简报标题")
    content = Column(Text, comment="简报正文")
    time_range_start = Column(DateTime, comment="覆盖时间开始")
    time_range_end = Column(DateTime, comment="覆盖时间结束")
    related_article_ids = Column(JSON, comment="关联文章 ID")
    related_insight_ids = Column(JSON, comment="关联洞察 ID")
    review_status = Column(String(32), nullable=False, default="pending", comment="审核状态")


class KbMapping(Base):
    """知识库文件映射 - ai_radar_kb_mapping"""
    __tablename__ = "ai_radar_kb_mapping"
    __table_args__ = (
        UniqueConstraint("kb_type", "kb_file_id", name="uk_kb_type_file_id"),
        Index("idx_article_id", "article_id"),
        Index("idx_insight_id", "insight_id"),
        Index("idx_briefing_id", "briefing_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    kb_type = Column(String(32), nullable=False, comment="入库内容类型")
    kb_file_id = Column(String(128), nullable=False, comment="EIPLite 文件 ID")
    article_id = Column(BigInteger, nullable=True, comment="关联文章 ID")
    analysis_id = Column(BigInteger, nullable=True, comment="关联分析 ID")
    insight_id = Column(BigInteger, nullable=True, comment="关联洞察 ID")
    briefing_id = Column(BigInteger, nullable=True, comment="关联简报 ID")
    kb_status = Column(String(32), nullable=False, default="success", comment="入库状态")
    error_message = Column(Text, comment="入库失败原因")
    tags = Column(JSON, comment="标签键值对")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


def get_engine():
    """
    创建 SQLAlchemy 数据库引擎

    出参：带连接池的 Engine 实例
    """
    cfg = InternalConfig.get_instance().mysql_config
    url = (
        f"mysql+pymysql://{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        f"?charset={cfg['charset']}"
    )
    return create_engine(
        url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        echo=False,
    )


def get_session():
    """
    获取数据库会话

    出参：SQLAlchemy Session 实例
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
