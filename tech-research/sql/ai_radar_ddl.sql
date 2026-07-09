-- AI技术趋势雷达数据库表结构
-- 版本: 2026-07-09
-- 修改说明: 新增数据源分类字段category，适配9大分类要求，优化索引结构

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 数据源表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_source`;
CREATE TABLE `ai_radar_source` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `code` varchar(64) NOT NULL COMMENT '数据源唯一编码',
  `name` varchar(128) NOT NULL COMMENT '数据源名称',
  `type` varchar(32) NOT NULL COMMENT '数据源类型(academic/vendor_blog/tech_media/tech_community/industry_application)',
  `category` varchar(64) NOT NULL COMMENT '内容分类(大模型基础技术/Agent与智能体/多模态技术/AI基础设施/生成式AI应用/安全与伦理/开源生态/行业动态/AI在金融领域应用)',
  `access_url` varchar(256) NOT NULL COMMENT '采集地址',
  `domain` varchar(128) NOT NULL COMMENT '域名白名单',
  `fetch_method` varchar(16) NOT NULL DEFAULT 'rss' COMMENT '采集方式(rss/html)',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `last_collect_time` datetime DEFAULT NULL COMMENT '最后采集时间',
  `last_collect_status` varchar(16) DEFAULT NULL COMMENT '最后采集状态(success/failed)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`),
  KEY `idx_category` (`category`),
  KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据源配置表';

