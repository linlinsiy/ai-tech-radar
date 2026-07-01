"""
Prompt模板管理

集中管理Agent使用的各类Prompt模板
"""

# 搜索决策判断Prompt
SEARCH_DECISION_PROMPT = """你是一个智能助手，可以使用联网搜索工具获取实时信息。

可用工具：
- search: 联网搜索工具，用于获取最新信息、新闻、实时数据等

请判断以下问题是否需要使用search工具：

问题：{user_question}

请以JSON格式返回你的决策：
{{
  "need_search": true/false,
  "search_query": "搜索关键词（仅当need_search=true时填写）",
  "reason": "判断理由"
}}

判断标准：
- 需要搜索：涉及最新新闻、实时数据、当前日期相关信息、最近发生的事件
- 无需搜索：常识性问题、技术概念解释、逻辑推理、数学计算等

重要：请直接返回JSON，不要包含其他文字说明。"""


# 基于搜索结果生成答案的Prompt
ANSWER_WITH_CONTEXT_PROMPT = """以下是通过联网搜索获取的相关信息：

{search_results}

请基于以上信息回答用户的问题：{user_question}

要求：
1. 只使用提供的搜索信息
2. 如果信息不足以回答问题，请明确说明
3. 回答要准确、简洁、有条理"""


# 无需搜索时的直接回答Prompt
DIRECT_ANSWER_PROMPT = """请回答以下问题：{user_question}

要求：回答要准确、简洁、有条理"""


def build_search_decision_prompt(user_question: str) -> str:
    """构造搜索决策判断的Prompt
    
    Args:
        user_question: 用户的问题
        
    Returns:
        完整的Prompt字符串
    """
    return SEARCH_DECISION_PROMPT.format(user_question=user_question)


def build_answer_with_context_prompt(user_question: str, search_results: str) -> str:
    """构造基于搜索结果生成答案的Prompt
    
    Args:
        user_question: 用户的问题
        search_results: 搜索结果文本
        
    Returns:
        完整的Prompt字符串
    """
    return ANSWER_WITH_CONTEXT_PROMPT.format(
        user_question=user_question,
        search_results=search_results
    )


def build_direct_answer_prompt(user_question: str) -> str:
    """构造直接回答的Prompt
    
    Args:
        user_question: 用户的问题
        
    Returns:
        完整的Prompt字符串
    """
    return DIRECT_ANSWER_PROMPT.format(user_question=user_question)
