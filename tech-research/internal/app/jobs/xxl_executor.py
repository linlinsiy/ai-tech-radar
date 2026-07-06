"""
内部侧 - XXL-Job Executor 集成模块

使用 pyxxl 库注册 JobHandler，连接到公司 XXL-Job Admin 调度平台。
内部侧注册 aiRadarBriefingJob，用于定时/手动触发简报生成。
"""
import os
import logging

# ?????????? XXL-Job Admin
_XXL_NO_PROXY = "168.64.38.162,168.64.18.190,127.0.0.1,localhost"
os.environ["no_proxy"] = _XXL_NO_PROXY
os.environ["NO_PROXY"] = _XXL_NO_PROXY

from pyxxl import ExecutorConfig, PyxxlRunner, JobHandler

from config import InternalConfig

logger = logging.getLogger("xxl_job")


def create_xxl_runner() -> PyxxlRunner:
    """
    ????????XXL-Job Executor Runner

    ?????yxxlRunner ???
    """
    cfg = InternalConfig.get_instance().xxl_config
    xxl_cfg = ExecutorConfig(
        xxl_admin_baseurl=cfg["admin_url"],
        executor_app_name=cfg["app_name"],
        access_token=cfg["access_token"],
        executor_listen_port=cfg["executor_port"],
        executor_log_path=cfg["log_path"],
    )

    # ?? JobHandler ?????
    from jobs.briefing_job import handle_briefing_job
    job_handler = JobHandler()

    @job_handler.register(name="aiRadarBriefingJob")
    def briefing_handler(params: str = ""):
        """???????JobHandler"""
        return handle_briefing_job(params)

    logger.info("XXL-Job Handlers ??????: aiRadarBriefingJob")
    return PyxxlRunner(xxl_cfg, handler=job_handler)


def register_handlers(runner: PyxxlRunner):
    """
    ????????JobHandler ??XXL-Job Executor
    ??? create_xxl_runner() ????????????????????????
    
    ?????
        runner: PyxxlRunner ???
    """
    pass

def start_xxl_executor():
    """
    启动内部侧 XXL-Job Executor（阻塞调用）

    在独立线程中调用，与 FastAPI 服务并行运行。
    """
    runner = create_xxl_runner()
    register_handlers(runner)
    logger.info("内部侧 XXL-Job Executor 启动中... app=%s",
                InternalConfig.get_instance().xxl_config["app_name"])
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
    try:
        import asyncio.unix_events
        asyncio.unix_events._UnixSelectorEventLoop.add_signal_handler = lambda self, sig, cb=None, *a, **kw: None
    except (AttributeError, ImportError):
        pass
    asyncio.AbstractEventLoop.add_signal_handler = lambda self, sig, cb=None, *a, **kw: None

    runner.run_executor()
