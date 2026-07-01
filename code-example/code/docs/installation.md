# 安装与配置指南

本文档提供 talentsview-sdk 和 langchain-htai 的详细安装和配置说明。

## 环境要求

| 项目 | 要求 |
|------|------|
| Python 版本 | = 3.12 |
| 包管理工具 | uv、pip |
| 操作系统 | Linux、macOS、Windows |

## 安装方式

> **网络超时解决方案**：如果pip install/uv add/uv sync安装过程中遇到超时问题，可指定公司内部源：
> - **测试环境**：添加参数 `-i http://repo.htzq.htsc.com.cn/repository/htscpypi/simple/`
> - **正式环境**：`-i [正式环境地址待补充]`

### 推荐：使用 uv 管理项目（推荐）

#### uv 安装

```bash
pip install uv -i http://repo.htzq.htsc.com.cn/repository/htscpypi/simple/

# 验证安装
uv --version
```

#### 使用 uv 安装 SDK

```bash
# 方式 1：uv pip install（推荐用于非项目环境或快速测试）
# 直接安装到当前 Python 环境，不修改 pyproject.toml
uv pip install talentsview
uv pip install langchain-htai

# 方式 2：uv add（推荐用于项目开发）
# 安装并自动添加到 pyproject.toml 的 dependencies，适合项目依赖管理
uv add talentsview
uv add langchain-htai
```


### 使用 pip 安装

```bash
# 安装 talentsview-sdk
pip install talentsview

# 安装 langchain-htai
pip install langchain-htai
```

### 验证安装

```python
# 验证 talentsview-sdk
import talentsview
print(f"talentsview 版本: {talentsview.__version__}")

# 验证 langchain-htai
import langchain_htai
print(f"langchain-htai 版本: {langchain_htai.__version__}")
```

预期输出：

```
talentsview 版本: 1.x.x
langchain-htai 版本: 1.x.x
```

### uv 项目管理最佳实践

#### 初始化新项目

```bash
# 创建新项目
mkdir my-ai-project
cd my-ai-project

# 初始化 Python 项目
uv init

# 添加依赖
uv add talentsview
uv add langchain-htai
uv add python-dotenv

# 同步依赖（安装所有 pyproject.toml 中的依赖）
uv sync
```

#### 使用高代码脚手架场景

```bash
# 下载项目后，一键安装所有依赖
cd existing-project
uv sync

# 查看已安装的包
uv pip list

# 更新依赖到最新版本
uv lock --upgrade
uv sync
```

## 环境配置

### 必需配置项

TalentsView SDK 组件通常需要以下环境变量才能正常工作（推荐使用环境变量而非每次调用方法时输入app_id/agent_id）：

| 配置项 | 说明 | 示例值 |
|-------|------|--------|
| ENV | 环境标识（UAT 或 PRD） | UAT |
| TALENTSVIEW_APP_ID | 应用标识 | your_app_id_here |
| TALENTSVIEW_AGENT_ID | 智能体标识 | your_agent_id_here |

### 可选配置项

请注意，如果使用泰为平台插件/工具/智能体/知识库等功能，TALENTSVIEW_WORKSPACE_ID为必填项。也可以选择在yaml配置中填写。

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| TALENTSVIEW_WORKSPACE_ID | 泰为平台workspace id | your_workspace_id |
| TALENTSVIEW_RESOURCES_FILE | 资源配置文件路径 | 自动查找 |

### 配置文件示例

#### .env.uat 文件

项目提供 `.env.uat` 和 `.env.prd` 配置文件：

```bash
# 环境标识（UAT 或 PRD）
ENV=UAT

# 应用标识
TALENTSVIEW_APP_ID=your_app_id_here

# 智能体标识（加密后密文）
TALENTSVIEW_AGENT_ID=your_agent_id_here

# 智能体标识是否已加密（默认 true）
TALENTSVIEW_AGENT_ID_ENCRYPTED=true

# （可选）资源配置文件路径

# TALENTSVIEW_WORKSPACE_ID=your_workspace_id
# TALENTSVIEW_RESOURCES_FILE=./resources.uat.yaml
```

#### resources.uat.yaml 文件

用于配置工具名称映射（可选，当使用泰为大模型应用平台组件时为必须）：

```yaml
# 工作空间ID（必需）
workspace_id: "your_workspace_id_here"

# 工具名称映射配置
tools:
  联网查询服务: "cvrmtpi4kmj6p97blt2g"
  离线ASR: "d4sj2sh8o1bgaqub62m0"
  资讯rag: "d4i2h1b0a51ick6963u0"
```

