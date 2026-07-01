# -*- coding: utf-8 -*-
"""
FastAPI 应用配置管理

使用 Pydantic Settings 从环境变量加载配置。
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """FastAPI 应用配置类"""
    
    # 应用基础配置
    app_name: str = "Talentsview SDK FastAPI Langchain Scaffold"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    
    # 路由配置（支持部署到网关后统一配置路由前缀）
    root_path: str = ""
    
    # CORS 配置（使用 str 类型避免 Pydantic Settings 自动 JSON 解析）
    cors_origins: str = "*"
    
    @field_validator('cors_origins', mode='after')
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """将逗号分隔的字符串转换为列表"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return ["*"]
    
    # 日志配置
    access_log: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # 允许忽略额外的环境变量
    )


# 全局配置实例
settings = Settings()
