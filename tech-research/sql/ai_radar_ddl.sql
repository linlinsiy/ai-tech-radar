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
