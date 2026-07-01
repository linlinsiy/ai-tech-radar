# 工具与插件（Tools & Plugins）

本文档介绍如何使用 talentsview-sdk 调用平台工具服务和插件服务。

## 功能概述

平台提供两类服务：

1. **工具服务（Tools）**：平台级通用工具
2. **插件服务（Plugins）**：第三方插件及其工具

两者都支持：
- 获取列表
- 查询详情
- 执行调用
- 工具名称映射（通过配置文件简化调用）

## 1. talentsview-sdk

### 1.1 工具服务（Tools）

#### 1.1.1 功能介绍

`ToolsClient` 提供平台工具服务的访问能力：
- **list_tools()**：获取工具列表
- **get_tool_info()**：获取工具详细信息
- **execute_tool()**：执行工具

支持两种调用方式：
- 使用 **tool_id**：直接传入工具ID
- 使用 **tool_name**：通过配置文件映射工具名称（推荐）

#### 1.1.2 基本调用示例

**获取工具列表**：

```python
from talentsview import ToolsClient

# 创建客户端
client = ToolsClient()

# 获取工具列表
tools = client.list_tools()
print(f"获取到 {len(tools)} 个工具")

for tool in tools:
    print(f"  工具ID: {tool.id}")
    print(f"  工具名称: {tool.name}")
    print(f"  描述: {tool.description}\n")
```

**获取工具详情（使用 tool_id）**：

```python
from talentsview import ToolsClient

client = ToolsClient()

# 使用工具ID获取详情
tool_detail = client.get_tool_info(tool_id="cvrmtpi4kmj6p97blt2g")

print(f"工具名称: {tool_detail.meta.name}")
print(f"工具描述: {tool_detail.meta.description}")

# 查看参数
for param_name, param_info in tool_detail.meta.parameters.items():
    print(f"参数: {param_name}, 类型: {param_info.type}, 必需: {param_info.required}")
```

**执行工具（使用 tool_id）**：

```python
from talentsview import ToolsClient

client = ToolsClient()

# 执行工具
result = client.execute_tool(
    tool_id="cvrmtpi4kmj6p97blt2g",
    input_data={"query": "南京今天的天气"},
    user_channel="Demo"
)

if result.Success:
    print(f"执行成功: {result.Result}")
else:
    print(f"执行失败: {result.ErrorMessage}")
```

#### 1.1.3 工具名称功能

**配置工具名称映射**：

在项目根目录创建 `resources.dev.yaml`（开发环境）或 `resources.prd.yaml`（生产环境）：

```yaml
# 工作空间ID（必需）
workspace_id: "your_workspace_id_here"

# 工具名称映射配置
tools:
  联网查询服务: "cvrmtpi4kmj6p97blt2g"
  离线ASR: "d4sj2sh8o1bgaqub62m0"
  资讯rag: "d4i2h1b0a51ick6963u0"
```

**配置文件查找优先级**：
1. 环境变量 `TALENTSVIEW_RESOURCES_FILE` 指定的路径
2. 当前工作目录下的 `resources.{ENV}.yaml`
3. 项目根目录下的 `resources.{ENV}.yaml`

**使用工具名称调用**：

```python
from talentsview import ToolsClient

client = ToolsClient()

# 使用工具名称获取详情
tool_detail = client.get_tool_info(tool_name="联网查询服务")
print(f"工具名称: {tool_detail.meta.name}")

# 使用工具名称执行
result = client.execute_tool(
    tool_name="联网查询服务",
    input_data={"query": "南京今天的天气"},
    user_channel="Demo"
)

if result.Success:
    print(f"执行结果: {result.Result}")
```

**注意事项**：
- `tool_id` 和 `tool_name` 不能同时指定，必须选择其中一个
- 工具名称必须在配置文件中存在对应的映射关系
- 配置文件修改后，需要重启应用或调用 `talentsview.update_apollo_config()` 生效

#### 1.1.4 异步调用

