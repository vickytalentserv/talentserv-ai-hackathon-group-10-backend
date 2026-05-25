from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.schemas.property import ListingStatus, PropertyCsvRow
from app.services.ingestion import IngestionService
from app.services.scraping.compliance import ComplianceGuard
from app.services.scraping.sites import (
    HousingScraper,
    MagicBricksScraper,
    NinetyNineAcresScraper,
    NoBrokerScraper,
    ScrapeContext,
    SiteScrapeResult,
)

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
    def __init__(self, ingestion: IngestionService, *, delay_seconds: float = 2.0) -> None:
        self.ingestion = ingestion
        self.guard = ComplianceGuard(delay_seconds=delay_seconds)

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

        for source_name in sources:
            key = source_name.strip().lower()
            scraper_cls = SUPPORTED_SCRAPE_SOURCES.get(key)
            if scraper_cls is None:
                run_result.errors.append(f"Unsupported source '{source_name}'")
                continue

            scraper = scraper_cls(self.guard)
            site_result = scraper.scrape(ctx)
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
