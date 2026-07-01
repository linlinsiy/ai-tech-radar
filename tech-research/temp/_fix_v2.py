import pathlib
import hashlib
import re
import json

# --- File paths ---
root = pathlib.Path(r"D:\013148\code")
target_dir = [x for x in root.iterdir() if x.is_dir() and "技术趋势" in x.name][0]
md_file = list((target_dir / "验证").glob("API*.md"))[0]

content = md_file.read_bytes()

# --- Generate real hashes ---
url_xz = "https://wechat2rss.bestblogs.dev/feed/e531a18b21c34cf787b83ab444eef659d7a980de.xml"
url_lw = "https://www.qbitai.com/feed"
url_arx = "http://export.arxiv.org/rss/cs.AI"

uh_xz = hashlib.sha256(url_xz.encode()).hexdigest()
uh_lw = hashlib.sha256(url_lw.encode()).hexdigest()
uh_arx = hashlib.sha256(url_arx.encode()).hexdigest()

fc1 = "(完整原文，本文长约1500字，含标题与正文，实际入库时为完整HTML/文本，此处省略)"
ch1 = hashlib.sha256(fc1.encode()).hexdigest()
fc2 = "(完整原文，本文约800字，实际入库字段较长，此处省略)"
ch2 = hashlib.sha256(fc2.encode()).hexdigest()
fc3 = "(完整原文，arXiv论文摘要及全文链接，此处省略)"
ch3 = hashlib.sha256(fc3.encode()).hexdigest()

print(f"url_hash xin-zhi-yuan: {uh_xz}")
print(f"url_hash liangziwei: {uh_lw}")
print(f"url_hash arxiv: {uh_arx}")
print(f"content_hash 1: {ch1}")
print(f"content_hash 2: {ch2}")
print(f"content_hash 3: {ch3}")

# --- Build replacement: complete request body JSON ---
articles_block = f"""  }},
  "articles": [
    {{
      "url": "{url_xz}",
      "source_code": "xin-zhi-yuan",
      "url_hash": "{uh_xz}",
      "title": "GPT-5 训练取得突破：采用 MoE 混合专家架构，推理能力大幅提升",
      "author": "新智元编辑部",
      "publish_time": "2026-06-15T10:00:00+08:00",
      "crawl_time": "2026-06-16T08:00:00+08:00",
      "raw_summary": "OpenAI 发布 GPT-5 最新进展，新模型采用 MoE 架构，在多项推理基准上取得重大突破，同时推理成本下降约 40%，预计2026年Q3开放API...",
      "full_content": "{fc1}",
      "content_hash": "{ch1}"
    }},
    {{
      "url": "{url_lw}",
      "source_code": "liangziwei",
      "url_hash": "{uh_lw}",
      "title": "多模态大模型竞争加剧：谷歌 Gemini 3 与 Anthropic Claude 4 对比评测",
      "author": "量子位编辑部",
      "publish_time": "2026-06-14T18:00:00+08:00",
      "crawl_time": "2026-06-16T08:00:00+08:00",
      "raw_summary": "谷歌最新发布的 Gemini 3 与 Anthropic 的 Claude 4 在多模态基准测试中展开激烈竞争，双方各有所长...",
      "full_content": "{fc2}",
      "content_hash": "{ch2}"
    }},
    {{
      "url": "{url_arx}",
      "source_code": "arxiv-cs-ai",
      "url_hash": "{uh_arx}",
      "title": "Scaling Laws for Mixture-of-Experts Transformers",
      "author": "Smith J., Chen L. et al.",
      "publish_time": "2026-06-13T00:00:00+00:00",
      "crawl_time": "2026-06-16T08:00:00+08:00",
      "raw_summary": "本文系统研究了 MoE Transformer 架构的缩放定律，发现专家数量与训练效率之间存在非线性关系...",
      "full_content": "{fc3}",
      "content_hash": "{ch3}"
    }}
  ],
  "analyses": [
    {{
      "article_url_hash": "{uh_xz}",
      "analysis_type": "l2_summary",
      "model": "saas-doubao-15-pro-32k",
      "content": "本文报道 OpenAI GPT-5 的最新进展：采用 MoE 混合专家架构，推理能力显著提升，成本下降约40%。GPT-5 预计2026年Q3开放API，这将进一步推动企业级AI应用的普及。",
      "tags": [
        {{"name": "category", "value": "大模型进展"}},
        {{"name": "lang", "value": "zh"}},
        {{"name": "kb_type", "value": "article_summary"}}
      ]
    }},
    {{
      "article_url_hash": "{uh_xz}",
      "analysis_type": "l3_deep_insight",
      "model": "saas-doubao-15-pro-32k",
      "content": "GPT-5 转向 MoE 架构是 OpenAI 应对大模型训练成本压力的关键信号。MoE 架构通过稀疏激活仅调用部分专家参数，在保持模型容量的同时降低推理成本。结合近期 Google Gemini 3 和 Anthropic Claude 4 均采用 MoE 变体的趋势，判断 2026 年将成为 MoE 架构从实验走向主流部署的转折点。建议持续跟踪各厂商 MoE 具体实现（如专家路由策略、负载均衡方案）以及对应的硬件适配方案。",
      "tags": [
        {{"name": "category", "value": "技术洞察"}},
        {{"name": "lang", "value": "zh"}},
        {{"name": "kb_type", "value": "deep_insight"}}
      ]
    }}
  ],
  "insights": [
    {{
      "insight_type": "cross_source_trend",
      "title": "MoE 架构成为 2026 年大模型标配",
      "related_article_hashes": ["{uh_xz}", "{uh_lw}"],
      "content": "跨来源扫描发现：GPT-5、Gemini 3、Claude 4 均采用 MoE 架构。判断 2026 年是 MoE 从实验走向主流部署的关键年，推理成本下降将成为AI应用爆发的催化剂。",
      "tags": [
        {{"name": "category", "value": "跨来源趋势"}},
        {{"name": "kb_type", "value": "trend_insight"}}
      ]
    }}
  ]"""

# --- Find the insertion point ---
# Current structure: "...source_scope": [...]" + "\n```\n\n- **成功响应**"
# We want to replace the fragment from after "source_scope" line through the "```" to "- **成功响应**"
old_marker = b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]\r\n```\r\n\r\n- **'
# New content: keep source_scope, add articles/analyses/insights, close JSON, then continue with headings
new_block = (b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"],\r\n'
             + articles_block.encode('utf-8')
             + b'\r\n}\r\n```\r\n\r\n- **')

idx = content.find(old_marker)
if idx < 0:
    print("ERROR: marker not found!")
    # try without \r
    old_marker2 = b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]\n```\n\n- **'
    idx = content.find(old_marker2)
    if idx >= 0:
        new_block = (b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"],\n'
                     + articles_block.encode('utf-8')
                     + b'\n}\n```\n\n- **')
        old_marker = old_marker2

if idx >= 0:
    content = content[:idx] + new_block + content[idx+len(old_marker):]
    md_file.write_bytes(content)
    print("SUCCESS: Document updated with articles/analyses/insights blocks")
else:
    print("FAILED: Could not find insertion point")
    # Debug: show what's around source_scope
    idx2 = content.find(b'source_scope')
    if idx2 >= 0:
        print("Around source_scope:", repr(content[idx2:idx2+200]))
