from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

DEFAULT_USER_AGENT = "RealEstateHackathonBot/1.0 (+https://github.com/hackathon; compliance-first scraper)"


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    blocked_by_robots: bool = False
    error: str | None = None


class ComplianceGuard:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, delay_seconds: float = 2.0) -> None:
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self._robot_cache: dict[str, RobotFileParser] = {}
        self._last_fetch_at = 0.0

    def _robot_parser(self, base_url: str) -> RobotFileParser:
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robot_cache:
            parser = RobotFileParser()
            parser.set_url(urljoin(origin, "/robots.txt"))
            try:
                parser.read()
            except Exception:
                parser = RobotFileParser()
                parser.parse("User-agent: *\nDisallow: /".splitlines())
            self._robot_cache[origin] = parser
        return self._robot_cache[origin]

    def allowed(self, url: str) -> bool:
        parser = self._robot_parser(url)
        return parser.can_fetch(self.user_agent, url)

    def fetch(self, url: str, *, timeout: float = 20.0) -> FetchResult:
        if not self.allowed(url):
            return FetchResult(
                url=url,
                status_code=0,
                text="",
                blocked_by_robots=True,
                error=f"Blocked by robots.txt: {url}",
            )

        elapsed = time.monotonic() - self._last_fetch_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }

        try:
            response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            self._last_fetch_at = time.monotonic()
            return FetchResult(
                url=str(response.url),
                status_code=response.status_code,
                text=response.text,
                error=None if response.is_success else f"HTTP {response.status_code}",
            )
        except httpx.HTTPError as exc:
            self._last_fetch_at = time.monotonic()
            return FetchResult(url=url, status_code=0, text="", error=str(exc))
