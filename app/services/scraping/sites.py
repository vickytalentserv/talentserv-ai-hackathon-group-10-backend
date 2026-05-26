from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.schemas.property import ListingStatus, PropertyCsvRow
from app.services.scraping.browser import PlaywrightFetcher
from app.services.scraping.compliance import ComplianceGuard, FetchResult
from app.services.scraping.parsers import (
    dict_to_property_row,
    extract_json_blobs,
    normalize_city,
    parse_cards_from_html,
    parse_housing_recent_cards,
    parse_housing_recent_cards_from_html,
    parse_nobroker_api_listings,
    walk_json,
)

PLAYWRIGHT_SOURCES = frozenset({"housing"})


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
    uses_playwright = False

    def __init__(
        self,
        guard: ComplianceGuard,
        *,
        playwright: PlaywrightFetcher | None = None,
    ) -> None:
        self.guard = guard
        self.playwright = playwright

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

        return rows[: ctx.max_results]


class PlaywrightSiteScraper(BaseSiteScraper):
    uses_playwright = True

    def scrape(self, ctx: ScrapeContext) -> SiteScrapeResult:
        if self.playwright is None:
            result = SiteScrapeResult(source=self.source)
            result.errors.append("Playwright is required for this source but is not available")
            return result
        return self.scrape_with_playwright(ctx)

    def scrape_with_playwright(self, ctx: ScrapeContext) -> SiteScrapeResult:
        raise NotImplementedError


class NoBrokerScraper(BaseSiteScraper):
    source = "nobroker"
    base_url = "https://www.nobroker.in"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city = ctx.city.lower().replace(" ", "-")
        segment = "rent" if ctx.listing_status == ListingStatus.FOR_RENT else "sale"
        return f"{self.base_url}/property/{segment}/{city}"

    def build_api_url(self, ctx: ScrapeContext, city_meta: dict[str, str]) -> str:
        city = ctx.city.lower().replace(" ", "-")
        segment = "RENT" if ctx.listing_status == ListingStatus.FOR_RENT else "BUY"
        return (
            f"{self.base_url}/api/v3/multi/property/{segment}/filter"
            f"?city={city}&pageNo=1"
            f"&latitude={city_meta['latitude']}&longitude={city_meta['longitude']}"
        )

    def scrape(self, ctx: ScrapeContext) -> SiteScrapeResult:
        result = SiteScrapeResult(source=self.source)
        page_url = self.build_search_url(ctx)
        city_meta = normalize_city(ctx.city)

        if not self.guard.allowed(page_url):
            result.blocked_by_robots = True
            result.errors.append(f"Blocked by robots.txt: {page_url}")
            return result

        api_url = self.build_api_url(ctx, city_meta)
        fetch = self.guard.fetch(api_url, referer=page_url)
        result.fetched = 1 if fetch.status_code else 0

        if fetch.blocked_by_robots or fetch.error:
            result.errors.append(fetch.error or "NoBroker API request failed")
            return result

        try:
            payload = json.loads(fetch.text)
        except json.JSONDecodeError:
            result.errors.append("Invalid JSON from NoBroker API")
            return result

        if isinstance(payload, dict) and payload.get("status") == "fail":
            result.errors.append(str(payload.get("error_message") or "NoBroker API request failed"))
            return result

        listings = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(listings, list):
            result.errors.append("NoBroker API returned no listing data")
            return result

        rows = parse_nobroker_api_listings(
            listings,
            listing_status=ctx.listing_status,
            city_meta=city_meta,
            base_url=self.base_url,
        )
        result.rows = rows[: ctx.max_results]
        if not result.rows:
            result.errors.append("No listings parsed from NoBroker API response")
        return result


class HousingScraper(PlaywrightSiteScraper):
    source = "housing"
    base_url = "https://housing.com"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city = ctx.city.lower().replace(" ", "-")
        segment = "rent" if ctx.listing_status == ListingStatus.FOR_RENT else "buy"
        return f"{self.base_url}/in/{segment}/{city}"

    def scrape_with_playwright(self, ctx: ScrapeContext) -> SiteScrapeResult:
        result = SiteScrapeResult(source=self.source)
        page_url = self.build_search_url(ctx)
        city_meta = normalize_city(ctx.city)

        if not self.guard.allowed(page_url):
            result.blocked_by_robots = True
            result.errors.append(f"Blocked by robots.txt: {page_url}")
            return result

        assert self.playwright is not None
        fetch = self.playwright.extract_housing_recent_cards(page_url)
        result.fetched = 1 if fetch.status_code else 0

        if fetch.error:
            result.errors.append(fetch.error)
            return result

        cards = fetch.json_data if isinstance(fetch.json_data, list) else []
        rows = parse_housing_recent_cards(
            cards,
            listing_status=ctx.listing_status,
            city_meta=city_meta,
            base_url=self.base_url,
        )
        if not rows and fetch.html:
            rows = parse_housing_recent_cards_from_html(
                fetch.html,
                listing_status=ctx.listing_status,
                city_meta=city_meta,
                base_url=self.base_url,
            )
        result.rows = rows[: ctx.max_results]
        if not result.rows:
            result.errors.append(
                "No listings parsed from Housing page. Site may block automated access intermittently."
            )
        return result


class MagicBricksScraper(BaseSiteScraper):
    source = "magicbricks"
    base_url = "https://www.magicbricks.com"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city_slug = ctx.city.strip().lower().replace(" ", "-")
        if ctx.listing_status == ListingStatus.FOR_RENT:
            return f"{self.base_url}/flats-for-rent-in-{city_slug}-pppfr"
        return f"{self.base_url}/flats-in-{city_slug}-for-sale-pppfs"


class NinetyNineAcresScraper(BaseSiteScraper):
    source = "99acres"
    base_url = "https://www.99acres.com"

    def build_search_url(self, ctx: ScrapeContext) -> str:
        city_slug = ctx.city.lower().replace(" ", "-")
        if ctx.listing_status == ListingStatus.FOR_RENT:
            return f"{self.base_url}/search/property/rent/{city_slug}"
        return f"{self.base_url}/search/property/buy/{city_slug}"
