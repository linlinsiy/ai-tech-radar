import pymysql
conn = pymysql.connect(host='10.102.37.253', port=8880, user='ysdjg_user', password='pcadKeWbV147_', database='ysdjg', charset='utf8mb4')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM ai_radar_article')
print('Articles:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM ai_radar_kb_mapping')
print('KB Mappings:', cur.fetchone()[0])
cur.execute('SELECT id, LEFT(title,60), LENGTH(full_content), content_hash FROM ai_radar_article ORDER BY id DESC LIMIT 10')
for row in cur.fetchall():
    print('  id=%s, title=%s, full_content_len=%s, content_hash=%s' % row)
cur.execute('SELECT id, article_id, kb_file_id, tags, created_at FROM ai_radar_kb_mapping ORDER BY id DESC LIMIT 5')
for row in cur.fetchall():
    print('  KB: id=%s, article_id=%s, kb_file_id=%s, tags=%s, created_at=%s' % row)
conn.close()