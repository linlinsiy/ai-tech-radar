# TalentsView SDK 使用模板

基于talentsview-sdk构建的智能Agent服务，展示LLM与联网搜索能力的组合应用。

## 核心功能

- 自动判断是否需要联网搜索（Function Calling模式）
- 基于实时信息生成准确回答
- 支持流式/非流式响应
- 生产级FastAPI架构

## 快速开始

### 环境要求

- Python 3.11+ （目前Langfuse暂不支持Python 3.14）
- 推荐使用Python 3.12（目前发布中心镜像支持的Python版本最高为3.12）
- uv（推荐）

### 1. 安装依赖

```bash
pip install uv
uv sync
```
注意，pip/uv在云桌面安装相关依赖，需要切换为公司源，powershell运行：
```powershell
$env:UV_DEFAULT_INDEX="http://repo.htzq.htsc.com.cn/repository/htscpypi/simple/"
```

### 2. 配置环境变量

项目提供 `.env.uat` 和 `.env.prd` 配置文件，两个环境均已设置好必需配置，如需更改设置，请修改对应文件。


#### 2.1 Langfuse 可观测（可选）

项目已集成Langfuse支持，可追踪Agent调用链路。配置方式参考配置文件：
从[Langfuse控制台](https://eiplite.htsc.com.cn/htgy/talents-view)获取Secret Key和Public Key，填入配置文件即可启用。

### 3. 启动服务

```bash
uv run python main.py
```

访问API文档：http://localhost:8000/docs

### 4. 测试Agent

**非流式调用：**

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "2024年诺贝尔物理学奖得主是谁？"}'
```

**流式调用：**

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "介绍一下人工智能"}'
```

## 本地调试

无需启动 FastAPI 服务，可直接使用 `run_agent.py` 在命令行测试 Agent 功能：

```bash
# 交互模式（持续对话）
uv run python run_agent.py

# 单次提问
uv run python run_agent.py -q "今天有什么新闻"

# 流式输出
uv run python run_agent.py -q "介绍人工智能" -s
```

## 项目结构

```
├── main.py                # FastAPI 服务入口
├── run_agent.py           # 本地调试脚本
app/
├── api/v1/agent.py        # Agent API端点
├── services/
│   └── agent_service.py   # Agent核心逻辑（LLM+搜索编排）
├── models/
│   └── agent_models.py    # 请求响应模型
└── utils/
    └── prompts.py         # Prompt模板
```

## 技术实现

### Function Calling流程

1. LLM判断是否需要联网搜索
2. 若需要，执行WebSearch获取实时信息
3. 将搜索结果作为上下文，LLM生成最终答案

### 关键特性

- 不依赖LangChain框架，基于原生Talentsview SDK实现
- Service层封装业务逻辑，保持代码整洁
- 统一错误处理，中文提示信息
- 支持流式响应（SSE协议）

## 配置说明

查看`.env.uat`或`.env.prd`了解所有可配置项。

## SDK文档

详细的SDK使用方法请参考`/docs`目录。

---

**注意事项：**
- 配置错误时会提示：应用ID或智能体ID配置有误，请检查后重试
