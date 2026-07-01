# 文档处理：解析与分块

本文档介绍如何使用 talentsview-sdk 和 langchain-htai 进行文档解析和文本分块。

## 功能概述

文档处理包括两个核心功能：

1. **文档解析（Doc Parser）**：将 PDF 等文档解析为结构化数据（md_detail）
2. **文档分块（Doc Chunker / Text Splitter）**：将文档或文本分割为语义块

**完整链路**：`PDF 文件` → **解析** → `md_detail` → **分块** → `chunks` → **向量化** → `向量库`

两个功能既可独立使用，也可链式调用。

## 1. talentsview-sdk

### 1.1 文档解析（DocParser）

#### 1.1.1 功能介绍

`DocParser` 提供文档解析能力。

**支持的文件类型**：

`png`、`jpg`、`jpeg`、`bmp`、`pdf`、`doc`、`docx`、`webp`、`tif`、`tiff`、`html`、`mhtml`、`xls`、`xlsx`、`ppt`、`pptx`、`wps`、`csv`、`txt`、`ofd`、`rtf`

**核心能力**：
- **文档解析**：将多种格式文档转换为结构化的 md_detail 数据
- **表格解析**：提取表格数据
- **图片提取**：可选择提取文档中的图片
- **目录树生成**：生成文档结构树
- **加密 PDF**：支持解析加密的 PDF 文档

#### 1.1.2 参数说明

**parse() 方法参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| file_path | str | 文件路径 | 是 | - |
| parse_params | dict | 解析参数配置 | 是 | - |
| polling_max_attempts | int | 最大轮询次数 | 否 | 100 |
| polling_http_error_tries | int | HTTP 错误重试次数 | 否 | 3 |
| polling_interval_seconds | int | 轮询间隔（秒） | 否 | 2 |
| create_timeout_seconds | int | 创建任务超时（秒） | 否 | 10 |
| polling_timeout_seconds | int | 单次轮询超时（秒） | 否 | 10 |

**parse_params 配置项**：

| 键 | 类型 | 说明 | 必填 | 可选值 |
|----|------|------|------|--------|
| parse_type | str | 解析类型 | 是 | `"document"`（推荐）、`"table"` |
| table_flavor | str | 表格格式 | 否 | `"html"`（默认）、`"md"`（推荐） |
| get_image | str | 图片获取方式 | 否 | `"none"`（默认）、`"page"`、`"objects"`、`"both"` |
| apply_document_tree | str | 生成文档目录 | 否 | `"0"`（不生成）、`"1"`（默认，生成） |
| markdown_details | str | 生成 Markdown 详情 | 否 | `"0"`（不生成）、`"1"`（默认，生成） |
| merge_images | str | 合并图片文件 | 否 | `"0"`（默认）、`"1"` |
| char_details | str | 返回字符位置信息 | 否 | `"0"`（不生成）、`"1"`（默认） |
| dpi | str | PDF 坐标基准 | 否 | `"72"`、`"144"`、`"216"`、`"auto"` |
| parse_mode | str | PDF 解析模式 | 否 | `"scan"`（默认，仅 OCR）、`"auto"`（综合模式） |
| page_start | str | 起始页码（从 1 开始） | 否 | 如 `"3"` |
| page_count | str | 转换页数 | 否 | 如 `"10"` |
| remove_watermark | str | 去水印 | 否 | `"0"`（默认）、`"1"` |
| pdf_pwd | str | 加密 PDF 密码 | 否 | - |

#### 1.1.3 基本调用示例

**标准文档解析**（推荐）：

```python
from talentsview import DocParser

# 创建解析器
parser = DocParser()

# 解析 PDF 文档
md_detail = parser.parse(
    file_path="./sample.pdf",
    parse_params={"parse_type": "document"}
)

print(f"解析完成，结果类型: {type(md_detail)}")
```

**完整功能解析**（包含图片和目录）：

```python
from talentsview import DocParser

parser = DocParser()

md_detail = parser.parse(
    file_path="./sample.pdf",
    parse_params={
        "parse_type": "document",
        "table_flavor": "md",
        "get_image": "objects",
        "apply_document_tree": "1",
        "markdown_details": "1"
    }
)
```

**表格解析**：

```python
from talentsview import DocParser

parser = DocParser()

md_detail = parser.parse(
    file_path="./table.pdf",
    parse_params={
        "parse_type": "table",
        "table_flavor": "md"
    }
)
```

**加密 PDF 解析**：

```python
from talentsview import DocParser

parser = DocParser()

md_detail = parser.parse(
    file_path="./encrypted.pdf",
    parse_params={
        "parse_type": "document",
        "pdf_pwd": "your_password"
    }
)
```

**异步解析**：

