USE ai;

SET @l3_min_rank_score = 6.00;
-- 如需指定分析批次，填入 IMP-* 或 RERUN-*；留空则查询最新成功且有 L2 关系的分析批次。
SET @analysis_batch_no = '';

WITH target_batch AS (
  SELECT b.id
  FROM ai_radar_import_batch b
  INNER JOIN ai_radar_analysis_article rel
    ON rel.analysis_batch_id = b.id
  WHERE b.import_status = 'success'
    AND (@analysis_batch_no = '' OR b.batch_no = @analysis_batch_no)
  GROUP BY b.id
  ORDER BY b.id DESC
  LIMIT 1
)
SELECT
  ROW_NUMBER() OVER (
    ORDER BY COALESCE(aa.rank_score, aa.value_score) DESC,
             a.publish_time DESC,
             a.id
  ) AS '序号',
  a.title AS '标题',
  aa.category AS '分类',
  aa.score_tech_depth AS '技术深度评分',
  aa.score_engineering AS '工程价值',
  aa.score_org_relevance AS '组织相关性',
  NULLIF(JSON_UNQUOTE(JSON_EXTRACT(
    aa.analysis_detail, '$.org_relevance_reason'
  )), '') AS '组织相关性原因',
  aa.score_trend AS '趋势重要性',
  NULLIF(JSON_UNQUOTE(JSON_EXTRACT(
    aa.analysis_detail, '$.trend_reason'
  )), '') AS '趋势重要性原因',
  aa.score_timeliness AS '时效性',
  COALESCE(aa.rank_score, aa.value_score) AS '综合得分',
  CASE
    WHEN COALESCE(aa.rank_score, aa.value_score) >= @l3_min_rank_score
      AND rel.l3_selected = 1
      AND di.id IS NOT NULL
    THEN '是'
    ELSE '否'
  END AS '是否L3最终入选'
FROM target_batch tb
INNER JOIN ai_radar_analysis_article rel
  ON rel.analysis_batch_id = tb.id
INNER JOIN ai_radar_article a
  ON a.id = rel.article_id
INNER JOIN ai_radar_article_analysis aa
  ON aa.id = rel.analysis_id
 AND aa.analysis_batch_id = tb.id
LEFT JOIN ai_radar_deep_insight di
  ON di.id = rel.insight_id
 AND di.analysis_batch_id = tb.id
 AND di.analysis_status = 'success'
WHERE aa.analysis_status = 'success'
ORDER BY
  COALESCE(aa.rank_score, aa.value_score) DESC,
  a.publish_time DESC,
  a.id;
