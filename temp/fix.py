import re, os

base = r"D:\013148\code\AI技术趋势雷达"

# Fix 1: insight.py - full_content KeyError + logger.exception
insight_path = os.path.join(base, "tech-research", "aws", "app", "deep", "insight.py")
with open(insight_path, "r", encoding="utf-8") as f:
    content = f.read()

count = content.count("content=full_text,")
content = content.replace("content=full_text,", "full_content=full_text,")
print(f"[insight.py] Fixed content=full_text: {count} occ")

content = content.replace(
    'logger.error("L3 分析异常: %s", str(e))',
    'logger.exception("L3 分析异常")'
)
print("[insight.py] Fixed logger.error -> logger.exception")

with open(insight_path, "w", encoding="utf-8") as f:
    f.write(content)

# Fix 2: collect_job.py - compute content_hash
collect_path = os.path.join(base, "tech-research", "aws", "app", "jobs", "collect_job.py")
with open(collect_path, "r", encoding="utf-8") as f:
    content = f.read()

calc = (
    "        # 对所有文章计算 content_hash（基于 raw_summary + raw_html）\n"
    '        for r in l2_results:\n'
    '            art = r["article"]\n'
    "            if not art.content_hash:\n"
    '                hash_source = art.raw_summary or ""\n'
    "                if art.raw_html:\n"
    '                    hash_source = (hash_source + "\\n" + art.raw_html)[:8000]\n'
    "                if hash_source:\n"
    "                    art.compute_content_hash(hash_source)\n"
    "\n"
)

marker = "# === 组装导入请求 ==="
content = content.replace(marker, calc + marker)
print("[collect_job.py] Added content_hash calc")

with open(collect_path, "w", encoding="utf-8") as f:
    f.write(content)

# Fix 4: kb_client.py - pass tags
kb_client_path = os.path.join(base, "tech-research", "internal", "app", "kb", "kb_client.py")
with open(kb_client_path, "r", encoding="utf-8") as f:
    content = f.read()

old = "result = self.client.upload_chunks(\n                filename=filename,\n                chunks=chunks,\n                dataset_id=self._dataset_id,\n            )"
new = "result = self.client.upload_chunks(\n                filename=filename,\n                chunks=chunks,\n                dataset_id=self._dataset_id,\n                tags=tags or {},\n            )"
if old in content:
    content = content.replace(old, new)
    print("[kb_client.py] Added tags to upload_chunks()")
else:
    print("[kb_client.py] WARNING: pattern not found")

with open(kb_client_path, "w", encoding="utf-8") as f:
    f.write(content)

# Fix 3: import_api.py - KB upload integration
import_path = os.path.join(base, "tech-research", "internal", "app", "api", "import_api.py")
with open(import_path, "r", encoding="utf-8") as f:
    content = f.read()

if "from datetime import datetime" not in content:
    content = content.replace(
        "from typing import List, Optional, Dict, Any",
        "from typing import List, Optional, Dict, Any\nfrom datetime import datetime"
    )
if "import os" not in content[:300]:
    content = content.replace("import logging", "import os\nimport logging", 1)

kb_block = r"""
        # 7. 知识库上传（失败不阻塞导入）
        kb_stats = {"attempted": 0, "success": 0, "failed": 0}
        try:
            dataset_id = os.environ.get("EIPLITE_KB_DATASET_ID", "")
            if dataset_id:
                from kb.kb_client import create_kb_client
                from kb.markdown_gen import generate_article_summary, generate_deep_insight
                kb_client = create_kb_client()
                for item in body.articles:
                    article_id = url_hash_to_article_id.get(item.url_hash)
                    if not article_id:
                        continue
                    try:
                        matched = None
                        for a in body.analyses:
                            if a.article_url_hash == item.url_hash:
                                matched = a
                                break
                        src_name = item.source_code or "unknown"
                        md = generate_article_summary(
                            title=item.title, source_name=src_name, url=item.url,
                            summary_cn=matched.summary_cn if matched else "",
                            raw_summary=item.raw_summary or "",
                            category=matched.category if matched else None,
                            author=item.author, publish_time=item.publish_time,
                            value_score=matched.value_score if matched else None,
                        )
                        tags = {"source": src_name, "category": matched.category if matched else "", "lang": "zh", "kb_type": "article_summary"}
                        fname = f"{item.url_hash[:16]}_{item.title[:30]}.md"
                        kb_stats["attempted"] += 1
                        kb_file_id = kb_client.upload_file(content=md, filename=fname, tags=tags)
                        if kb_file_id:
                            mapping = KbMapping(article_id=article_id, kb_file_id=kb_file_id, kb_type="article_summary", uploaded_at=datetime.now())
                            session.add(mapping)
                            kb_stats["success"] += 1
                        else:
                            kb_stats["failed"] += 1
                    except Exception as kbe:
                        logger.warning("KB upload fail: %s %s", item.url_hash, str(kbe))
                        kb_stats["failed"] += 1
        except Exception as kbi:
            logger.warning("KB upload init error: %s", str(kbi))
"""

commit_marker = "        session.commit()"
content = content.replace(commit_marker, commit_marker + kb_block)
print("[import_api.py] Added KB upload integration")

with open(import_path, "w", encoding="utf-8") as f:
    f.write(content)

print("\n=== All 4 fixes applied ===")
