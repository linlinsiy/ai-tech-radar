"""
自定义异常类

定义业务异常类型，用于统一错误处理。
"""
from typing import Optional, Dict, Any


class AgentException(Exception):
    """智能体基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AgentException):
    """参数验证异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class AgentNotFoundError(AgentException):
    """智能体不存在异常"""
    
    def __init__(self, message: str = "智能体不存在"):
        super().__init__(
            message=message,
            error_code="AGENT_NOT_FOUND",
            status_code=404
        )


class AgentExecutionError(AgentException):
    """智能体执行失败异常"""
    
    def __init__(self, message: str, agent_name: str = "unknown"):
        super().__init__(
            message=message,
            error_code="AGENT_EXECUTION_ERROR",
            status_code=500,
            details={"agent_name": agent_name}
        )


class LLMServiceError(AgentException):
    """LLM 服务异常"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="LLM_SERVICE_ERROR",
            status_code=502
        )
