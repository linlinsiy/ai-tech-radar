"""
Agent API路由

提供智能Agent对话端点：
- /chat: 非流式响应
- /chat/stream: 流式SSE响应
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.agent_models import AgentChatRequest, AgentChatResponse
from app.services.agent_service import AgentService, AgentServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest):
    """Agent智能对话端点（非流式）
    
    自动判断是否需要联网搜索，并基于搜索结果生成准确回答。
    
    Args:
        request: Agent对话请求
        
    Returns:
        完整的AgentChatResponse
    """
    logger.info(f"Agent对话请求: message_length={len(request.message)}")
    
    try:
        agent_service = AgentService(
            model=request.model,
            temperature=request.temperature,
            search_count=request.search_count
        )
        
        result = await agent_service.chat(request.message)
        logger.info(f"Agent对话完成: used_search={result['used_search']}")
        
        return AgentChatResponse(
            answer=result["answer"],
            used_search=result["used_search"],
            search_results=result.get("search_results"),
            model=result["model"]
        )
        
    except AgentServiceError as e:
        logger.error(f"Agent服务错误: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": e.message, "error_code": e.error_code}
        )
    except Exception as e:
        logger.error(f"未预期的错误: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": f"服务内部错误: {str(e)}", "error_code": "INTERNAL_ERROR"}
        )


@router.post("/chat/stream")
async def agent_chat_stream(request: AgentChatRequest):
    """Agent智能对话端点（流式SSE）
    
    自动判断是否需要联网搜索，并基于搜索结果生成准确回答。
    
    Args:
        request: Agent对话请求
        
    Returns:
        SSE流式响应
    """
    logger.info(f"Agent流式对话请求: message_length={len(request.message)}")
    
    try:
        agent_service = AgentService(
            model=request.model,
            temperature=request.temperature,
            search_count=request.search_count
        )
        
        return StreamingResponse(
            _stream_response(agent_service, request.message),
            media_type="text/event-stream"
        )
        
    except AgentServiceError as e:
        logger.error(f"Agent服务错误: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": e.message, "error_code": e.error_code}
        )
    except Exception as e:
        logger.error(f"未预期的错误: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": f"服务内部错误: {str(e)}", "error_code": "INTERNAL_ERROR"}
        )


async def _stream_response(agent_service: AgentService, message: str):
    """流式响应生成器
    
    Args:
        agent_service: Agent服务实例
        message: 用户消息
        
    Yields:
        SSE格式的数据流
    """
    try:
        async for chunk in agent_service.chat_stream(message):
            # SSE格式：data: {json}\n\n
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {data}\n\n"
            
    except AgentServiceError as e:
        # 流式错误响应
        error_data = json.dumps({
            "error": e.message,
            "error_code": e.error_code,
            "done": True
        }, ensure_ascii=False)
        yield f"data: {error_data}\n\n"
    except Exception as e:
        logger.error(f"流式响应错误: {str(e)}", exc_info=True)
        error_data = json.dumps({
            "error": f"服务内部错误: {str(e)}",
            "error_code": "INTERNAL_ERROR",
            "done": True
        }, ensure_ascii=False)
        yield f"data: {error_data}\n\n"
