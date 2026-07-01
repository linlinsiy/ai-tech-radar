import pathlib, re
root = pathlib.Path(r"D:\013148\code")
d = [x for x in root.iterdir() if x.is_dir() and "技术趋势" in x.name][0]
f = list((d / "验证").glob("API*.md"))[0]
c = f.read_text("utf-8")

# Check section 3.2 fields
section_32 = c[c.index("### 3.2"):c.index("### 3.3")] if "### 3.3" in c else ""

checks = [
    ("article_url_hash", "analyses.article_url_hash"),
    ("summary_cn", "analyses.summary_cn"),
    ("technical_background", "insights.technical_background"),
    ("core_problem", "insights.core_problem"),
    ("technical_solution", "insights.technical_solution"),
    ("impact_analysis", "insights.impact_analysis"),
    ("reference_value", "insights.reference_value"),
    ("score_tech_depth", "analyses.score_tech_depth"),
    ("companies", "analyses.companies"),
    ("<sha256hex", "placeholder"),
]
for field, desc in checks:
    print(f"  {desc}: {'OK' if field in section_32 else 'MISSING'}")

# Check JSON validity
json_start = section_32.index('{\n  "batch"')
json_end = section_32.index('\n```\n\n- **成功响应**')
json_str = section_32[json_start:json_end+1]
try:
    import json
    parsed = json.loads(json_str)
    print("\nJSON valid: OK")
    print(f"  articles: {len(parsed.get('articles', []))} items")
    print(f"  analyses: {len(parsed.get('analyses', []))} items")
    print(f"  insights: {len(parsed.get('insights', []))} items")
except Exception as e:
    print(f"\nJSON Error: {e}")
