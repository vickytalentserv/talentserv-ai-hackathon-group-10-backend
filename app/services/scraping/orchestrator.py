from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from sqlalchemy.orm import Session

from app.schemas.property import ListingStatus
from app.services.ingestion import IngestionService
from app.services.scraping.compliance import ComplianceGuard
from app.services.scraping.sites import (
    PLAYWRIGHT_SOURCES,
    HousingScraper,
    MagicBricksScraper,
    NinetyNineAcresScraper,
    NoBrokerScraper,
    ScrapeContext,
    SiteScrapeResult,
)
from app.services.scraping.worker import deserialize_site_result, run_housing_scrape_worker

T = TypeVar("T")

SUPPORTED_SCRAPE_SOURCES = {
    "nobroker": NoBrokerScraper,
    "housing": HousingScraper,
    "magicbricks": MagicBricksScraper,
    "99acres": NinetyNineAcresScraper,
}


@dataclass
class ScrapeRunResult:
    sources: list[SiteScrapeResult] = field(default_factory=list)
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class ScrapeOrchestrator:
    def __init__(
        self,
        ingestion: IngestionService,
        *,
        delay_seconds: float = 2.0,
        playwright_enabled: bool = True,
        playwright_headless: bool = True,
        playwright_channel: str | None = None,
        playwright_timeout_ms: int = 45_000,
    ) -> None:
        self.ingestion = ingestion
        self.guard = ComplianceGuard(delay_seconds=delay_seconds)
        self.playwright_enabled = playwright_enabled
        self.playwright_headless = playwright_headless
        self.playwright_channel = playwright_channel
        self.playwright_timeout_ms = playwright_timeout_ms

    @staticmethod
    def _run_in_isolated_thread(func: Callable[[], T]) -> T:
        """Run Playwright sync code outside FastAPI's asyncio worker thread."""
        result_box: dict[str, Any] = {}
        error_box: dict[str, BaseException] = {}

        def worker() -> None:
            try:
                result_box["value"] = func()
            except BaseException as exc:
                error_box["error"] = exc

        thread = threading.Thread(target=worker, name="playwright-scraper", daemon=True)
        thread.start()
        thread.join()
        if "error" in error_box:
            raise error_box["error"]
        return result_box["value"]

    def _scrape_housing(self, ctx: ScrapeContext) -> SiteScrapeResult:
        payload = self._run_in_isolated_thread(
            lambda: run_housing_scrape_worker(
                city=ctx.city,
                listing_status=ctx.listing_status.value,
                max_results=ctx.max_results,
                headless=self.playwright_headless,
                channel=self.playwright_channel,
                timeout_ms=self.playwright_timeout_ms,
                delay_seconds=self.guard.delay_seconds,
            )
        )
        return deserialize_site_result(payload)

    def run(
        self,
        db: Session,
        *,
        sources: list[str],
        city: str,
        listing_status: ListingStatus,
        max_results: int,
    ) -> ScrapeRunResult:
        run_result = ScrapeRunResult()
        ctx = ScrapeContext(city=city, listing_status=listing_status, max_results=max_results)
        normalized_sources = [source_name.strip().lower() for source_name in sources]

        if "housing" in normalized_sources and not self.playwright_enabled:
            run_result.errors.append(
                "Playwright scraping is disabled (SCRAPE_PLAYWRIGHT_ENABLED=false) but required for Housing"
            )
            return run_result

        for source_name in sources:
            key = source_name.strip().lower()
            scraper_cls = SUPPORTED_SCRAPE_SOURCES.get(key)
            if scraper_cls is None:
                run_result.errors.append(f"Unsupported source '{source_name}'")
                continue

            try:
                if key in PLAYWRIGHT_SOURCES:
                    site_result = self._scrape_housing(ctx)
                else:
                    site_result = scraper_cls(self.guard).scrape(ctx)
            except Exception as exc:
                site_result = SiteScrapeResult(source=key, errors=[f"Scrape failed: {exc}"])

            run_result.sources.append(site_result)

            if not site_result.rows:
                run_result.errors.extend(site_result.errors)
                continue

            ingest_result = self.ingestion.ingest_property_records(
                db,
                filename=f"scrape-{site_result.source}",
                rows=site_result.rows,
            )
            run_result.rows_read += ingest_result.rows_read
            run_result.rows_inserted += ingest_result.rows_inserted
            run_result.rows_updated += ingest_result.rows_updated
            run_result.rows_skipped += ingest_result.rows_skipped
            run_result.errors.extend(ingest_result.errors)

        return run_result
