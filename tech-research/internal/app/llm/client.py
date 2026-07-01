"""大模型调用客户端（内部侧）

通过 httpx 直连 OpenAI 兼容的 /chat/completions 端点，
不经过中间 SDK（如 LangChain、OpenAI SDK）。
此模式在基线工程 baseline-builder 中经 25+ 处调用点验证。

包含：JSON 解析（json-repair）、重试策略（3次+随机 jitter）。
"""
import json
import logging
import random
import re
import time
from typing import Any

import httpx

logger = logging.getLogger("llm.client")


def call_llm(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float = 300.0,
) -> str:
    """调用大模型，返回文本内容

    入参：
        messages: 消息列表，格式 [{"role": "user", "content": "..."}]
        model: 模型名称，不传则使用环境变量 LLM_MODEL
        temperature: 温度，不传则使用环境变量 LLM_TEMPERATURE
        max_tokens: 最大 token 数，不传则使用环境变量 LLM_MAX_TOKENS
        timeout: 超时时间（秒），默认 300 秒

    出参：
        模型输出的文本内容字符串

    重试策略：
        3 次尝试，退避时间 0.1s / 0.3s / 1s，每次叠加 0-0.1s 随机 jitter
    """
    import os

    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    api_key = os.environ.get("LLM_API_KEY", "")
    default_model = os.environ.get("LLM_MODEL", "local-qwen3-235b-nothink-moe")
    default_temperature = float(os.environ.get("LLM_TEMPERATURE", "0.01"))
    default_max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
    user_id = os.environ.get("LLM_USER_ID", "013148")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model or default_model,
        "messages": messages,
        "temperature": temperature if temperature is not None else default_temperature,
        "max_tokens": max_tokens or default_max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "userid": user_id,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    logger.info(
        "LLM call: model=%s, messages=%d, timeout=%.0fs",
        payload["model"],
        len(messages),
        timeout,
    )

    RETRY_DELAYS = [0.1, 0.3, 1.0]
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            break
        except Exception as e:
            if attempt < 3:
                delay = RETRY_DELAYS[attempt - 1] + random.uniform(0, 0.1)
                logger.warning(
                    "LLM HTTP failed (attempt %d/3), retry in %.1fs: %s",
                    attempt, delay, e,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "LLM HTTP failed after 3 attempts: %s (type=%s)",
                    e, type(e).__name__,
                )
                raise

    content = data["choices"][0]["message"]["content"]
    logger.info("LLM response: %d chars", len(content))
    return content


def parse_llm_json(content: str) -> Any:
    """解析 LLM 返回的 JSON（兼容 code fence 包裹和格式问题）

    入参：
        content: LLM 返回的原始文本

    出参：
        解析后的 Python 对象（dict / list），解析失败抛出 json.JSONDecodeError

    解析策略依次尝试：
        1. 直接 json.loads
        2. json-repair 修复后解析
        3. 正则提取 JSON 数组 / 对象后解析
        4. 处理多个 JSON 对象拼接
    """
    text = content.strip()

    # 去除 code fence
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 1. 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. json-repair 修复
    try:
        return _repair_and_parse_json(text)
    except Exception:
        pass

    # 3. 提取 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            try:
                return _repair_and_parse_json(text[start : end + 1])
            except Exception:
                pass

    # 4. 提取 JSON 对象
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            try:
                return _repair_and_parse_json(text[start : end + 1])
            except Exception:
                pass

    # 5. 多个 JSON 对象（用 }{ 分隔）
    try:
        json_strings = re.findall(r"\{.*?\}", text, re.DOTALL)
        if json_strings:
            results = []
            for json_str in json_strings:
                try:
                    results.append(json.loads(json_str))
                except json.JSONDecodeError:
                    try:
                        results.append(_repair_and_parse_json(json_str))
                    except Exception:
                        continue
            if results:
                return results if len(results) > 1 else results[0]
    except Exception:
        pass

    raise json.JSONDecodeError(
        f"无法解析 LLM JSON 响应: {text[:100]}...", text, 0
    )


def _repair_and_parse_json(text: str) -> Any:
    """使用 json-repair 包修复并解析 JSON

    入参：
        text: 可能损坏的 JSON 文本

    出参：
        修复后的 JSON 解析结果
    """
    from json_repair import repair_json

    repaired = repair_json(text)
    return json.loads(repaired)
