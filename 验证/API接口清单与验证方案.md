# AI技术趋势雷达 -- API接口清单与验证方案

> 生成日期：2026-06-16
> 覆盖范围：AWS侧服务 + 内部应用节点（含XXL-Job调度接口 + 系统出站调用）

---

## 一、服务拓扑概览

| 侧 | 服务 | 监听端口 | XXL-Job Executor 端口 | 部署位置 |
|---|---|---|---|---|
| AWS 侧 | FastAPI（uvicorn） | 9003 | 9999 | 亚马逊云节点 |
| 内部侧 | FastAPI（uvicorn） | 9001 | 9998 | 内部节点 168.64.18.190 |

XXL-Job Admin 地址：`http://168.64.38.162:8080/xxl-job-admin/api/`

### 1.1 服务后台启动方式

推荐使用 `systemd` 后台运行，具备开机自启、异常自动重启、统一状态查看能力。启动顺序建议为：**先启动内部侧，再启动 AWS 侧**。

#### 1.1.1 内部侧服务（internal）

首次部署或依赖变更后，先执行安装脚本：

```bash
cd /app/001804/internal
chmod +x deploy/install.sh deploy/start.sh
./deploy/install.sh
```

注册并启动 systemd 服务：

```bash
sudo cp /app/001804/internal/deploy/ai-radar-internal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-radar-internal
sudo systemctl start ai-radar-internal
```

常用运维命令：

```bash
sudo systemctl status ai-radar-internal
sudo systemctl restart ai-radar-internal
journalctl -u ai-radar-internal -f
curl http://127.0.0.1:9001/health
```

#### 1.1.2 AWS 侧服务（aws）

首次部署或依赖变更后，先执行安装脚本：

```bash
cd /app/001804/aws
chmod +x deploy/install.sh deploy/start.sh
./deploy/install.sh
```

注册并启动 systemd 服务：

```bash
sudo cp /app/001804/aws/deploy/ai-radar-aws.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-radar-aws
sudo systemctl start ai-radar-aws
```

常用运维命令：

```bash
sudo systemctl status ai-radar-aws
sudo systemctl restart ai-radar-aws
journalctl -u ai-radar-aws -f
curl http://127.0.0.1:9003/health
```

#### 1.1.3 Windows 本地启动方式

Windows 本地验证建议先启动 internal，再启动 AWS；两个服务分别使用一个 PowerShell 窗口前台运行，便于直接查看日志。首次启动前分别在两个目录安装依赖：

```powershell
# internal 侧首次安装
Set-Location E:\code\AI技术趋势雷达\tech-research\internal
py -3 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# AWS 侧首次安装
Set-Location E:\code\AI技术趋势雷达\tech-research\aws
py -3 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动 internal 服务：

```powershell
Set-Location E:\code\AI技术趋势雷达\tech-research\internal
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9001 --log-level info
```

在第二个 PowerShell 窗口启动 AWS 服务：

```powershell
Set-Location E:\code\AI技术趋势雷达\tech-research\aws
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9003 --log-level info
```

本地服务健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:9001/health | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:9003/health | ConvertTo-Json -Depth 5
```

如需后台启动，可执行以下命令；日志分别写入各服务的 `logs/windows-dev.stdout.log` 和 `logs/windows-dev.stderr.log`：

```powershell
$internalDir = 'E:\code\AI技术趋势雷达\tech-research\internal'
New-Item -ItemType Directory -Force -Path "$internalDir\logs" | Out-Null
Start-Process -FilePath "$internalDir\venv\Scripts\python.exe" `
  -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 9001 --log-level info' `
  -WorkingDirectory $internalDir `
  -RedirectStandardOutput "$internalDir\logs\windows-dev.stdout.log" `
  -RedirectStandardError "$internalDir\logs\windows-dev.stderr.log"

$awsDir = 'E:\code\AI技术趋势雷达\tech-research\aws'
New-Item -ItemType Directory -Force -Path "$awsDir\logs" | Out-Null
Start-Process -FilePath "$awsDir\venv\Scripts\python.exe" `
  -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 9003 --log-level info' `
  -WorkingDirectory $awsDir `
  -RedirectStandardOutput "$awsDir\logs\windows-dev.stdout.log" `
  -RedirectStandardError "$awsDir\logs\windows-dev.stderr.log"
```

停止本地服务：前台启动时在对应 PowerShell 窗口按 `Ctrl+C`；后台启动时按端口定位并停止进程：

```powershell
# 查看 9001（internal）和 9003（AWS）当前监听进程
Get-NetTCPConnection -State Listen -LocalPort 9001,9003 |
  Select-Object LocalPort, OwningProcess

# 停止 internal 服务
$internalProcess = Get-NetTCPConnection -State Listen -LocalPort 9001 -ErrorAction SilentlyContinue
if ($internalProcess) {
  $internalProcess | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ }
}

# 停止 AWS 服务
$awsProcess = Get-NetTCPConnection -State Listen -LocalPort 9003 -ErrorAction SilentlyContinue
if ($awsProcess) {
  $awsProcess | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ }
}
```

#### 1.1.4 临时后台启动方式

如果当前服务器暂不方便注册 systemd，可使用 `nohup` 临时后台启动：

```bash
cd /app/001804/internal
mkdir -p logs
nohup ./deploy/start.sh > logs/nohup.log 2>&1 &

