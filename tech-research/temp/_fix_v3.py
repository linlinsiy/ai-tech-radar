import pathlib
import hashlib

root = pathlib.Path(r"D:\013148\code")
d = [x for x in root.iterdir() if x.is_dir() and "技术趋势" in x.name][0]
md_file = list((d / "验证").glob("API*.md"))[0]
content = md_file.read_bytes()

# --- Real hashes ---
url_xz = "https://wechat2rss.bestblogs.dev/feed/e531a18b21c34cf787b83ab444eef659d7a980de.xml"
url_lw = "https://www.qbitai.com/feed"
url_arx = "http://export.arxiv.org/rss/cs.AI"
uh_xz = hashlib.sha256(url_xz.encode()).hexdigest()
uh_lw = hashlib.sha256(url_lw.encode()).hexdigest()
uh_arx = hashlib.sha256(url_arx.encode()).hexdigest()

fc1_txt = "(完整原文，本文长约1500字，含标题与正文，实际入库时为完整HTML/文本，此处省略)"
ch1 = hashlib.sha256(fc1_txt.encode()).hexdigest()
fc2_txt = "(完整原文，本文约800字，实际入库字段较长，此处省略)"
ch2 = hashlib.sha256(fc2_txt.encode()).hexdigest()
fc3_txt = "(完整原文，arXiv论文摘要及全文链接，此处省略)"
ch3 = hashlib.sha256(fc3_txt.encode()).hexdigest()

# Build the COMPLETE request body JSON matching actual AnalysisItem/InsightItem schemas
req_body = rf"""{{
  "batch": {{
    "batch_no": "IMP-20260616-001",
    "task_type": "scheduled",
    "source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]
  }},
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
      "full_content": "{fc1_txt}",
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
      "full_content": "{fc2_txt}",
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
      "full_content": "{fc3_txt}",
      "content_hash": "{ch3}"
    }}
  ],
  "analyses": [
    {{
      "article_url_hash": "{uh_xz}",
      "summary_cn": "本文报道 OpenAI GPT-5 的最新进展：采用 MoE 混合专家架构，推理能力显著提升，成本下降约40%。GPT-5 预计2026年Q3开放API，这将进一步推动企业级AI应用的普及。",
      "keywords": ["GPT-5", "MoE", "大模型", "OpenAI", "推理成本"],
      "tech_tags": ["大模型进展", "MoE架构"],
      "companies": ["OpenAI"],
      "score_tech_depth": 6.5,
      "score_engineering": 4.0,
      "score_trend": 8.5,
      "score_credibility": 9.0,
      "score_timeliness": 9.5
    }},
    {{
      "article_url_hash": "{uh_xz}",
      "summary_cn": "GPT-5 转向 MoE 架构是 OpenAI 应对大模型训练成本压力的关键信号。MoE 架构通过稀疏激活仅调用部分专家参数，在保持模型容量的同时降低推理成本。结合近期 Google Gemini 3 和 Anthropic Claude 4 均采用 MoE 变体的趋势，判断 2026 年将成为 MoE 架构从实验走向主流部署的转折点。建议持续跟踪各厂商 MoE 具体实现（如专家路由策略、负载均衡方案）以及对应的硬件适配方案。",
      "keywords": ["MoE", "模型架构", "推理成本", "行业趋势"],
      "tech_tags": ["技术洞察", "MoE架构"],
      "companies": ["OpenAI", "Google", "Anthropic"],
      "score_tech_depth": 8.5,
      "score_engineering": 5.0,
      "score_trend": 9.0,
      "score_credibility": 8.5,
      "score_timeliness": 9.5
    }}
  ],
  "insights": [
    {{
      "article_url_hash": "{uh_xz}",
      "technical_background": "2025年以来，大模型训练与推理成本持续上升，成为限制AI应用大规模部署的主要瓶颈。传统Dense架构所有参数在每次推理中均被激活，导致计算资源需求随模型规模线性增长。",
      "core_problem": "如何在保持模型容量的同时大幅降低推理成本？MoE（Mixture-of-Experts）架构通过稀疏激活机制提供了潜在解决方案，但其工程实现复杂，路由策略与负载均衡方案仍在快速迭代中。",
      "technical_solution": "MoE 架构将模型参数划分为多个专家子网络，每次推理仅激活部分专家（通常 1-3 个），从而在几乎不损失模型容量的前提下将推理成本降低 40%-70%。各厂商实现差异主要集中在：(1) 专家路由算法（Top-K vs 随机路由）；(2) 负载均衡策略（辅助损失 vs 容量因子）；(3) 硬件适配（GPU 显存布局优化）。",
      "impact_analysis": "MoE 架构的成熟将从根本上改变大模型的部署经济学。预计 2026 年下半年起，基于 MoE 的 API 服务将逐步取代 Dense 模型成为主流，推理成本下降将推动 AI 应用在边缘设备和企业私有化部署场景的爆发。",
      "reference_value": "建议内部技术雷达持续跟踪各主要厂商（OpenAI、Google、Anthropic、Meta）的 MoE 具体实现方案，特别关注各自的路由策略和专家负载均衡方法，这些细节将直接影响我们在私有化部署场景中的技术选型。"
    }}
  ]
}}"""

# Find and replace: from "source_scope": [...] through to "- **成功响应**"
old_marker = b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]\r\n```\r\n\r\n- **'
new_block = req_body.encode('utf-8') + b'\r\n```\r\n\r\n- **'

idx = content.find(old_marker)
if idx < 0:
    # Try without \r
    old_marker = b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]\n```\n\n- **'
    idx = content.find(old_marker)
    if idx >= 0:
        new_block = req_body.encode('utf-8') + b'\n```\n\n- **'

if idx >= 0:
    content = content[:idx] + b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]\n' + new_block[len(b'"source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]\n'):] + content[idx+len(old_marker):]
    md_file.write_bytes(content)
    print("SUCCESS: Document updated with complete schema-compliant payload")
else:
    print("FAILED: marker not found")
    # Debug
    idx2 = content.find(b'source_scope')
    if idx2 >= 0:
        print("Around source_scope:", repr(content[idx2:idx2+400]))
