import sys
sys.stdout.reconfigure(encoding="utf-8")

md_path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\kb\markdown_gen.py"
with open(md_path, "rb") as f:
    md_data = f.read()

# Fix 1: Add full_content section to ARTICLE_SUMMARY_TEMPLATE
old1 = b"## \xe5\x8e\x9f\xe6\x96\x87\xe6\x91\x98\xe8\xa6\x81\n{raw_summary}\n\"\"\""
new1 = b"## \xe5\x8e\x9f\xe6\x96\x87\xe6\x91\x98\xe8\xa6\x81\n{raw_summary}\n\n## \xe5\x85\xa8\xe6\x96\x87\n{full_content}\n\"\"\""
if old1 in md_data:
    md_data = md_data.replace(old1, new1)
    print("Added full_content to template")
else:
    print("Pattern1 not found, trying variant...")
    # Try with \r\n
    old1b = b"## \xe5\x8e\x9f\xe6\x96\x87\xe6\x91\x98\xe8\xa6\x81\r\n{raw_summary}\r\n\"\"\""
    if old1b in md_data:
        md_data = md_data.replace(old1b, new1.replace(b"\n", b"\r\n"))
        print("Added full_content to template (CRLF)")
    else:
        print("Neither pattern found")

# Fix 2: Add full_content param to generate_article_summary signature
old2 = b"    raw_summary: str = \"\",\n    category: Optional[str] = None,"
new2 = b"    raw_summary: str = \"\",\n    full_content: str = \"\",\n    category: Optional[str] = None,"
if old2 in md_data:
    md_data = md_data.replace(old2, new2)
    print("Added full_content param to function signature")
else:
    print("Pattern2 not found")

# Fix 3: Add full_content to .format() call
old3 = b"        raw_summary=raw_summary or \"N/A\",\n    )"
new3 = b"        raw_summary=raw_summary or \"N/A\",\n        full_content=full_content or \"N/A\",\n    )"
if old3 in md_data:
    md_data = md_data.replace(old3, new3)
    print("Added full_content to format call")
else:
    print("Pattern3 not found")

with open(md_path, "wb") as f:
    f.write(md_data)
print("markdown_gen.py updated")
