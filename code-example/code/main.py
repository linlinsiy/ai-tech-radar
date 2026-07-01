"""
FastAPI 应用主入口

提供完整的 FastAPI 服务，包括：
- API 路由
- 中间件和异常处理
- 健康检查
- 示例 API
"""
# 在所有导入前加载环境变量，确保后续集成的 SDK 能正确读取配置
import os
from dotenv import load_dotenv
# 读取环境标识，优先级: TALENTSVIEW_ENV > ENV > uat
env = os.getenv('TALENTSVIEW_ENV', os.getenv('ENV', 'uat')).lower()
env_file = f'.env.{env}'
load_dotenv(env_file)

# 云桌面需要禁用代理
os.environ['no_proxy'] = '*'

from fastapi import FastAPI
import uvicorn

from app.utils.logger import get_logger, setup_logger
from app.web.config import settings
from app.web.middleware import setup_middleware, setup_exception_handlers

# 初始化日志系统
setup_logger()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用
    
    Returns:
        FastAPI 应用实例
    """
    # 检查环境变量是否配置，同时拉取SDK最新配置
    from talentsview.core.apollo_manager import ApolloManager
    ApolloManager.update_now()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="基于TalentsView SDK的智能Agent服务模板，展示LLM与联网搜索的组合应用",
        docs_url="/docs",
        redoc_url="/redoc" if settings.debug else None,
        root_path=settings.root_path
    )
    
    # 设置中间件
    setup_middleware(app)
    
    # 设置异常处理器
    setup_exception_handlers(app)
    
    # 注册路由
    from app.api.v1 import health, demo, agent
    
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["健康检查"]
    )
    
    app.include_router(
        agent.router,
        prefix="/api/v1/agent",
        tags=["智能Agent"]
    )
    
    app.include_router(
        demo.router,
        prefix="/api/v1/demo",
        tags=["示例 API"]
    )
    
    # 根路径
    @app.get("/")
    async def root():
        """根路径，返回服务基本信息"""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs_url": "/docs" if settings.debug else None
        }
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    # 本地启动
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=1 if settings.reload else settings.workers,
        access_log=settings.access_log
    )
