"""
FastAPI 中间件

包含 CORS、请求日志、异常处理等中间件。
"""
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.utils.logger import get_logger
from app.web.config import settings
from app.web.exceptions import AgentException

logger = get_logger(__name__)


def setup_middleware(app: FastAPI):
    """
    设置所有中间件
    
    Args:
        app: FastAPI 应用实例
    """
    # 1. CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 2. 信任主机中间件（生产环境）
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            #allowed_hosts=["localhost", "127.0.0.1", settings.host]
            allowed_hosts=["*"]
        )
    
    # 3. 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # 记录请求
        logger.info(f"[请求开始] {request.method} {request.url}")
        
        response = await call_next(request)
        
        # 记录响应
        process_time = time.time() - start_time
        logger.info(
            f"[请求完成] {request.method} {request.url} - "
            f"{response.status_code} - {process_time:.3f}s"
        )
        
        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


def setup_exception_handlers(app: FastAPI):
    """
    设置异常处理器
    
    Args:
        app: FastAPI 应用实例
    """
    
    @app.exception_handler(AgentException)
    async def agent_exception_handler(request: Request, exc: AgentException):
        """处理自定义业务异常"""
        logger.error(f"业务异常: {exc.message} - {exc.details}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "error_message": exc.message,
                "details": exc.details,
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 HTTP 异常"""
        logger.error(f"HTTP异常: {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": f"HTTP_{exc.status_code}",
                "error_message": exc.detail,
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理通用异常"""
        logger.error(f"未处理异常: {type(exc).__name__} - {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "error_message": "服务器内部错误" if not settings.debug else str(exc),
                "timestamp": time.time()
            }
        )
