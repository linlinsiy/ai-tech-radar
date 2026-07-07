-- ============================================================
-- AI技术趋势雷达 - v2.5 增量变更
-- 目的：将旧的全局应用评分设计调整为通用分类结构
-- 适用：已有 ai_radar_article_analysis 表的环境
-- 说明：MariaDB 环境可重复执行；已存在的列和索引会自动跳过。
-- ============================================================

ALTER TABLE ai_radar_article_analysis
  ADD COLUMN IF NOT EXISTS sub_category VARCHAR(128) NULL COMMENT '资讯子分类，用于简报章节内细分' AFTER category,
  ADD COLUMN IF NOT EXISTS info_type VARCHAR(64) NULL COMMENT '资讯类型：技术方案 / 模型发布 / 产品发布 / 开源项目 / 研究论文 / 工程实践 / 行业动态 / 投融资并购 / 政策监管 / 观点分析 / 案例实践 / 其他' AFTER sub_category,
  ADD COLUMN IF NOT EXISTS briefing_focus TEXT NULL COMMENT '简报表达重点' AFTER info_type,
  ADD COLUMN IF NOT EXISTS analysis_detail JSON NULL COMMENT '按资讯类型存放的结构化分析详情' AFTER briefing_focus;

CREATE INDEX IF NOT EXISTS idx_category_sub_category
  ON ai_radar_article_analysis (category, sub_category);

CREATE INDEX IF NOT EXISTS idx_info_type
  ON ai_radar_article_analysis (info_type);
