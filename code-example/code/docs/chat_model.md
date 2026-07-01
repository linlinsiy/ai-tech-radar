# 聊天模型（Chat Model）

本文档介绍如何使用 talentsview-sdk 和 langchain-htai 调用大语言模型（LLM）。

## 功能概述

聊天模型是与 AI 对话的核心功能，支持：

- **多种调用模式**：同步/异步、流式/非流式
- **推理模型支持**：支持 DeepSeek、Qwen 等推理模型的 thinking 模式
- **OpenAI 兼容**：接口设计符合 OpenAI SDK 规范
- **LangChain 集成**：langchain-htai 提供便捷方法get_llm()快速获取标准 LangChain LLM组件

## 1. talentsview-sdk

### 1.1 功能介绍

talentsview-sdk 提供 `LLMClient` 和 `AsyncLLMClient` 两个客户端类，支持四种调用模式的组合：

| 调用方式 | 同步 | 异步 |
|---------|------|------|
| **非流式** | `LLMClient` + `stream=False` | `AsyncLLMClient` + `stream=False` |
| **流式** | `LLMClient` + `stream=True` | `AsyncLLMClient` + `stream=True` |

### 1.2 基本调用示例

#### 1.2.1 同步调用（非流式 + 流式）

```python
from talentsview import LLMClient

# 创建 LLM 客户端
client = LLMClient(model="local-qwen3-235b-nothink-moe")

# 非流式调用
response = client.chat.completions.create(
    model=client.model,
    messages=[{"role": "user", "content": "你好"}],
    stream=False
)
content = response.choices[0].message.content
print(content)

# 流式调用
stream = client.chat.completions.create(
    model=client.model,
    messages=[{"role": "user", "content": "介绍一下Python"}],
    stream=True
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end='', flush=True)
```

#### 1.2.2 异步调用（非流式 + 流式）

```python
import asyncio
from talentsview import AsyncLLMClient

async def main():
    # 创建异步 LLM 客户端
    client = AsyncLLMClient(model="local-qwen3-235b-nothink-moe")
    
    # 异步非流式调用
    response = await client.chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": "你好"}],
        stream=False
    )
    content = response.choices[0].message.content
    print(content)
    
    # 异步流式调用
    stream = await client.chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": "介绍一下Python"}],
        stream=True
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)

# 运行异步函数
asyncio.run(main())
```

### 1.3 参数说明

#### 1.3.1 客户端初始化参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 是 | - |
| llm_url | str | LLM 服务 URL | 否 | 自动从配置中心获取 |
| app_id | str | 应用 ID | 否 | 推荐从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 推荐环境变量获取 |
| http_client | httpx.Client | 同步 HTTP 客户端 | 否 | 默认使用SDK全局单例 |
| http_async_client | httpx.AsyncClient | 异步 HTTP 客户端 | 否 | 默认使用SDK全局单例 |

#### 1.3.2 调用参数（chat.completions.create）

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 是 | - |
| messages | List[dict] | 对话消息列表 | 是 | - |
| stream | bool | 是否流式返回 | 否 | False |
| temperature | float | 采样温度（0.0-2.0） | 否 | 1.0 |
| max_tokens | int | 最大生成 token 数 | 否 | 无限制 |
| top_p | float | 核采样参数 | 否 | 1.0 |
| frequency_penalty | float | 频率惩罚 | 否 | 0.0 |
| presence_penalty | float | 存在惩罚 | 否 | 0.0 |

