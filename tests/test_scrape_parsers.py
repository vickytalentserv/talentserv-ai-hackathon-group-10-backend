from decimal import Decimal

from app.schemas.property import ListingStatus
from app.services.scraping.parsers import (
    dict_to_property_row,
    normalize_city,
    parse_housing_recent_cards,
    parse_listing_links_from_html,
    parse_nobroker_api_listings,
    parse_price_inr,
)


def test_parse_price_inr_lakh_and_crore() -> None:
    assert parse_price_inr("80 lakh") == Decimal("8000000")
    assert parse_price_inr("1.2 crore") == Decimal("12000000")
    assert parse_price_inr("35000", listing_status=ListingStatus.FOR_RENT) == Decimal("35000")


def test_parse_price_inr_rejects_title_fragments() -> None:
    assert parse_price_inr("2 BHK flat in Santacruz East, Mumbai", listing_status=ListingStatus.FOR_SALE) is None
    assert parse_price_inr("2", listing_status=ListingStatus.FOR_SALE) is None
    assert parse_price_inr("₹2", listing_status=ListingStatus.FOR_SALE) is None


def test_parse_listing_links_from_html_magicbricks_style() -> None:
    html = """
    <div>
      <p>You can explore this 3 BHK flat on rent in Hadapsar Pune.
         You can get this flat at monthly rent of ₹30,000.</p>
      <a href="/propertyDetails/3-BHK-Flat-FOR-Rent-Hadapsar-in-Pune&id=123">View Property</a>
    </div>
    """
    rows = parse_listing_links_from_html(
        html,
        source="magicbricks",
        listing_status=ListingStatus.FOR_RENT,
        city_meta=normalize_city("Pune"),
        base_url="https://www.magicbricks.com",
    )

    assert len(rows) == 1
    assert rows[0].bedrooms == 3
    assert rows[0].price == Decimal("30000")
    assert "Hadapsar" in rows[0].title


def test_parse_listing_links_from_html_magicbricks_sale_lakh_price() -> None:
    html = """
    <div>
      <p>2 BHK flat for sale in Hadapsar Pune. You can buy this flat for 65 Lac.</p>
      <a href="/propertyDetails/2-BHK-Flat-FOR-Sale-Hadapsar-in-Pune&id=456">View Property</a>
    </div>
    """
    rows = parse_listing_links_from_html(
        html,
        source="magicbricks",
        listing_status=ListingStatus.FOR_SALE,
        city_meta=normalize_city("Pune"),
        base_url="https://www.magicbricks.com",
    )

    assert len(rows) == 1
    assert rows[0].bedrooms == 2
    assert rows[0].price == Decimal("6500000")
    assert "Hadapsar" in rows[0].title


def test_dict_to_property_row_builds_valid_record() -> None:
    row = dict_to_property_row(
        {
            "id": "123",
            "title": "2 BHK in Baner",
            "formattedPrice": "95 lakh",
            "url": "https://housing.com/in/sample/123",
            "locality": "Baner",
        },
        source="housing",
        listing_status=ListingStatus.FOR_SALE,
        city_meta=normalize_city("Pune"),
    )

    assert row is not None
    assert row.city == "Pune"
    assert row.state == "MH"
    assert row.price == Decimal("9500000")
    assert row.external_id.startswith("HOUSING-")


def test_parse_nobroker_api_listings() -> None:
    rows = parse_nobroker_api_listings(
        [
            {
                "id": "abc123",
                "propertyTitle": "2 BHK Flat for Rent In Baner",
                "rent": 25000,
                "propertySize": 900,
                "locality": "Baner",
                "detailUrl": "/property/2-bhk-flat-for-rent-in-baner-pune/abc123/detail",
                "latitude": 18.55,
                "longitude": 73.78,
            }
        ],
        listing_status=ListingStatus.FOR_RENT,
        city_meta=normalize_city("Pune"),
        base_url="https://www.nobroker.in",
    )

    assert len(rows) == 1
    assert rows[0].price == Decimal("25000")
    assert rows[0].square_feet == 900
    assert rows[0].source_url.startswith("https://www.nobroker.in/")


def test_parse_housing_recent_cards() -> None:
    rows = parse_housing_recent_cards(
        [
            {
                "href": "https://housing.com/rent/19732996-300-sqft-1-rk-duplex-on-rent-in-bhosari-pune",
                "text": "1 RK Duplex | 1 RK Duplex | Bhosari, Pune | 6,000 | Contact",
            }
        ],
        listing_status=ListingStatus.FOR_RENT,
        city_meta=normalize_city("Pune"),
        base_url="https://housing.com",
    )

    assert len(rows) == 1
    assert rows[0].price == Decimal("6000")
    assert rows[0].bedrooms == 1
    assert "Bhosari" in rows[0].address
