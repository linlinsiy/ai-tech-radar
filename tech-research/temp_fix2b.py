import sys
path = r"D:\013148\code\AI技术趋势雷达\tech-research\aws\app\deep\insight.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# The broken section:
#         # Truncate... (lines 114-118 of bad output)
#         except Exception:
#             full_text = analysis.get(...)
# We need to move truncate after the except block

old_broken = """        # Truncate full_text to avoid consuming output token budget
        max_full_text_chars = 6000
        if len(full_text) > max_full_text_chars:
            logger.info("Truncating full_text: %d -> %d chars", len(full_text), max_full_text_chars)
            full_text = full_text[:max_full_text_chars]
        except Exception:
            full_text = analysis.get("summary_cn", "") or article.raw_summary or """""

new_fixed = """        except Exception:
            full_text = analysis.get("summary_cn", "") or article.raw_summary or ""

        # Truncate full_text to avoid consuming output token budget
        max_full_text_chars = 6000
        if len(full_text) > max_full_text_chars:
            logger.info("Truncating full_text: %d -> %d chars", len(full_text), max_full_text_chars)
            full_text = full_text[:max_full_text_chars]"""

if old_broken in content:
    content = content.replace(old_broken, new_fixed, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fix 2b OK: moved truncate after except block")
else:
    print("Fix 2b FAIL: broken pattern not found")
    # Debug
    idx = content.find("Truncating full_text")
    if idx > 0:
        print("Found Truncating at", idx)
        print(repr(content[idx-50:idx+200]))
