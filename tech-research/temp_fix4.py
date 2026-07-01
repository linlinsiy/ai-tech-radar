import sys

# Fix 4: import_api.py - add full_content and tags
path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Part A: Add full_content to generate_article_summary call
# Anchor: the function call line with raw_summary parameter
old_a = '                            raw_summary=item.raw_summary or "",'
new_a = '                            raw_summary=item.raw_summary or "",\n                            full_content=item.full_content or "",'
if old_a in content:
    content = content.replace(old_a, new_a, 1)
    print("Part A OK: added full_content to generate_article_summary")
else:
    print("Part A FAIL: raw_summary anchor not found")

# Part B: Add tags to KbMapping
old_b = '                            mapping = KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type="article_summary", uploaded_at=datetime.now())'
new_b = '                            mapping = KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type="article_summary", tags=tags, uploaded_at=datetime.now())'
if old_b in content:
    content = content.replace(old_b, new_b, 1)
    print("Part B OK: added tags to KbMapping")
else:
    print("Part B FAIL: KbMapping anchor not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fix 4 done")

# Summary
print("=== All 4 fixes applied ===")
