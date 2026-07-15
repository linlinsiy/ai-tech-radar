"""Local collection manifest and source health persistence for the AWS single node."""

import json
import os
from datetime import datetime
from typing import Dict, List

from logging_config import get_logger

logger = get_logger("processor.collection_audit")


class CollectionAudit:
    def __init__(self, data_dir: str, batch_no: str):
        self.data_dir = data_dir
        self.batch_no = batch_no
        self.started_at = datetime.now().isoformat()
        self.sources: List[Dict] = []

    def record_source(
        self,
        source: Dict[str, str],
        article_count: int,
        status: str,
        error: str = "",
        details: Dict = None,
    ):
        record = {
            "source_code": source.get("code", ""),
            "source_name": source.get("name", ""),
            "category": source.get("category", ""),
            "fetch_method": source.get("fetch_method", "rss"),
            "article_count": article_count,
            "status": status,
            "error": error[:500],
        }
        if details:
            record.update(details)
        self.sources.append(record)

    def save(self, articles: List[Dict], stats: Dict):
        audit_dir = os.path.join(self.data_dir, "collection_audit")
        os.makedirs(audit_dir, exist_ok=True)
        payload = {
            "batch_no": self.batch_no,
            "started_at": self.started_at,
            "finished_at": datetime.now().isoformat(),
            "sources": self.sources,
            "articles": articles,
            "stats": stats,
        }
        self._write_json(os.path.join(audit_dir, f"{self.batch_no}.json"), payload)
        self._update_health()

    def save_candidate_pool(self, candidates: List[Dict]):
        """保存未读取正文的候选元数据，供覆盖核对和后续重跑参考。"""
        candidate_dir = os.path.join(self.data_dir, "candidate_pool")
        os.makedirs(candidate_dir, exist_ok=True)
        payload = {
            "batch_no": self.batch_no,
            "saved_at": datetime.now().isoformat(),
            "candidates": candidates,
        }
        self._write_json(
            os.path.join(candidate_dir, f"{self.batch_no}.json"),
            payload,
        )

    def _update_health(self):
        path = os.path.join(self.data_dir, "source_health.json")
        health = {}
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as handle:
                    health = json.load(handle)
        except (OSError, json.JSONDecodeError):
            health = {}

        now = datetime.now().isoformat()
        for source in self.sources:
            code = source["source_code"]
            previous = health.get(code, {})
            status = source["status"]
            consecutive_failures = 0 if status == "success" else int(
                previous.get("consecutive_failures", 0)
            ) + 1
            health[code] = {
                "source_name": source["source_name"],
                "last_status": status,
                "last_article_count": source["article_count"],
                "last_checked_at": now,
                "last_success_at": now if status == "success" else previous.get("last_success_at"),
                "consecutive_failures": consecutive_failures,
            }
        self._write_json(path, health)

    @staticmethod
    def _write_json(path: str, payload: Dict):
        tmp_path = f"{path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_path, path)
        except OSError as exc:
            logger.warning("采集审计文件保存失败: path=%s, error=%s", path, str(exc))
