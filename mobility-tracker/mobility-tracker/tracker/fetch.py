"""Page text fetchers. 'http' is a plain GET (tiny data use). 'headless' renders with Playwright."""
import re
import time
import requests
from bs4 import BeautifulSoup


def fetch_http(url, settings):
    r = requests.get(url, timeout=settings["request_timeout_s"],
                     headers={"User-Agent": settings["user_agent"], "Accept-Language": "en-CA,en;q=0.9"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ")


def fetch_headless(url, settings, wait_ms=6000, actions=None):
    from playwright.sync_api import sync_playwright  # imported lazily so http-only runs need no browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=settings["user_agent"], locale="en-CA", viewport={"width": 1400, "height": 2000})
        # Block images, fonts and media to keep data use low; prices are text.
        ctx.route("**/*", lambda route: route.abort() if route.request.resource_type in ("image", "media", "font") else route.continue_())
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=settings["request_timeout_s"] * 1000)
            page.wait_for_timeout(wait_ms)
            for a in actions or []:
                kind, _, target = a.partition(":")
                if kind == "click":
                    try:
                        page.click(target, timeout=4000)
                        page.wait_for_timeout(2500)
                    except Exception:
                        pass  # optional expanders; absence is reported by the min_plans check
            # Read twice: if the page is still changing (e.g. a tab switch half-rendered), wait and read again.
            first = page.inner_text("body")
            page.wait_for_timeout(2000)
            second = page.inner_text("body")
            if first != second:
                page.wait_for_timeout(3000)
                second = page.inner_text("body")
            return second
        finally:
            browser.close()


def fetch_text(src, settings, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            if src["fetch"] == "http":
                return fetch_http(src["url"], settings)
            return fetch_headless(src["url"], settings, src.get("wait_ms", 6000), src.get("actions"))
        except Exception as e:  # noqa: BLE001 - recorded in the run log
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {retries + 1} tries: {last}")