**OpenAI SDK 兼容性**：talentsview-sdk 基于 OpenAI Python SDK 封装，调用方式与 OpenAI 完全一致。详细参数请参考 [OpenAI API 文档](https://platform.openai.com/docs/api-reference/chat)。

**推理模型（Reasoning Model）使用说明**：

如需启用推理模式（thinking），请在调用 `chat.completions.create()` 时传入 `extra_body` 参数。目前支持以下三款推理模型：

| 模型名称 | extra_body 配置 | 说明 |
|---------|----------------|------|
| saas-deepseek-v31 | `{"thinking": {"type": "enabled"}}` | SaaS 版外部模型|
| local-deepseek-v31 | `{"chat_template_kwargs": {"thinking": True}}` | 本地部署模型 |
| local-qwen3-32b | （默认开启思考） | 本地部署 Qwen3，关闭需在 prompt 中拼接 `/no_think` |

示例代码：

```python
from talentsview import LLMClient

# SaaS DeepSeek R1
client = LLMClient(model="saas-deepseek-v31")
response = client.chat.completions.create(
    model=client.model,
    messages=[{"role": "user", "content": "分析一下为什么天空是蓝色的"}],
    extra_body={"thinking": {"type": "enabled"}}
)

# 本地 DeepSeek R1
client = LLMClient(model="local-deepseek-v31")
response = client.chat.completions.create(
    model=client.model,
    messages=[{"role": "user", "content": "分析一下为什么天空是蓝色的"}],
    extra_body={"chat_template_kwargs": {"thinking": True}}
)

```


## 2. langchain-htai

### 2.1 功能介绍

langchain-htai 提供两个便捷函数用于创建 LangChain 兼容的 LLM 实例：

- **`get_llm()`**：返回标准 `ChatOpenAI` 实例，适用于普通对话模型
- **`get_reasoning_llm()`**：返回 `ChatDeepSeek` 推理模型实例，支持推理模式（thinking）便捷开关

返回的实例是原生 LangChain 对象，可直接用于 chains、agents、RAG 等所有 LangChain 组件。

**推理模型说明**：`get_reasoning_llm()` 提供 `enable_thinking` 参数便捷控制推理模式，目前支持以下模型：

| 模型名称 | enable_thinking=True | enable_thinking=False | 说明 |
|---------|---------------------|----------------------|------|
| saas-deepseek-v31 | 启用思考 | 禁用思考 | SaaS 版 DeepSeek R1 |
| local-deepseek-v31 | 启用思考 | 禁用思考 | 本地部署 DeepSeek R1 |
| local-qwen3-32b | （默认开启） | （不支持关闭） | 本地 Qwen3，需在 prompt 中拼接 `/no_think` 关闭 |

### 2.2 基本调用示例

#### 2.2.1 同步调用（非流式 + 流式）

```python
from langchain_htai import get_llm

# 获取 LangChain LLM 实例
llm = get_llm(model="local-qwen3-235b-nothink-moe")

# 非流式调用
response = llm.invoke("你好，请介绍一下自己")
print(response.content)

# 流式调用
for chunk in llm.stream("介绍一下Python"):
    if chunk.content:
        print(chunk.content, end='', flush=True)
```

#### 2.2.2 异步调用（非流式 + 流式）

```python
import asyncio
from langchain_htai import get_llm

async def main():
    llm = get_llm(model="local-qwen3-235b-nothink-moe")
    
    # 异步调用
    response = await llm.ainvoke("你好")
    print(response.content)
    
    # 异步流式调用
    async for chunk in llm.astream("介绍Python"):
        if chunk.content:
            print(chunk.content, end='', flush=True)

asyncio.run(main())
```

#### 2.2.3 推理模型调用（非流式 + 流式）

```python
from langchain_htai import get_reasoning_llm

# 创建推理模型（默认启用 thinking）
reasoning_llm = get_reasoning_llm(model="local-deepseek-v31")

# 非流式调用
response = reasoning_llm.invoke("分析一下为什么天空是蓝色的")
print(response.content)

# 流式调用
for chunk in reasoning_llm.stream("计算 15 的阶乘"):
    if chunk.content:
        print(chunk.content, end='', flush=True)

# 禁用 thinking 模式（仅支持 DeepSeek 系列）
normal_llm = get_reasoning_llm(
    model="local-deepseek-v31",
    enable_thinking=False
)

response = normal_llm.invoke("你好")
print(response.content)
```

### 2.3 参数说明

#### 2.3.1 get_llm() 参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 是 | "local-qwen3-235b-nothink-moe" |
| llm_url | str | LLM 服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| temperature | float | 采样温度 | 否 | 1.0 |
| max_tokens | int | 最大生成 token 数 | 否 | 无限制 |
| **kwargs | Any | 其他 ChatOpenAI 参数 | 否 | - |

#### 2.3.2 get_reasoning_llm() 参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 推理模型名称 | 是 | "local-deepseek-v31" |
| enable_thinking | bool | 是否启用推理模式 | 否 | True |
| llm_url | str | LLM 服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| temperature | float | 采样温度 | 否 | 1.0 |
| max_tokens | int | 最大生成 token 数 | 否 | 无限制 |
| **kwargs | Any | 其他 ChatDeepSeek 参数 | 否 | - |

**注意**：`get_reasoning_llm()` 会根据模型类型自动配置对应的 `extra_body` 参数，无需手动配置。

### 2.4 LangChain Agent 集成示例

以下示例展示如何使用 `get_llm()` 和 `get_web_search_tool()` 创建一个具备联网搜索能力的 Agent：

```python
from langchain_htai import get_llm, get_web_search_tool
from langchain.agents import create_agent

# 创建 LLM
llm = get_llm(model="local-qwen3-235b-nothink-moe", temperature=0)

# 创建 Web 搜索工具
web_search_tool = get_web_search_tool()

# 创建 Agent
agent = create_agent(
    model=llm,
    tools=[web_search_tool]
)

# 使用 Agent
response = agent.invoke({
    "messages": [{"role": "user", "content": "2024年诺贝尔物理学奖颁发给了谁？"}]
})

print(response["messages"][-1].content)
```

**说明**：
- `get_web_search_tool()` 返回符合 LangChain Tool 协议的 Web 搜索工具
- `create_agent()` 是 LangChain v1 的标准 React Agent 创建方法，会自动决定何时调用搜索工具获取实时信息


## 相关文档

- [安装与配置指南](installation.md)
- [向量化文档](embedding.md)
- [重排序文档](rerank.md)

---

返回 [主文档](../README.md)
