from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright

STEALTH_INIT_SCRIPT = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class BrowserFetchResult:
    url: str
    status_code: int
    html: str = ""
    json_data: Any | None = None
    error: str | None = None


class PlaywrightFetcher:
    """Headless browser fetcher with basic anti-bot mitigations for JS-heavy sites."""

    def __init__(
        self,
        *,
        headless: bool = True,
        channel: str | None = None,
        timeout_ms: int = 45_000,
    ) -> None:
        self.headless = headless
        self.channel = channel
        self.timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> PlaywrightFetcher:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._browser is not None:
            return

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self.channel:
            try:
                self._browser = self._playwright.chromium.launch(channel=self.channel, **launch_kwargs)
            except Exception:
                self._browser = self._playwright.chromium.launch(**launch_kwargs)
        else:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)

        self._context = self._browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
        )
        self._context.add_init_script(STEALTH_INIT_SCRIPT)

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def _page(self) -> Page:
        if self._context is None:
            raise RuntimeError("PlaywrightFetcher is not started")
        return self._context.new_page()

    def fetch_html(
        self,
        url: str,
        *,
        wait_selector: str | None = None,
        wait_ms: int = 0,
        scroll_y: int = 0,
    ) -> BrowserFetchResult:
        page = self._page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=self.timeout_ms)
            if scroll_y:
                page.evaluate(f"window.scrollTo(0, {scroll_y})")
                page.wait_for_timeout(1500)

            status_code = response.status if response is not None else 0
            html = page.content()
            blocked = "Security Alert" in page.title() or "Request Blocked" in html
            if blocked:
                return BrowserFetchResult(
                    url=url,
                    status_code=status_code,
                    html=html,
                    error="Blocked by site security (bot detection)",
                )
            return BrowserFetchResult(url=page.url, status_code=status_code, html=html)
        except Exception as exc:
            return BrowserFetchResult(url=url, status_code=0, html="", error=str(exc))
        finally:
            page.close()

    def fetch_json_via_browser(
        self,
        page_url: str,
        api_url: str,
        *,
        wait_ms: int = 3_000,
    ) -> BrowserFetchResult:
        page = self._page()
        try:
            response = page.goto(page_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            if wait_ms:
                page.wait_for_timeout(wait_ms)

            api_response = page.request.get(
                api_url,
                headers={"Accept": "application/json", "Referer": page.url},
            )
            payload: Any | None = None
            error: str | None = None
            try:
                payload = api_response.json()
            except Exception as exc:
                error = f"Invalid JSON from API: {exc}"

            if isinstance(payload, dict) and payload.get("status") == "fail":
                error = str(payload.get("error_message") or "API request failed")

            status_code = response.status if response is not None else 0
            return BrowserFetchResult(
                url=api_url,
                status_code=status_code,
                html=page.content(),
                json_data=payload,
                error=error,
            )
        except Exception as exc:
            return BrowserFetchResult(url=api_url, status_code=0, error=str(exc))
        finally:
            page.close()

    def extract_housing_recent_cards(self, page_url: str, *, wait_ms: int = 15_000) -> BrowserFetchResult:
        page = self._page()
        try:
            response = page.goto(page_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page.wait_for_timeout(wait_ms)
            cards = page.evaluate(
                """() => Array.from(document.querySelectorAll('a[class*="recentlyAddedCardStyle"]')).map((anchor) => ({
                    href: anchor.href,
                    text: anchor.innerText,
                }))"""
            )
            status_code = response.status if response is not None else 0
            html = page.content()
            blocked = "Security Alert" in page.title() or "Request Blocked" in html
            if blocked:
                return BrowserFetchResult(
                    url=page_url,
                    status_code=status_code,
                    html=html,
                    error="Blocked by site security (bot detection)",
                )
            return BrowserFetchResult(
                url=page.url,
                status_code=status_code,
                html=html,
                json_data=cards,
            )
        except Exception as exc:
            return BrowserFetchResult(url=page_url, status_code=0, error=str(exc))
        finally:
            page.close()


@contextmanager
def playwright_fetcher(
    *,
    headless: bool = True,
    channel: str | None = "chrome",
    timeout_ms: int = 45_000,
) -> Iterator[PlaywrightFetcher]:
    fetcher = PlaywrightFetcher(headless=headless, channel=channel, timeout_ms=timeout_ms)
    fetcher.start()
    try:
        yield fetcher
    finally:
        fetcher.close()
