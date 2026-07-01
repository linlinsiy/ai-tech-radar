# 联网搜索（Web Search）

本文档介绍如何使用 talentsview-sdk 和 langchain-htai 进行联网搜索。

## 入参说明

联网搜索的主要参数如下：

| 参数名 | 类型 | 说明 | 必填 | 默认值 | 取值范围/示例 |
|-------|------|------|------|--------|--------------|
| query | str | 搜索查询内容 | 是 | - | 1-50个字符 |
| count | int | 返回结果数量 | 否 | 10 | 最多50条 |
| time_range | str | 发文时间范围 | 否 | None | OneDay, OneWeek, OneMonth, OneYear, YYYY-MM-DD..YYYY-MM-DD |
| clean | bool | 是否返回清洗后的文本 | 否 | True（langchain-htai）<br/>False（talentsview-sdk） | True/False |

**注意事项**：
- ⚠️ **并发限制**：联网搜索服务当前存在并发限制，高并发场景下需控制请求频率
- 建议在生产环境中合理设置请求间隔

## 1. talentsview-sdk

### 1.1 功能介绍

talentsview-sdk 提供 `WebSearch` 和 `AsyncWebSearch` 两个客户端类，支持：

- **结构化返回**：默认返回 `List[WebSearchItem]` Pydantic 模型，类型安全
- **清洗模式**：可选择返回 LLM 友好的清洗后文本
- **参数化搜索**：支持结果数量、时间范围等参数
- **同步/异步调用**：支持同步和异步两种调用方式

### 1.2 基本调用

```python
from talentsview import WebSearch

# 创建客户端
searcher = WebSearch()

# 默认返回 List[WebSearchItem] Pydantic 模型
results = searcher.search(query="Python编程", count=3)

# Pydantic 模型访问（推荐，类型安全）
for item in results:
    print(f"标题: {item.title}")
    print(f"URL: {item.url}")
    print(f"摘要: {item.snippet}")
    print(f"权威度: {item.auth_info_level}\n")

# 向后兼容：也支持字典式访问
print(results[0]['title'])  # Python风格
print(results[0]['Title'])  # API原始字段名
```

### 1.3 清洗模式（LLM 友好）

```python
from talentsview import WebSearch

searcher = WebSearch()

# clean=True 返回清洗后的字符串，适合直接给 LLM 使用
clean_text = searcher.search(
    query="机器学习应用",
    count=3,
    clean=True
)

print(type(clean_text))  # <class 'str'>
print(clean_text[:300])  # 清洗后的文本
```

### 1.4 异步调用

```python
import asyncio
from talentsview import AsyncWebSearch

async def main():
    searcher = AsyncWebSearch()
    
    # 异步搜索，返回 List[WebSearchItem]
    results = await searcher.search(
        query="深度学习",
        count=5
    )
    
    print(f"找到 {len(results)} 条结果")
    for item in results:
        print(f"- {item.title}")

asyncio.run(main())
```

### 1.5 参数说明

#### 1.5.1 客户端初始化参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| search_url | str | 搜索服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| timeout | float | 请求超时时间（秒） | 否 | 30.0 |
| http_client | httpx.Client | 同步 HTTP 客户端 | 否 | 使用全局单例 |

#### 1.5.2 search() 方法参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| query | str | 搜索查询内容（1-100字符） | 是 | - |
| count | int | 返回结果数量（最多50条） | 否 | 10 |
| time_range | str | 时间范围 | 否 | None |
| clean | bool | 是否返回清洗后的文本 | 否 | False |

**time_range 取值**：
- `"OneDay"`：最近一天
- `"OneWeek"`：最近一周
- `"OneMonth"`：最近一个月
- `"OneYear"`：最近一年
- `"YYYY-MM-DD..YYYY-MM-DD"`：自定义日期范围（如 "2024-01-01..2024-01-31"）

#### 1.5.3 返回值说明

**clean=False 时**（默认）：

