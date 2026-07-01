# -*- coding: utf-8 -*-
import sys, os
from dotenv import load_dotenv
# 加载 internal 侧的 .env
env_path = r'D:\013148\code\AI技术趋势雷达\tech-research\internal\secrets\.env'
if os.path.exists(env_path):
    load_dotenv(env_path)

sys.path.insert(0, r'D:\013148\code\AI技术趋势雷达\tech-research\internal\app')
os.chdir(r'D:\013148\code\AI技术趋势雷达\tech-research\internal\app')

import pymysql, logging
from datetime import datetime
from kb.kb_client import create_kb_client
from kb.markdown_gen import generate_article_summary
from db.models import KbMapping, get_session

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')
logger = logging.getLogger('reimport')

conn = pymysql.connect(host='10.102.37.253', port=8880, user='ysdjg_user', password='pcadKeWbV147_', database='ysdjg', charset='utf8mb4')
cur = conn.cursor()

cur.execute('''SELECT a.id, a.title, a.url, a.author, a.publish_time, a.raw_summary, a.full_content, a.source_id, a.url_hash,
    s.source_name, aa.summary_cn, aa.category, aa.value_score
    FROM ai_radar_article a
    LEFT JOIN ai_radar_kb_mapping m ON a.id = m.article_id
    LEFT JOIN ai_radar_source s ON a.source_id = s.id
    LEFT JOIN ai_radar_article_analysis aa ON a.id = aa.article_id
    WHERE m.id IS NULL ORDER BY a.id''')

articles = cur.fetchall()
logger.info('Found %d articles to import', len(articles))

kb = create_kb_client()
session = get_session()
success = 0

for a in articles:
    aid, title, url, author, pt, raw_s, fc, src_id, uh, src_name, summary_cn, cat, vs = a
    try:
        md = generate_article_summary(
            title=title, source_name=src_name or 'unknown', url=url or '',
            summary_cn=summary_cn or '', raw_summary=raw_s or '',
            full_content=fc or '', category=cat, author=author,
            publish_time=pt, value_score=float(vs) if vs else None
        )
        safe_title = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in (title or 'untitled'))[:30].strip()
        fname = '%s_%s.md' % (uh[:16], safe_title)
        tags = {'source': src_name or 'unknown', 'category': cat or '', 'lang': 'zh', 'kb_type': 'article_summary'}
        kb_file_id = kb.upload_file(content=md, filename=fname)
        if kb_file_id:
            mapping = KbMapping(article_id=aid, kb_file_id=kb_file_id, kb_type='article_summary', tags=tags, created_at=datetime.now())
            session.add(mapping)
            session.commit()
            success += 1
            logger.info('[%d/%d] OK: id=%d, kb_file_id=%s', success, len(articles), aid, kb_file_id)
        else:
            logger.warning('[%d/%d] NO FILE ID: id=%d', success, len(articles), aid)
    except Exception as e:
        session.rollback()
        logger.error('[%d/%d] FAIL: id=%d, error=%s', success, len(articles), aid, str(e)[:120])

session.close(); cur.close(); conn.close()
logger.info('Done: %d/%d articles uploaded to KB', success, len(articles))