import pathlib, re
root = pathlib.Path(r"D:\013148\code")
d = [x for x in root.iterdir() if x.is_dir() and "技术趋势" in x.name][0]
f = list((d / "验证").glob("API*.md"))[0]
c = f.read_text("utf-8")

# Count in 3.2 section
section_32 = c[c.index("### 3.2"):c.index("### 3.3")] if "### 3.3" in c else c
hashes_64 = re.findall(r'[a-f0-9]{64}', section_32)
print(f"Real SHA256 hashes in 3.2 section: {len(hashes_64)}")
print(f"sha256hex placeholder count: {c.count('<sha256hex')}")
print(f"url_hash fields: {c.count('url_hash')}")
print(f"content_hash fields: {c.count('content_hash')}")
# Check articles/analyses/insights presence
for key in ["articles", "analyses", "insights", "cross_source_trend", "l2_summary", "l3_deep_insight"]:
    print(f'  "{key}" present: {key in c}')
