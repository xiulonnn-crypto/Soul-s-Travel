import re
import urllib.request
import json
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# PiTravel (圆周旅迹)
# ---------------------------------------------------------------------------

def scrape_pitravel_api(url: str) -> dict:
    """Fetch structured journey JSON from PiTravel's public API.

    Supports URLs:
        https://www.pitravel.cn/web/journey/detail/676874
        https://pitravel.cn/journey/676874  (short form)
    Returns raw API response dict (the 'data' subtree).
    """
    parsed = urlparse(url)
    if parsed.hostname not in ('www.pitravel.cn', 'pitravel.cn', 'm.pitravel.cn'):
        raise ValueError(f"不支持的域名: {parsed.hostname}，此路径仅支持 pitravel.cn 链接")

    m = re.search(r'/(?:journey/detail|journey)/(\d+)', parsed.path)
    if not m:
        raise ValueError("无法从 URL 中解析行程 ID，请确认链接格式为 .../journey/detail/<id>")

    journey_id = m.group(1)
    api_url = f"https://www.pitravel.cn/api/slytherin/v1/web/journey/detail?journey_id={journey_id}"

    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "application/json",
            "Referer": url,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"PiTravel API 请求失败: {e}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"PiTravel API 返回了非法 JSON: {e}")

    if not data.get("success") and data.get("code") != 0:
        msg = data.get("msg", "未知错误")
        raise RuntimeError(f"PiTravel API 返回错误: {msg}")

    journey_data = data.get("data")
    if not journey_data or "journey" not in journey_data:
        raise RuntimeError("PiTravel API 未返回行程数据，请确认行程已公开分享")

    return journey_data


# ---------------------------------------------------------------------------
# Qyer (穷游)
# ---------------------------------------------------------------------------

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
