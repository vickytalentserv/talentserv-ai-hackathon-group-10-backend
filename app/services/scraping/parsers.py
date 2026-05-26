from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from bs4 import BeautifulSoup

from app.schemas.property import ListingStatus, PropertyCsvRow, PropertyType

CITY_META = {
    "pune": {
        "city": "Pune",
        "state": "MH",
        "pin": "411001",
        "latitude": "18.5204",
        "longitude": "73.8567",
    },
    "mumbai": {
        "city": "Mumbai",
        "state": "MH",
        "pin": "400001",
        "latitude": "19.0760",
        "longitude": "72.8777",
    },
    "bengaluru": {
        "city": "Bengaluru",
        "state": "KA",
        "pin": "560001",
        "latitude": "12.9716",
        "longitude": "77.5946",
    },
    "bangalore": {
        "city": "Bengaluru",
        "state": "KA",
        "pin": "560001",
        "latitude": "12.9716",
        "longitude": "77.5946",
    },
}


def normalize_city(city: str) -> dict[str, str]:
    return CITY_META.get(city.strip().lower(), {"city": city.title(), "state": "MH", "pin": "411001"})


def parse_price_inr(raw: str | int | float | None) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = Decimal(str(raw))
        return value if value > 0 else None

    text = str(raw).lower().replace(",", "").strip()
    if not text:
        return None

    crore = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", text)
    if crore:
        return Decimal(crore.group(1)) * Decimal("10000000")

    lakh = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|l)\b", text)
    if lakh:
        return Decimal(lakh.group(1)) * Decimal("100000")

    digits = re.sub(r"[^\d.]", "", text)
    if not digits:
        return None
    value = Decimal(digits)
    return value if value > 0 else None


def parse_bhk(text: str | None) -> int:
    if not text:
        return 2
    lowered = text.lower()
    match = re.search(r"(\d+)\s*(?:bhk|rk)\b", lowered)
    return int(match.group(1)) if match else 2


def infer_property_type(text: str) -> PropertyType:
    lowered = text.lower()
    if "villa" in lowered:
        return PropertyType.VILLA
    if "flat" in lowered:
        return PropertyType.FLAT
    if "house" in lowered or "bungalow" in lowered:
        return PropertyType.HOUSE
    return PropertyType.APARTMENT


