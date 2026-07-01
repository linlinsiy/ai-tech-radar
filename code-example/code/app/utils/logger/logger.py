# -*- coding: utf-8 -*-
"""脚手架日志配置工具

使用场景说明：
1) structlog：统一获取 logger（get_logger/LoggerMixin），支持结构化日志与上下文绑定；
   生产环境建议配合 format='json' 以利于日志采集系统处理。
2) rich：本地开发或调试（debug=True）时，美化控制台输出与 Traceback；
   不用于 json 模式，避免破坏结构化日志格式。
3) 文件日志：支持将日志写入本地文件，可配置文件路径；
   默认写入项目根目录的 logs/ 文件夹，自动按日期滚动。
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import TimedRotatingFileHandler

import structlog
from rich.logging import RichHandler
from rich.console import Console
from rich.traceback import install as install_rich_traceback
from structlog.stdlib import ProcessorFormatter


def setup_logger(
    level: str = "INFO", 
    format: Optional[str] = None, 
    debug: Optional[bool] = None,
    log_file: Optional[str] = None,
    enable_file_log: Optional[bool] = None
) -> None:
    """
    配置全局日志
    
    Args:
        level: 日志级别，默认INFO
        format: 日志格式，可选 "text" 或 "json"
        debug: 是否启用调试模式（Rich美化）
        log_file: 日志文件路径
        enable_file_log: 是否启用文件日志
    """
    # 参数优先级：函数参数 > 环境变量 > 默认值
    log_level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = (format or os.getenv("LOG_FORMAT", "text")).lower()
    debug_flag = debug if debug is not None else os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # 文件日志配置（默认启用文件日志）
    file_log_enabled = (
        enable_file_log if enable_file_log is not None 
        else os.getenv("LOG_FILE_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    log_file_path = log_file or os.getenv("LOG_FILE_PATH", "")

    # structlog 渲染器：根据格式选择
    use_rich_handler = log_format == "text" and debug_flag
    
    if log_format == "json":
        # JSON 格式：统一使用 JSONRenderer
        renderer = structlog.processors.JSONRenderer()
    elif use_rich_handler:
        # 使用 RichHandler 时，用简单的 KeyValueRenderer 避免 ANSI 码重复
        renderer = structlog.dev.ConsoleRenderer(colors=False, pad_event=0)
    else:
        # text 格式：使用 ConsoleRenderer（支持颜色）
        renderer = structlog.dev.ConsoleRenderer(pad_event=0)

    # structlog 基本配置
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # 调试模式可增加堆栈信息（仅 text 模式）
    if debug_flag and log_format != "json":
        processors.insert(4, structlog.processors.StackInfoRenderer())
    
    # 使用 ProcessorFormatter 统一交由 logging.Handler 格式化
    processors.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)

    # ProcessorFormatter：让标准 logging 和 structlog 输出统一渲染
    processor_formatter = ProcessorFormatter(
        foreign_pre_chain=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    # 标准库 logging 配置
    handlers = []
    
    # 控制台 handler
    if log_format == "text" and debug_flag:
        # 启用 Rich 美化异常堆栈（带框框和变量追踪）
        install_rich_traceback(show_locals=True)
        console_handler = RichHandler(
            console=Console(stderr=True),
            show_time=False,  # structlog 已经添加时间戳
            show_path=True,
            markup=True,
            rich_tracebacks=True
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
    
    # 使用 ProcessorFormatter，让SDK的logging输出与structlog保持一致
    console_handler.setFormatter(processor_formatter)
    
    handlers.append(console_handler)
    
    # 文件 handler
    if file_log_enabled:
        if not log_file_path:
            project_root = Path.cwd()
            log_dir = project_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = str(log_dir / "app.log")
        else:
            log_file_path_obj = Path(log_file_path)
            log_file_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = TimedRotatingFileHandler(
            filename=log_file_path,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        file_handler.suffix = "%Y-%m-%d.log"
        
        class PlainTextFormatter(logging.Formatter):
            def format(self, record):
                message = record.getMessage()
                import re
                ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
                return ansi_escape.sub('', message)
        
        file_handler.setFormatter(PlainTextFormatter())
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=handlers,
        force=True
    )

    # 第三方库日志级别控制
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    获取structlog logger实例
    
    Args:
        name: logger名称，通常使用__name__
        
    Returns:
        structlog.stdlib.BoundLogger实例
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """Logger Mixin类，为类提供logger属性"""
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        return get_logger(self.__class__.__name__)
