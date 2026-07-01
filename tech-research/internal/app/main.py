"""
内部应用节点 FastAPI 入口

启动受控导入接口、健康检查、任务状态查询、RAG 问答等服务。
"""
import sys
import os
import threading
import logging

# === 配置日志输出到文件 ===
import os as _os_log
_log_dir = _os_log.path.join(_os_log.path.dirname(_os_log.path.abspath(__file__)), '..', 'logs')
_os_log.makedirs(_log_dir, exist_ok=True)
logging.basicConfig(
    filename=_os_log.path.join(_log_dir, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    filemode='a',
)
from sqlalchemy import text

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import InternalConfig

config = InternalConfig.get_instance()

app = FastAPI(
    title="AI技术趋势雷达 - 内部应用节点",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """应用启动时初始化"""
    logging.info("内部应用节点启动中...")
    try:
        from db.models import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info("MySQL 连接验证成功: %s:%s",
                      config.mysql_config["host"], config.mysql_config["port"])
    except Exception as e:
        logging.warning("MySQL 连接验证失败（服务仍可启动）: %s", str(e))

    # 启动 XXL-Job Executor（后台线程，注册 aiRadarBriefingJob）
    try:
        from jobs.xxl_executor import start_xxl_executor
        xxl_thread = threading.Thread(
            target=start_xxl_executor, daemon=True, name="xxl-executor"
        )
        xxl_thread.start()
        logging.info("XXL-Job Executor 后台线程已启动")
    except Exception as e:
        logging.warning("XXL-Job Executor 启动失败: %s", e)

    logging.info("内部应用节点就绪，监听端口 %s", config.server_config["port"])


@app.on_event("shutdown")
async def shutdown():
    """应用停止时清理"""
    logging.info("内部应用节点停止")


# === 注册路由 ===
from api.import_api import router as import_router
app.include_router(import_router)

from api.task_api import router as task_router
app.include_router(task_router)

from api.qa_api import router as qa_router
app.include_router(qa_router)


# 健康检查保留在 main 中（不依赖 EIPLite 状态）
@app.get("/health")
async def health_check():
    """健康检查端点"""
    checks = {}
    try:
        from db.models import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["mysql"] = {"status": "healthy"}
    except Exception as e:
        checks["mysql"] = {"status": "unhealthy", "error": str(e)}

    # 知识库检查（TalentsView SDK）
    try:
        dataset_id = os.environ.get("EIPLITE_KB_DATASET_ID", "")
        if not dataset_id:
            checks["knowledge_base"] = {"status": "unhealthy", "error": "KB_DATASET_ID not configured"}
        else:
            from kb.kb_client import create_kb_client
            client = create_kb_client()
            checks["knowledge_base"] = {
                "status": "healthy",
                "dataset_id": dataset_id,
            }
    except Exception as e:
        checks["knowledge_base"] = {"status": "unhealthy", "error": str(e)}

    # 内部 LLM 检查
    try:
        llm_cfg = config.internal_llm_config
        if not llm_cfg.get("base_url"):
            checks["internal_llm"] = {"status": "unhealthy", "error": "LLM_BASE_URL not configured"}
        else:
            import httpx
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(
                    f"{llm_cfg['base_url']}/models",
                    headers={"Authorization": f"Bearer {llm_cfg.get('api_key', '')}"}
                )
            checks["internal_llm"] = {
                "status": "healthy" if resp.status_code < 500 else "degraded",
                "model": llm_cfg.get("model", ""),
                "endpoint": llm_cfg["base_url"],
            }
    except Exception as e:
        checks["internal_llm"] = {"status": "degraded", "error": str(e)}

    from datetime import datetime
    all_healthy = all(
        c.get("status") in ("healthy", "pending")
        for c in checks.values()
    )
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    """启动入口"""
    import uvicorn
    server_cfg = config.server_config
    uvicorn.run(
        "main:app",
        host=server_cfg["host"],
        port=server_cfg["port"],
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
