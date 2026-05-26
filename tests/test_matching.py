from decimal import Decimal

import pytest

from app.models import Property
from app.schemas.requirement import ParsedRequirement
from app.services.matching import MatchingService


@pytest.fixture
def matcher() -> MatchingService:
    return MatchingService()


def _property(
    *,
    property_id: int = 1,
    city: str = "Pune",
    address: str = "101 Baner Road, Baner",
    title: str = "Luxury 2BHK in Baner",
    bedrooms: int = 3,
    price: str = "9500000",
    property_type: str = "apartment",
    listing_status: str = "for_sale",
    description: str | None = "Clubhouse and landscaped gardens",
) -> Property:
    return Property(
        id=property_id,
        external_id=f"EXT-{property_id}",
        source="housing",
        source_url="https://example.com/listing",
        title=title,
        description=description,
        address=address,
        city=city,
        state="MH",
        zip_code="411045",
        price=Decimal(price),
        bedrooms=bedrooms,
        bathrooms=Decimal("2.0"),
        square_feet=1150,
        property_type=property_type,
        listing_status=listing_status,
    )


def test_matches_city_and_bedrooms(matcher: MatchingService) -> None:
    parsed = ParsedRequirement(
        raw_text="3 BHK apartment in Pune",
        intent="buy",
        bedrooms=3,
        city="Pune",
        property_type="apartment",
    )
    properties = [
        _property(property_id=1, bedrooms=3, city="Pune"),
        _property(property_id=2, bedrooms=2, city="Mumbai", title="Andheri Flat"),
    ]

    results = matcher.match(properties, parsed, min_score=0.2)

    assert len(results) >= 1
    assert results[0].property.id == 1
    assert results[0].score >= 0.5
    assert any("City match" in reason for reason in results[0].reasons)
    assert any("Bedrooms match" in reason for reason in results[0].reasons)


def test_matches_rent_intent_and_budget(matcher: MatchingService) -> None:
    parsed = ParsedRequirement(
        raw_text="2 bedroom apartment for rent in Bengaluru under 35000",
        intent="rent",
        bedrooms=2,
        budget_max=Decimal("35000"),
        budget_currency="INR",
        city="Bengaluru",
        property_type="apartment",
    )
    properties = [
        _property(
            property_id=1,
            city="Bengaluru",
            address="1204 ITPL Main Road, Whitefield",
            title="Whitefield IT Park 2BHK",
            bedrooms=2,
            price="32000",
            property_type="apartment",
            listing_status="for_rent",
        ),
        _property(
            property_id=2,
            city="Bengaluru",
            title="Luxury Penthouse",
            bedrooms=2,
            price="9000000",
            property_type="apartment",
            listing_status="for_sale",
        ),
    ]

    results = matcher.match(properties, parsed, min_score=0.2)

    assert results[0].property.id == 1
    assert any("Intent match" in reason for reason in results[0].reasons)
    assert any("Within budget" in reason for reason in results[0].reasons)


def test_matches_locality_keyword(matcher: MatchingService) -> None:
    parsed = ParsedRequirement(
        raw_text="Looking for home near Baner Pune",
        intent="buy",
        city="Pune",
        locality="Baner",
    )
    properties = [
        _property(property_id=1, title="Luxury 2BHK in Baner", address="101 Baner Road, Baner"),
        _property(property_id=2, title="Hinjewadi Flat", address="502 Blue Ridge, Hinjewadi"),
    ]

    results = matcher.match(properties, parsed, min_score=0.2)

    assert results[0].property.id == 1
    assert any("Locality match" in reason for reason in results[0].reasons)


def test_build_candidate_query_uses_exact_bedrooms(matcher: MatchingService) -> None:
    parsed = ParsedRequirement(
        raw_text="2 BHK in Pune",
        bedrooms=2,
        city="Pune",
    )
    compiled = str(
        matcher.build_candidate_query(parsed).compile(compile_kwargs={"literal_binds": True})
    ).lower()

    assert "between" not in compiled
    assert "bedrooms = 2" in compiled or "properties.bedrooms = 2" in compiled


def test_ignores_city_area_locality_filter(matcher: MatchingService) -> None:
    parsed = ParsedRequirement(
        raw_text="I want a 2BHK property in Pune area",
        bedrooms=2,
        city="Pune",
        locality="Pune Area",
    )
    compiled = str(
        matcher.build_candidate_query(parsed).compile(compile_kwargs={"literal_binds": True})
    ).lower()

    assert "pune area" not in compiled


def test_ranks_higher_scores_first(matcher: MatchingService) -> None:
    parsed = ParsedRequirement(
        raw_text="2 BHK apartment in Mumbai",
        bedrooms=2,
        city="Mumbai",
        property_type="apartment",
    )
    properties = [
        _property(
            property_id=1,
            city="Mumbai",
            bedrooms=2,
            property_type="apartment",
            title="Andheri East Metro 2BHK",
            address="1204 Veera Desai Road, Andheri East",
        ),
        _property(
            property_id=2,
            city="Mumbai",
            bedrooms=4,
            property_type="villa",
            title="Worli Luxury Penthouse",
        ),
    ]

    results = matcher.match(properties, parsed, min_score=0.1)

    assert len(results) == 2
    assert results[0].property.id == 1
    assert results[0].score > results[1].score
