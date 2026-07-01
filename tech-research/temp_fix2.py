import sys

# Fix 2: insight.py - truncate full_text before LLM call
# Strategy: insert before the self.prompts.render() call line
path = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\deep\insight.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Anchor: the render call line (English, no Chinese)
old = '            full_text = analysis.get("summary_cn", "") or article.raw_summary or ""'

new = '''            full_text = analysis.get("summary_cn", "") or article.raw_summary or ""

        # Truncate full_text to avoid consuming output token budget
        max_full_text_chars = 6000
        if len(full_text) > max_full_text_chars:
            logger.info("Truncating full_text: %d -> %d chars", len(full_text), max_full_text_chars)
            full_text = full_text[:max_full_text_chars]'''

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fix 2 OK: deep/insight.py")
else:
    print("Fix 2 FAIL: anchor not found in insight.py")
    sys.exit(1)
