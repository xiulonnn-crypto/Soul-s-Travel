import re
from urllib.parse import urlparse


def _validate_qyer_url(url: str) -> str:
    """Validate and normalize a qyer trip plan URL."""
    parsed = urlparse(url)
    if parsed.hostname not in ('plan.qyer.com', 'www.qyer.com', 'm.qyer.com'):
        raise ValueError(f"不支持的域名: {parsed.hostname}，仅支持穷游行程助手链接")
    if not re.search(r'/trip/[A-Za-z0-9_-]+', parsed.path):
        raise ValueError("无效的穷游行程链接格式")
    return url


def scrape_qyer_url(url: str) -> str:
    """Load a qyer.com trip plan page via mobile endpoint and return its text content.

    The mobile version (m.qyer.com) doesn't require JS-based anti-bot verification,
    so we use a mobile user-agent to get redirected there automatically.
    """
    url = _validate_qyer_url(url)

    from playwright.sync_api import sync_playwright
    import time

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            locale="zh-CN",
            viewport={"width": 375, "height": 812},
            is_mobile=True,
        )
        page = context.new_page()
        page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", { get: () => undefined });'
        )

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Click "加载更多" until all days are loaded
            for _ in range(10):
                btn = page.query_selector("text=点击加载更多")
                if not btn or not btn.is_visible():
                    break
                btn.click()
                time.sleep(2)

            text = page.inner_text("body")
        finally:
            browser.close()

    if not text or len(text.strip()) < 100:
        raise RuntimeError("页面内容抓取失败，可能遇到了反爬验证或页面加载超时")

    return text
