"""
API 请求和响应模型

使用 Pydantic 定义所有请求和响应的数据模型。

开发者指南：
- 添加新智能体时，可在此定义专用的请求/响应模型
- 或复用通用模型 AgentRequest 和 AgentResponse

备注：此处并未选择使用OpenAI兼容格式，请自行实现转化逻辑。
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AgentRequest(BaseModel):
    """
    智能体通用请求模型
    
    用于大多数智能体的标准输入格式。
    如果智能体需要特殊字段，可继承此类或创建新模型。
    """
    input: str = Field(..., description="用户输入内容")
    stream: bool = Field(default=True, description="是否使用流式输出")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(default=None, gt=0, description="最大生成 token 数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "input": "请帮我总结这段文本的核心内容",
                "stream": False,
                "temperature": 0.7
            }
        }


class AgentResponse(BaseModel):
    """
    智能体通用响应模型（非流式）
    
    标准的非流式响应格式。
    """
    output: str = Field(..., description="智能体输出内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "output": "这是智能体生成的回复内容...",
                "metadata": {
                    "tokens_used": 150
                }
            }
        }


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="应用版本")
    uptime: float = Field(..., description="运行时长（秒）")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="当前时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "uptime": 3600.5,
                "timestamp": "2025-01-17T10:30:00Z"
            }
        }
