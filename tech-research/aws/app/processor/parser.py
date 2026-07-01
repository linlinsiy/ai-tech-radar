"""
L1 内容解析器

从 RawArticle 中提取正文内容，包括 HTML 清洗和纯文本提取。
"""
import re
import logging
from typing import Optional
from bs4 import BeautifulSoup

from logging_config import get_logger
logger = get_logger("processor.parser")


class ContentParser:
    """
    内容解析器

    方法：
        extract_text: 从 HTML 中提取纯文本内容
        extract_main_content: 提取文章主体内容（去除导航、广告等）
        compute_content_hash: 计算内容 SHA-256 指纹
    """

    @staticmethod
    def extract_text(html: str) -> str:
        """
        从 HTML 中提取纯文本

        入参：
            html: 原始 HTML 字符串
        出参：纯文本内容
        """
        try:
            soup = BeautifulSoup(html, "lxml")
            # 移除 script / style 标签
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # 合并多余空行
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text
        except Exception as e:
            logger.warning("HTML 解析失败: %s", str(e))
            return html  # 兜底返回原始内容

    @staticmethod
    def extract_main_content(html: str) -> str:
        """
        提取文章主体内容

        入参：
            html: 原始 HTML
        出参：主体文本，优先取 <article> 或 main content 区域
        """
        try:
            soup = BeautifulSoup(html, "lxml")
            # 尝试找到主体内容标签
            for selector in ["article", "main", '[role="main"]', ".post-content", ".article-content", "#content"]:
                content = soup.select_one(selector)
                if content:
                    return ContentParser.extract_text(str(content))
            # 兜底：提取 body 内容
            body = soup.find("body")
            if body:
                return ContentParser.extract_text(str(body))
            return ContentParser.extract_text(html)
        except Exception as e:
            logger.warning("主体内容提取失败: %s", str(e))
            return ContentParser.extract_text(html)

    @staticmethod
    def fetch_full_content(url: str, timeout: int = 15) -> Optional[str]:
        """
        通过网络请求获取文章全文

        入参：
            url: 文章链接
            timeout: 请求超时秒数
        出参：文章全文（HTML），获取失败返回 None
        """
        import requests
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "AI-Radar-Bot/1.0"},
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning("获取文章全文失败: url=%s, %s", url, str(e))
            return None
