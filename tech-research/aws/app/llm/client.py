"""
AWS 侧 LLM 客户端封装

封装外部大模型 API 调用（OpenAI / Claude 等），提供统一接口。
支持自动重试、超时控制、并发限制、Prompt 版本追踪。
"""
import json
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI

from logging_config import get_logger

logger = get_logger("llm.client")


class LLMClient:
    """
    外部大模型调用客户端

    封装 OpenAI 兼容 API 调用，支持重试和并发控制。
    每条分析记录落盘 model_name 和 prompt_version 用于追踪。

    类变量：
        client: OpenAI SDK 客户端实例
        max_concurrency: 信号量控制的最大并发数（需结合 asyncio 使用）
        max_retries: 单次调用最大重试次数
        timeout: 请求超时秒数
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        max_retries: int = 2,
        timeout: int = 60,
    ):
        """
        初始化 LLM 客户端

        入参：
            api_key: OpenAI API Key
            base_url: 自定义 API Base URL（Claude 代理等）
            max_retries: 最大重试次数
            timeout: 请求超时秒数
        """
        import httpx
        http_client = httpx.Client(
            timeout=timeout,
            trust_env=False,    # 忽略 Windows 系统代理设置，关键是这个
        )
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={"userid": "013148"},  # 临时：本地测试内部大模型需要此 header
            http_client=http_client,
        )
        self.max_retries = max_retries
        self.timeout = timeout

    def call(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_json: bool = False,
    ) -> Dict[str, Any]:
        """
        调用 LLM，自动重试

        入参：
            messages: 消息列表 [{"role": "system", "content": "..."}, ...]
            model: 模型名称，如 gpt-4o-mini
            temperature: 生成温度
            max_tokens: 最大输出 token
            response_json: 是否要求 JSON 格式响应
        出参：{"success": bool, "content": str, "model": str, "usage": {...}}
        """
        logger.info("调用 LLM: model=%s, messages_count=%d", model, len(messages))

        for attempt in range(self.max_retries + 1):
            try:
                kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_json:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)
                # 兼容内部 API 响应格式：某些实现可能返回 dict 或字符串
                if isinstance(response, str):
                    import json
                    response = json.loads(response)
                    response = type('ChatCompletion', (), {
                        'choices': [type('Choice', (), {
                            'message': type('Message', (), {'content': response.get('choices', [{}])[0].get('message', {}).get('content', '')})()
                        })()],
                        'usage': response.get('usage', {})
                    })()
                    usage_raw = response.usage
                elif hasattr(response, 'usage'):
                    usage_raw = response.usage
                else:
                    usage_raw = None
                # 规范化 usage
                if usage_raw is None:
                    usage = {}
                elif hasattr(usage_raw, 'model_dump'):
                    usage = usage_raw.model_dump()
                elif isinstance(usage_raw, dict):
                    usage = usage_raw
                else:
                    usage = {"total_tokens": str(usage_raw)}
                # 提取响应文本
                content = response.choices[0].message.content or ""

                logger.info(
                    "LLM 调用成功: model=%s, tokens=%s",
                    model, usage.get("total_tokens", "N/A")
                )
                return {
                    "success": True,
                    "content": content,
                    "model": model,
                    "usage": usage,
                }

            except Exception as e:
                logger.warning(
                    "LLM 调用失败 (attempt %d/%d): %s",
                    attempt + 1, self.max_retries + 1, str(e)
                )
                if attempt < self.max_retries:
                    wait = 10 if attempt == 0 else 30
                    logger.info("等待 %d 秒后重试...", wait)
                    time.sleep(wait)
                else:
                    logger.error("LLM 调用最终失败: %s", str(e))
                    return {"success": False, "error": str(e), "model": model}

    def parse_json_response(self, result: Dict[str, Any]) -> Optional[Dict]:
        """
        从 LLM 响应中解析 JSON

        入参：
            result: call() 返回的结果字典
        出参：解析后的 JSON 字典，解析失败返回 None
        """
        if not result.get("success"):
            return None
        content = result.get("content", "").strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 ```json ... ``` 代码块
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

            # Try to repair truncated JSON (LLM output may hit max_tokens)
            try:
                repaired = _repair_truncated_json(content)
                if repaired:
                    return json.loads(repaired)
            except json.JSONDecodeError:
                pass

            logger.error("LLM response not JSON: %s", content[:200])
            return None


def _repair_truncated_json(text):
    """
    Repair truncated JSON from LLM output.
    Counts unmatched braces/brackets and appends closing chars.
    Returns repaired JSON string or None.
    """
    brace_depth = 0
    bracket_depth = 0
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth -= 1

    if brace_depth == 0 and bracket_depth == 0 and not in_string:
        return None
    if brace_depth < 0 or bracket_depth < 0:
        return None

    repaired = text
    if in_string:
        repaired += '"'
    for _ in range(bracket_depth):
        repaired += "]"
    for _ in range(brace_depth):
        repaired += "}"

    return repaired

