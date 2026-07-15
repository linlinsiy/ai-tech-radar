-- AI技术趋势雷达 v2.6 增量升级脚本
-- 用途: 仅供已有数据库增加采集分析运营过程表。
-- 全新环境请直接执行 ai_radar_ddl.sql，不需要再执行本文件。

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `ai_radar_pipeline_operation` (
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
