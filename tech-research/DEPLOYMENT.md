# AI技术趋势雷达 - 部署指南

## 项目概述

本项目包含两个独立的 Python FastAPI 服务：

| 服务 | 目录 | 端口 | 职责 |
|------|------|------|------|
| AWS侧服务 | `/app/001804/aws/` | 9003 | 数据采集、L2/L3分析、外部LLM调用 |
| 内部应用节点 | `/app/001804/internal/` | 9001 | 数据导入、MySQL、知识库集成、RAG问答 |

## 环境要求

- Linux 系统（CentOS 7+/Ubuntu 18.04+）
- Python 3.11+
- MySQL 8.0+（仅内部节点需要）
- XXL-Job 调度平台（可选）
- crontab（可选，用于不接入 XXL-Job 时按本机周期调度任务）

## 部署方式（appadmin 用户）

### 一、打包代码

在开发机上执行：

```bash
cd /path/to/tech-research
python3 pack.py
```

生成文件：
- `ai-radar-aws-YYYYMMDD_HHMMSS.tar.gz`
- `ai-radar-internal-YYYYMMDD_HHMMSS.tar.gz`

### 二、上传到服务器

```bash
scp ai-radar-aws-*.tar.gz appadmin@server:/app/001804/
scp ai-radar-internal-*.tar.gz appadmin@server:/app/001804/
```

### 三、解压代码

```bash
ssh appadmin@server

cd /app/001804

tar -xzf ai-radar-aws-*.tar.gz
tar -xzf ai-radar-internal-*.tar.gz
```

### 四、部署 AWS 侧服务

```bash
cd /app/001804/aws

# 创建目录结构和设置权限
./deploy/install.sh

# 配置环境变量
cp secrets/.env.example secrets/.env
vi secrets/.env

# 创建虚拟环境并安装依赖
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 启动服务
./deploy/start.sh
```

### 五、部署内部应用节点

```bash
cd /app/001804/internal

# 创建目录结构和设置权限
./deploy/install.sh

# 配置环境变量
cp secrets/.env.example secrets/.env
vi secrets/.env

# 创建虚拟环境并安装依赖
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 启动服务
./deploy/start.sh
```

### 六、后台运行服务（nohup）

```bash
# AWS侧服务
cd /app/001804/aws
nohup ./deploy/start.sh > logs/app.log 2>&1 &

# 内部应用节点
cd /app/001804/internal
nohup ./deploy/start.sh > logs/app.log 2>&1 &

# 查看进程
ps aux | grep uvicorn
```

### 七、使用 systemd 服务（需要 root 权限）

如果有 sudo 权限，可以配置 systemd 服务：

```bash
# AWS侧服务
sudo cp deploy/ai-radar-aws.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-radar-aws
sudo systemctl start ai-radar-aws

# 内部应用节点
sudo cp deploy/ai-radar-internal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-radar-internal
sudo systemctl start ai-radar-internal
```

### 八、调度模式配置

服务部署和启动方式保持不变。调度方式通过 `config/config.properties` 中的 `scheduler.mode` 控制：

| 值 | 说明 |
|---|---|
| `xxljob` | 启动服务时注册 XXL-Job Executor，由 XXL-Job 触发任务 |
| `crontab` | 不注册 XXL-Job Executor，由本机 crontab 通过 HTTP 接口触发任务 |
| `none` | 不启用调度器，仅保留 HTTP 手动触发能力 |

#### AWS 侧配置

配置文件：`/app/001804/aws/config/config.properties`

```properties
scheduler.mode=xxljob
scheduler.cron.collect=0 8 * * *
scheduler.cron.health_check=*/30 * * * *
```

当 `scheduler.mode=crontab` 时，服务仍按原方式启动，只是不注册 XXL-Job。运维人员按配置中的 cron 表达式手动维护系统 crontab，触发已有 HTTP 接口：

```cron
# 每天 08:00 执行采集分析
0 8 * * * curl -fsS -X POST http://127.0.0.1:9003/api/v1/jobs/collect -H 'Content-Type: application/json' -d '{"scope":"all","task_type":"scheduled"}' >> /app/001804/aws/logs/cron.log 2>&1

# 每 30 分钟执行数据源健康检查
*/30 * * * * curl -fsS -X POST http://127.0.0.1:9003/api/v1/jobs/health-check >> /app/001804/aws/logs/cron.log 2>&1
```

