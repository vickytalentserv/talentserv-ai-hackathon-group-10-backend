from decimal import Decimal

from app.schemas.property import ListingStatus
from app.services.scraping.parsers import dict_to_property_row, normalize_city, parse_price_inr


def test_parse_price_inr_lakh_and_crore() -> None:
    assert parse_price_inr("80 lakh") == Decimal("8000000")
    assert parse_price_inr("1.2 crore") == Decimal("12000000")
    assert parse_price_inr("35000") == Decimal("35000")


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
