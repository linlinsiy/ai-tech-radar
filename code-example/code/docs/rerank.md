# 重排序（Rerank）

本文档介绍如何使用 talentsview-sdk 和 langchain-htai 进行文本重排序。

## 1. talentsview-sdk

### 1.1 功能介绍

talentsview-sdk 提供 `Rerank` 和 `AsyncRerank` 两个客户端类，公司推荐使用qwen3-rerank-06b，支持：

- **基础重排序**：根据查询对文档列表排序
- **Top-N 限制**：指定返回前 N 个最相关结果
- **相关性分数**：返回每个文档的相关性分数（降序排列）
- **同步/异步调用**：支持同步和异步两种调用方式

### 1.2 基本调用示例

#### 1.2.1 基础重排序

```python
from talentsview import Rerank

# 创建 Rerank 客户端（使用默认模型 qwen3-rerank-06b）
rerank = Rerank()

# 准备查询和文档列表
query = "什么是Python"
documents = [
    "Python是一种编程语言",
    "苹果是一种水果",
    "Python由Guido van Rossum创建",
    "天气今天很好"
]

# 执行重排序
results = rerank.rerank(query=query, documents=documents)

# 查看结果
for result in results:
    print(f"索引: {result['index']}, 分数: {result['relevance_score']:.4f}")
    print(f"文档: {result['document']}\n")
```

#### 1.2.2 Top-N 限制

```python
from talentsview import Rerank

rerank = Rerank()

query = "Python编程"
documents = [
    "Python编程语言",
    "Java编程语言",
    "C++编程语言",
    "JavaScript编程语言",
    "Go编程语言"
]

# 只返回最相关的前 3 个结果
results = rerank.rerank(query=query, documents=documents, top_n=3)

print(f"返回 {len(results)} 个结果")
for result in results:
    print(f"  {result['index']}: {documents[result['index']]} (分数: {result['relevance_score']:.4f})")
```

#### 1.2.3 异步重排序

```python
import asyncio
from talentsview import AsyncRerank

async def main():
    # 创建异步 Rerank 客户端
    rerank = AsyncRerank()
    
    query = "人工智能"
    documents = ["AI技术", "机器学习", "深度学习", "数据分析"]
    
    # 异步重排序
    results = await rerank.arerank(query=query, documents=documents)
    
    for result in results:
        print(f"索引: {result['index']}, 分数: {result['relevance_score']:.4f}")

asyncio.run(main())
```

### 1.3 参数说明

#### 1.3.1 客户端初始化参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 否 | "qwen3-rerank-06b" |
| rerank_url | str | Rerank 服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| timeout | int | 请求超时时间（秒） | 否 | 60 |
| http_client | httpx.Client | 同步 HTTP 客户端 | 否 | 使用全局单例 |

#### 1.3.2 rerank() 方法参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| query | str | 查询文本 | 是 | - |
| documents | List[str] | 待排序文档列表 | 是 | - |
| top_n | int | 返回前 N 个结果 | 否 | 返回全部 |
| model | str | 模型名称（覆盖初始化时的模型） | 否 | 使用初始化模型 |

#### 1.3.3 返回值结构

返回 `List[RerankResult]`，每个元素包含：

| 字段 | 类型 | 说明 |
|-----|------|------|
| index | int | 原文档列表中的索引 |
| relevance_score | float | 相关性分数（降序排列） |
| document | str | 文档内容 |

### 1.4 高级用法

#### 1.4.1 检索结果重排序

```python
from talentsview import Embedding, Rerank
import numpy as np

# 第一步：向量检索（初排）
embedding = Embedding()
query = "Python机器学习"
query_vector = embedding.embed_query(query)

documents = [
    "Python是一种编程语言",
    "机器学习是人工智能的分支",
    "Python用于数据科学和机器学习",
    "Java是企业级应用开发语言",
    "深度学习需要大量计算资源"
]

# 计算相似度（简化示例）
doc_vectors = embedding.embed_documents(documents)
# ... 相似度计算和Top-K召回 ...

# 第二步：重排序（精排）
rerank = Rerank()
recalled_docs = documents[:5]  # 假设召回前5个
results = rerank.rerank(query=query, documents=recalled_docs, top_n=3)

print("精排后的Top-3结果：")
for result in results:
    print(f"  {result['document']} (分数: {result['relevance_score']:.4f})")
```

#### 1.4.2 多路召回融合

```python
from talentsview import Rerank

# 来自不同检索源的结果
bm25_results = ["文档A", "文档B", "文档C"]
vector_results = ["文档C", "文档D", "文档E"]

# 合并并去重
all_docs = list(set(bm25_results + vector_results))

# 使用 Rerank 统一排序
rerank = Rerank()
query = "查询内容"
results = rerank.rerank(query=query, documents=all_docs, top_n=5)

print("融合后的Top-5结果：")
for result in results:
    print(f"  {result['document']} (分数: {result['relevance_score']:.4f})")
```


## 2. langchain-htai

### 2.1 功能介绍

langchain-htai 提供 `LangChainRerank` 类，支持多种输入类型：

