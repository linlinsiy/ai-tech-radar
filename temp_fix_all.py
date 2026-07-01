import sys
sys.stdout.reconfigure(encoding="utf-8")

# 1. Fix DDL comment quotes
ddl_path = r"D:\013148\code\AI技术趋势雷达\tech-research\sql\ai_radar_ddl.sql"
with open(ddl_path, "r", encoding="utf-8") as f:
    ddl = f.read()
ddl = ddl.replace("COMMENT 标签键值对,", "COMMENT '标签键值对',")
with open(ddl_path, "w", encoding="utf-8") as f:
    f.write(ddl)
print("1. DDL comment quotes fixed")

# 2. Update markdown_gen.py: embed tags metadata in Markdown content
md_path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\kb\markdown_gen.py"
with open(md_path, "rb") as f:
    md_data = f.read()

# Add full_content/raw_summary to article summary template
old_tmpl = b"## \xe5\x8e\x9f\xe6\x96\x87\xe6\x91\x98\xe8\xa6\x81\r\n{raw_summary}\r\n\"\"\""
new_tmpl = b"## \xe5\x8e\x9f\xe6\x96\x87\xe6\x91\x98\xe8\xa6\x81\r\n{raw_summary}\r\n\r\n## \xe5\x85\xa8\xe6\x96\x87\r\n{full_content}\r\n\"\"\""

if old_tmpl in md_data:
    md_data = md_data.replace(old_tmpl, new_tmpl)
    with open(md_path, "wb") as f:
        f.write(md_data)
    print("2. markdown_gen.py: added full_content to template")
else:
    print("2. markdown_gen.py: pattern not found, checking...")
    idx = md_data.find(b"raw_summary")
    if idx >= 0:
        print("   raw_summary found at", idx, repr(md_data[idx:idx+80]))

# 3. Update kb_client.py docstring
kb_path = r"D:\013148\code\AI技术趋势雷达\tech-research\internal\app\kb\kb_client.py"
with open(kb_path, "rb") as f:
    kb_data = f.read()

# Fix the tags docstring line
old_doc = b"            tags: \xe6\xa0\x87\xe7\xad\xbe\xe5\xad\x97\xe5\x85\xb8\xef\xbc\x8cSDK \xe7\x9a\x84 upload_chunks \xe6\x94\xb6\xe5\x8f\x97\xe6\xa0\x87\xe7\xad\xbe\xe5\xad\x97\xe5\x85\xb8"
new_doc = b"            tags: \xe6\xa0\x87\xe7\xad\xbe\xe5\xad\x97\xe5\x85\xb8\xef\xbc\x8c\xe5\xbd\x93\xe5\x89\x8d SDK \xe4\xb8\x8d\xe6\x94\xaf\xe6\x8c\x81\xef\xbc\x8c\xe5\xb0\x86\xe5\xad\x98\xe5\x85\xa5 KbMapping \xe8\xa1\xa8"

if old_doc in kb_data:
    kb_data = kb_data.replace(old_doc, new_doc)
    with open(kb_path, "wb") as f:
        f.write(kb_data)
    print("3. kb_client.py docstring updated")
else:
    print("3. kb_client.py: docstring pattern not found")
    idx = kb_data.find(b"tags: \xe6\xa0\x87")
    if idx >= 0:
        print("   found at", idx, repr(kb_data[idx:idx+120]))

print("All fixes applied.")
