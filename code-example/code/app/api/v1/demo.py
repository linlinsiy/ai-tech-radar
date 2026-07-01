"""
示例 API 路由

提供简单的示例端点，演示 FastAPI 脚手架的基本使用
"""
from fastapi import APIRouter

from app.api.models import AgentRequest, AgentResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/hello", response_model=AgentResponse)
async def hello(request: AgentRequest):
    """
    简单问候接口
    
    演示最基本的请求响应模式
    """
    logger.info(f"收到问候请求，输入: {request.input[:50]}...")
    
    return AgentResponse(
        output=f"{request.input}！欢迎使用 FastAPI 脚手架",
        metadata={
            "input_length": len(request.input),
            "example": "这是一个示例 API"
        }
    )
