# -*- coding: utf-8 -*-
import pathlib

path = pathlib.Path(r"D:\013148\code\AI技术趋势雷达\验证\API接口清单与验证方案.md")
content = path.read_text(encoding="utf-8")

content = content.replace("**\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd**", "**成功响应**")

lines = content.split("\n")

start = None
for i, line in enumerate(lines):
    if '"source_scope": ["aws-ml-blog", "arxiv-cs-ai"]' in line:
        start = i
        break

if start is None:
    print("NOT FOUND start")
    exit(1)

end = None
for i in range(start, len(lines)):
    if lines[i].strip() == "}" and i > start + 40:
        end = i
        break

if end is None:
    print("NOT FOUND end")
    exit(1)

new_block = [
    '    "source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"]',
    '  },',
    '  "articles": [',
    '    {',
    '      "url": "https://wechat2rss.bestblogs.dev/feed/e531a18b21c34cf787b83ab444eef659d7a980de.xml",',
    '      "source_code": "xin-zhi-yuan",',
    '      "url_hash": "<sha256hex>",',
    '      "title": "GPT-5 推理性能突破：从 MoE 到稠密架构的演进",',
    '      "author": "John Doe",',
    '      "publish_time": "2026-06-15T10:00:00",',
    '      "crawl_time": "2026-06-16T08:00:00",',
    '      "raw_summary": "OpenAI 发布 GPT-5 技术报告，披露新一代模型在推理基准上的重大提升...",',
    '      "full_content": "(完整原文，实际字段较长，此处省略)",',
    '      "content_hash": "<sha256hex>"',
    '    }',
    '  ],',
    '  "analyses": [',
    '    {',
    '      "article_url_hash": "<sha256hex>",',
    '      "summary_cn": "OpenAI 发布 GPT-5 技术报告，新模型在推理、数学、编码等基准上大幅超越 GPT-4，采用稠密 Transformer 架构替代 MoE 方案。",',
    '      "category": "大模型技术",',
    '      "keywords": ["GPT-5", "推理", "Transformer", "MoE", "稠密架构"],',
    '      "tech_tags": ["LLM 架构", "推理优化"],',
    '      "companies": ["OpenAI"],',
    '      "score_tech_depth": 8.0,',
    '      "score_engineering": 7.5,',
    '      "score_trend": 8.5,',
    '      "score_credibility": 9.0,',
    '      "score_timeliness": 9.0,',
    '      "value_score": 8.4,',
    '      "model_name": "saas-doubao-15-pro-32k",',
    '      "prompt_version": "v2.1"',
    '    }',
    '  ],',
    '  "insights": [',
    '    {',
    '      "article_url_hash": "<sha256hex>",',
    '      "technical_background": "GPT-4 及此前版本采用 Mixture of Experts (MoE) 架构以降低推理成本，但 MoE 引入的路由开销和专家负载不均问题限制了极致性能。",',
    '      "core_problem": "如何在保持推理效率的前提下，通过架构创新突破大模型性能天花板？",',
    '      "technical_solution": "GPT-5 回归稠密 Transformer 架构，通过训练稳定性改进、注意力机制优化和超大规模并行训练策略实现更优的性能/成本比。",',
    '      "impact_analysis": "该架构选择可能影响未来 1-2 年大模型技术路线，稠密架构的复兴将对 GPU 显存、互联带宽提出更高要求。",',
    '      "reference_value": "内部 LLM 选型和架构评估时，需关注稠密 vs MoE 的工程化差异，尤其推理部署阶段的资源规划。",',
    '      "model_name": "saas-doubao-15-pro-32k",',
    '      "prompt_version": "v2.1"',
    '    }',
    '  ]',
    '}',
]

result = lines[:start] + new_block + lines[end+1:]
path.write_text("\n".join(result), encoding="utf-8")
print("SUCCESS: replaced import example + fixed encoding")
