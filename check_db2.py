import pymysql
conn = pymysql.connect(host="10.102.37.253", port=8880, user="ysdjg_user", password="pcadKeWbV147_", database="ysdjg", charset="utf8mb4")
cur = conn.cursor()

# Latest batch
cur.execute("SELECT batch_no, article_count, success_count, import_status, created_at FROM ai_radar_import_batch ORDER BY id DESC LIMIT 3")
print("=== Import Batches ===")
for row in cur.fetchall():
    print(row)

# Latest articles - full_content & content_hash
cur.execute("SELECT id, title, LENGTH(full_content) as fc_len, content_hash FROM ai_radar_article ORDER BY id DESC LIMIT 5")
print("\n=== Latest Articles ===")
for row in cur.fetchall():
    print(row)

# KbMapping
cur.execute("SELECT id, kb_type, kb_file_id, tags, kb_status FROM ai_radar_kb_mapping ORDER BY id DESC LIMIT 5")
print("\n=== KbMapping ===")
for row in cur.fetchall():
    print(row)

conn.close()
