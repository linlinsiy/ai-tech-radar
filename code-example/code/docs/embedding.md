# 向量化（Embedding）

本文档介绍如何使用 talentsview-sdk 和 langchain-htai 进行文本向量化。

## 1. talentsview-sdk

### 1.1 功能介绍

talentsview-sdk 提供 `Embedding` 和 `AsyncEmbedding` 两个客户端类，支持：

- **单文本向量化**：`embed_query(text)` - 适用于查询文本
- **批量文本向量化**：`embed_documents(texts)` - 适用于文档批处理
- **同步/异步调用**：支持同步和异步两种调用方式

### 1.2 基本调用示例

#### 1.2.1 单文本向量化

```python
from talentsview import Embedding

# 创建 Embedding 客户端（使用默认模型 qwen3-embedding-06b）
embedding = Embedding()

# 单文本向量化
vector = embedding.embed_query(text="这是一个测试文本")

# 查看向量维度
print(f"向量维度: {len(vector)}")
print(f"向量示例: {vector[:5]}...")  # 显示前5个元素
```

#### 1.2.2 批量文本向量化

```python
from talentsview import Embedding

# 创建 Embedding 客户端
embedding = Embedding()

# 批量文本向量化
texts = ["文本1", "文本2", "文本3"]
vectors = embedding.embed_documents(texts=texts)  # 如果单次传入过多导致报错，参考1.2.4 批量处理大量文本

# 查看结果
print(f"文本数量: {len(texts)}")
print(f"向量数量: {len(vectors)}")
print(f"向量维度: {len(vectors[0])}")
```

#### 1.2.3 异步向量化

```python
import asyncio
from talentsview import AsyncEmbedding

async def main():
    # 创建异步 Embedding 客户端
    embedding = AsyncEmbedding()
    
    # 异步单文本向量化
    vector = await embedding.aembed_query(text="异步测试文本")
    print(f"向量维度: {len(vector)}")
    
    # 异步批量文本向量化
    texts = ["文本1", "文本2", "文本3"]
    vectors = await embedding.aembed_documents(texts=texts)
    print(f"生成了 {len(vectors)} 个向量")

asyncio.run(main())
```

#### 1.2.4 批量处理大量文本

```python
from talentsview import Embedding

embedding = Embedding()

# 大量文本分批处理
all_texts = ["文本" + str(i) for i in range(1000)]
batch_size = 100

all_vectors = []
for i in range(0, len(all_texts), batch_size):
    batch = all_texts[i:i + batch_size]
    vectors = embedding.embed_documents(texts=batch)
    all_vectors.extend(vectors)
    print(f"已处理 {min(i + batch_size, len(all_texts))}/{len(all_texts)} 个文本")

print(f"共生成 {len(all_vectors)} 个向量")
```

### 1.3 参数说明

#### 1.3.1 客户端初始化参数

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 否 | "qwen3-embedding-06b" |
| embedding_url | str | Embedding 服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| http_client | httpx.Client | 同步 HTTP 客户端 | 否 | 使用全局单例 |

#### 1.3.2 方法参数

**embed_query() 参数**：

| 参数名 | 类型 | 说明 | 必填 |
|-------|------|------|------|
| text | str | 待向量化的文本 | 是 |

**embed_documents() 参数**：

| 参数名 | 类型 | 说明 | 必填 |
|-------|------|------|------|
| texts | List[str] | 待向量化的文本列表 | 是 |



## 2. langchain-htai

### 2.1 功能介绍

langchain-htai 提供 `LangChainEmbedding` 类，继承自 `langchain_core.embeddings.Embeddings`，提供 LangChain 标准接口，可用于所有接受 Embeddings 的 LangChain 组件：

- **embed_documents(texts)**：批量文本向量化
- **embed_query(text)**：单文本向量化
- **aembed_documents(texts)**：异步批量向量化
- **aembed_query(text)**：异步单文本向量化

### 2.2 基本调用示例

#### 2.2.1 基础使用

```python
from langchain_htai import LangChainEmbedding

# 创建 Embedding 客户端
embedding = LangChainEmbedding(model="qwen3-embedding-06b")

# 单文本向量化
vector = embedding.embed_query("这是一个测试文本")
print(f"向量维度: {len(vector)}")

# 批量文本向量化
texts = ["文本1", "文本2", "文本3"]
vectors = embedding.embed_documents(texts)
print(f"生成了 {len(vectors)} 个向量")
```

#### 2.2.2 异步调用

```python
import asyncio
from langchain_htai import LangChainEmbedding

async def main():
    embedding = LangChainEmbedding(model="qwen3-embedding-06b")
    
    # 异步单文本向量化
    vector = await embedding.aembed_query("异步测试文本")
    print(f"向量维度: {len(vector)}")
    
    # 异步批量向量化
    texts = ["文本1", "文本2"]
    vectors = await embedding.aembed_documents(texts)
    print(f"生成了 {len(vectors)} 个向量")

asyncio.run(main())
```

### 2.3 参数说明

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| model | str | 模型名称 | 否 | "qwen3-embedding-06b" |
| embedding_url | str | Embedding 服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| http_client | httpx.Client | 同步 HTTP 客户端 | 否 | 使用全局单例 |
| http_async_client | httpx.AsyncClient | 异步 HTTP 客户端 | 否 | 使用全局单例 |

### 2.4 LangChain 集成示例

#### 2.4.1 与 FAISS 向量库集成

```python
from langchain_htai import LangChainEmbedding
from langchain_community.vectorstores import FAISS

# 创建 Embedding
embedding = LangChainEmbedding(model="qwen3-embedding-06b")

# 准备文档
texts = [
    "Python是一种编程语言",
    "Java是一种编程语言",
    "机器学习是人工智能的分支"
]

# 创建向量库
vectorstore = FAISS.from_texts(texts, embedding)

# 相似度搜索
query = "什么是Python"
docs = vectorstore.similarity_search(query, k=2)

for doc in docs:
    print(f"文档: {doc.page_content}")
```

#### 2.4.2 与 Retriever 集成

```python
from langchain_htai import LangChainEmbedding
from langchain_community.vectorstores import FAISS

# 创建向量库
embedding = LangChainEmbedding(model="qwen3-embedding-06b")
vectorstore = FAISS.from_texts(["文档1", "文档2"], embedding)

# 创建检索器
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 3}
)

# 检索
docs = retriever.get_relevant_documents("查询内容")
for doc in docs:
    print(doc.page_content)
```

## 相关文档

- [安装与配置指南](installation.md)
- [聊天模型文档](chat_model.md)
- [重排序文档](rerank.md)
- [文档处理文档](document.md)

---

返回 [主文档](../README.md)