cd /app/001804/aws
mkdir -p logs
nohup ./deploy/start.sh > logs/nohup.log 2>&1 &
```

查看进程和日志：

```bash
ps -ef | grep "uvicorn app.main:app" | grep -v grep
tail -f /app/001804/internal/logs/nohup.log
tail -f /app/001804/aws/logs/nohup.log
```

临时方式不会自动开机启动，也不具备 systemd 的自动拉起能力，仅建议用于验证或临时排障。

---

## 二、AWS侧接口

### 2.1 `GET /health` -- 健康检查

- **协议**：HTTP（FastAPI 直接注册路由）
- **端口**：9003
- **鉴权**：无
- **功能**：异步检查数据源可达性、外部大模型 API 连通性、内部导入端点连通性
- **请求示例**

```http
GET http://<aws-node>:9003/health HTTP/1.1
```

- **成功响应**（200）

```json
{
  "status": "healthy",
  "checks": {
    "data_sources": {
      "total": 12,
      "reachable": 12,
      "unreachable": 0,
      "details": [
        {"code": "aws-ml-blog", "status": "reachable", "latency_ms": 234}
      ]
    },
    "external_llm": {
      "status": "healthy",
      "models": ["gpt-4o-mini"],
      "latency_ms": 120
    },
    "import_endpoint": {
      "status": "reachable",
      "url": "http://168.64.18.190:9001/api/v1/radar/import",
      "latency_ms": 45
    }
  },
  "timestamp": "2026-06-16T08:00:00"
}
```

- **异常情况**：任一组件不可达时 `status` 为 `"degraded"`；数据源无 URL 时返回 `"no URL configured"`
- **验证方式**

```bash
# AWS 侧服务器上执行
curl http://localhost:9003/health | python -m json.tool
# 验证 status 字段为 healthy，各组件 checks 状态正常
```

---

### 2.2 `aiRadarCollectJob` -- 定时采集分析（XXL-Job）

- **协议**：XXL-Job（pyxxl Executor 注册到 XXL-Job Admin）
- **Executor 端口**：9999
- **鉴权**：XXL-Job access_token（当前配置：`kSaGFtaEcMXcrPBGkyWWkM78yNtMKmhT`）
- **功能**：编排 L0采集 -> L1解析去重 -> L2基础分析 -> L3深度洞察 -> 受控导入全流程
- **调度参数**（JSON 字符串）

```json
{"scope": "all"}
{"scope": "sources", "sources": "aws-ml-blog,arxiv-cs-ai"}
{"scope": "sources", "sources": "aws-ml-blog,arxiv-cs-ai", "from": "2026-06-20", "to": "2026-06-22"}
{"scope": "timerange", "from": "2026-06-01", "to": "2026-06-10"}
{"scope": "rerun", "batch_no": "IMP-20260610-001"}
```

- **scope 说明**

| scope | 含义 | 必填附加字段 |
|---|---|---|
| `all` | 全量采集所有启用的数据源 | -- |
| `sources` | 仅采集指定数据源 | `sources`: 数据源编码，逗号分隔字符串 |
| `timerange` | 限定文章发布时间范围补跑 | `from` / `to`: ISO 8601 日期 |
| -- | `sources` 与 `from`/`to` 可叠加使用，scope 值不影响组合逻辑 | -- |
| `rerun` | 重新处理失败批次 | `batch_no`: 失败批次号 |

- **验证方式**

```
1. 登录 XXL-Job Admin -> 找到 aiRadarCollectJob 任务
2. 点击"执行一次"，参数填 {"scope":"all"}
3. 查看调度日志确认 JobHandler 被触发并执行
4. 检查 AWS 侧 app.log 确认各阶段日志输出
```

---

### 2.3 `aiRadarHealthCheckJob` -- 数据源健康检查（XXL-Job）

- **协议**：XXL-Job（pyxxl Executor）
- **Executor 端口**：9999
- **功能**：遍历 12 个数据源，对每个源发起 HTTP HEAD 请求，记录可达性和延迟。不可达源写入 error.log
- **调度参数**：无（预留空字符串）
- **预期频率**：每 30 分钟
- **验证方式**

```
1. XXL-Job Admin -> 手动执行 aiRadarHealthCheckJob
2. 检查 AWS 侧 app.log：应有 "健康检查完成: reachable=7/12, unreachable=[]" 类似输出
3. 对于 access_url 为 https://... 的源（新智元等5个），检查日志为 "access_url 为空，跳过检查"
```

---


---

### 2.4 `POST /api/v1/jobs/collect` -- 手动触发采集分析（HTTP）

- **协议**：HTTP
- **端口**：9003
- **鉴权**：无
- **功能**：绕过 XXL-Job 直接触发采集分析全流程，用于本地调试和 XXL-Job Admin 不可达时的替代方案。参数语义与 `aiRadarCollectJob` 相同
- **请求体**（JSON）

```json
{
  "scope": "all",
  "sources": "xin-zhi-yuan,aws-ml-blog",
  "from_date": "2026-06-20",
  "to_date": "2026-06-22",
  "task_type": "manual_backfill"
}
```

- **字段说明**（全部可选，默认 scope=all）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scope` | string | 否 | all / sources / timerange，默认 all |
| `sources` | string | 否 | 数据源编码，逗号分隔。可与 from_date/to_date 组合使用 |
| `from_date` | string | 否 | 开始日期 YYYY-MM-DD，限定文章发布时间范围 |
| `to_date` | string | 否 | 结束日期 YYYY-MM-DD |
| `task_type` | string | 否 | scheduled / manual_backfill，默认 manual_backfill |

