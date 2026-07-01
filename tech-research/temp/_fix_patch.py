import os, re

BASE = r"D:\013148\code\AI\u6280\u672f\u8d8b\u52bf\u96f7\u8fbe\tech-research\aws\app"

def fix_logging_config():
    full = os.path.join(BASE, "logging_config.py")
    with open(full, "r", encoding="utf-8") as f:
        c = f.read()
    old = "root = logging.getLogger(name)"
    new = "root = logging.getLogger(name)\n    # prevent duplicate handler registration\n    if root.handlers:\n        return root"
    c = c.replace(old, new)
    with open(full, "w", encoding="utf-8") as f:
        f.write(c)
    print("OK: logging_config.py")

def fix_logger_import(rel_path, logger_name):
    full = os.path.join(BASE, rel_path)
    with open(full, "r", encoding="utf-8") as f:
        c = f.read()
    old = 'logger = logging.getLogger("{}")'.format(logger_name)
    new = 'from logging_config import get_logger\nlogger = get_logger("{}")'.format(logger_name)
    c = c.replace(old, new)
    with open(full, "w", encoding="utf-8") as f:
        f.write(c)
    print("OK:", rel_path)

fix_logging_config()

targets = [
    ("api/health_api.py", "health_api"),
    ("api/jobs_api.py", "api.jobs"),
    ("crawler/api_crawler.py", "crawler.api"),
    ("crawler/rss_crawler.py", "crawler.rss"),
    ("crawler/web_crawler.py", "crawler.web"),
    ("deep/insight.py", "deep.insight"),
    ("exporter/import_client.py", "exporter.import_client"),
    ("jobs/health_check_job.py", "jobs.health_check"),
    ("jobs/xxl_executor.py", "xxl_job"),
    ("processor/parser.py", "processor.parser"),
]
for fp, ln in targets:
    fix_logger_import(fp, ln)

print("All done - 11 files fixed")