```python
import asyncio
from talentsview import AsyncToolsClient

async def main():
    client = AsyncToolsClient()
    
    # 异步获取工具列表
    tools = await client.list_tools()
    print(f"获取到 {len(tools)} 个工具")
    
    # 异步获取工具详情
    if tools:
        tool_detail = await client.get_tool_info(tool_id=tools[0].id)
        print(f"工具名称: {tool_detail.meta.name}")
    
    # 异步执行工具
    result = await client.execute_tool(
        tool_name="联网查询服务",
        input_data={"query": "测试"},
        user_channel="AsyncDemo"
    )
    
    print(f"执行结果: {result.Success}")

asyncio.run(main())
```

#### 1.1.5 参数说明

**list_tools() 参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| detail_info | bool | 是否返回详细信息 | 否 | False |
| tool_id_contain | List[str] | 工具ID过滤列表 | 否 | None |

**get_tool_info() 参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| tool_id | str | 工具ID | tool_id 和 tool_name 二选一 | None |
| tool_name | str | 工具名称 | tool_id 和 tool_name 二选一 | None |

**execute_tool() 参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| tool_id | str | 工具ID | tool_id 和 tool_name 二选一 | None |
| tool_name | str | 工具名称 | tool_id 和 tool_name 二选一 | None |
| input_data | dict | 工具执行输入数据 | 是 | - |
| user_channel | str | 用户渠道标识 | 是 | - |

### 1.2 插件服务（Plugins）

#### 1.2.1 功能介绍

`PluginsClient` 提供平台插件服务的访问能力：
- **list_plugins()**：获取插件列表
- **get_plugin_tool_info()**：获取插件工具详细信息
- **execute_plugin_tool()**：执行插件工具

插件工具同样支持工具名称功能，与 Tools 模块共享配置。

#### 1.2.2 基本调用示例

**获取插件列表**：

```python
from talentsview import PluginsClient

# 创建客户端
client = PluginsClient()

# 获取插件列表
plugins = client.list_plugins()
print(f"获取到 {len(plugins)} 个插件")

for plugin in plugins:
    print(f"插件: {plugin.name}, 工具数量: {plugin.tool_count}")
    for tool in plugin.tools:
        print(f"  工具: {tool.name} - {tool.description}")
```

**获取插件工具详情**：

```python
from talentsview import PluginsClient

client = PluginsClient()

# 方式1：通过工具ID获取详情
tool_detail = client.get_plugin_tool_info(
    tool_id="tool_id_here",
    plugin_id="plugin_id_here"  # 可选
)

# 方式2：仅通过工具ID获取（自动查找）
tool_detail = client.get_plugin_tool_info(tool_id="tool_id_here")

# 方式3：使用工具名称获取详情（推荐）
tool_detail = client.get_plugin_tool_info(tool_name="工具名称")

print(f"工具名称: {tool_detail.name}")
print(f"所属插件: {tool_detail.plugin_name}")
```

**执行插件工具**：

```python
from talentsview import PluginsClient

client = PluginsClient()

# 使用工具ID执行
result = client.execute_plugin_tool(
    tool_id="tool_id_here",
    input_data={"param1": "value1"},
    user_channel="PluginDemo",
    config={"temp_auth": "auth_info"}  # 可选的配置参数
)

# 使用工具名称执行（推荐）
result = client.execute_plugin_tool(
    tool_name="工具名称",
    input_data={"param1": "value1"},
    user_channel="PluginDemo"
)

if result.Success:
    print(f"执行结果: {result.Result}")
else:
    print(f"执行失败: {result.ErrorMessage}")
```

#### 1.2.3 工具名称配置

插件工具与 Tools 模块共享相同的配置文件和映射机制：

```yaml
# resources.dev.yaml
workspace_id: "your_workspace_id_here"

# 工具名称映射配置（同时支持 Tools 和 Plugins）
tools:
  联网查询服务: "cvrmtpi4kmj6p97blt2g"
  数据分析插件: "plugin_tool_id_here"
  文件处理工具: "another_tool_id_here"
```

**使用方式**：

