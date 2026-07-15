"""
L1 去重模块

基于 URL 哈希和内容指纹进行去重，支持文件缓存。
与设计文档对齐：在受控导入前进行去重，避免重复入库。
"""
import json
import os
import logging
from typing import List, Set, Dict
from crawler.base import RawArticle

from logging_config import get_logger
logger = get_logger("processor.dedup")


class DedupManager:
    """
    去重管理器

    在本地文件缓存中维护已处理文章的 url_hash 集合，
    采集后先查重再进入分析流程。

    类变量：
        cache_path: 去重缓存文件路径
        _hashes: 已处理的 url_hash 集合
        _content_hashes: 已处理的内容指纹集合
    """

    def __init__(self, cache_path: str = "./data/interim/processed_hashes.json"):
        """
        初始化去重管理器

        入参：
            cache_path: 缓存文件路径
        """
        self.cache_path = cache_path
        self._hashes: Set[str] = set()
        self._content_hashes: Set[str] = set()
        self._load()

    def _load(self):
        """从缓存文件加载已处理哈希"""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._hashes = set(data.get("url_hashes", []))
                    self._content_hashes = set(data.get("content_hashes", []))
                logger.info(
                    "去重缓存加载: url_hashes=%d, content_hashes=%d",
                    len(self._hashes), len(self._content_hashes)
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("去重缓存加载失败，将全新开始: %s", str(e))
            self._hashes = set()
            self._content_hashes = set()

    def _save(self):
        """保存去重缓存"""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "url_hashes": list(self._hashes),
                    "content_hashes": list(self._content_hashes),
                }, f, indent=2)
        except OSError as e:
            logger.warning("去重缓存保存失败: %s", str(e))

    def is_duplicate(self, article: 'RawArticle') -> bool:
        """
        检查文章是否重复

        入参：
            article: RawArticle 实例
        出参：True 表示已存在（重复），False 表示新文章
        """
        return article.url_hash in self._hashes

    def filter_duplicates(self, articles: List['RawArticle']) -> List['RawArticle']:
        """
        过滤重复文章，返回新文章列表并更新缓存

        入参：
            articles: 待过滤的文章列表
        出参：去重后的新文章列表
        """
        new_articles: List[RawArticle] = []
        duplicates = 0
        for article in articles:
            if article.url_hash in self._hashes:
                duplicates += 1
                logger.debug("去重命中: %s", article.url_hash[:16])
                continue
            self._hashes.add(article.url_hash)
            new_articles.append(article)

        if duplicates > 0 or new_articles:
            self._save()

        logger.info(
            "去重完成: total=%d, new=%d, skipped=%d",
            len(articles), len(new_articles), duplicates
        )
        return new_articles

    def mark_processed(self, article: 'RawArticle'):
        """标记单篇文章为已处理（用于重试场景）"""
        self._hashes.add(article.url_hash)
        if article.content_hash:
            self._content_hashes.add(article.content_hash)
        self._save()

    def mark_processed_batch(self, articles: List['RawArticle']):
        """在 L2 成功后批量提交去重状态，失败文章保留重试机会。"""
        for article in articles:
            self._hashes.add(article.url_hash)
            if article.content_hash:
                self._content_hashes.add(article.content_hash)
        if articles:
            self._save()

    def is_content_duplicate(self, article: 'RawArticle') -> bool:
        """检查正文指纹是否已处理。"""
        return bool(article.content_hash and article.content_hash in self._content_hashes)