- **与 XXL-Job 版本的差异**：XXL-Job `sources` 为 JSON 数组 `["a","b"]`，HTTP 版为逗号分隔字符串 `"a,b"`；XXL-Job 日期字段为 `from`/`to`，HTTP 版为 `from_date`/`to_date`
- **验证方式**

```powershell
# 全量采集（无参数）
Invoke-RestMethod -Method Post -Uri "http://localhost:9003/api/v1/jobs/collect" -Body '{"scope":"all"}' -ContentType "application/json" | ConvertTo-Json -Depth 5

# 指定源 + 时间范围
$body = @{ scope = "all"; sources = "xin-zhi-yuan,aws-ml-blog"; from_date = "2026-06-20"; to_date = "2026-06-22" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:9003/api/v1/jobs/collect" -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 5
```

- **Linux curl 示例**

```bash
# 全量采集
curl -sS -X POST 'http://127.0.0.1:9003/api/v1/jobs/collect' \
  -H 'Content-Type: application/json' \
  -d '{"scope":"all","task_type":"manual_backfill"}' | python3 -m json.tool

# 指定源 + 时间范围
curl -sS -X POST 'http://127.0.0.1:9003/api/v1/jobs/collect' \
  -H 'Content-Type: application/json' \
  -d '{"scope":"all","sources":"aws-ml-blog,arxiv-cs-ai","from_date":"2026-06-20","to_date":"2026-06-22","task_type":"manual_backfill"}' | python3 -m json.tool
```

---

### 2.5 `POST /api/v1/validation/collect` -- 分阶段采集验证（HTTP）

- **协议**：HTTP
- **端口**：9003
- **鉴权**：无
- **功能**：只执行来源采集和文章详情读取，不调用 L2/L3、不导入内部服务、不写入正式去重缓存。采集结果保存到 AWS 本地，供后续单独验证分析阶段。
- **主逻辑关系**：复用正式任务的 `CollectOrchestrator.collect_stage()`；验证接口仅关闭正式副作用，不维护一套独立爬虫逻辑。
- **请求体**：除 `strategy` 外，字段与 `POST /api/v1/jobs/collect` 一致。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `strategy` | string | 否 | `primary_resilient` 或 `server_recommended`，默认 `primary_resilient` |
| `scope` | string | 否 | `all` / `sources` / `timerange`，默认 `all` |
| `sources` | string | 否 | 逗号分隔的数据源编码；用于缩小验证范围 |
| `from_date` | string | 否 | 开始日期，格式 `YYYY-MM-DD` |
| `to_date` | string | 否 | 结束日期，格式 `YYYY-MM-DD` |
| `task_type` | string | 否 | 任务标识，默认 `manual_backfill` |

- **策略说明**：`server_recommended` 使用服务器探测后给出的站点适配配置；`primary_resilient` 使用当前工程的主采集方式及其降级变体。两种策略均可用相同参数验证同一批来源。
- **本地结果**：成功后返回 `batch_no` 和 `result_file`，原始文章、来源执行结果、正文可用数量及来源分布保存到 `data/validation/collections/<batch_no>.json`。
- **Linux curl 示例**

```bash
# 使用当前工程的主/降级采集策略，验证指定来源和时间范围
curl -sS -X POST 'http://127.0.0.1:9003/api/v1/validation/collect' \
  -H 'Content-Type: application/json' \
  -d '{"strategy":"primary_resilient","scope":"sources","sources":"36kr-ai,qbitai","from_date":"2026-06-20","to_date":"2026-06-22","task_type":"manual_backfill"}' \
  | python3 -m json.tool

# 使用服务器探测适配策略，验证全部启用来源
curl -sS -X POST 'http://127.0.0.1:9003/api/v1/validation/collect' \
  -H 'Content-Type: application/json' \
  -d '{"strategy":"server_recommended","scope":"all","task_type":"manual_backfill"}' \
  | python3 -m json.tool
```

- **Windows PowerShell 示例**

```powershell
# 使用服务器探测适配策略，采集 2026-06-17 至 2026-07-17 的全部启用来源
$body = @{
  strategy = 'primary_resilient'
  scope = 'all'
  task_type = 'manual_backfill'
  from_date = '2026-06-17'
  to_date = '2026-07-17'
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:9003/api/v1/validation/collect' `
  -ContentType 'application/json' `
  -Body $body | ConvertTo-Json -Depth 10
```

- **验证要点**：响应的 `success` 应为 `true`；记录返回的 `data.batch_no`，检查 `data.result_file` 存在，并关注 `article_count`、`content_available_count`、`source_distribution` 和各来源 `status`。该接口不会创建内部导入批次或简报草稿。

---

### 2.6 `POST /api/v1/validation/analyze` -- 分阶段分析验证（HTTP）

