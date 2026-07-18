"""Local snapshots of hydrated articles for formal L2/L3 re-analysis."""
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from crawler.base import RawArticle


class CollectionSnapshotStore:
    """Persist the latest formal analysis input without coupling AWS to MySQL."""

    SAFE_BATCH_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

    def __init__(self, data_dir: str):
        self.directory = os.path.join(data_dir, "analysis_snapshots")
        self.latest_path = os.path.join(self.directory, "latest.json")

    @staticmethod
    def article_to_dict(article: RawArticle) -> Dict[str, Any]:
        return {
            "source_code": article.source_code,
            "title": article.title,
            "url": article.url,
            "url_hash": article.url_hash,
            "author": article.author,
            "publish_time": article.publish_time.isoformat() if article.publish_time else None,
            "crawl_time": article.crawl_time.isoformat(),
            "raw_html": article.raw_html,
            "raw_summary": article.raw_summary,
            "content_hash": article.content_hash,
            "predicted_category": article.predicted_category,
            "ai_related": article.ai_related,
            "info_type_hint": article.info_type_hint,
            "route_confidence": article.route_confidence,
            "route_reason": article.route_reason,
            "route_method": article.route_method,
            "candidate_score": article.candidate_score,
        }

    @staticmethod
    def article_from_dict(data: Dict[str, Any]) -> RawArticle:
        article = RawArticle(
            source_code=data["source_code"],
            title=data.get("title") or "Untitled",
            url=data["url"],
            author=data.get("author"),
            publish_time=datetime.fromisoformat(data["publish_time"]) if data.get("publish_time") else None,
            crawl_time=datetime.fromisoformat(data["crawl_time"]) if data.get("crawl_time") else datetime.now(),
            raw_html=data.get("raw_html"),
            raw_summary=data.get("raw_summary"),
            content_hash=data.get("content_hash"),
            predicted_category=data.get("predicted_category"),
            ai_related=data.get("ai_related"),
            info_type_hint=data.get("info_type_hint"),
            route_confidence=float(data.get("route_confidence") or 0),
            route_reason=data.get("route_reason"),
            route_method=data.get("route_method"),
            candidate_score=float(data.get("candidate_score") or 0),
        )
        if data.get("url_hash"):
            article.url_hash = data["url_hash"]
        return article

    def save(
        self,
        batch_no: str,
        request: Dict[str, Any],
        source_profiles: Dict[str, Dict[str, Any]],
        articles: Iterable[RawArticle],
        update_latest: bool = True,
    ) -> str:
        os.makedirs(self.directory, exist_ok=True)
        unique = {}
        for article in articles:
            unique[article.url_hash] = self.article_to_dict(article)
        payload = {
            "schema_version": "1.0",
            "batch_no": batch_no,
            "created_at": datetime.now().isoformat(),
            "request": request,
            "source_profiles": source_profiles,
            "article_count": len(unique),
            "articles": list(unique.values()),
        }
        batch_path = os.path.join(self.directory, f"{batch_no}.json")
        self._atomic_write(batch_path, payload)
        if update_latest:
            self._atomic_write(self.latest_path, payload)
        return os.path.abspath(batch_path)

    def load_latest(self) -> Dict[str, Any]:
        if not os.path.isfile(self.latest_path):
            raise FileNotFoundError("不存在可重跑的采集快照，请先完成一次正式采集分析")
        with open(self.latest_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def load(self, batch_no: str) -> Dict[str, Any]:
        """Load one named formal snapshot without changing the latest pointer."""
        normalized_batch_no = self._normalize_batch_no(batch_no)
        path = os.path.join(self.directory, f"{normalized_batch_no}.json")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"未找到采集快照批次: {normalized_batch_no}")
        with open(path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
        if snapshot.get("batch_no") != normalized_batch_no:
            raise ValueError(f"采集快照批次内容不匹配: {normalized_batch_no}")
        return snapshot

    def list_snapshots(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return lightweight metadata for selectable formal analysis snapshots."""
        if not os.path.isdir(self.directory):
            return []
        snapshots = []
        for filename in os.listdir(self.directory):
            if filename == "latest.json" or not filename.endswith(".json"):
                continue
            batch_no = filename[:-5]
            if not self.SAFE_BATCH_PATTERN.fullmatch(batch_no):
                continue
            try:
                snapshot = self.load(batch_no)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            request = snapshot.get("request") or {}
            snapshots.append({
                "batch_no": batch_no,
                "created_at": snapshot.get("created_at"),
                "article_count": int(snapshot.get("article_count") or 0),
                "scope": request.get("scope"),
                "from_date": request.get("from_date"),
                "to_date": request.get("to_date"),
                "sources": request.get("sources"),
            })
        snapshots.sort(
            key=lambda item: (item.get("created_at") or "", item["batch_no"]),
            reverse=True,
        )
        return snapshots[:max(1, min(limit, 500))]

    def _validate_batch_no(self, batch_no: str) -> None:
        if not batch_no or not self.SAFE_BATCH_PATTERN.fullmatch(batch_no):
            raise ValueError("采集快照批次号仅允许字母、数字、点、下划线和连字符")

    def _normalize_batch_no(self, batch_no: str) -> str:
        """Accept a batch number or the copied <batch_no>.json filename."""
        normalized = str(batch_no or "").strip()
        if normalized.lower().endswith(".json"):
            normalized = normalized[:-5]
        self._validate_batch_no(normalized)
        return normalized

    @staticmethod
    def _atomic_write(path: str, payload: Dict[str, Any]) -> None:
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
