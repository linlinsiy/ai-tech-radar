-- ============================================================
-- AI技术趋势雷达 - 内部业务数据库 DDL
-- 数据库：ai_radar
-- 表数量：8
-- 生成日期：2026-06-12
-- ============================================================

-- ============================================================
-- 部署说明：
--   本 DDL 是参考脚本，记录完整表结构定义。
--   实际部署位置：ysdjg 库（10.102.37.253:8880）
--   表名前缀 ai_radar_ 保证在共享 ysdjg 库中命名空间隔离。
--   执行时去掉 CREATE DATABASE / USE 语句，直接在 ysdjg 库中建表。
-- ============================================================

-- ============================================================
-- 1. ai_radar_source - 数据源主数据
-- 记录外部资讯来源，用于追溯文章来源和统计数据源质量
-- ============================================================
DROP TABLE IF EXISTS ai_radar_source;
CREATE TABLE ai_radar_source (
  id            BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  source_code   VARCHAR(64)     NOT NULL                 COMMENT '数据源编码，唯一标识，如 aws-ml-blog、arxiv-cs-ai',
  source_name   VARCHAR(128)    NOT NULL                 COMMENT '数据源名称，如 AWS ML Blog',
  source_type   VARCHAR(64)                             COMMENT '数据源分类：tech_media / vendor_blog / academic / tech_community / research_institute',
  access_url    VARCHAR(512)                            COMMENT 'RSS / API / 网页地址',
  domain        VARCHAR(128)                            COMMENT '访问域名',
  enabled       TINYINT         NOT NULL DEFAULT 1       COMMENT '是否启用：1=启用，0=停用',
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE INDEX uk_source_code (source_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据源主数据';

-- ============================================================
-- 2. ai_radar_import_batch - 导入批次
-- 记录每次从亚马逊云侧导入内部的数据批次，用于追溯和排障
-- 注：先于 article 表创建，因 article 依赖其外键
-- ============================================================
DROP TABLE IF EXISTS ai_radar_import_batch;
CREATE TABLE ai_radar_import_batch (
  id              BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  batch_no        VARCHAR(64)     NOT NULL                 COMMENT '批次号，唯一，如 IMP-20260612-001',
  task_type       VARCHAR(64)                             COMMENT '任务类型：scheduled / manual_backfill / rerun',
  source_scope    VARCHAR(512)                            COMMENT '本次涉及数据源列表，JSON 数组格式',
  article_count   INT             NOT NULL DEFAULT 0       COMMENT '导入文章数量',
  success_count   INT             NOT NULL DEFAULT 0       COMMENT '成功导入数量',
  failed_count    INT             NOT NULL DEFAULT 0       COMMENT '失败数量',
  import_status   VARCHAR(32)     NOT NULL DEFAULT 'pending' COMMENT '导入状态：pending / success / partial_success / failed',
  error_summary   TEXT                                    COMMENT '错误摘要',
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE INDEX uk_batch_no (batch_no),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='导入批次';

-- ============================================================
-- 3. ai_radar_pipeline_operation - 采集分析运营过程
-- 每个批次一行，记录 L1/L2/L3 数量及来源、分类分布
-- ============================================================
DROP TABLE IF EXISTS ai_radar_pipeline_operation;
CREATE TABLE ai_radar_pipeline_operation (
  id                        BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  import_batch_id           BIGINT      NOT NULL                COMMENT '导入批次 ID',
  batch_no                  VARCHAR(64) NOT NULL                COMMENT '采集批次号',
  batch_time                DATETIME    NOT NULL                COMMENT '采集批次时间',
  l1_article_count          INT         NOT NULL DEFAULT 0      COMMENT 'L1 候选文章数',
  l1_source_distribution    JSON                                COMMENT 'L1 来源数量分布',
  l2_article_count          INT         NOT NULL DEFAULT 0      COMMENT 'L2 筛选后文章数',
  l2_source_distribution    JSON                                COMMENT 'L2 来源数量分布',
  l2_category_distribution  JSON                                COMMENT 'L2 分类数量分布',
  l3_article_count          INT         NOT NULL DEFAULT 0      COMMENT 'L3 入选文章数',
  l3_source_distribution    JSON                                COMMENT 'L3 来源数量分布',
  l3_category_distribution  JSON                                COMMENT 'L3 分类数量分布',
  stage_detail              JSON                                COMMENT '候选、补采、失败等扩展阶段指标',
  created_at                DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at                DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE INDEX uk_pipeline_batch_no (batch_no),
  UNIQUE INDEX uk_pipeline_import_batch_id (import_batch_id),
  INDEX idx_pipeline_batch_time (batch_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采集分析运营过程';

-- ============================================================
-- 4. ai_radar_article - 外部文章基础信息
-- 记录采集到的外部文章基础信息，幂等去重依赖 url_hash 和 content_hash
-- ============================================================
DROP TABLE IF EXISTS ai_radar_article;
CREATE TABLE ai_radar_article (
  id              BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  source_id       BIGINT          NOT NULL                 COMMENT '来源 ID，关联 ai_radar_source.id',
  title           VARCHAR(512)    NOT NULL                 COMMENT '原始标题',
  url             VARCHAR(1024)   NOT NULL                 COMMENT '原文链接',
  url_hash        CHAR(64)        NOT NULL                 COMMENT 'URL SHA-256 哈希，用于去重',
  author          VARCHAR(128)                             COMMENT '作者',
  publish_time    DATETIME                                COMMENT '原文发布时间',
  crawl_time      DATETIME                                COMMENT '抓取时间',
  raw_summary     TEXT                                    COMMENT '原文摘要或 RSS 自带摘要',
  full_content    LONGTEXT        NULL                    COMMENT '文章完整原文，仅对触发 L3 深度分析的文章填充',
  content_hash    CHAR(64)                                COMMENT '内容 SHA-256 指纹，用于内容级去重',
  import_batch_id BIGINT          NOT NULL                 COMMENT '导入批次 ID，关联 ai_radar_import_batch.id',
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE INDEX uk_url_hash (url_hash),
  INDEX idx_source_id (source_id),
  INDEX idx_import_batch_id (import_batch_id),
  INDEX idx_publish_time (publish_time),
  INDEX idx_content_hash (content_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='外部文章基础信息';

-- ============================================================
-- 5. ai_radar_article_analysis - 文章分析结果
-- 记录模型生成的摘要、分类、标签、评分等结构化分析结果
-- ============================================================
DROP TABLE IF EXISTS ai_radar_article_analysis;
CREATE TABLE ai_radar_article_analysis (
  id                  BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  article_id          BIGINT          NOT NULL                 COMMENT '文章 ID，关联 ai_radar_article.id',
  summary_cn          TEXT            NOT NULL                 COMMENT '中文摘要，150-300 字',
  category            VARCHAR(128)                            COMMENT '技术分类：大语言模型 / 推理优化 / AI Agent / 多模态 / 训练与微调 / 部署与推理 / 数据与评测 / 安全与对齐 / RAG与检索 / 其他',
  keywords            VARCHAR(512)                            COMMENT '关键词，逗号分隔，3-5 个',
  tech_tags           JSON                                    COMMENT '技术标签数组，如 ["LLM Inference", "FlashAttention"]',
  companies           JSON                                    COMMENT '涉及厂商数组，如 ["NVIDIA", "Meta"]',
  score_tech_depth    DECIMAL(3,1)                            COMMENT '技术深度评分，1.0-10.0',
  score_engineering   DECIMAL(3,1)                            COMMENT '工程参考价值评分，1.0-10.0',
  score_trend         DECIMAL(3,1)                            COMMENT '趋势重要性评分，1.0-10.0',
  score_credibility   DECIMAL(3,1)                            COMMENT '来源可信度评分，1.0-10.0',
  score_timeliness    DECIMAL(3,1)                            COMMENT '时效性评分，1.0-10.0',
  value_score         DECIMAL(4,2)                            COMMENT '综合价值评分，五项维度平均值',
  model_name          VARCHAR(128)                            COMMENT '调用模型，如 gpt-4o-mini / gpt-4o',
  prompt_version      VARCHAR(64)                             COMMENT 'Prompt 版本，如 v2.1',
  analysis_status     VARCHAR(32)     NOT NULL DEFAULT 'success' COMMENT '分析状态：success / failed',
  created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  INDEX idx_article_id (article_id),
  INDEX idx_category (category),
  INDEX idx_value_score (value_score),
  INDEX idx_prompt_version (prompt_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章分析结果';

-- ============================================================
-- 6. ai_radar_deep_insight - 深度洞察
-- 仅对高价值文章（value_score >= 7 且有 full_content）生成
-- 用于入知识库和简报复用
-- ============================================================
DROP TABLE IF EXISTS ai_radar_deep_insight;
CREATE TABLE ai_radar_deep_insight (
  id                  BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  article_id          BIGINT          NOT NULL                 COMMENT '文章 ID，关联 ai_radar_article.id',
  technical_background TEXT          NOT NULL                  COMMENT '技术背景：领域背景知识、前置技术、发展脉络',
  core_problem        TEXT            NOT NULL                 COMMENT '核心问题：文章试图解决的具体问题或挑战',
  technical_solution  TEXT            NOT NULL                 COMMENT '技术方案：核心思路、关键技术决策、实现方法',
  impact_analysis     TEXT                                    COMMENT '影响分析：可能带来的行业影响、技术栈变化',
  reference_value     TEXT                                    COMMENT '内部参考价值：对公司技术团队的参考意义和可借鉴之处',
  model_name          VARCHAR(128)                            COMMENT '调用模型，如 gpt-4o',
  prompt_version      VARCHAR(64)                             COMMENT 'Prompt 版本，如 v2.1',
  analysis_status     VARCHAR(32)     NOT NULL DEFAULT 'success' COMMENT '分析状态：success / failed',
  created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  INDEX idx_article_id (article_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='深度洞察';

-- ============================================================
-- 7. ai_radar_briefing_draft - 简报草稿
-- 保存系统生成的周报、月报、专题报告草稿元数据
-- 正文仅存入 EIPLite 知识库，MySQL 不存储正文
-- ============================================================
DROP TABLE IF EXISTS ai_radar_briefing_draft;
CREATE TABLE ai_radar_briefing_draft (
  id                  BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  briefing_type       VARCHAR(32)     NOT NULL                 COMMENT '简报类型：weekly / monthly / topic',
  title               VARCHAR(256)    NOT NULL                 COMMENT '简报标题',
  time_range_start    DATE                                    COMMENT '覆盖时间开始',
  time_range_end      DATE                                    COMMENT '覆盖时间结束',
  related_article_ids JSON                                    COMMENT '关联文章 ID 列表',
  related_insight_ids JSON                                    COMMENT '关联洞察 ID 列表',
  review_status       VARCHAR(32)     NOT NULL DEFAULT 'pending' COMMENT '审核状态：pending / reviewed',
  created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  INDEX idx_briefing_type (briefing_type),
  INDEX idx_time_range_start (time_range_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='简报草稿';

-- ============================================================
-- 8. ai_radar_kb_mapping - 知识库文件映射
-- 记录 MySQL 业务记录与 EIPLite 知识库文件的对应关系
-- 用于排障、溯源和重新入库
-- ============================================================
DROP TABLE IF EXISTS ai_radar_kb_mapping;
CREATE TABLE ai_radar_kb_mapping (
  id              BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '主键',
  kb_type         VARCHAR(32)     NOT NULL                 COMMENT '入库内容类型：article_summary / deep_insight / briefing',
  kb_file_id      VARCHAR(128)    NOT NULL                 COMMENT 'EIPLite 知识库返回的文件 ID',
  article_id      BIGINT          NULL                    COMMENT '关联 ai_radar_article.id（kb_type=article_summary 或 deep_insight 时填充）',
  analysis_id     BIGINT          NULL                    COMMENT '关联 ai_radar_article_analysis.id（kb_type=article_summary 时填充）',
  insight_id      BIGINT          NULL                    COMMENT '关联 ai_radar_deep_insight.id（kb_type=deep_insight 时填充）',
  briefing_id     BIGINT          NULL                    COMMENT '关联 ai_radar_briefing_draft.id（kb_type=briefing 时填充）',
  kb_status       VARCHAR(32)     NOT NULL DEFAULT 'success' COMMENT '入库状态：success / failed / updating',
  error_message   TEXT                                    COMMENT '入库失败原因',
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE INDEX uk_kb_type_file_id (kb_type, kb_file_id),
  INDEX idx_article_id (article_id),
  INDEX idx_insight_id (insight_id),
  INDEX idx_briefing_id (briefing_id),
  INDEX idx_kb_status (kb_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文件映射';

-- ============================================================
-- 初始化数据：12 个首期数据源
-- ============================================================
INSERT INTO ai_radar_source (source_code, source_name, source_type, access_url, domain, enabled) VALUES
('xin-zhi-yuan',     '新智元',          'tech_media',          NULL,                                   NULL,                  1),
('saibochangxin',    '赛博禅心',         'tech_media',          NULL,                                   NULL,                  1),
('zhidx',            '智东西',           'tech_media',          NULL,                                   NULL,                  1),
('jiqizhixin',       '机器之心',         'tech_media',          NULL,                                   NULL,                  1),
('liangziwei',       '量子位',           'tech_media',          'https://www.qbitai.com',               'www.qbitai.com',      1),
('tencent-research', '腾讯研究院',       'research_institute',  NULL,                                   NULL,                  1),
('aws-ml-blog',      'AWS ML Blog',      'vendor_blog',         'https://aws.amazon.com/blogs/machine-learning/feed/', 'aws.amazon.com', 1),
('netflix-techblog', 'Netflix TechBlog', 'vendor_blog',         'https://netflixtechblog.com/feed/',    'netflixtechblog.com', 1),
('infoq-ai-ml',      'InfoQ AI/ML',      'tech_media',          'https://www.infoq.com/feed/',          'www.infoq.com',       1),
('hackernews',       'Hacker News',      'tech_community',      'https://news.ycombinator.com/rss',     'news.ycombinator.com', 1),
('huggingface',      'HuggingFace Blog', 'vendor_blog',         'https://huggingface.co/blog/feed.xml', 'huggingface.co',      1),
('arxiv-cs-ai',      'arXiv cs.AI',      'academic',            'https://arxiv.org/rss/cs.AI',          'arxiv.org',           1);

ALTER TABLE ai_radar_article MODIFY COLUMN `raw_summary` TEXT COMMENT '原始摘要内容';
-- 如果需要存储更长内容可以用MEDIUMTEXT/LONGTEXT，足够存储万字以上内容