- **协议**：HTTP
- **端口**：9003
- **鉴权**：无
- **功能**：读取一次采集验证的本地结果，只执行候选池、L2 和 L3；不重新采集、不调用自动 URL 发现、不写入正式去重缓存、不导入内部服务。
- **主逻辑关系**：复用正式任务的 `CollectOrchestrator.analyze_stage()`，因此评分、标题语义路由、L3 候选均衡和深度分析规则与正式运行一致。
- **请求体**

```json
{
  "collection_batch_no": "VAL-COL-20260717-101530-123456"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `collection_batch_no` | string | 是 | 上一步采集验证接口返回的 `data.batch_no` |

- **本地结果**：分析结果保存到 `data/validation/analyses/<analysis_batch_no>.json`，文件包含 L2 分析、被过滤结果、L3 深度洞察、候选均衡结果和阶段统计。
- **Linux curl 示例**

```bash
# 将下面的批次号替换为采集验证接口实际返回的 data.batch_no
curl -sS -X POST 'http://127.0.0.1:9003/api/v1/validation/analyze' \
  -H 'Content-Type: application/json' \
  -d '{"collection_batch_no":"VAL-COL-20260717-101530-123456"}' \
  | python3 -m json.tool
```

- **验证要点**：响应中应包含 `analysis_batch_no`、`result_file`、`l2_success`、`l3_selected` 和 `l3_success`。可通过 `l2_source_distribution`、`l2_category_distribution`、`l3_selection` 和 `pipeline_stage_stats` 检查来源均衡、分类覆盖、统一评分门槛及 L3 失败原因。分析验证不创建 MySQL 记录、知识库文件或简报草稿。

---

### 2.7 `POST /api/v1/jobs/health-check` -- 手动触发健康检查（HTTP）

- **协议**：HTTP
- **端口**：9003
- **鉴权**：无
- **功能**：绕过 XXL-Job 直接触发数据源可达性检查，遍历 12 个数据源逐一发起 HTTP HEAD 请求
- **请求体**：无
- **响应示例**

```json
{
  "success": true,
  "data": {
    "total": 12,
    "reachable": 7,
    "unreachable": 5,
    "details": [
      {"code": "aws-ml-blog", "status": "reachable", "latency_ms": 234},
      {"code": "xin-zhi-yuan", "status": "unreachable", "error": "no URL configured"}
    ]
  }
}
```

- **验证方式**

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:9003/api/v1/jobs/health-check" | ConvertTo-Json -Depth 5
# 预期 reachable + unreachable 合计 = 12，含各数据源详情
```

- **Linux curl 示例**

```bash
curl -sS -X POST 'http://127.0.0.1:9003/api/v1/jobs/health-check' | python3 -m json.tool
# 预期 reachable + unreachable 合计 = data_sources.count，含各数据源详情
```


## 三、内部侧接口

### 3.1 `GET /health` -- 健康检查

- **协议**：HTTP
- **端口**：9001
- **鉴权**：无
- **功能**：检查 MySQL 连通性、TalentsView SDK 知识库状态、内部大模型连通性
- **请求示例**

```http
GET http://168.64.18.190:9001/health HTTP/1.1
```

- **成功响应示例**

```json
{
  "status": "healthy",
  "checks": {
    "mysql": {"status": "healthy"},
    "knowledge_base": {"status": "healthy", "dataset_id": "019eca45-59a0-746f-ad81-715e1b9a61e8"},
    "internal_llm": {"status": "healthy", "model": "saas-doubao-15-pro-32k", "endpoint": "http://168.63.65.40:8090/llm-service/v1"}
  },
  "timestamp": "2026-06-16T08:00:00"
}
```

- **验证方式**

```powershell
Invoke-RestMethod -Uri "http://168.64.18.190:9001/health" | ConvertTo-Json -Depth 5
# 验证 status 为 healthy，各组件正常
```

- **Linux curl 示例**

```bash
curl -sS 'http://168.64.18.190:9001/health' | python3 -m json.tool
# 验证 status 为 healthy，各组件正常
```

---

### 3.2 `POST /api/v1/radar/import` -- 受控导入接口

- **协议**：HTTP（FastAPI APIRouter）
- **端口**：9001
- **鉴权**：无应用层鉴权（安全边界由网络侧防火墙负责）
- **功能**：接收 AWS 侧加工的结构化成果，写入 MySQL（6 张表）+ 生成 Markdown 文件上传知识库
- **幂等规则**：
  - `batch_no` 已存在且 `import_status=success` -> 直接返回 200
  - `url_hash` 唯一索引去重
- **请求体结构**

