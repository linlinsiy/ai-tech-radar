"""内部侧 LLM 调用模块

包含：
    client.py: call_llm() 大模型调用 + parse_llm_json() JSON 解析
    prompt_manager.py: Jinja2 Prompt 模板管理
"""
from llm.client import call_llm, parse_llm_json
from llm.prompt_manager import PromptManager

__all__ = ["call_llm", "parse_llm_json", "PromptManager"]
