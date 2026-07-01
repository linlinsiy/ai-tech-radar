import pymysql
conn = pymysql.connect(host='10.102.37.253', port=8880, user='ysdjg_user', password='pcadKeWbV147_', database='ysdjg')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM ai_radar_kb_mapping')
print(f'kb_mapping: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM ai_radar_article WHERE full_content IS NOT NULL AND LENGTH(full_content) > 0')
print(f'full_content: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM ai_radar_article WHERE content_hash IS NOT NULL AND LENGTH(content_hash) > 0')
print(f'content_hash: {cur.fetchone()[0]}')
cur.execute('SELECT batch_no, import_status, article_count FROM ai_radar_import_batch ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    print(f'  {r[0]} status={r[1]} articles={r[2]}')
conn.close()
