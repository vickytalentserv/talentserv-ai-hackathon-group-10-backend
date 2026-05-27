from __future__ import annotations

from typing import Any

from app.schemas.property import ListingStatus, PropertyCsvRow
from app.services.scraping.compliance import ComplianceGuard
from app.services.scraping.sites import HousingScraper, ScrapeContext, SiteScrapeResult


def _serialize_site_result(result: SiteScrapeResult) -> dict[str, Any]:
    return {
        "source": result.source,
        "fetched": result.fetched,
        "rows": [row.model_dump(mode="json") for row in result.rows],
        "blocked_by_robots": result.blocked_by_robots,
        "errors": result.errors,
    }


def deserialize_site_result(payload: dict[str, Any]) -> SiteScrapeResult:
    return SiteScrapeResult(
        source=str(payload["source"]),
        fetched=int(payload.get("fetched", 0)),
        rows=[PropertyCsvRow.model_validate(row) for row in payload.get("rows", [])],
        blocked_by_robots=bool(payload.get("blocked_by_robots", False)),
        errors=[str(error) for error in payload.get("errors", [])],
    )


def run_housing_scrape_worker(
    *,
    city: str,
    listing_status: str,
    max_results: int,
    headless: bool,
    channel: str | None,
    timeout_ms: int,
    delay_seconds: float,
) -> dict[str, Any]:
    """Run Housing Playwright scrape in an isolated process (avoids asyncio conflicts)."""
    from app.services.scraping.browser import PlaywrightFetcher

    ctx = ScrapeContext(
        city=city,
        listing_status=ListingStatus(listing_status),
        max_results=max_results,
    )
    guard = ComplianceGuard(delay_seconds=delay_seconds)
    playwright = PlaywrightFetcher(headless=headless, channel=channel, timeout_ms=timeout_ms)
    playwright.start()
    try:
        scraper = HousingScraper(guard, playwright=playwright)
        result = scraper.scrape_with_playwright(ctx)
        return _serialize_site_result(result)
    finally:
        playwright.close()
