import sys

# Fix 2: insight.py - truncate full_text before LLM call
path = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\deep\insight.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Find and modify the full_text section before prompt rendering
# Target: the line before "# Render Prompt" where full_text is prepared
old_insight = '''        # Render Prompt
        system, user, version, _model_name = self.prompts.render(
            "l3_deep_insight",
            title=article.title,
            full_content=full_text,
        )'''

new_insight = '''        # Truncate full_text to avoid consuming output token budget
        # (LLM output may be truncated if input is too long)
        max_full_text_chars = 6000
        if len(full_text) > max_full_text_chars:
            logger.info("Truncating full_text: %d -> %d chars", len(full_text), max_full_text_chars)
            full_text = full_text[:max_full_text_chars]

        # Render Prompt
        system, user, version, _model_name = self.prompts.render(
            "l3_deep_insight",
            title=article.title,
            full_content=full_text,
        )'''

if old_insight in content:
    content = content.replace(old_insight, new_insight, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fix 2 OK: deep/insight.py")
else:
    print("Fix 2 FAIL: pattern not found")

# Fix 3: collect_job.py - remove duplicate content_hash loop, add fallback
path = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\jobs\collect_job.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove the duplicate second content_hash loop
old_dup = '''        # 对所有文章计算 content_hash（基于 raw_summary + raw_html）
        for r in l2_results:
            art = r["article"]
            if not art.content_hash:
                hash_source = art.raw_summary or ""
                if art.raw_html:
                    hash_source = (hash_source + "\n" + art.raw_html)[:8000]
                if hash_source:
                    art.compute_content_hash(hash_source)

# === 组装导入请求 ==="""'

new_dup = '''# === 组装导入请求 ==="""'

if old_dup in content:
    content = content.replace(old_dup, new_dup, 1)
    # Now enhance the first content_hash loop with URL fallback
    old_first = '''        # 对所有文章计算 content_hash（基于 raw_summary + raw_html）
        for r in l2_results:
            art = r["article"]
            if not art.content_hash:
                hash_source = art.raw_summary or ""
                if art.raw_html:
                    hash_source = (hash_source + "\n" + art.raw_html)[:8000]
                if hash_source:
                    art.compute_content_hash(hash_source)

        # 对所有文章计算 content_hash（基于 raw_summary + raw_html）
        for r in l2_results:
            art = r["article"]
            if not art.content_hash:
                hash_source = art.raw_summary or ""
                if art.raw_html:
                    hash_source = (hash_source + "\n" + art.raw_html)[:8000]
                if hash_source:
                    art.compute_content_hash(hash_source)'''

    new_first = '''        # 对所有文章计算 content_hash（基于 raw_summary + raw_html）
        for r in l2_results:
            art = r["article"]
            if not art.content_hash:
                hash_source = art.raw_summary or ""
                if art.raw_html:
                    hash_source = (hash_source + "\n" + art.raw_html)[:8000]
                if not hash_source:
                    # Fallback: use URL as hash source when no content available
                    hash_source = art.url or ""
                if hash_source:
                    art.compute_content_hash(hash_source)'''

    if old_first in content:
        content = content.replace(old_first, new_first, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fix 3 OK: jobs/collect_job.py")
    else:
        print("Fix 3 FAIL: first loop pattern not found")
else:
    print("Fix 3 FAIL: duplicate loop not found")

# Fix 4: import_api.py - add full_content and tags
path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\api\import_api.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add full_content to generate_article_summary call
old_md = '''                        md = generate_article_summary(
                            title=item.title, source_name=src_name, url=item.url,
                            summary_cn=matched.summary_cn if matched else "",
                            raw_summary=item.raw_summary or "",
                            category=matched.category if matched else None,
                            author=item.author, publish_time=item.publish_time,
                            value_score=matched.value_score if matched else None,
                        )'''

new_md = '''                        md = generate_article_summary(
                            title=item.title, source_name=src_name, url=item.url,
                            summary_cn=matched.summary_cn if matched else "",
                            raw_summary=item.raw_summary or "",
                            full_content=item.full_content or "",
                            category=matched.category if matched else None,
                            author=item.author, publish_time=item.publish_time,
                            value_score=matched.value_score if matched else None,
                        )'''

if old_md in content:
    content = content.replace(old_md, new_md, 1)
    # Now fix KbMapping to include tags
    old_kbm = '''                            mapping = KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type="article_summary", uploaded_at=datetime.now())'''
    new_kbm = '''                            mapping = KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type="article_summary", tags=tags, uploaded_at=datetime.now())'''
    if old_kbm in content:
        content = content.replace(old_kbm, new_kbm, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fix 4 OK: api/import_api.py")
    else:
        print("Fix 4 FAIL: KbMapping pattern not found")
else:
    print("Fix 4 FAIL: generate_article_summary pattern not found")

print("Done")