#### 内部侧配置

配置文件：`/app/001804/internal/config/config.properties`

```properties
scheduler.mode=xxljob
scheduler.cron.briefing=0 9 * * 1
scheduler.briefing_type=weekly
```

当 `scheduler.mode=crontab` 时，服务仍按原方式启动，只是不注册 XXL-Job。运维人员按配置中的 cron 表达式手动维护系统 crontab，触发已有 HTTP 接口：

```cron
# 每周一 09:00 生成周报草稿
0 9 * * 1 curl -fsS -X POST http://127.0.0.1:9001/api/v1/jobs/briefing -H 'Content-Type: application/json' -d '{"briefing_type":"weekly"}' >> /app/001804/internal/logs/cron.log 2>&1
```

说明：

1. `deploy/crontab.example` 仅作为 crontab 配置参考，不参与部署流程。
2. 本地 crontab 通过 HTTP 接口触发任务，不新增独立 CLI 入口。
3. crontab 日志建议追加到 `logs/cron.log`，业务日志仍写入服务自身日志。

## 配置说明

### AWS侧服务配置（secrets/.env）

```env
# 外部大模型 API Key
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# 内部受控导入接口地址
IMPORT_ENDPOINT_URL=http://localhost:9001/api/v1/radar/import

# 服务端口
AI_RADAR_PORT=9003
```

### 内部应用节点配置（secrets/.env）

```env
# MySQL 连接
MYSQL_HOST=10.102.37.253
MYSQL_PORT=8880
MYSQL_USERNAME=ysdjg_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ysdjg

# 内部大模型
LLM_API_KEY=your_key
LLM_BASE_URL=http://your-llm-server:8000
LLM_MODEL=your-model-name

# 服务端口
SERVER_PORT=9001

# XXL-Job（可选）
XXL_ADMIN_URL=http://xxl-job-admin:8080/xxl-job-admin/api/
XXL_APP_NAME=ai-radar-internal-executor
XXL_ACCESS_TOKEN=your_token
XXL_EXECUTOR_PORT=9998
```

## 健康检查

```bash
# AWS侧
curl http://localhost:9003/health

# 内部节点
curl http://localhost:9001/health
```

## 目录结构

```
/app/001804/
├── aws/                    # AWS侧服务
│   ├── app/               # 应用代码
│   ├── config/            # 配置文件
│   ├── data/              # 数据目录
│   ├── deploy/            # 部署脚本
│   ├── logs/              # 日志目录
│   ├── secrets/           # 环境变量
│   ├── venv/              # Python虚拟环境
│   └── requirements.txt
└── internal/              # 内部应用节点
    ├── app/               # 应用代码
    ├── config/            # 配置文件
    ├── deploy/            # 部署脚本
    ├── logs/              # 日志目录
    ├── secrets/           # 环境变量
    ├── venv/              # Python虚拟环境
    └── requirements.txt
```

## 安全建议

1. 限制 `secrets/` 目录权限：`chmod 700`
2. 使用非 root 用户运行服务（已配置 appadmin 用户）
3. 配置防火墙限制访问端口

## 常用管理命令

```bash
# 查看服务进程
ps aux | grep uvicorn

# 停止服务
kill $(ps aux | grep 'uvicorn' | grep -v grep | awk '{print $2}')

# 查看日志
tail -f /app/001804/aws/logs/app.log
tail -f /app/001804/internal/logs/app.log

# 重启服务
cd /app/001804/aws
kill $(ps aux | grep 'uvicorn' | grep aws | grep -v grep | awk '{print $2}')
nohup ./deploy/start.sh > logs/app.log 2>&1 &
```

## 常见问题

### Q: 服务启动失败
A: 检查日志：`tail -f logs/app.log`

### Q: MySQL 连接失败
A: 确认 MySQL 服务运行，且允许远程连接，检查防火墙规则

### Q: XXL-Job 注册失败
A: 确认 XXL-Job Admin 地址可访问，检查 access_token 是否正确

### Q: 依赖安装失败
A: 确保已安装编译工具：`gcc`, `python3-devel`, `mysql-devel`