```json
{
  "batch": {
    "batch_no": "IMP-20260616-001",
    "task_type": "scheduled",
    "source_scope": ["xin-zhi-yuan", "liangziwei", "arxiv-cs-ai"],
  },
  "articles": [
    {
      "url": "https://wechat2rss.bestblogs.dev/feed/e531a18b21c34cf787b83ab444eef659d7a980de.xml",
      "source_code": "xin-zhi-yuan",
      "url_hash": "a028766efb889d88a180fa2dbe1c776cd2e68d6c736b5ec12f0863fc3c2efa00",
      "title": "GPT-5 训练取得突破：采用 MoE 混合专家架构，推理能力大幅提升",
      "author": "新智元编辑部",
      "publish_time": "2026-06-15T10:00:00+08:00",
      "crawl_time": "2026-06-16T08:00:00+08:00",
      "raw_summary": "OpenAI 发布 GPT-5 最新进展，新模型采用 MoE 架构，在多项推理基准上取得重大突破，同时推理成本下降约 40%，预计2026年Q3开放API...",
      "full_content": "(完整原文，本文长约1500字，含标题与正文，实际入库时为完整HTML/文本，此处省略)",
      "content_hash": "f900614639c6e252c07184fb006d97d00c1a7738f81b9ea4bee57136dfb68327"
    },
    {
      "url": "https://www.qbitai.com/feed",
      "source_code": "liangziwei",
      "url_hash": "8cb0c38845e1e86d464fdc910e1d6476ab4c4084ac9fc8faff700f01a6041099",
      "title": "多模态大模型竞争加剧：谷歌 Gemini 3 与 Anthropic Claude 4 对比评测",
      "author": "量子位编辑部",
      "publish_time": "2026-06-14T18:00:00+08:00",
      "crawl_time": "2026-06-16T08:00:00+08:00",
      "raw_summary": "谷歌最新发布的 Gemini 3 与 Anthropic 的 Claude 4 在多模态基准测试中展开激烈竞争，双方各有所长...",
      "full_content": "(完整原文，本文约800字，实际入库字段较长，此处省略)",
      "content_hash": "a8b76e8e97d7e03355ec6c761c2acde54c8dcd5a15dd22d4b5bf9a4b6c024f85"
    },
    {
      "url": "http://export.arxiv.org/rss/cs.AI",
      "source_code": "arxiv-cs-ai",
      "url_hash": "c87545f0db97677a5199597167d7ab1583351458f559cb0749235bbca84cdfb7",
      "title": "Scaling Laws for Mixture-of-Experts Transformers",
      "author": "Smith J., Chen L. et al.",
      "publish_time": "2026-06-13T00:00:00+00:00",
      "crawl_time": "2026-06-16T08:00:00+08:00",
      "raw_summary": "本文系统研究了 MoE Transformer 架构的缩放定律，发现专家数量与训练效率之间存在非线性关系...",
      "full_content": "(完整原文，arXiv论文摘要及全文链接，此处省略)",
      "content_hash": "a5cee077ef02681fd489ff15a14da9127efd966afc3cb8c28f304910e337b6df"
    }
  ],
  "analyses": [
    {
      "article_url_hash": "a028766efb889d88a180fa2dbe1c776cd2e68d6c736b5ec12f0863fc3c2efa00",
      "summary_cn": "本文报道 OpenAI GPT-5 的最新进展：采用 MoE 混合专家架构，推理能力显著提升，成本下降约40%。GPT-5 预计2026年Q3开放API，这将进一步推动企业级AI应用的普及。",
      "keywords": ["GPT-5", "MoE", "大模型", "OpenAI", "推理成本"],
      "tech_tags": ["大模型进展", "MoE架构"],
      "companies": ["OpenAI"],
      "score_tech_depth": 6.5,
      "score_engineering": 4.0,
      "score_trend": 8.5,
      "score_credibility": 9.0,
      "score_timeliness": 9.5
    },
    {
      "article_url_hash": "a028766efb889d88a180fa2dbe1c776cd2e68d6c736b5ec12f0863fc3c2efa00",
      "summary_cn": "GPT-5 转向 MoE 架构是 OpenAI 应对大模型训练成本压力的关键信号。MoE 架构通过稀疏激活仅调用部分专家参数，在保持模型容量的同时降低推理成本。结合近期 Google Gemini 3 和 Anthropic Claude 4 均采用 MoE 变体的趋势，判断 2026 年将成为 MoE 架构从实验走向主流部署的转折点。建议持续跟踪各厂商 MoE 具体实现（如专家路由策略、负载均衡方案）以及对应的硬件适配方案。",
      "keywords": ["MoE", "模型架构", "推理成本", "行业趋势"],
      "tech_tags": ["技术洞察", "MoE架构"],
      "companies": ["OpenAI", "Google", "Anthropic"],
      "score_tech_depth": 8.5,
      "score_engineering": 5.0,
      "score_trend": 9.0,
      "score_credibility": 8.5,
      "score_timeliness": 9.5
    }
  ],
  "insights": [
    {
      "article_url_hash": "a028766efb889d88a180fa2dbe1c776cd2e68d6c736b5ec12f0863fc3c2efa00",
      "technical_background": "2025年以来，大模型训练与推理成本持续上升，成为限制AI应用大规模部署的主要瓶颈。传统Dense架构所有参数在每次推理中均被激活，导致计算资源需求随模型规模线性增长。",
      "core_problem": "如何在保持模型容量的同时大幅降低推理成本？MoE（Mixture-of-Experts）架构通过稀疏激活机制提供了潜在解决方案，但其工程实现复杂，路由策略与负载均衡方案仍在快速迭代中。",
      "technical_solution": "MoE 架构将模型参数划分为多个专家子网络，每次推理仅激活部分专家（通常 1-3 个），从而在几乎不损失模型容量的前提下将推理成本降低 40%-70%。各厂商实现差异主要集中在：(1) 专家路由算法（Top-K vs 随机路由）；(2) 负载均衡策略（辅助损失 vs 容量因子）；(3) 硬件适配（GPU 显存布局优化）。",
      "impact_analysis": "MoE 架构的成熟将从根本上改变大模型的部署经济学。预计 2026 年下半年起，基于 MoE 的 API 服务将逐步取代 Dense 模型成为主流，推理成本下降将推动 AI 应用在边缘设备和企业私有化部署场景的爆发。",
      "reference_value": "建议内部技术雷达持续跟踪各主要厂商（OpenAI、Google、Anthropic、Meta）的 MoE 具体实现方案，特别关注各自的路由策略和专家负载均衡方法，这些细节将直接影响我们在私有化部署场景中的技术选型。"
    }
  ]}
```

