import re

path = r'D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py'
with open(path, 'rb') as f:
    data = f.read()

# Find and replace the buggy KbMapping line
# Old: KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type=\"article_summary\", uploaded_at=datetime.now())
old = b'KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type=\"article_summary\", uploaded_at=datetime.now())'
new = b'KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type=\"article_summary\", tags=tags)'

if old in data:
    data = data.replace(old, new)
    with open(path, 'wb') as f:
        f.write(data)
    print('import_api.py: fixed uploaded_at -> tags=tags')
else:
    print('Pattern not found. Looking for KbMapping lines...')
    idx = data.find(b'KbMapping')
    if idx >= 0:
        print(data[idx:idx+200])