```python
from talentsview import ToolsClient, PluginsClient

# Tools 模块使用
tools_client = ToolsClient()
result1 = tools_client.execute_tool(tool_name="联网查询服务", input_data={...})

# Plugins 模块使用（共享相同配置）
plugins_client = PluginsClient()
result2 = plugins_client.execute_plugin_tool(tool_name="数据分析插件", input_data={...})
```

**注意事项**：
- Tools 和 Plugins 模块共享同一个工具名称映射配置
- 工具名称在配置文件中必须唯一
- 配置要求与 Tools 模块完全相同

#### 1.2.4 异步调用

```python
import asyncio
from talentsview import AsyncPluginsClient

async def main():
    client = AsyncPluginsClient()
    
    # 异步获取插件列表
    plugins = await client.list_plugins()
    print(f"获取到 {len(plugins)} 个插件")
    
    # 异步获取插件工具详情
    if plugins and plugins[0].tools:
        tool_detail = await client.get_plugin_tool_info(
            tool_id=plugins[0].tools[0].id
        )
        print(f"工具名称: {tool_detail.name}")
    
    # 异步执行插件工具
    result = await client.execute_plugin_tool(
        tool_name="工具名称",
        input_data={},
        user_channel="AsyncDemo"
    )
    
    print(f"执行结果: {result.Success}")

asyncio.run(main())
```

#### 1.2.5 参数说明

**get_plugin_tool_info() 参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| tool_id | str | 工具ID | tool_id 和 tool_name 二选一 | None |
| tool_name | str | 工具名称 | tool_id 和 tool_name 二选一 | None |
| plugin_id | str | 插件ID（可选） | 否 | None |

**execute_plugin_tool() 参数**：

| 参数名 | 类型 | 说明 | 必填 | 默认值 |
|-------|------|------|------|--------|
| tool_id | str | 工具ID | tool_id 和 tool_name 二选一 | None |
| tool_name | str | 工具名称 | tool_id 和 tool_name 二选一 | None |
| input_data | dict | 工具执行输入数据 | 是 | - |
| user_channel | str | 用户渠道标识 | 是 | - |
| config | dict | 工具执行配置（可选） | 否 | None |

### 1.3 注意事项

1. **认证配置**：
   - 需要配置 `TALENTSVIEW_APP_ID`、`TALENTSVIEW_AGENT_ID`
   - 使用工具名称功能还需配置 `workspace_id`

2. **错误处理**：
   - 配置错误（错误码 803）：应用ID或智能体ID配置有误，请检查环境变量配置
   - 工具名称未找到：检查配置文件中是否存在对应映射
   - 执行失败：查看 `result.ErrorMessage` 获取详细错误信息

3. **配置文件**：
   - 支持 DEV 和 PRD 两种环境配置
   - 配置文件修改后需重启应用或调用 `talentsview.update_apollo_config()`

4. **最佳实践**：
   - 优先使用工具名称而非工具ID，便于代码维护
   - 在配置文件中集中管理工具映射
   - 使用异步调用提高并发性能

## 2. langchain-htai

### 2.1 状态说明

langchain-htai 当前**未实现** Tools 和 Plugins 模块。

如需使用工具和插件服务，请直接使用 **talentsview-sdk**：

```python
from talentsview import ToolsClient, PluginsClient

# 使用 talentsview-sdk 调用工具服务
tools_client = ToolsClient()
result = tools_client.execute_tool(
    tool_name="联网查询服务",
    input_data={"query": "测试"},
    user_channel="Demo"
)

# 使用 talentsview-sdk 调用插件服务
plugins_client = PluginsClient()
result = plugins_client.execute_plugin_tool(
    tool_name="插件工具",
    input_data={"param": "value"},
    user_channel="Demo"
)
```

### 2.2 未来计划

langchain-htai 将在后续版本中提供：
- LangChain Tool 协议适配
- 与 LangChain Agent 的集成支持
- 工具自动发现和注册机制

## 相关文档

- [安装与配置指南](installation.md)
- [聊天模型文档](chat_model.md)
- [联网搜索文档](web_search.md)

---

返回 [主文档](../README.md)
