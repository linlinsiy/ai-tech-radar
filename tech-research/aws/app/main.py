"""
AWS 侧主入口

负责：
- 初始化配置和日志系统
- 注册 XXL-Job Executor 到公司调度平台
- 提供健康检查 HTTP 端点
- 编排采集分析全流程（L0 → L1 → L2 → L3 → 导入）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AWSConfig
from logging_config import setup_logging, get_logger

logger = get_logger("main")


def init_app():
    """
    初始化应用：加载配置、设置日志

    出参：(AWSConfig, logging.Logger)
    """
    config = AWSConfig()
    setup_logging(config)
    logger.info("AI技术趋势雷达 - AWS 侧服务启动")
    logger.info("配置目录: %s", config._config_dir)
    logger.info("数据源数量: %d", len(config.get_data_sources()))
    logger.info("L2 模型: %s", config.l2_model["model"])
    logger.info("L3 模型: %s", config.l3_model["model"])
    return config


def create_app(config: AWSConfig):
    """
    创建 FastAPI 应用（含路由注册）

    入参：
        config: AWSConfig 实例
    出参：FastAPI 应用实例
    """
    from fastapi import FastAPI

    app = FastAPI(
        title="AI技术趋势雷达 - AWS 侧服务",
        version="1.0.0",
    )

    # 注册健康检查路由
    from api.health_api import health_check
    app.get("/health", response_model=None)(health_check)

    # 注册手动触发接口路由（绕过 XXL-Job 直接调用）
    from api.jobs_api import (
        trigger_collect,
        trigger_health_check,
        list_analysis_snapshots,
        trigger_validation_analysis,
        trigger_validation_collect,
    )
    app.post("/api/v1/jobs/collect", response_model=None)(trigger_collect)
    app.post("/api/v1/jobs/health-check", response_model=None)(trigger_health_check)
    app.get("/api/v1/jobs/analysis-snapshots", response_model=None)(list_analysis_snapshots)
    app.post("/api/v1/validation/collect", response_model=None)(trigger_validation_collect)
    app.post("/api/v1/validation/analyze", response_model=None)(trigger_validation_analysis)
    logger.info(
        "手动触发接口已注册: POST /api/v1/jobs/collect, "
        "POST /api/v1/jobs/health-check, GET /api/v1/jobs/analysis-snapshots, "
        "POST /api/v1/validation/collect, "
        "POST /api/v1/validation/analyze"
    )

    @app.on_event("startup")
    async def startup_scheduler():
        """按配置启动调度接入。"""
        scheduler_mode = config.scheduler_config["mode"]
        logger.info("调度模式: %s", scheduler_mode)

        if scheduler_mode == "xxljob":
            if getattr(app.state, "xxl_started", False):
                return
            from jobs.xxl_executor import start_xxl_executor
            import threading
            xxl_thread = threading.Thread(
                target=start_xxl_executor,
                args=(config,),
                daemon=True,
                name="xxl-executor"
            )
            xxl_thread.start()
            app.state.xxl_started = True
            logger.info("XXL-Job Executor 已启动（后台线程）")
        elif scheduler_mode == "crontab":
            logger.info("本地 crontab 调度模式，不注册 XXL-Job Executor")
        else:
            logger.info("调度模式为 none，不注册调度器")

    return app


# 模块级 app 实例，供 uvicorn 直接引用（uvicorn app.main:app）
# 此实例仅含基础路由，不含 XXL-Job Executor。
_config = init_app()
app = create_app(_config)


def main():
    """
    主入口：启动 FastAPI 服务 + XXL-Job Executor（后台线程）。
    复用模块级 _config 和 app，避免 init_app() 重复调用导致日志双写。
    """
    try:
        # 复用模块级初始化结果（模块导入时已完成），跳过重复的 init_app 调用
        config = _config
        app._config = config  # 挂载 config 供路由使用

        import uvicorn
        server_port = int(os.environ.get("AI_RADAR_PORT", "9003"))
        logger.info("服务启动，监听端口 %d", server_port)

        uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="info")

    except KeyboardInterrupt:
        logger.info("收到终止信号，服务退出")
    except Exception:
        logger.exception("服务启动失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
