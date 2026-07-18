-- AI技术趋势雷达数据库表结构
-- 版本: 2026-07-17
-- 用途: 重建数据库时的全量建库脚本。
-- 修改说明: 对齐当前 L1-L5 流程、统一 rank_score、来源选题角色和批次运营统计设计。

SET NAMES utf8mb4;
-- 2026-07-17 维护基线：本文件是重建数据库时的唯一执行入口。
-- 注意：下方 DROP TABLE 会删除并重建全部 ai_radar_* 表及初始化来源数据。
-- 后续表结构、索引和初始化数据变更均直接更新本文件，不再新增常规增量 SQL 文件。
-- 历史 ai_radar_alter_v*.sql 仅保留给已部署旧库的特定版本升级使用，不作为新建库入口。
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 文章原始数据表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_article`;
CREATE TABLE `ai_radar_article` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `source_id` bigint unsigned NOT NULL COMMENT '来源ID',
  `title` varchar(512) NOT NULL COMMENT '文章标题',
  `url` varchar(1024) NOT NULL COMMENT '原文链接',
  `url_hash` char(64) NOT NULL COMMENT 'URL SHA-256哈希',
  `author` varchar(128) DEFAULT NULL COMMENT '作者',
  `publish_time` datetime DEFAULT NULL COMMENT '发布时间',
  `crawl_time` datetime DEFAULT NULL COMMENT '抓取时间',
  `raw_summary` text COMMENT '原文摘要',
  `full_content` longtext COMMENT '完整原文',
  `content_hash` char(64) DEFAULT NULL COMMENT '内容指纹',
  `import_batch_id` bigint unsigned NOT NULL COMMENT '最近一次导入或重分析批次ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_url_hash` (`url_hash`),
  KEY `idx_source_id` (`source_id`),
  KEY `idx_import_batch_id` (`import_batch_id`),
  KEY `idx_publish_time` (`publish_time`),
  KEY `idx_content_hash` (`content_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章原始数据表';

-- ----------------------------
-- 文章L2分析结果表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_article_analysis`;
CREATE TABLE `ai_radar_article_analysis` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `article_id` bigint unsigned NOT NULL COMMENT '关联文章ID',
  `summary_cn` text NOT NULL COMMENT '中文摘要',
  `category` varchar(128) DEFAULT NULL COMMENT '资讯一级分类',
  `sub_category` varchar(128) DEFAULT NULL COMMENT '资讯子分类',
  `info_type` varchar(64) DEFAULT NULL COMMENT '资讯类型',
  `briefing_focus` text COMMENT '简报表达重点',
  `analysis_detail` json DEFAULT NULL COMMENT '按资讯类型存放的结构化分析详情',
  `keywords` varchar(512) DEFAULT NULL COMMENT '关键词',
  `tech_tags` json DEFAULT NULL COMMENT '技术标签',
  `companies` json DEFAULT NULL COMMENT '涉及厂商',
  `score_tech_depth` decimal(3,1) DEFAULT NULL COMMENT '技术深度',
  `score_engineering` decimal(3,1) DEFAULT NULL COMMENT '工程参考价值',
  `score_org_relevance` decimal(3,1) DEFAULT NULL COMMENT '券商技术岗位领域匹配度',
  `score_trend` decimal(3,1) DEFAULT NULL COMMENT '趋势重要性',
  `score_timeliness` decimal(3,1) DEFAULT NULL COMMENT '时效性',
  `value_score` decimal(4,2) DEFAULT NULL COMMENT '旧字段兼容，新批次与rank_score同值',
  `rank_score` decimal(4,2) DEFAULT NULL COMMENT '统一排序评分',
  `model_name` varchar(128) DEFAULT NULL COMMENT '调用模型',
  `prompt_version` varchar(64) DEFAULT NULL COMMENT 'Prompt版本',
  `analysis_status` varchar(32) NOT NULL DEFAULT 'success' COMMENT '分析状态',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_article_id` (`article_id`),
  KEY `idx_rank_score` (`rank_score`),
  KEY `idx_category` (`category`),
  KEY `idx_category_sub_category` (`category`, `sub_category`),
  KEY `idx_info_type` (`info_type`),
  KEY `idx_analysis_status` (`analysis_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章L2分析结果表';

-- ----------------------------
-- 深度洞察结果表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_deep_insight`;
CREATE TABLE `ai_radar_deep_insight` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `article_id` bigint unsigned NOT NULL COMMENT '关联文章ID',
  `technical_background` text NOT NULL COMMENT '技术背景',
  `core_problem` text NOT NULL COMMENT '核心问题',
  `technical_solution` text NOT NULL COMMENT '技术方案',
  `impact_analysis` text COMMENT '影响分析',
  `reference_value` text COMMENT '内部参考价值',
  `model_name` varchar(128) DEFAULT NULL COMMENT '调用模型',
  `prompt_version` varchar(64) DEFAULT NULL COMMENT 'Prompt版本',
  `analysis_status` varchar(32) NOT NULL DEFAULT 'success' COMMENT '分析状态',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_article_id` (`article_id`),
  KEY `idx_analysis_status` (`analysis_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='深度洞察结果表';

-- ----------------------------
-- 导入批次表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_import_batch`;
CREATE TABLE `ai_radar_import_batch` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `batch_no` varchar(64) NOT NULL COMMENT '批次号',
  `task_type` varchar(64) DEFAULT NULL COMMENT '任务类型',
  `source_scope` varchar(512) DEFAULT NULL COMMENT '数据源列表JSON',
  `article_count` int NOT NULL DEFAULT '0' COMMENT '文章数量',
  `success_count` int NOT NULL DEFAULT '0' COMMENT '成功数量',
  `failed_count` int NOT NULL DEFAULT '0' COMMENT '失败数量',
  `import_status` varchar(32) NOT NULL DEFAULT 'pending' COMMENT '导入状态',
  `error_summary` text COMMENT '错误摘要',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_batch_no` (`batch_no`),
  KEY `idx_import_status` (`import_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='导入批次表';

-- ----------------------------
-- 采集分析运营过程表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_pipeline_operation`;
CREATE TABLE `ai_radar_pipeline_operation` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `import_batch_id` bigint unsigned NOT NULL COMMENT '导入批次ID',
  `batch_no` varchar(64) NOT NULL COMMENT '采集批次号',
  `batch_time` datetime NOT NULL COMMENT '采集批次时间',
  `l1_article_count` int NOT NULL DEFAULT '0' COMMENT 'L1候选文章数',
  `l1_source_distribution` json DEFAULT NULL COMMENT 'L1来源数量分布',
  `l2_article_count` int NOT NULL DEFAULT '0' COMMENT 'L2筛选后文章数',
  `l2_source_distribution` json DEFAULT NULL COMMENT 'L2来源数量分布',
  `l2_category_distribution` json DEFAULT NULL COMMENT 'L2分类数量分布',
  `l3_article_count` int NOT NULL DEFAULT '0' COMMENT 'L3入选文章数',
  `l3_source_distribution` json DEFAULT NULL COMMENT 'L3来源数量分布',
  `l3_category_distribution` json DEFAULT NULL COMMENT 'L3分类数量分布',
  `stage_detail` json DEFAULT NULL COMMENT '候选补采失败等扩展阶段指标',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pipeline_batch_no` (`batch_no`),
  UNIQUE KEY `uk_pipeline_import_batch_id` (`import_batch_id`),
  KEY `idx_pipeline_batch_time` (`batch_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采集分析运营过程表';


-- ----------------------------
-- 简报草稿表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_briefing_draft`;
CREATE TABLE `ai_radar_briefing_draft` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `briefing_type` varchar(32) NOT NULL COMMENT '简报类型(weekly/monthly/quarterly/topic)',
  `title` varchar(256) NOT NULL COMMENT '简报标题',
  `content` longtext COMMENT '简报正文',
  `time_range_start` datetime DEFAULT NULL COMMENT '覆盖时间开始',
  `time_range_end` datetime DEFAULT NULL COMMENT '覆盖时间结束',
  `related_article_ids` json DEFAULT NULL COMMENT '关联文章ID列表',
  `related_insight_ids` json DEFAULT NULL COMMENT '关联洞察ID列表',
  `review_status` varchar(32) NOT NULL DEFAULT 'pending' COMMENT '审核状态(pending/passed/rejected)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_briefing_type` (`briefing_type`),
  KEY `idx_time_range` (`time_range_start`, `time_range_end`),
  KEY `idx_review_status` (`review_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='简报草稿表';

-- ----------------------------
-- 知识库映射表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_kb_mapping`;
CREATE TABLE `ai_radar_kb_mapping` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `kb_type` varchar(32) NOT NULL COMMENT '入库内容类型',
  `kb_file_id` varchar(128) NOT NULL COMMENT 'EIPLite文件ID',
  `article_id` bigint unsigned DEFAULT NULL COMMENT '关联文章ID',
  `analysis_id` bigint unsigned DEFAULT NULL COMMENT '关联分析ID',
  `insight_id` bigint unsigned DEFAULT NULL COMMENT '关联洞察ID',
  `briefing_id` bigint unsigned DEFAULT NULL COMMENT '关联简报ID',
  `kb_status` varchar(32) NOT NULL DEFAULT 'success' COMMENT '入库状态',
  `error_message` text COMMENT '入库失败原因',
  `tags` json DEFAULT NULL COMMENT '标签键值对',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_kb_type_file_id` (`kb_type`, `kb_file_id`),
  KEY `idx_article_id` (`article_id`),
  KEY `idx_analysis_id` (`analysis_id`),
  KEY `idx_insight_id` (`insight_id`),
  KEY `idx_briefing_id` (`briefing_id`),
  KEY `idx_kb_status` (`kb_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库映射表';


-- ============================================================
-- AI技术趋势雷达 - 数据源初始化 INSERT（32个全量验证版）
-- 时间: 2026-07-09 17:10
-- 表: ai_radar_source
-- * 所有 URL 均经 curl 200 验证通过
-- * OpenAI/DeepMind/HuggingFace/量子位 RSS 正文空，改用 web 采集
-- * 恒生电子 JS空壳，替换为零壹财经
-- ============================================================

-- ----------------------------
-- 数据源表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_source`;
CREATE TABLE `ai_radar_source` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `source_code` varchar(64) NOT NULL COMMENT '数据源编码',
  `source_name` varchar(128) NOT NULL COMMENT '数据源名称',
  `source_type` varchar(64) DEFAULT NULL COMMENT '数据源分类',
  `category` varchar(64) DEFAULT NULL COMMENT '数据源主题提示，仅辅助采集和L2判断，不代表文章最终分类',
  `selection_role` varchar(16) NOT NULL DEFAULT 'industry' COMMENT '来源分析角色（兼容字段，不参与选题）',
  `access_url` varchar(512) DEFAULT NULL COMMENT 'RSS/API/网页地址',
  `domain` varchar(128) DEFAULT NULL COMMENT '访问域名',
  `fetch_method` varchar(16) NOT NULL DEFAULT 'rss' COMMENT '采集方式(rss/web)',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `last_collect_time` datetime DEFAULT NULL COMMENT '最后采集时间',
  `last_collect_status` varchar(16) DEFAULT NULL COMMENT '最后采集状态(success/failed)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_source_code` (`source_code`),
  KEY `idx_category` (`category`),
  KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据源配置表';

INSERT INTO ai_radar_source (source_code, source_name, source_type, category, access_url, domain, fetch_method, enabled) VALUES

-- ============================================================================
-- 一、大模型基础技术（5个）
-- ============================================================================
('google-research',         'Google Research Blog',        'vendor_blog',  '大模型基础技术',  'http://googleresearch.blogspot.com/feeds/posts/default', 'googleresearch.blogspot.com', 'rss',  1),
('openai-blog',             'OpenAI Blog',                 'vendor_blog',  '大模型基础技术',  'https://openai.com/blog/rss.xml',                        'openai.com',                  'rss',  1),
('deepmind-blog',           'Google DeepMind Blog',        'vendor_blog',  '大模型基础技术',  'https://deepmind.google/blog/feed/',                      'deepmind.google',             'web',  1),
('bair-blog',               'BAIR Berkeley AI',            'academic',     '大模型基础技术',  'https://bair.berkeley.edu/blog/feed.xml',                 'bair.berkeley.edu',           'rss',  1),
('arxiv-cs-cl',             'arXiv cs.CL 计算语言学',       'academic',     '大模型基础技术',  'http://export.arxiv.org/rss/cs.CL',                       'export.arxiv.org',            'rss',  1),

-- ============================================================================
-- 二、Agent与智能体（3个）
-- ============================================================================
('langchain-blog',          'LangChain Blog',              'vendor_blog',  'Agent与智能体',   'https://blog.langchain.dev/rss.xml',                      'blog.langchain.dev',          'rss',  1),
('meta-eng',                'Meta Engineering Blog',       'vendor_blog',  'Agent与智能体',   'https://engineering.fb.com/feed/',                        'engineering.fb.com',          'rss',  1),
('aws-ml-blog',             'AWS ML Blog',                 'vendor_blog',  'Agent与智能体',   'https://aws.amazon.com/blogs/machine-learning/feed/',     'aws.amazon.com',              'rss',  1),

-- ============================================================================
-- 三、多模态技术（3个）
-- ============================================================================
('huggingface-blog',        'HuggingFace Blog',            'vendor_blog',  '多模态技术',      'https://huggingface.co/blog/feed.xml',                    'huggingface.co',              'web',  1),
('roboflow-blog',           'Roboflow CV Blog',            'tech_media',   '多模态技术',      'https://blog.roboflow.com/rss/',                          'blog.roboflow.com',           'rss',  1),
('pyimagesearch',           'PyImageSearch',               'tech_media',   '多模态技术',      'https://pyimagesearch.com/feed/',                         'pyimagesearch.com',           'rss',  1),

-- ============================================================================
-- 四、AI基础设施（3个）
-- ============================================================================
('nvidia-dev',              'NVIDIA Developer Blog',       'vendor_blog',  'AI基础设施',      'https://developer.nvidia.com/blog/feed/',                 'developer.nvidia.com',        'rss',  1),
('infoq-en',                'InfoQ AI/ML（英文）',         'tech_media',   'AI基础设施',      'https://feed.infoq.com/ai-ml-data-eng/news',              'feed.infoq.com',              'rss',  1),
('aliyun-ai-dev',           '阿里云AI开发者社区',           'vendor_blog',  'AI基础设施',      'https://developer.aliyun.com/group/ai',                   'developer.aliyun.com',        'web',  1),

-- ============================================================================
-- 五、生成式AI应用（2个）
-- ============================================================================
('last-week-in-ai',         'Last Week in AI',             'tech_media',   '生成式AI应用',    'https://lastweekin.ai/feed/',                             'lastweekin.ai',               'rss',  1),
('importai',                'Import AI（周报）',           'tech_media',   '生成式AI应用',    'https://importai.substack.com/feed',                      'importai.substack.com',       'rss',  1),

-- ============================================================================
-- 六、安全与伦理（2个）
-- ============================================================================
('lesswrong',               'LessWrong（AI Alignment）',   'academic',     '安全与伦理',      'https://www.lesswrong.com/feed.xml',                      'www.lesswrong.com',           'rss',  1),
('alignment-forum',         'AI Alignment Forum',          'academic',     '安全与伦理',      'https://www.alignmentforum.org/',                         'www.alignmentforum.org',      'web',  1),

-- ============================================================================
-- 七、学术论文（1个）
-- ============================================================================
('arxiv-cs-ai',             'arXiv cs.AI',                 'academic',     '学术论文',        'http://export.arxiv.org/rss/cs.AI',                       'export.arxiv.org',            'rss',  1),

-- ============================================================================
-- 八、周报与深度评论（5个）
-- ============================================================================
('ai-weekly',               'AI Weekly',                   'tech_media',   '周报与深度评论',  'https://aiweekly.co/rss.xml',                             'aiweekly.co',                 'rss',  1),
('karpathy',                'Andrej Karpathy Blog',        'tech_community','周报与深度评论',  'https://karpathy.github.io/feed.xml',                     'karpathy.github.io',          'rss',  1),
('simon-willison',          'Simon Willison Weblog',       'tech_community','周报与深度评论',  'https://simonwillison.net/atom/everything/',               'simonwillison.net',           'rss',  1),
('stratechery',             'Stratechery（科技战略）',     'tech_media',   '周报与深度评论',  'https://stratechery.com/feed/',                           'stratechery.com',             'rss',  1),
('ars-technica',            'Ars Technica AI',             'tech_media',   '周报与深度评论',  'https://arstechnica.com/ai/feed/',                        'arstechnica.com',             'rss',  1),

-- ============================================================================
-- 九、行业动态（中文源）（6个）
-- ============================================================================
('qbitai',                  '量子位',                      'tech_media',   '行业动态',        'https://www.qbitai.com/ai',                               'www.qbitai.com',              'web',  1),
('36kr-ai',                 '36氪AI频道',                  'tech_media',   '行业动态',        'https://36kr.com/information/AI/',                        '36kr.com',                    'web',  1),
('tmtpost',                 '钛媒体',                      'tech_media',   '行业动态',        'https://www.tmtpost.com/feed',                            'www.tmtpost.com',             'rss',  1),
('infoq-cn',                'InfoQ中文',                   'tech_media',   '行业动态',        'https://www.infoq.cn/feed',                               'www.infoq.cn',                'rss',  1),
('oschina-ai',              '开源中国AI',                  'tech_community','行业动态',       'https://www.oschina.net/news/rss/ai',                     'www.oschina.net',             'rss',  1),
('tencent-cloud-ai',        '腾讯云AI专栏',                'tech_community','AI基础设施',    'https://cloud.tencent.com/developer/column/102946',       'cloud.tencent.com',           'web',  1),

-- ============================================================================
-- 十、金融应用（2个）
-- ============================================================================
('10jqka-news',             '同花顺金融AI',                 'industry_application', '金融应用',  'https://news.10jqka.com.cn/',                             'news.10jqka.com.cn',          'web',  1),
('01caijing-home',       '零壹财经金融科技',             'industry_application', '金融应用',  'https://www.01caijing.com/',                      'www.01caijing.com',           'web',  1);

UPDATE ai_radar_source
SET selection_role = CASE
  WHEN source_type = 'academic' THEN 'research'
  WHEN source_type IN ('tech_media', 'industry_application', 'regulator') THEN 'industry'
  ELSE 'engineering'
END;

SET FOREIGN_KEY_CHECKS = 1;
