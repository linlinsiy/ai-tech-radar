# TalentsView AI SDK 文档中心

欢迎使用 TalentsView AI SDK！本文档提供 **talentsview-sdk**（原生 Python SDK）和 **langchain-htai**（LangChain 适配层）的统一使用指南。

## 📚 快速导航

- [安装与配置指南](docs/installation.md)
- [聊天模型](docs/chat_model.md)
- [文本向量化](docs/embedding.md)
- [文本重排序](docs/rerank.md)
- [联网搜索](docs/web_search.md)
- [文档处理](docs/document.md)
- [工具与插件](docs/tools_plugins.md)
- 实体识别（待补充文档）

## 📚 SDK 简介

### talentsview-sdk

**核心定位**：泰为平台的原生 Python SDK，提供完整的 AI 能力调用接口。

**主要能力**：
- **Models 模块**：大语言模型（LLM）、文本向量化（Embedding）、文本重排序（Rerank）
- **AIServices 模块**：文档解析（DocParser）、文档分块（DocChunker）、实体识别（EntityRecognizer）、联网搜索（WebSearch）
- **Platform 模块**：工具服务（Tools）、插件服务（Plugins）

**调用风格**：支持同步/异步、流式/非流式四种调用模式，接口设计符合 OpenAI SDK 规范。

### langchain-htai

**核心定位**：LangChain 生态适配层，基于 talentsview-sdk 封装，无缝集成 LangChain 工作流。

**主要能力**：
- **Models**：ChatOpenAI、ChatDeepSeek（推理模型）、LangChainEmbedding、LangChainRerank
- **AIServices**：DocumentLoader、TextSplitter（JsonTextSplitter、PlainTextSplitter）、WebSearchTool
- **常用便捷函数**：`get_llm()`、`get_reasoning_llm()`、`get_web_search_tool()`

**调用风格**：完全兼容 LangChain 标准接口，可直接用于 chains、agents、RAG 等场景。

## 🚀 快速安装

```bash
# 安装 talentsview-sdk
pip install talentsview

# 安装 langchain-htai
pip install langchain-htai
```

详细安装步骤和环境配置请参考 [安装与配置指南](docs/installation.md)。

## 📖 功能模块导航

| 功能模块 | talentsview-sdk | langchain-htai | 文档链接 |
|---------|:--------------:|:--------------:|---------|
| 聊天模型 | ✓ | ✓ | [chat_model.md](docs/chat_model.md) |
| 向量化 | ✓ | ✓ | [embedding.md](docs/embedding.md) |
| 重排序 | ✓ | ✓ | [rerank.md](docs/rerank.md) |
| 联网搜索 | ✓ | ✓ | [web_search.md](docs/web_search.md) |
| 文档处理 | ✓ | ✓ | [document.md](docs/document.md) |
| 工具与插件 | ✓ | 待实现 | [tools_plugins.md](docs/tools_plugins.md) |

## ⚡ 快速开始

### talentsview-sdk 示例

```python
from talentsview import LLMClient

# 创建 LLM 客户端
client = LLMClient(model="local-qwen3-235b-nothink-moe")

# 调用模型
response = client.client.chat.completions.create(
    model=client.model,
    messages=[{"role": "user", "content": "你好"}],
    stream=False
)

print(response.choices[0].message.content)
```

### langchain-htai 示例

```python
from langchain_htai import get_llm

# 获取 LangChain 兼容的 LLM 实例
llm = get_llm(model="local-qwen3-235b-nothink-moe")

# 调用模型
response = llm.invoke("你好")
print(response.content)
```

## ⚙️ 环境配置

使用 SDK 前需配置环境变量（创建 `.env` 文件）：

```bash
# 环境标识（DEV 或 PRD）
ENV=DEV

# 应用标识
TALENTSVIEW_APP_ID=your_app_id_here

# 智能体标识
TALENTSVIEW_AGENT_ID=your_agent_id_here
```

在代码中加载配置：

```python
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
```

详细配置说明请参考 [安装与配置指南](docs/installation.md)。

## 📝 文档结构

```
/
├── README.md                 # 本文档（快速导航）
└── docs/
    ├── installation.md       # 安装与配置详细指南
    ├── chat_model.md         # 聊天模型使用文档
    ├── embedding.md          # 向量化使用文档
    ├── rerank.md             # 重排序使用文档
    ├── web_search.md         # 联网搜索使用文档
    ├── document.md           # 文档处理（解析+分块）
    └── tools_plugins.md      # 工具与插件使用文档
```

## 🔗 相关链接

- **talentsview-sdk 详细文档**：[talentsview-sdk/README.md](talentsview-sdk/README.md)
- **langchain-htai 详细文档**：[langchain-htai/README.md](langchain-htai/README.md)
- **配置示例**：[.env.example](.env.example)

## 📮 技术支持

如遇到问题，请检查：
1. 环境变量配置是否正确（使用 `talentsview.diagnose_config()` 诊断）
2. 应用 ID 和智能体 ID 是否有效
3. 网络连接是否正常

常见问题解决方案请参考 [安装与配置指南](docs/installation.md#常见问题与解决方案)。

---

**版权所有** © 2025 华泰证券