```python
import asyncio
from talentsview import AsyncDocParser

async def main():
    parser = AsyncDocParser()
    md_detail = await parser.parse(
        file_path="./sample.pdf",
        parse_params={"parse_type": "document"}
    )
    print("解析完成")

asyncio.run(main())
```

#### 1.1.4 大文件解析配置

大文件解析耗时较长，需调整多个参数配合使用。以 30 分钟（1800 秒）解析为例：

```python
from talentsview import DocParser

parser = DocParser()

# 30分钟解析配置：轮询 900 次 × 2 秒 = 1800 秒
md_detail = parser.parse(
    file_path="./large_file.pdf",
    parse_params={"parse_type": "document", "table_flavor": "md"},
    polling_max_attempts=900,         # 增大轮询次数
    polling_http_error_tries=10,      # 增大 HTTP 错误重试次数，避免临时网络问题中断
    polling_interval_seconds=2,       # 轮询间隔（可保持默认）
    polling_timeout_seconds=30,       # 增大单次轮询超时，防止网络慢时超时
)
```

**参数计算公式**：`总等待时间 ≈ polling_max_attempts × polling_interval_seconds`

| 解析时长 | polling_max_attempts | polling_interval_seconds | polling_http_error_tries |
|----------|----------------------|--------------------------|---------------------------|
| 10 分钟  | 300                  | 2                        | 5                         |
| 30 分钟  | 900                  | 2                        | 10                        |
| 60 分钟  | 1800                 | 2                        | 15                        |

#### 1.1.5 注意事项

1. **轮询机制**：解析是异步任务，SDK 会自动轮询获取结果
2. **大文件配置**：需同时调整 `polling_max_attempts` 和 `polling_http_error_tries`，后者避免网络波动导致提前中断
3. **返回值**：`md_detail` 是结构化数据，可直接传给 `DocChunker` 进行分块

### 1.2 文档分块（DocChunker）

#### 1.2.1 功能介绍

`DocChunker` 提供文档分块能力，支持两种模式：

1. **纯文本语义分块**：直接对文本内容进行语义分块
2. **解析结果分块**（推荐）：对 `DocParser` 的输出进行分块，效果更好

#### 1.2.2 参数说明

**初始化参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| chunk_url | str | 分块服务 URL | 否 | 从配置中心获取 |
| app_id | str | 应用 ID | 否 | 从环境变量获取 |
| agent_id | str | 智能体 ID | 否 | 从环境变量获取 |
| timeout | float | 超时时间（秒） | 否 | 30.0 |
| http_client | httpx.Client | HTTP 客户端 | 否 | 使用全局单例 |

**data_dict 参数结构**（纯文本分块）：

| 键 | 类型 | 说明 | 必填 |
|----|------|------|------|
| fileType | str | "txt" | 是 |
| txt_parse_mode | str | "semantic" | 是 |
| txt_content | str | 文本内容 | 是 |
| chunk_token_num | int | 每块 token 数（推荐768） | 是 |
| lang | str | "chinese" 或 "english" | 是 |
| app_id | str | 应用标识 | 否 |
| filename | str | 文件名 | 否 |

**data_dict 参数结构**（解析结果分块）：

| 键 | 类型 | 说明 | 必填 |
|----|------|------|------|
| fileType | str | "json" | 是 |
| pdf_json | Any | DocParser 输出的 md_detail | 是 |
| chunk_token_num | int | 每块 token 数（推荐768） | 是 |
| lang | str | "chinese" 或 "english" | 是 |
| app_id | str | 应用标识 | 否 |
| filename | str | 文件名 | 否 |

#### 1.2.3 基本调用示例

**纯文本语义分块**：

```python
from talentsview import DocChunker

chunker = DocChunker()

chunks = chunker.chunk(
    data_dict={
        "fileType": "txt",
        "txt_parse_mode": "semantic",
        "txt_content": "这里是长文本内容...",
        "chunk_token_num": 768,
        "lang": "chinese"
    }
)

print(f"分块完成，共 {len(chunks)} 个分块")
```

**解析结果分块**（推荐）：

```python
from talentsview import DocParser, DocChunker

# 步骤1: 解析文档
parser = DocParser()
md_detail = parser.parse(
    file_path="./sample.pdf",
    parse_params={"parse_type": "document"}
)

# 步骤2: 分块
chunker = DocChunker()
chunks = chunker.chunk(
    data_dict={
        "fileType": "json",
        "pdf_json": md_detail,
        "chunk_token_num": 768,
        "lang": "chinese",
        "filename": "sample.pdf"
    }
)

print(f"分块完成，共 {len(chunks)} 个分块")

# 查看分块内容
for i, chunk in enumerate(chunks[:3]):
    print(f"\n分块 {i+1}:")
    print(f"  标题: {chunk.title}")
    print(f"  内容: {chunk.content_with_weight[:100]}...")
```

