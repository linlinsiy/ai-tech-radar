"""KB integration module

Contains:
    kb_client.py: KBClient (TalentsView SDK wrapper)
    markdown_gen.py: Markdown file generator (3 template types)
"""
from .kb_client import KBClient, KBError, create_kb_client
from .markdown_gen import generate_article_summary, generate_deep_insight, generate_briefing

__all__ = [
    "KBClient",
    "KBError",
    "create_kb_client",
    "generate_article_summary",
    "generate_deep_insight",
    "generate_briefing",
]