返回 `List[WebSearchItem]` Pydantic 模型列表，每个 `WebSearchItem` 包含：

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| id | str | 是 | 结果ID |
| sort_id | int | 是 | 排序ID |
| title | str | 是 | 标题 |
| snippet | str | 是 | 普通摘要（约100字） |
| auth_info_des | str | 是 | 权威度描述 |
| auth_info_level | int | 是 | 权威度评级（1-4） |
| site_name | str | 否 | 站点名 |
| url | str | 否 | 落地页URL |
| summary | str | 否 | 精准摘要（300-500字） |
| content | str | 否 | 正文内容 |
| publish_time | str | 否 | 发布时间（ISO格式） |
| logo_url | str | 否 | 站点图标URL |
| rank_score | float | 否 | 排序得分 |

**向后兼容**：WebSearchItem 支持字典式访问，可以使用 `item['title']` 或 `item.title`。

**clean=True 时**：

返回 `str`，清洗后的文本字符串，适合直接作为 LLM 上下文。


### 1.6 注意事项

1. **并发限制**：
   - 联网搜索服务当前存在并发限制
   - 高并发场景下需控制请求频率，建议添加请求间隔
   - 生产环境建议使用异步调用配合并发控制

2. **查询优化**：
   - 查询长度限制在 1-50 个字符
   - 使用精确的关键词可提高搜索质量
   - 避免过于宽泛的查询



## 2. langchain-htai

### 2.1 功能介绍

langchain-htai 提供 `get_web_search_tool()` 函数，返回符合 LangChain 标准的 Tool：

- **LangChain Tool 协议**：继承自 `BaseTool`，完全兼容 Agent
- **默认 LLM 友好**：默认 `clean=True`，返回清洗后的文本
- **两种调用方式**：`invoke()`/`ainvoke()`（Agent用）、`search()`/`asearch()`（直接调用）

### 2.2 基本调用

```python
from langchain_htai import get_web_search_tool

# 创建工具（默认 clean=True）
tool = get_web_search_tool()

# 便捷方法调用
result = tool.search(query="Python编程", count=3)
print(type(result))  # <class 'str'>
print(result[:200])

# LangChain 标准方式
result = tool.invoke({"query": "人工智能", "count": 3})
print(result[:200])
```

### 2.3 异步调用

```python
import asyncio
from langchain_htai import get_web_search_tool

async def main():
    tool = get_web_search_tool()
    
    # 异步便捷方法
    result = await tool.asearch(query="深度学习", count=5)
    print(result[:200])
    
    # 异步 LangChain 方式
    result = await tool.ainvoke({"query": "机器学习"})
    print(result[:200])

asyncio.run(main())
```

### 2.4 参数说明

#### 2.4.1 get_web_search_tool() 参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| search_url | str | 搜索服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| timeout | float | 请求超时时间（秒） | 否 | 30.0 |
| clean | bool | 是否返回清洗后的文本 | 否 | True |

#### 2.4.2 search() / asearch() 参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| query | str | 搜索查询内容 | 是 | - |
| count | int | 返回结果数量 | 否 | 5 |
| time_range | str | 时间范围 | 否 | None |
| clean | bool | 覆盖实例的 clean 配置 | 否 | 使用实例配置 |

### 2.5 与 Agent 集成

```python
from langchain_htai import get_llm, get_web_search_tool
from langgraph.prebuilt import create_react_agent

# 创建 LLM 和工具
llm = get_llm(model="local-qwen3-235b-nothink-moe", temperature=0)
tool = get_web_search_tool()

# 创建 Agent
agent = create_react_agent(llm, tools=[tool])

# 使用 Agent
response = agent.invoke({
    "messages": [{"role": "user", "content": "2024年诺贝尔物理学奖得主是谁？"}]
})

print(response["messages"][-1].content)
```



## 相关文档

- [安装与配置指南](installation.md)
- [聊天模型文档](chat_model.md)
- [文档处理文档](document.md)
- [工具与插件文档](tools_plugins.md)

---

返回 [主文档](../README.md)
