"""ASGI entry - use: uvicorn asgi:app"""
import sys, os
_basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_basedir, "app"))

from config import AWSConfig
from logging_config import setup_logging, get_logger
from fastapi import FastAPI

logger = get_logger("main")
config = AWSConfig()
setup_logging(config)

app = FastAPI(title="AI Radar - AWS", version="1.0.0")

from api.health_api import health_check
app.get("/health", response_model=None)(health_check)

from api.jobs_api import trigger_collect, trigger_health_check
app.post("/api/v1/jobs/collect", response_model=None)(trigger_collect)
app.post("/api/v1/jobs/health-check", response_model=None)(trigger_health_check)

logger.info("Routes registered OK")
