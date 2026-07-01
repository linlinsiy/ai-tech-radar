import pymysql
conn = pymysql.connect(host="10.102.37.253", port=8880, user="ysdjg_user", password="pcadKeWbV147_", database="ysdjg", charset="utf8mb4")
cur = conn.cursor()

# Check current columns
cur.execute("DESCRIBE ai_radar_kb_mapping")
print("=== ai_radar_kb_mapping columns ===")
for row in cur.fetchall():
    print(row)

# Add tags column if missing
cur.execute("SHOW COLUMNS FROM ai_radar_kb_mapping LIKE 'tags'")
if not cur.fetchone():
    cur.execute("ALTER TABLE ai_radar_kb_mapping ADD COLUMN tags JSON NULL COMMENT '标签键值对' AFTER error_message")
    conn.commit()
    print("\nAdded tags column to ai_radar_kb_mapping")

# Check full_content situation
cur.execute("SELECT COUNT(*) as total, SUM(CASE WHEN full_content IS NULL OR full_content='' THEN 1 ELSE 0 END) as missing FROM ai_radar_article")
total, missing = cur.fetchone()
print(f"\n=== Articles: total={total}, missing_full_content={missing} ===")

conn.close()