- **成功响应**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "batch_no": "IMP-20260616-001",
    "article_count": 1,
    "success_count": 1,
    "failed_count": 0,
    "kb_uploaded": 1,
    "imported_articles": [
      {"url_hash": "a028766efb889d88a180fa2dbe1c776cd2e68d6c736b5ec12f0863fc3c2efa00", "mysql_id": 42, "status": "imported"}
    ]
  }
}
```

- **错误响应示例**

```json
// 503, database connection error
{"code": 503, "message": "service_unavailable", "detail": "internal service error"}

// Idempotent return
{"code": 0, "message": "ok", "data": {"batch_no": "IMP-20260616-001", "import_status": "success", "note": "batch_already_exists"}}
```

- **验证方式**

```powershell
$body = @{
  batch = @{ batch_no = "TEST-20260616-001"; task_type = "scheduled"; source_scope = @() }
  articles = @()
  analyses = @()
  insights = @()
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "http://168.64.18.190:9001/api/v1/radar/import" -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 5

# 预期：返回 code=0，article_count=0，success_count=0
# 验证 MySQL ai_radar_import_batch 表中新增一条记录
```

- **Linux curl 示例**

```bash
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/radar/import' \
  -H 'Content-Type: application/json' \
  -d '{
    "batch": {
      "batch_no": "TEST-20260616-001",
      "task_type": "scheduled",
      "source_scope": []
    },
    "articles": [],
    "analyses": [],
    "insights": []
  }' | python3 -m json.tool

# 预期：返回 code=0，article_count=0，success_count=0
# 验证 MySQL ai_radar_import_batch 表中新增一条记录
```

```bash
# 失败后重新导入
curl -sS -X POST 'http://127.0.0.1:9001/api/v1/radar/import' \
  -H 'Content-Type: application/json' \
  --data-binary @data/failed_imports/IMP-20260710-123456.payload.json
```

---

### 3.3 `POST /api/v1/qa/ask` -- RAG 问答接口

- **协议**：HTTP
- **端口**：9001
- **鉴权**：Bearer Token（`Authorization: Bearer <QA_API_TOKEN>`），若未配置 token 则跳过校验
- **功能**：SDK 知识库混合检索（语义+关键词）-> 内部大模型生成回答 -> 返回带来源引用的答案
- **请求体**

```json
{
  "question": "What are recent advances in LLM inference optimization?",
  "top_k": 5,
  "tag_filters": [
    {"name": "category", "value": "AI Inference"},
    {"name": "kb_type", "value": "article_summary"}
  ]
}
```

- **字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `question` | string | 是 | 用户问题 |
| `top_k` | int | 否 | 召回片段数，默认 5，范围 1-20 |
| `tag_filters` | array | 否 | 标签过滤条件，对应 EIPLite 中"参与过滤"的标签 |
| `tag_filters[].name` | string | 是 | 标签名，如 `category` / `kb_type` / `source_name` |
| `tag_filters[].value` | string | 是 | 标签值 |

- **成功响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answer": "Recent advances in LLM inference optimization focus on...",
    "sources": [
      {
        "title": "FlashAttention-3 Paper Released",
        "url": "https://arxiv.org/abs/...",
        "kb_file_id": "kb_file_xxx",
        "relevance_score": 0.94
      }
    ],
    "retrieval_method": "hybrid",
    "tokens_used": 1850
  }
}
```

- **降级行为**

| 场景 | 表现 |
|---|---|
| 检索返回空 | `answer: "no results found, try different query"` |
| 内部大模型生成超时/不可用 | 降级返回检索片段原文+来源引用，`note: "LLM generation unavailable, only retrieval results returned"` |
| SDK 检索异常 | HTTP 503，`detail: "knowledge base retrieval failed: ..."` |

- **当前可用标签过滤字段**（已在 EIPLite Web UI 配置并参与过滤的 12 个标签）

| 标签名 | 类型 | 说明 |
|---|---|---|
| `kb_type` | String | article_summary / deep_insight / briefing |
| `source_name` | String | 数据源名称 |
| `title` | String | 文章标题 |
| `publish_time` | String | 发布时间 |
| `category` | String | 技术分类 |
| `author` | String | 作者 |
| `value_score` | Number | 综合价值评分 |
| ... | | （其余标签按 EIPLite 实际配置） |

- **验证方式**

```powershell
# 无鉴权场景（当前 token 未配置）
$body = @{ question = "What is FlashAttention"; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://168.64.18.190:9001/api/v1/qa/ask" -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 5

# 带标签过滤
$body = @{
  question = "LLM inference optimization"
  top_k = 3
  tag_filters = @(@{name = "kb_type"; value = "article_summary"})
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "http://168.64.18.190:9001/api/v1/qa/ask" -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 5

# 预期：返回 answer 字符串 + sources 数组
```

- **Linux curl 示例**

```bash
# 无鉴权场景（当前 token 未配置）
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/qa/ask' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is FlashAttention","top_k":3}' | python3 -m json.tool

# 带标签过滤
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/qa/ask' \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "LLM inference optimization",
    "top_k": 3,
    "tag_filters": [
      {"name": "kb_type", "value": "article_summary"}
    ]
  }' | python3 -m json.tool

# 如果已配置 QA_API_TOKEN：
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/qa/ask' \
  -H "Authorization: Bearer ${QA_API_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"question":"LLM inference optimization","top_k":3}' | python3 -m json.tool
```

---

### 3.4 `GET /api/v1/tasks/{task_id}` -- 任务状态查询

- **协议**：HTTP
- **端口**：9001
- **鉴权**：无
- **功能**：按 batch_no / task_id 查询任务处理进度（内存存储）
- **请求示例**

```http
GET http://168.64.18.190:9001/api/v1/tasks/IMP-20260616-001 HTTP/1.1
```

- **响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "IMP-20260616-001",
    "scope": "all",
    "status": "completed",
    "started_at": "2026-06-16T08:00:00",
    "completed_at": "2026-06-16T08:05:30",
    "progress": {
      "phase": "importing",
      "sources_total": 12,
      "sources_done": 12,
      "articles_collected": 45
    },
    "stats": {
      "articles_total": 45,
      "analyses_success": 42,
      "insights_generated": 3
    }
  }
}
```

- **异常情况**：task_id 不存在 -> `code: 404, message: "task_not_found"`
- **验证方式**

```powershell
Invoke-RestMethod -Uri "http://168.64.18.190:9001/api/v1/tasks/TEST-20260616-001" | ConvertTo-Json -Depth 5
# 若已通过导入接口创建该批次，返回状态；否则返回 404
```

- **Linux curl 示例**

```bash
curl -sS 'http://168.64.18.190:9001/api/v1/tasks/TEST-20260616-001' | python3 -m json.tool
# 若已通过导入接口创建该批次，返回状态；否则返回 404
```

---

### 3.5 `GET /api/v1/tasks` -- 任务列表

- **协议**：HTTP
- **端口**：9001
- **鉴权**：无
- **功能**：列出最近任务（内存存储，默认 20 条）
- **请求示例**

```http
GET http://168.64.18.190:9001/api/v1/tasks?limit=10 HTTP/1.1
```

- **响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "tasks": [
      {"task_id": "IMP-20260616-001", "status": "completed"}
    ],
    "count": 1
  }
}
```

