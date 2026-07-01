# -*- coding: utf-8 -*-
"""
app.utils - 脚手架核心工具模块

提供：
- 日志系统（logger）
"""

from .logger import get_logger, setup_logger

__all__ = [
    "get_logger",
    "setup_logger"
]