-- ----------------------------
-- 文章原始数据表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_article`;
CREATE TABLE `ai_radar_article` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `source_code` varchar(64) NOT NULL COMMENT '来源数据源code',
  `category` varchar(64) NOT NULL COMMENT '内容分类',
  `title` varchar(512) NOT NULL COMMENT '文章标题',
  `url` varchar(1024) NOT NULL COMMENT '原文链接',
  `pub_time` datetime DEFAULT NULL COMMENT '发布时间',
  `author` varchar(128) DEFAULT NULL COMMENT '作者',
  `content` longtext COMMENT '原始正文内容',
  `content_hash` varchar(64) NOT NULL COMMENT '内容哈希(去重用)',
  `status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '处理状态(pending/analyzed/failed)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_url` (`url`(255)),
  UNIQUE KEY `uk_content_hash` (`content_hash`),
  KEY `idx_source_code` (`source_code`),
  KEY `idx_category` (`category`),
  KEY `idx_pub_time` (`pub_time`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章原始数据表';

-- ----------------------------
-- 文章L2分析结果表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_article_analysis`;
CREATE TABLE `ai_radar_article_analysis` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `article_id` bigint unsigned NOT NULL COMMENT '关联文章ID',
  `summary` text NOT NULL COMMENT '摘要内容',
  `keywords` varchar(512) DEFAULT NULL COMMENT '关键词列表(逗号分隔)',
  `value_score` decimal(3,1) NOT NULL COMMENT '价值评分0-10',
  `tags` varchar(512) DEFAULT NULL COMMENT '标签列表(逗号分隔)',
  `category` varchar(64) NOT NULL COMMENT '自动分类结果',
  `model` varchar(64) NOT NULL COMMENT '使用模型',
  `tokens_used` int NOT NULL DEFAULT '0' COMMENT '消耗token数',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_article_id` (`article_id`),
  KEY `idx_value_score` (`value_score`),
  KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章L2分析结果表';

-- ----------------------------
-- 深度洞察结果表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_deep_insight`;
CREATE TABLE `ai_radar_deep_insight` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `article_id` bigint unsigned NOT NULL COMMENT '关联文章ID',
  `content` longtext NOT NULL COMMENT '深度分析内容',
  `key_findings` text COMMENT '核心发现',
  `technical_points` text COMMENT '技术要点',
  `business_value` text COMMENT '业务价值',
  `model` varchar(64) NOT NULL COMMENT '使用模型',
  `tokens_used` int NOT NULL DEFAULT '0' COMMENT '消耗token数',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_article_id` (`article_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='深度洞察结果表';

-- ----------------------------
-- 采集批次表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_import_batch`;
CREATE TABLE `ai_radar_import_batch` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `batch_no` varchar(32) NOT NULL COMMENT '批次号',
  `scope` varchar(32) NOT NULL COMMENT '采集范围(all/sources)',
  `article_count` int NOT NULL DEFAULT '0' COMMENT '采集文章数',
  `analysis_count` int NOT NULL DEFAULT '0' COMMENT '完成分析数',
  `insight_count` int NOT NULL DEFAULT '0' COMMENT '生成深度洞察数',
  `status` varchar(16) NOT NULL DEFAULT 'running' COMMENT '批次状态(running/success/failed)',
  `error_msg` text COMMENT '错误信息',
  `start_time` datetime NOT NULL COMMENT '开始时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_batch_no` (`batch_no`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采集批次表';

-- ----------------------------
-- 简报草稿表
-- ----------------------------
DROP TABLE IF EXISTS `ai_radar_briefing_draft`;
CREATE TABLE `ai_radar_briefing_draft` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `briefing_type` varchar(32) NOT NULL COMMENT '简报类型(daily/weekly/monthly)',
  `title` varchar(256) NOT NULL COMMENT '简报标题',
  `time_range_start` date DEFAULT NULL COMMENT '时间范围-开始',
  `time_range_end` date DEFAULT NULL COMMENT '时间范围-结束',
  `related_article_ids` longtext COMMENT '关联文章ID列表(JSON数组)',
  `related_insight_ids` longtext COMMENT '关联洞察ID列表(JSON数组)',
  `content` longtext NOT NULL COMMENT '简报内容',
  `review_status` varchar(32) NOT NULL DEFAULT 'pending' COMMENT '审核状态(pending/passed/rejected)',
  `reviewer` varchar(64) DEFAULT NULL COMMENT '审核人',
  `review_time` datetime DEFAULT NULL COMMENT '审核时间',
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
  `article_id` bigint unsigned NOT NULL COMMENT '关联文章ID',
  `kb_id` varchar(64) NOT NULL COMMENT '知识库ID',
  `sync_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '同步状态(pending/success/failed)',
  `sync_time` datetime DEFAULT NULL COMMENT '同步时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_article_kb` (`article_id`, `kb_id`),
  KEY `idx_sync_status` (`sync_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库映射表';

ALTER TABLE ai_radar_article_analysis
  ADD COLUMN IF NOT EXISTS sub_category VARCHAR(128) NULL COMMENT '资讯子分类，用于简报章节内细分' AFTER category,
  ADD COLUMN IF NOT EXISTS info_type VARCHAR(64) NULL COMMENT '资讯类型：技术方案 / 模型发布 / 产品发布 / 开源项目 / 研究论文 / 工程实践 / 行业动态 / 投融资并购 / 政策监管 / 观点分析 / 案例实践 / 其他' AFTER sub_category,
  ADD COLUMN IF NOT EXISTS briefing_focus TEXT NULL COMMENT '简报表达重点' AFTER info_type,
  ADD COLUMN IF NOT EXISTS analysis_detail JSON NULL COMMENT '按资讯类型存放的结构化分析详情' AFTER briefing_focus;

CREATE INDEX IF NOT EXISTS idx_category_sub_category
  ON ai_radar_article_analysis (category, sub_category);

CREATE INDEX IF NOT EXISTS idx_info_type
  ON ai_radar_article_analysis (info_type);


-- ============================================================
-- AI技术趋势雷达 - 数据源初始化 INSERT（32个全量验证版）
-- 时间: 2026-07-09 17:10
-- 表: ai_radar_source
-- * 所有 URL 均经 curl 200 验证通过
-- * OpenAI/DeepMind/HuggingFace/量子位 RSS 正文空，改用 web 采集
-- * 恒生电子 JS空壳，替换为零壹财经
-- ============================================================

INSERT INTO ai_radar_source (code, name, type, category, access_url, domain, fetch_method, enabled) VALUES

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
('01caijing-fintech',       '零壹财经金融科技',             'industry_application', '金融应用',  'https://www.01caijing.com/fintech/',                      'www.01caijing.com',           'web',  1);


ALTER TABLE ai_radar_import_batch ADD COLUMN `task_type` varchar(32) DEFAULT 'manual' COMMENT '任务类型' AFTER `scope`;

ALTER TABLE ai_radar_import_batch ADD COLUMN `source_scope` varchar(64) DEFAULT 'all' COMMENT '采集范围' AFTER `task_type`;