def extract_json_blobs(html: str) -> list[Any]:
    soup = BeautifulSoup(html, "html.parser")
    blobs: list[Any] = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            blobs.append(json.loads(script.string or ""))
        except json.JSONDecodeError:
            continue

    for script in soup.find_all("script"):
        content = script.string or ""
        if "__NEXT_DATA__" in content:
            match = re.search(r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*;?\s*</script>", content, re.S)
            if match:
                try:
                    blobs.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    pass
        if "window.__INITIAL_STATE__" in content:
            match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", content, re.S)
            if match:
                try:
                    blobs.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    pass

    return blobs


def walk_json(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_json(item)


def dict_to_property_row(
    payload: dict[str, Any],
    *,
    source: str,
    listing_status: ListingStatus,
    city_meta: dict[str, str],
) -> PropertyCsvRow | None:
    title = str(payload.get("title") or payload.get("propertyTitle") or payload.get("name") or "").strip()
    if title.lower() in {"view property", "view details"}:
        return None
    if not title:
        return None

    external_id = str(
        payload.get("id")
        or payload.get("propertyId")
        or payload.get("listingId")
        or payload.get("slug")
        or title[:40]
    ).strip()
    if not external_id:
        return None

    locality = str(payload.get("locality") or payload.get("localityName") or payload.get("area") or "").strip()
    address = str(payload.get("address") or payload.get("shortAddress") or locality or title).strip()
    if locality and locality.lower() not in address.lower():
        address = f"{address}, {locality}" if address else locality

    price = parse_price_inr(payload.get("price") or payload.get("rent") or payload.get("formattedPrice"))
    if price is None:
        return None

    bedrooms = parse_bhk(str(payload.get("bedrooms") or payload.get("bhk") or title))
    bathrooms_raw = payload.get("bathrooms") or payload.get("bathroom") or 2
    bathrooms = Decimal(str(bathrooms_raw))

    sqft_raw = (
        payload.get("square_feet")
        or payload.get("area")
        or payload.get("builtUpArea")
        or payload.get("carpetArea")
        or payload.get("propertySize")
    )
    square_feet = None
    if sqft_raw is not None:
        sqft_digits = re.sub(r"[^\d.]", "", str(sqft_raw))
        if sqft_digits:
            square_feet = int(float(sqft_digits))

    detail_url = str(payload.get("detailUrl") or "").strip()
    raw_url = str(payload.get("url") or payload.get("link") or "").strip()
    base = str(payload.get("base_url") or "").strip()

    source_url = ""
    for candidate in (detail_url, raw_url):
        if not candidate or "/static/" in candidate:
            continue
        if candidate.startswith("/"):
            source_url = f"{base.rstrip('/')}{candidate}" if base else ""
        elif candidate.startswith("http"):
            source_url = candidate
        if source_url:
            break

    property_type = infer_property_type(str(payload.get("propertyType") or title))

    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    latitude_value = Decimal(str(latitude)) if latitude not in (None, "") else None
    longitude_value = Decimal(str(longitude)) if longitude not in (None, "") else None

    return PropertyCsvRow(
        external_id=f"{source.upper()}-{external_id}"[:64],
        source=source,
        source_url=source_url or f"https://example.com/{source}/{external_id}",
        title=title[:255],
        description=str(payload.get("description") or payload.get("summary") or "")[:2000] or None,
        address=address[:255],
        city=city_meta["city"],
        state=city_meta["state"],
        zip_code=city_meta["pin"],
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        square_feet=square_feet,
        property_type=property_type,
        listing_status=listing_status,
        latitude=latitude_value,
        longitude=longitude_value,
    )


def parse_nobroker_api_listings(
    listings: list[dict[str, Any]],
    *,
    listing_status: ListingStatus,
    city_meta: dict[str, str],
    base_url: str,
) -> list[PropertyCsvRow]:
    rows: list[PropertyCsvRow] = []
    seen: set[str] = set()

    for listing in listings:
        if not isinstance(listing, dict):
            continue
        payload = dict(listing)
        payload["base_url"] = base_url
        row = dict_to_property_row(
            payload,
            source="nobroker",
            listing_status=listing_status,
            city_meta=city_meta,
        )
        if row and row.external_id not in seen:
            seen.add(row.external_id)
            rows.append(row)

    return rows


def parse_housing_recent_cards(
    cards: list[dict[str, Any]],
    *,
    listing_status: ListingStatus,
    city_meta: dict[str, str],
    base_url: str,
) -> list[PropertyCsvRow]:
    rows: list[PropertyCsvRow] = []
    seen: set[str] = set()

    for card in cards:
        if not isinstance(card, dict):
            continue
        href = str(card.get("href") or "").strip()
        text = str(card.get("text") or "").strip()
        if not href or not text:
            continue

        parts = [part.strip() for part in text.split("|") if part.strip()]
        if len(parts) < 3:
            continue

        title = parts[0]
        locality = parts[2].removesuffix(", Pune").removesuffix(f", {city_meta['city']}")
        price_text = parts[3] if len(parts) > 3 else ""
        if not price_text or price_text.lower() == "contact":
            continue

        id_match = re.search(r"/rent/(\d+)-", href) or re.search(r"/buy/(\d+)-", href)
        external_id = id_match.group(1) if id_match else href.rsplit("/", 1)[-1]

        row = dict_to_property_row(
            {
                "id": external_id,
                "title": title,
                "locality": locality,
                "formattedPrice": price_text,
                "url": href if href.startswith("http") else f"{base_url.rstrip('/')}{href}",
            },
            source="housing",
            listing_status=listing_status,
            city_meta=city_meta,
        )
        if row and row.external_id not in seen:
            seen.add(row.external_id)
            rows.append(row)

    return rows


def parse_cards_from_html(
    html: str,
    *,
    source: str,
    listing_status: ListingStatus,
    city_meta: dict[str, str],
    base_url: str,
) -> list[PropertyCsvRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PropertyCsvRow] = []

    for card in soup.select("[data-listing-id], [data-property-id], article, .property-card, .listing-card"):
        listing_id = card.get("data-listing-id") or card.get("data-property-id")
        title_el = card.select_one("h2, h3, .title, .property-title, a")
        price_el = card.select_one("[data-price], .price, .rent, .amount")
        link_el = card.select_one("a[href]")
        if not title_el:
            continue

        title = title_el.get_text(" ", strip=True)
        price_text = price_el.get_text(" ", strip=True) if price_el else title
        href = link_el.get("href") if link_el else ""
        if href and href.startswith("/"):
            href = base_url.rstrip("/") + href

        row = dict_to_property_row(
            {
                "id": listing_id or title,
                "title": title,
                "formattedPrice": price_text,
                "url": href,
            },
            source=source,
            listing_status=listing_status,
            city_meta=city_meta,
        )
        if row:
            rows.append(row)

    rows.extend(
        parse_listing_links_from_html(
            html,
            source=source,
            listing_status=listing_status,
            city_meta=city_meta,
            base_url=base_url,
        )
    )
    return rows


def parse_housing_recent_cards_from_html(
    html: str,
    *,
    listing_status: ListingStatus,
    city_meta: dict[str, str],
    base_url: str,
) -> list[PropertyCsvRow]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[dict[str, str]] = []
    for anchor in soup.select('a[class*="recentlyAddedCardStyle"]'):
        href = str(anchor.get("href") or "").strip()
        text = anchor.get_text("|", strip=True)
        if href and text:
            cards.append({"href": href, "text": text})
    return parse_housing_recent_cards(
        cards,
        listing_status=listing_status,
        city_meta=city_meta,
        base_url=base_url,
    )


def parse_listing_links_from_html(
    html: str,
    *,
    source: str,
    listing_status: ListingStatus,
    city_meta: dict[str, str],
    base_url: str,
) -> list[PropertyCsvRow]:
    """Parse listing cards linked via property detail URLs (MagicBricks-style markup)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PropertyCsvRow] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="propertyDetails"], a[href*="/property/"]'):
        href = str(link.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        if href.startswith("/"):
            href = base_url.rstrip("/") + href

        id_match = re.search(r"[?&]id=([^&]+)", href)
        external_id = id_match.group(1) if id_match else href.rsplit("/", 1)[-1]

        title = None
        price_text = None
        container = link
        for _ in range(8):
            if container is None:
                break
            text = container.get_text(" ", strip=True)
            if not title:
                title_match = re.search(
                    r"\d+\s*BHK[^.₹]{0,120}(?:in|at|on)\s+[^.₹]{3,80}",
                    text,
                    re.I,
                )
                if title_match:
                    title = title_match.group(0).strip()
            price_match = re.search(r"₹[\d,]+(?:\s*/\s*month)?", text)
            if price_match:
                price_text = price_match.group(0)
                if title:
                    break
            container = container.parent

        if not title:
            slug_match = re.search(r"/propertyDetails/([^?&]+)", href)
            if slug_match:
                title = slug_match.group(1).replace("-", " ")[:255]
            else:
                continue

        if not price_text:
            continue

        row = dict_to_property_row(
            {
                "id": external_id,
                "title": title,
                "formattedPrice": price_text,
                "url": href,
            },
            source=source,
            listing_status=listing_status,
            city_meta=city_meta,
        )
        if row and row.external_id not in seen:
            seen.add(row.external_id)
            rows.append(row)

    return rows