**异步分块**：

```python
import asyncio
from talentsview import AsyncDocChunker

async def main():
    chunker = AsyncDocChunker()
    chunks = await chunker.chunk(
        data_dict={
            "fileType": "txt",
            "txt_parse_mode": "semantic",
            "txt_content": "文本内容...",
            "chunk_token_num": 768,
            "lang": "chinese"
        }
    )
    print(f"分块完成，共 {len(chunks)} 个分块")

asyncio.run(main())
```

#### 1.2.4 完整链路示例（解析+分块）

```python
from talentsview import DocParser, DocChunker, Embedding

# 步骤1: 解析文档
parser = DocParser()
md_detail = parser.parse(
    file_path="./document.pdf",
    parse_params={"parse_type": "document"}
)
print("✓ 文档解析完成")

# 步骤2: 文档分块
chunker = DocChunker()
chunks = chunker.chunk(
    data_dict={
        "fileType": "json",
        "pdf_json": md_detail,
        "chunk_token_num": 768,
        "lang": "chinese"
    }
)
print(f"✓ 文档分块完成，共 {len(chunks)} 个分块")

# 步骤3: 向量化（可选）
embedding = Embedding()
chunk_texts = [chunk.content_with_weight for chunk in chunks]
vectors = embedding.embed_documents(texts=chunk_texts)
print(f"✓ 向量化完成，共 {len(vectors)} 个向量")

# 现在可以将向量存入向量库
```

#### 1.2.5 注意事项

1. **推荐链路**：先用 `DocParser` 解析文档，再用 `DocChunker` 分块，效果优于纯文本分块
2. **chunk_token_num**：推荐值为 768，可根据实际需求调整
3. **语言参数**：正确设置 `lang` 参数可提高分块质量
4. **返回值**：返回 `List[ChunkDoc]`，每个分块包含 `title`、`content_with_weight` 等字段

## 2. langchain-htai

### 2.1 文档加载（DocumentLoader）

#### 2.1.1 功能介绍

`DocumentLoader` 继承自 `BaseLoader`，封装了 `DocParser`，提供 LangChain 标准接口：
- **load()**：同步加载文档，返回 `List[Document]`
- **lazy_load()**：懒加载，逐个生成 Document
- **alazy_load()**：异步懒加载

返回的 Document 的 `page_content` 为 JSON 字符串形式的 md_detail。

#### 2.1.2 参数说明

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| file_path | str | 文件路径 | 是 | - |
| parse_params | dict | 解析参数（同 DocParser） | 是 | - |
| create_task_url | str | 创建任务 URL | 否 | 从配置中心获取 |
| get_result_url | str | 获取结果 URL | 否 | 从配置中心获取 |
| metadata | dict | 附加元数据 | 否 | {} |
| polling_max_attempts | int | 最大轮询次数 | 否 | 100 |
| polling_interval_seconds | int | 轮询间隔 | 否 | 2 |

#### 2.1.3 基本调用示例

**标准文档加载**：

```python
from langchain_htai import DocumentLoader

# 创建加载器
loader = DocumentLoader(
    file_path="./sample.pdf",
    parse_params={"parse_type": "document", "table_flavor": "md"}
)

# 加载文档
documents = loader.load()

print(f"加载了 {len(documents)} 个文档")
print(f"文档元数据: {documents[0].metadata}")
```

**完整功能加载**（包含图片和目录）：

```python
from langchain_htai import DocumentLoader

loader = DocumentLoader(
    file_path="./sample.pdf",
    parse_params={
        "parse_type": "document",
        "table_flavor": "md",
        "get_image": "objects",
        "apply_document_tree": "1",
        "markdown_details": "1"
    }
)

documents = loader.load()
```

**异步加载**：

```python
import asyncio
from langchain_htai import DocumentLoader

async def main():
    loader = DocumentLoader(
        file_path="./sample.pdf",
        parse_params={"parse_type": "document"}
    )
    
    documents = []
    async for doc in loader.alazy_load():
        documents.append(doc)
    
    print(f"加载了 {len(documents)} 个文档")

asyncio.run(main())
```

### 2.2 文本分割（TextSplitter）

#### 2.2.1 功能介绍

langchain-htai 提供四个 TextSplitter 类：

- **JsonTextSplitter**：处理 DocumentLoader 解析的 JSON（同步）
- **PlainTextSplitter**：处理纯文本（同步）
- **AsyncJsonTextSplitter**：异步 JSON 分割
- **AsyncPlainTextSplitter**：异步纯文本分割

#### 2.2.2 JsonTextSplitter

