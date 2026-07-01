"""
健康检查 API

提供基础的健康检查端点，用于监控和部署。
"""
import time
from fastapi import APIRouter

from app.api.models import HealthCheckResponse
from app.web.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 服务启动时间
START_TIME = time.time()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    基础健康检查
    
    Returns:
        健康检查响应，包含服务状态、版本、运行时长等信息
        
    用途：
    - Kubernetes liveness 和 readiness 探针
    - 监控系统健康检查
    - 部署后验证服务是否正常
    """
    uptime = time.time() - START_TIME
    
    return HealthCheckResponse(
        status="healthy",
        version=settings.app_version,
        uptime=uptime
    )
