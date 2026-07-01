"""
AWS 举日志配置模块

按许计文框接求，使用双文件日志策略：
- app.log: 记录所有运行信息（INFO 及以上），每日轮转，保留 30 天
- error.log: 仅记录 ERROR 及以上，每日轮转，保留 90 天

不接入 APM，保认日志跨转30天。
"""
import logging
import logging.handlers
import os
from typing import Optional


def setup_logging(config, name: str = "ai-radar"):
    log_cfg = config.log_config
    root = logging.getLogger(name)
    # prevent duplicate handler registration (main.py calls init_app twice)
    if root.handlers:
        return root
    root.setLevel(logging.DEBUG)

    # app.log
    app_path = log_cfg["app_log_path"]
    os.makedirs(os.path.dirname(app_path), exist_ok=True)
    app_handler = logging.handlers.TimedRotatingFileHandler(
        app_path, when="midnight", interval=1, backupCount=log_cfg["app_log_retention"],
        encoding="utf-8"
    )
    app_handler.setLevel(getattr(logging, log_cfg["app_log_level"], logging.INFO))
    app_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root.addHandler(app_handler)

    # error.log
    err_path = log_cfg["error_log_path"]
    os.makedirs(os.path.dirname(err_path), exist_ok=True)
    err_handler = logging.handlers.TimedRotatingFileHandler(
        err_path, when="midnight", interval=1, backupCount=log_cfg["error_log_retention"],
        encoding="utf-8"
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root.addHandler(err_handler)

    # console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root.addHandler(console)

    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ai-radar.{name}")