- **验证方式**

```powershell
Invoke-RestMethod -Uri "http://168.64.18.190:9001/api/v1/tasks?limit=5" | ConvertTo-Json -Depth 5
```

- **Linux curl 示例**

```bash
curl -sS 'http://168.64.18.190:9001/api/v1/tasks?limit=5' | python3 -m json.tool
```

---

### 3.6 `aiRadarBriefingJob` -- 简报生成（XXL-Job）

- **协议**：XXL-Job（pyxxl Executor）
- **Executor 端口**：9998
- **功能**：基于已入库文章摘要和深度洞察，调用内部大模型生成周报/月报/季报/专题简报草稿
- **调度参数**（JSON 字符串）

```json
{"briefing_type": "weekly"}
{"briefing_type": "monthly"}
{"briefing_type": "quarterly"}
{"briefing_type": "quarterly", "from_date": "2026-04-01", "to_date": "2026-06-30"}
{"briefing_type": "topic", "topic": "LLM Inference Optimization"}
```

- **验证方式**

```
1. XXL-Job Admin -> 找到 aiRadarBriefingJob（需先在 Admin 上配置内部侧 Executor）
2. 手动执行，参数 {"briefing_type": "weekly"}
3. 检查内部侧日志确认简报生成结果
4. 验证 MySQL ai_radar_briefing_draft 表中新增记录
```

- **Linux curl 示例（绕过 XXL-Job，直接触发 HTTP 接口）**

```bash
# 生成周报
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/jobs/briefing' \
  -H 'Content-Type: application/json' \
  -d '{"briefing_type":"weekly"}' | python3 -m json.tool

# 生成月报
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/jobs/briefing' \
  -H 'Content-Type: application/json' \
  -d '{"briefing_type":"monthly"}' | python3 -m json.tool

# 生成最近 90 天季报
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/jobs/briefing' \
  -H 'Content-Type: application/json' \
  -d '{"briefing_type":"quarterly"}' | python3 -m json.tool

# 生成指定自然季度简报，例如 2026 年二季度
curl -sS -X POST 'http://168.64.18.190:9001/api/v1/jobs/briefing' \
  -H 'Content-Type: application/json' \
  -d '{"briefing_type":"quarterly","from_date":"2026-04-01","to_date":"2026-06-30"}' | python3 -m json.tool
```

---

## 四、系统出站调用（非对外接口，供完整性参考）

