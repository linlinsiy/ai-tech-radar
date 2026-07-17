-- V2.7: 统一 rank_score 与来源选题角色
-- 适用于从 V2.6 升级的现有数据库；全新建库直接执行 ai_radar_ddl.sql。

ALTER TABLE ai_radar_source
  ADD COLUMN selection_role varchar(16) NOT NULL DEFAULT 'industry'
    COMMENT '选题软配额角色(engineering/industry/research)' AFTER category;

UPDATE ai_radar_source
SET selection_role = CASE
  WHEN source_type = 'academic' THEN 'research'
  WHEN source_type IN ('tech_media', 'industry_application', 'regulator') THEN 'industry'
  ELSE 'engineering'
END;

ALTER TABLE ai_radar_article_analysis
  ADD COLUMN score_org_relevance decimal(3,1) DEFAULT NULL
    COMMENT '组织相关性' AFTER score_engineering,
  ADD COLUMN rank_score decimal(4,2) DEFAULT NULL
    COMMENT '统一排序评分' AFTER value_score;

UPDATE ai_radar_article_analysis
SET rank_score = value_score
WHERE rank_score IS NULL;

CREATE INDEX idx_rank_score ON ai_radar_article_analysis (rank_score);
