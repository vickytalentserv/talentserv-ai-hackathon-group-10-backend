from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.property import ListingStatus, PropertyCsvRow
from app.services.scraping.compliance import ComplianceGuard, FetchResult
from app.services.scraping.parsers import (
    dict_to_property_row,
    extract_json_blobs,
    normalize_city,
    parse_cards_from_html,
    walk_json,
)


@dataclass
class ScrapeContext:
    city: str
    listing_status: ListingStatus
    max_results: int = 20


@dataclass
class SiteScrapeResult:
    source: str
    fetched: int = 0
    rows: list[PropertyCsvRow] = field(default_factory=list)
    blocked_by_robots: bool = False
    errors: list[str] = field(default_factory=list)


class BaseSiteScraper:
    source: str
    base_url: str

    def __init__(self, guard: ComplianceGuard) -> None:
        self.guard = guard

    def build_search_url(self, ctx: ScrapeContext) -> str:
        raise NotImplementedError

    def scrape(self, ctx: ScrapeContext) -> SiteScrapeResult:
        result = SiteScrapeResult(source=self.source)
        url = self.build_search_url(ctx)
        fetch = self.guard.fetch(url)

        if fetch.blocked_by_robots:
            result.blocked_by_robots = True
            result.errors.append(fetch.error or "Blocked by robots.txt")
            return result

        if fetch.error or not fetch.text:
            result.errors.append(fetch.error or "Empty response")
            return result

        result.fetched = 1
        city_meta = normalize_city(ctx.city)
        rows = self.parse_response(fetch, ctx, city_meta)
        result.rows = rows[: ctx.max_results]
        if not result.rows:
            result.errors.append(
                "No listings parsed. Site may require JavaScript or block automated access — use CSV upload fallback."
            )
        return result

    def parse_response(
        self,
        fetch: FetchResult,
        ctx: ScrapeContext,
        city_meta: dict[str, str],
    ) -> list[PropertyCsvRow]:
        rows: list[PropertyCsvRow] = []
        seen: set[str] = set()

        for blob in extract_json_blobs(fetch.text):
            for node in walk_json(blob):
                if not isinstance(node, dict):
                    continue
                if not any(key in node for key in ("price", "rent", "formattedPrice", "propertyTitle", "title")):
                    continue
                row = dict_to_property_row(
                    node,
                    source=self.source,
                    listing_status=ctx.listing_status,
                    city_meta=city_meta,
                )
                if row and row.external_id not in seen:
                    seen.add(row.external_id)
                    rows.append(row)

        for row in parse_cards_from_html(
            fetch.text,
            source=self.source,
            listing_status=ctx.listing_status,
            city_meta=city_meta,
            base_url=self.base_url,
        ):
            if row.external_id not in seen:
                seen.add(row.external_id)
                rows.append(row)

        return rows


class NoBrokerScraper(BaseSiteScraper):
    source = "nobroker"
    base_url = "https://www.nobroker.in"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city = ctx.city.lower().replace(" ", "-")
        segment = "rent" if ctx.listing_status == ListingStatus.FOR_RENT else "sale"
        return f"{self.base_url}/{segment}/{city}"


class HousingScraper(BaseSiteScraper):
    source = "housing"
    base_url = "https://housing.com"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city = ctx.city.lower().replace(" ", "-")
        segment = "rent" if ctx.listing_status == ListingStatus.FOR_RENT else "buy"
        return f"{self.base_url}/in/{segment}/{city}"


class MagicBricksScraper(BaseSiteScraper):
    source = "magicbricks"
    base_url = "https://www.magicbricks.com"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city = ctx.city.title().replace(" ", "-")
        if ctx.listing_status == ListingStatus.FOR_RENT:
            return f"{self.base_url}/{city}/Rent"
        return f"{self.base_url}/{city}"


class NinetyNineAcresScraper(BaseSiteScraper):
    source = "99acres"
    base_url = "https://www.99acres.com"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city_slug = ctx.city.lower().replace(" ", "-")
        if ctx.listing_status == ListingStatus.FOR_RENT:
            return f"{self.base_url}/search/property/rent/{city_slug}"
        return f"{self.base_url}/search/property/buy/{city_slug}"