用于处理 DocumentLoader 解析后的文档：

```python
from langchain_htai import DocumentLoader, JsonTextSplitter

# 步骤1: 加载文档
loader = DocumentLoader(
    file_path="./document.pdf",
    parse_params={"parse_type": "document", "table_flavor": "md"}
)
docs = loader.load()

# 步骤2: 分割文档
splitter = JsonTextSplitter(chunk_size=768, lang="chinese")
chunks = splitter.split_documents(docs)

print(f"分割完成，共 {len(chunks)} 个分块")

# 查看分块
for chunk in chunks[:3]:
    print(f"\n标题: {chunk.metadata.get('parsed_heading', 'N/A')}")
    print(f"内容: {chunk.page_content[:100]}...")
```

#### 2.2.3 PlainTextSplitter

用于处理纯文本：

```python
from langchain_htai import PlainTextSplitter

# 创建分割器
splitter = PlainTextSplitter(chunk_size=768, lang="chinese")

# 分割文本
texts = ["这是一段很长的文本内容..."]
documents = splitter.create_documents(texts)

print(f"生成了 {len(documents)} 个分块")
```

#### 2.2.4 异步版本

```python
import asyncio
from langchain_htai import DocumentLoader, AsyncJsonTextSplitter

async def main():
    # 加载文档
    loader = DocumentLoader(
        file_path="./document.pdf",
        parse_params={"parse_type": "document"}
    )
    docs = []
    async for doc in loader.alazy_load():
        docs.append(doc)
    
    # 异步分割
    splitter = AsyncJsonTextSplitter(chunk_size=768, lang="chinese")
    
    # 提取 page_content
    texts = [doc.page_content for doc in docs]
    chunks = await splitter.acreate_documents(texts)
    
    print(f"分割完成，共 {len(chunks)} 个分块")

asyncio.run(main())
```

#### 2.2.5 完整链路示例（加载+分割）

```python
from langchain_htai import DocumentLoader, JsonTextSplitter, LangChainEmbedding
from langchain_community.vectorstores import FAISS

# 步骤1: 加载文档
loader = DocumentLoader(
    file_path="./document.pdf",
    parse_params={"parse_type": "document", "table_flavor": "md"}
)
docs = loader.load()
print(f"✓ 加载了 {len(docs)} 个文档")

# 步骤2: 分割文档
splitter = JsonTextSplitter(chunk_size=768, lang="chinese")
chunks = splitter.split_documents(docs)
print(f"✓ 分割完成，共 {len(chunks)} 个分块")

# 步骤3: 创建向量库
embedding = LangChainEmbedding(model="qwen3-embedding-06b")
vectorstore = FAISS.from_documents(chunks, embedding)
print(f"✓ 向量库创建完成")

# 步骤4: 检索
results = vectorstore.similarity_search("查询内容", k=3)
for doc in results:
    print(f"\n标题: {doc.metadata.get('parsed_heading', 'N/A')}")
    print(f"内容: {doc.page_content[:100]}...")
```

### 2.3 LangChain 集成示例

#### 2.3.1 RAG 完整流程

```python
from langchain_htai import (
    DocumentLoader,
    JsonTextSplitter,
    LangChainEmbedding,
    get_llm
)
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# 1. 加载并分割文档
loader = DocumentLoader(
    file_path="./knowledge.pdf",
    parse_params={"parse_type": "document"}
)
docs = loader.load()

splitter = JsonTextSplitter(chunk_size=768, lang="chinese")
chunks = splitter.split_documents(docs)

# 2. 创建向量库
embedding = LangChainEmbedding()
vectorstore = FAISS.from_documents(chunks, embedding)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 3. 构建 RAG Chain
llm = get_llm(model="local-qwen3-235b-nothink-moe")

prompt = ChatPromptTemplate.from_template(
    "基于以下上下文回答问题：\n{context}\n\n问题：{question}"
)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
)

# 4. 查询
response = rag_chain.invoke("你的问题")
print(response.content)
```

### 2.4 注意事项

1. **文档加载**：DocumentLoader 返回的 Document 的 page_content 是 JSON 字符串，必须使用 JsonTextSplitter
2. **元数据保留**：分割后的文档会保留原始元数据，并添加 `parsed_heading` 字段
3. **异步版本**：异步 TextSplitter 不支持 `split_text()` 同步方法，只能使用 `asplit_text()` 或 `acreate_documents()`
4. **与 talentsview-sdk 的关系**：langchain-htai 基于 talentsview-sdk 的 DocParser 和 DocChunker 封装

## 相关文档

- [安装与配置指南](installation.md)
- [向量化文档](embedding.md)
- [重排序文档](rerank.md)

---

返回 [主文档](../README.md)
