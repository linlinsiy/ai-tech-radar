import os

def fix_insight_py():
    path = r'D:\013148\code\AI技术趋势雷达\tech-research\aws\app\deep\insight.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old = '        full_text = ""\n        if article.raw_html:\n            full_text = ContentParser.extract_main_content(article.raw_html)\n        if not full_text:\n            full_text = analysis.get("summary_cn", "") or article.raw_summary or ""'
    
    new = '        full_text = ""\n        try:\n            if article.raw_html:\n                full_text = ContentParser.extract_main_content(article.raw_html)\n            if not full_text:\n                full_text = analysis.get("summary_cn", "") or article.raw_summary or ""\n        except Exception:\n            full_text = analysis.get("summary_cn", "") or article.raw_summary or ""'
    
    if old in content:
        content = content.replace(old, new, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print('insight.py: FIXED - added try/except around full_content extraction')
    else:
        print('WARNING: old pattern not found in insight.py')

fix_insight_py()
