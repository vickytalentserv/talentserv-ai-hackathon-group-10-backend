import pytest

from app.services.parser import ParserService


@pytest.fixture
def parser() -> ParserService:
    return ParserService()


def test_parses_lakh_budget_for_rent(parser: ParserService) -> None:
    result = parser.parse("2 BHK flat for rent in Hinjewadi, Pune under 50 lakh")

    assert result.intent == "rent"
    assert result.bedrooms == 2
    assert result.budget_max == pytest.approx(5_000_000)
    assert result.budget_currency == "INR"
    assert result.city == "Pune"
    assert result.locality == "Hinjewadi"
    assert result.property_type == "apartment"


def test_parses_bhk_buy_intent(parser: ParserService) -> None:
    result = parser.parse("Want to buy 3 BHK house in Mumbai between 60 lakh and 90 lakh")

    assert result.intent == "buy"
    assert result.bedrooms == 3
    assert result.budget_min == pytest.approx(6_000_000)
    assert result.budget_max == pytest.approx(9_000_000)
    assert result.budget_currency == "INR"
    assert result.city == "Mumbai"
    assert result.property_type == "house"


def test_parses_bedroom_shorthand(parser: ParserService) -> None:
    result = parser.parse("Looking for 2 bedroom apartment to rent in Bengaluru near Koramangala")

    assert result.intent == "rent"
    assert result.bedrooms == 2
    assert result.city == "Bengaluru"
    assert result.locality == "Koramangala"


def test_parses_crore_budget(parser: ParserService) -> None:
    result = parser.parse("Buy 4 BHK villa in Mumbai under 1.2 crore")

    assert result.intent == "buy"
    assert result.bedrooms == 4
    assert result.budget_max == pytest.approx(12_000_000)
    assert result.budget_currency == "INR"
    assert result.city == "Mumbai"
    assert result.property_type == "house"


def test_parses_locality_and_usd_budget(parser: ParserService) -> None:
    result = parser.parse("2bhk apartment for rent in Baner Pune max $500000")

    assert result.intent == "rent"
    assert result.bedrooms == 2
    assert result.budget_max == pytest.approx(500_000)
    assert result.budget_currency == "USD"
    assert result.locality == "Baner"
    assert result.city == "Pune"


def test_parses_k_suffix_budget(parser: ParserService) -> None:
    result = parser.parse("Rent 1 BHK in Whitefield Bangalore under 500k")

    assert result.intent == "rent"
    assert result.bedrooms == 1
    assert result.budget_max == pytest.approx(500_000)
    assert result.budget_currency == "INR"
    assert result.locality == "Whitefield"
    assert result.city == "Bengaluru"


def test_parses_borivali_rent_budget_in_inr(parser: ParserService) -> None:
    parser_without_llm = ParserService(openai_service=type("Off", (), {"is_enabled": lambda self: False})())
    result = parser_without_llm.parse("2 BHK for rent in Borivali Mumbai under 40k")

    assert result.intent == "rent"
    assert result.bedrooms == 2
    assert result.city == "Mumbai"
    assert result.locality == "Borivali"
    assert result.budget_max == pytest.approx(40_000)
    assert result.budget_currency == "INR"


def test_parses_city_area_without_locality(parser: ParserService) -> None:
    result = parser.parse("I want a 2BHK property in Pune area")

    assert result.bedrooms == 2
    assert result.city == "Pune"
    assert result.locality is None
