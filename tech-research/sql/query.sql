USE ai;

WITH latest_batch AS (
  SELECT id
  FROM ai_radar_import_batch
  WHERE import_status = 'success'
  ORDER BY id DESC
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
  NULLIF(
    JSON_UNQUOTE(JSON_EXTRACT(aa.analysis_detail, '$.org_relevance_reason')),
    ''
  ) AS '组织相关性原因',
  aa.score_trend AS '趋势重要性',
  NULLIF(
    JSON_UNQUOTE(JSON_EXTRACT(aa.analysis_detail, '$.trend_reason')),
    ''
  ) AS '趋势重要性原因',
  aa.score_timeliness AS '时效性',
  COALESCE(aa.rank_score, aa.value_score) AS '综合得分',
  CASE
    WHEN di.article_id IS NOT NULL AND di.analysis_status = 'success'
    THEN '是'
    ELSE '否'
  END AS '是否L3最终入选'
FROM latest_batch lb
INNER JOIN ai_radar_article a
  ON a.import_batch_id = lb.id
INNER JOIN ai_radar_article_analysis aa
  ON aa.article_id = a.id
LEFT JOIN ai_radar_deep_insight di
  ON di.article_id = a.id
WHERE aa.analysis_status = 'success'
ORDER BY
  COALESCE(aa.rank_score, aa.value_score) DESC,
  a.publish_time DESC,
  a.id;