### 加载环境变量

在 Python 代码中加载环境变量：

```python
from dotenv import load_dotenv

# 加载 .env.uat 文件
load_dotenv('.env.uat')

# 现在可以使用 SDK 了
from talentsview import LLMClient

client = LLMClient(model="local-qwen3-235b-nothink-moe")
```

## 配置验证

使用内置诊断工具验证配置是否正确：

```python
import talentsview

# 诊断配置状态
talentsview.diagnose_config()
```

预期输出（配置正确）：

```
==================================================
TalentsView SDK 配置诊断
==================================================
✓ 环境: DEV
✓ APP_ID: app_123***
✓ AGENT_ID: agent_789***
✓ Apollo配置: 已加载
==================================================
```

## 常见问题与解决方案

### 问题 1：模块未找到错误

**症状**：

```python
ModuleNotFoundError: No module named 'talentsview'
```

**原因**：SDK 未正确安装。

**解决方案**：

```bash
# 确认 pip 版本
pip --version

# 重新安装
pip install --upgrade talentsview

# 验证安装
python -c "import talentsview; print(talentsview.__version__)"
```

### 问题 2：应用ID或智能体ID配置有误

**症状**：

```python
应用ID或智能体ID配置有误，请检查后重试
```

**原因**：环境变量未配置或配置错误（错误码 803）。

**解决方案**：

1. 检查 `.env` 文件是否存在且包含必需配置项
2. 确认代码中调用了 `load_dotenv()`
3. 使用 `talentsview.diagnose_config()` 检查配置状态
4. 验证 `TALENTSVIEW_APP_ID` 和 `TALENTSVIEW_AGENT_ID` 是否正确

```python
import os
from dotenv import load_dotenv

load_dotenv()

# 检查环境变量是否加载
print(f"APP_ID: {os.getenv('TALENTSVIEW_APP_ID')}")
print(f"AGENT_ID: {os.getenv('TALENTSVIEW_AGENT_ID')}")
```

### 问题 3：异步方法运行时错误

**症状**：

```python
RuntimeError: This event loop is already running
```

**原因**：在已有事件循环中使用了 `asyncio.run()`。

**解决方案**：

- **在 Jupyter Notebook 中**：直接使用 `await` 而不是 `asyncio.run()`

```python
# Jupyter Notebook 中
from talentsview import AsyncLLMClient

client = AsyncLLMClient(model="local-qwen3-235b-nothink-moe")
response = await client.chat.completions.create(
    model=client.model,
    messages=[{"role": "user", "content": "你好"}],
    stream=False
)
```

- **在 FastAPI 等异步框架中**：直接使用 `await`

```python
from fastapi import FastAPI
from talentsview import AsyncLLMClient

app = FastAPI()
client = AsyncLLMClient(model="local-qwen3-235b-nothink-moe")

@app.get("/chat")
async def chat(message: str):
    response = await client.chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": message}],
        stream=False
    )
    return {"response": response.choices[0].message.content}
```


## 高级配置

### 自定义 HTTP 客户端

```python
import httpx
from talentsview import LLMClient

# 创建自定义 HTTP 客户端
custom_client = httpx.Client(timeout=30.0)

# 使用自定义客户端
client = LLMClient(
    model="local-qwen3-235b-nothink-moe",
    http_client=custom_client
)
```

### 手动更新配置

适用于运维修改配置后需要立即生效的场景：

```python
import talentsview

# 手动从 Apollo 拉取最新配置
talentsview.update_apollo_config()
```

### 资源清理

应用关闭时清理资源（如 HTTP 连接池）：

```python
import asyncio
import talentsview

async def shutdown_app():
    await talentsview.shutdown()

# 在应用关闭时调用
asyncio.run(shutdown_app())
```

**FastAPI 集成示例**：

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import talentsview

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动
    yield
    # 应用关闭时清理资源
    await talentsview.shutdown()

app = FastAPI(lifespan=lifespan)
```

## 下一步

配置完成后，您可以：

1. 查看 [聊天模型文档](chat_model.md) 了解 LLM 使用方法
2. 查看 [向量化文档](embedding.md) 了解 Embedding 使用方法
3. 查看 [文档处理文档](document.md) 了解文档解析和分块
4. 返回 [主文档](../README.md) 浏览所有功能模块

---

如有其他问题，请联系技术支持团队。