| 调用方 | 目标 | 协议 | 认证方式 | 用途 |
|---|---|---|---|---|
| AWS 侧 L2/L3 分析 | 外部大模型 API（OpenAI 兼容） | HTTPS POST `/chat/completions` | API Key（环境变量） | 摘要、分类、评分、洞察 |
| AWS 侧采集 | 各数据源 RSS/API/网页 | HTTP GET | 无（公开内容） | 抓取技术文章 |
| AWS 侧导入客户端 | 内部受控导入接口 `POST /api/v1/radar/import` | HTTP POST | 无（防火墙管控） | 推送加工成果 |
| 内部侧 QA / 简报 | 内部大模型 `{LLM_BASE_URL}/chat/completions` | HTTP POST | Bearer token（Header `userid`） | RAG 生成+简报生成 |
| 内部侧知识库操作 | TalentsView SDK (`KnowledgeBaseClient`) | SDK 内部 HTTP | SDK 自动认证（`TALENTSVIEW_APP_ID` 等） | 文件上传、检索 |

---

## 五、验证优先级建议

| 优先级 | 接口 | 原因 |
|---|---|---|
| P0 | `POST /api/v1/radar/import` | 核心数据入口，不通则整个系统无数据 |
| P0 | `POST /api/v1/qa/ask` | 核心用户价值出口，依赖 SDK+LLM+KB 三方联动 |
| P1 | `GET /health`（两侧） | 快速定位故障组件 |
| P1 | `aiRadarCollectJob` | 自动化数据管道入口 |
| P2 | `GET /api/v1/tasks` | 运维辅助 |
| P2 | `aiRadarBriefingJob` | 简报功能依赖入库数据积累 |
| P3 | `aiRadarHealthCheckJob` | 辅助监控，非核心链路 |

---

## 六、已知占位 / 待补充项

1. **5 个中文数据源无实际 URL**（新智元、机器之心、赛博禅心、智东西、腾讯研究院）-- config.properties 中标记为 `https://...`，健康检查会跳过（"no URL configured"），待用户后续补充
2. **内部导入接口无应用层鉴权** -- 依赖网络侧防火墙管控，已确认
3. **任务状态存储为内存实现** -- 重启后丢失，生产可替换为 MySQL / Redis
4. **OpenAPI 文档** -- 内部节点已开启 `/docs`（Swagger UI），AWS 侧暂未开启

---

## 七、本地启动方式

### 7.1 前置条件

- Python 3.11+
- 两项依赖已安装（`pip install -r requirements.txt`）
- 内部侧 MySQL `10.102.37.253:8880` 本机可达
- 内部大模型 `168.63.65.40:8090` 本机可达
- 内部侧 `secrets/.env` 已配置（MySQL / TalentsView / LLM / XXL-Job）
- AWS 侧 `secrets/.env` 已配置（临时指向内部 LLM）
- AWS 侧 `config/config.properties` 中 `import_endpoint.url` 指向 `localhost:9001`

### 7.2 启动顺序

**必须先启动内部侧，再启动 AWS 侧**（AWS 侧启动时会尝试连接内部导入端点做健康检查）。

**步骤 1 — 启动内部应用节点（端口 9001）**

```powershell
cd D:\013148\code\AI技术趋势雷达\tech-research\internal
python -m uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload
```

启动后验证：

```powershell
Invoke-RestMethod -Uri "http://localhost:9001/health" | ConvertTo-Json -Depth 5
```

预期 `status: "healthy"`（若 XXL-Job 连不上则 degraded 属正常，不影响 HTTP 接口）。

**步骤 2 — 启动 AWS 侧服务（端口 9003）**

```powershell
cd D:\013148\code\AI技术趋势雷达\tech-research\aws
$env:AI_RADAR_CONFIG_DIR = "D:\013148\code\AI技术趋势雷达\tech-research\aws\config"
python -m uvicorn app.main:app --host 0.0.0.0 --port 9003 --reload
```

启动后验证：

```powershell
Invoke-RestMethod -Uri "http://localhost:9003/health" | ConvertTo-Json -Depth 5
```

### 7.3 本地测试的临时配置说明

| 项目 | 正式环境 | 本地测试 | 恢复方式 |
|---|---|---|---|
| AWS 侧 LLM 目标 | 外部 OpenAI API | 内部 `168.63.65.40:8090` | 改回 `secrets/.env` 中的 `OPENAI_BASE_URL` + `OPENAI_API_KEY` |
| AWS 侧 `llm/client.py` 的 `default_headers` | 无 | `{"userid": "013148"}` | 删除该行 |
| AWS 侧 `collect_job.py` 的 `base_url` | `None`（走 SDK 默认） | 读 `OPENAI_BASE_URL` 环境变量 | 删除该行 |
| 模型名称 | `gpt-4o-mini` / `gpt-4o` | `saas-doubao-15-pro-32k` | 改回 `config.properties` 中 `l2_model.model` / `l3_model.model` |
| 导入端点 | `168.64.18.190:9001` | `localhost:9001` | 改回 `config.properties` 中 `import_endpoint.url` |

### 7.4 XXL-Job 说明

本地测试不依赖 XXL-Job 调度平台。两侧启动时后台线程尝试连接 XXL-Job Admin 会失败并记录 warning 日志，不影响 HTTP 接口正常使用。采集和导入通过直接调用 HTTP 接口手动验证即可。