- **List[str]**：字符串列表，返回 `List[Dict]`
- **List[Document]**：LangChain Document 列表，返回 `List[Document]`（保留元数据并附加 relevance_score）
- **List[Dict]**：字典列表，返回 `List[Dict]`（需指定 text_key，兼容 Cohere API）

### 2.2 基本调用示例

#### 2.2.1 字符串列表重排序

```python
from langchain_htai import LangChainRerank

# 创建 Rerank 客户端
rerank = LangChainRerank(model="qwen3-rerank-06b")

# 字符串列表
query = "什么是Python"
documents = [
    "Python是一种编程语言",
    "苹果是一种水果",
    "Python用于数据科学"
]

# 重排序
results = rerank.rerank(query=query, documents=documents)

# 查看结果（返回 List[Dict]）
for result in results:
    print(f"索引: {result['index']}, 分数: {result['relevance_score']:.4f}")
    print(f"文档: {result['document']}\n")
```

#### 2.2.2 Document 列表重排序

```python
from langchain_htai import LangChainRerank
from langchain_core.documents import Document

# 创建 Rerank 客户端
rerank = LangChainRerank(model="qwen3-rerank-06b")

# 创建 Document 列表
documents = [
    Document(page_content="Python是一种编程语言", metadata={"source": "doc1"}),
    Document(page_content="苹果是一种水果", metadata={"source": "doc2"}),
    Document(page_content="Python用于数据科学", metadata={"source": "doc3"})
]

# 重排序（返回 List[Document]，保留原始元数据）
results = rerank.rerank(query="Python", documents=documents, top_n=2)

# 查看结果
for doc in results:
    print(f"内容: {doc.page_content}")
    print(f"来源: {doc.metadata['source']}")
    print(f"相关性分数: {doc.metadata['relevance_score']:.4f}\n")
```

#### 2.2.3 字典列表重排序（Cohere API 风格）

```python
from langchain_htai import LangChainRerank

rerank = LangChainRerank(model="qwen3-rerank-06b")

# 字典列表
documents = [
    {"text": "Python编程", "id": 1, "category": "tech"},
    {"text": "苹果水果", "id": 2, "category": "food"},
    {"text": "机器学习", "id": 3, "category": "tech"}
]

# 重排序（指定 text_key）
results = rerank.rerank(
    query="编程",
    documents=documents,
    text_key="text",  # 指定文本字段
    top_n=2
)

# 查看结果（保留原始字段并附加 relevance_score）
for result in results:
    print(f"ID: {result['id']}, 类别: {result['category']}")
    print(f"文本: {result['text']}")
    print(f"分数: {result['relevance_score']:.4f}\n")
```

#### 2.2.4 异步重排序

```python
import asyncio
from langchain_htai import LangChainRerank

async def main():
    rerank = LangChainRerank(model="qwen3-rerank-06b")
    
    query = "Python"
    documents = ["Python编程", "Java编程", "水果"]
    
    # 异步重排序
    results = await rerank.arerank(query=query, documents=documents, top_n=2)
    
    for result in results:
        print(f"{result['document']} (分数: {result['relevance_score']:.4f})")

asyncio.run(main())
```

### 2.3 参数说明

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 否 | "qwen3-rerank-06b" |
| rerank_url | str | Rerank 服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| timeout | int | 请求超时时间（秒） | 否 | 60 |
| http_client | httpx.Client | 同步 HTTP 客户端 | 否 | 使用全局单例 |
| http_async_client | httpx.AsyncClient | 异步 HTTP 客户端 | 否 | 使用全局单例 |

**rerank() / arerank() 方法参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| query | str | 查询文本 | 是 | - |
| documents | Union[List[str], List[Document], List[Dict]] | 待排序文档 | 是 | - |
| top_n | int | 返回前 N 个结果 | 否 | 返回全部 |
| model | str | 模型名称（覆盖初始化模型） | 否 | 使用初始化模型 |
| text_key | str | 字典类型文档的文本字段名 | 否（Dict时必填） | None |

### 2.4 LangChain 集成示例

#### 2.4.1 与 Retriever 集成

```python
from langchain_htai import LangChainEmbedding, LangChainRerank
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# 创建向量库
embedding = LangChainEmbedding(model="qwen3-embedding-06b")
texts = ["文档1", "文档2", "文档3", "文档4", "文档5"]
vectorstore = FAISS.from_texts(texts, embedding)

# 初步检索
query = "查询内容"
initial_docs = vectorstore.similarity_search(query, k=5)

# 使用 Rerank 精排
rerank = LangChainRerank(model="qwen3-rerank-06b")
reranked_docs = rerank.rerank(query=query, documents=initial_docs, top_n=3)

# 查看精排结果
for doc in reranked_docs:
    print(f"{doc.page_content} (分数: {doc.metadata['relevance_score']:.4f})")
```


## 相关文档

- [安装与配置指南](installation.md)
- [向量化文档](embedding.md)
- [聊天模型文档](chat_model.md)
- [联网搜索文档](web_search.md)

---

返回 [主文档](../README.md)
