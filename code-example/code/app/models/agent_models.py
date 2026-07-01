"""
Agent相关数据模型

定义Agent API的请求和响应模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Agent对话请求模型"""
    message: str = Field(..., description="用户输入的问题", min_length=1)
    model: Optional[str] = Field(None, description="使用的模型名称", examples=["local-qwen3-235b-nothink-moe"])
    temperature: Optional[float] = Field(None, description="采样温度", ge=0.0, le=2.0, examples=[0.7])
    search_count: Optional[int] = Field(None, description="搜索结果数量", ge=1, le=50, examples=[5])


class AgentChatResponse(BaseModel):
    """Agent对话响应模型（非流式）"""
    answer: str = Field(..., description="Agent生成的最终答案")
    used_search: bool = Field(..., description="是否使用了联网搜索")
    search_results: Optional[List[Dict[str, Any]]] = Field(None, description="搜索结果列表")
    model: str = Field(..., description="使用的模型名称")


class StreamChunk(BaseModel):
    """流式响应数据块"""
    delta: str = Field("", description="增量内容")
    done: bool = Field(False, description="是否完成")
    used_search: Optional[bool] = Field(None, description="是否使用了搜索（仅在done=true时返回）")
