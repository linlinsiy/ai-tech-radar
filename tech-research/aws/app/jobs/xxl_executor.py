"""
AWS 侧 - XXL-Job Executor 集成模块

使用 pyxxl 库注册 JobHandler，连接到公司 XXL-Job Admin 调度平台。
"""
import os
import logging

# ?????????? XXL-Job Admin?PAC ??????? IP?
_XXL_NO_PROXY = "168.64.38.162,168.64.18.190,127.0.0.1,localhost"
os.environ["no_proxy"] = _XXL_NO_PROXY
os.environ["NO_PROXY"] = _XXL_NO_PROXY

from pyxxl import ExecutorConfig, PyxxlRunner

from logging_config import get_logger
logger = get_logger("xxl_job")


def create_xxl_runner(config) -> PyxxlRunner:
    """
    创建 XXL-Job Executor Runner

    入参：
        config: AWSConfig 实例
    出参：PyxxlRunner 实例
    """
    xxl_cfg = ExecutorConfig(
        xxl_admin_baseurl=os.environ.get(
            "XXL_ADMIN_URL",
            config.get(option="xxl_job.admin_addresses", fallback="http://localhost:8080/xxl-job-admin/api/")
        ),
        executor_app_name=config.get(option="xxl_job.app_name", fallback="ai-radar-aws-executor"),
        access_token=os.environ.get(
            "XXL_ACCESS_TOKEN",
            config.get(option="xxl_job.access_token", fallback="")
        ),
        executor_listen_port=int(os.environ.get(
            "XXL_EXECUTOR_PORT",
            config.get(option="xxl_job.executor_port", fallback="9999")
        )),
        executor_log_path=config.get(
            option="xxl_job.log_path",
            fallback="./logs/xxl-job"
        ),
        log_expired_days=int(config.get(
            option="xxl_job.log_retention_days",
            fallback="14"
        )),
    )
    return PyxxlRunner(xxl_cfg)


def register_handlers(runner: PyxxlRunner):
    """
    注册所有 JobHandler 到 XXL-Job Executor

    入参：
        runner: PyxxlRunner 实例
    """
    from jobs.collect_job import handle_collect_job
    from jobs.health_check_job import handle_health_check_job

    @runner.register(name="aiRadarCollectJob")
    def collect_handler(params: str = ""):
        """定时采集分析 JobHandler"""
        return handle_collect_job(params)

    @runner.register(name="aiRadarHealthCheckJob")
    def health_check_handler(params: str = ""):
        """数据源健康检查 JobHandler"""
        return handle_health_check_job(params)

    logger.info(
        "XXL-Job Handlers 注册完成: aiRadarCollectJob, aiRadarHealthCheckJob"
    )


def start_xxl_executor(config):
    """
    启动 XXL-Job Executor

    入参：
        config: AWSConfig 实例
    """
    # pyxxl logger bridge to app log
    pyxxl_logger = logging.getLogger("pyxxl")
    pyxxl_logger.setLevel(logging.DEBUG)
    ai_radar_root = logging.getLogger("ai-radar")
    if ai_radar_root.handlers:
        for h in ai_radar_root.handlers:
            if h not in pyxxl_logger.handlers:
                pyxxl_logger.addHandler(h)

    logger.info("XXL-Job Executor starting (AWS)... app=%s",
                config.get(option="xxl_job.app_name", fallback="ai-radar-aws-executor"))

    runner = create_xxl_runner(config)
    register_handlers(runner)
    # Patch: Linux signal handler can only be registered from main thread;
    # pyxxl runs in a background thread; aiohttp.web.run_app internally calls
    # asyncio.new_event_loop(), so instance-level patch won't work on Linux.
    # We must patch at the class level before any loop is created.
    import asyncio
    try:
        import uvloop
        uvloop.Loop.add_signal_handler = lambda self, sig, cb=None, *a, **kw: None
    except Exception:
        pass
    asyncio.AbstractEventLoop.add_signal_handler = lambda self, sig, cb=None, *a, **kw: None

    runner.run_executor()