"""Headless Chromium fallback used when normal HTTP collection cannot read a page."""

import os
import threading
from typing import Optional

from logging_config import get_logger

logger = get_logger("crawler.browser")


class BrowserFetcher:
    """Fetch rendered HTML with Playwright. Calls are serialized on the single node."""

    _lock = threading.Lock()
    _dependency_warning_emitted = False

    def __init__(self, timeout_seconds: int = 45):
        self.timeout_ms = max(1, timeout_seconds) * 1000

    def fetch_html(self, url: str) -> Optional[str]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError:
            if not BrowserFetcher._dependency_warning_emitted:
                logger.warning("Playwright 未安装，跳过浏览器降级采集")
                BrowserFetcher._dependency_warning_emitted = True
            return None

        with self._lock:
            browser = None
            context = None
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(
                        locale="zh-CN",
                        user_agent=(
                            "Mozilla/5.0 (X11; Linux x86_64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                    )
                    page = context.new_page()
                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self.timeout_ms,
                    )
                    html = page.content()
                    return html
            except PlaywrightTimeoutError:
                logger.warning("浏览器降级请求超时: %s", url)
            except Exception as exc:
                browser_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "default")
                logger.warning(
                    "浏览器降级请求失败: url=%s, browsers_path=%s, error=%s",
                    url,
                    browser_path,
                    str(exc),
                )
            finally:
                if context is not None:
                    try:
                        context.close()
                    except Exception:
                        pass
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass
        return None
