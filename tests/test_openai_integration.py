from decimal import Decimal

from app.models import Property
from app.schemas.requirement import ParsedRequirement
from app.services.llm_matching import LLMMatchingService
from app.services.matching import PropertyMatchResult
from app.services.openai_service import OpenAIService, parse_json_content


class FakeOpenAIService(OpenAIService):
    def __init__(self, payload: dict | list | None) -> None:
        self.payload = payload
        self.calls = 0

    def is_enabled(self) -> bool:
        return True

    def chat_json(self, *, system: str, user: str, temperature: float = 0.0) -> dict | list | None:
        self.calls += 1
        return self.payload


def _property(
    *,
    property_id: int,
    city: str = "Mumbai",
    title: str = "2 BHK in Borivali",
    bedrooms: int = 2,
    price: str = "9500000",
) -> Property:
    return Property(
        id=property_id,
        external_id=f"EXT-{property_id}",
        source="housing",
        source_url="https://example.com/listing",
        title=title,
        description="Sample listing",
        address="Borivali West, Mumbai",
        city=city,
        state="MH",
        zip_code="400001",
        price=Decimal(price),
        bedrooms=bedrooms,
        bathrooms=Decimal("2.0"),
        square_feet=900,
        property_type="apartment",
        listing_status="for_sale",
    )


def test_parse_json_content_strips_markdown_fence() -> None:
    payload = parse_json_content('```json\n{"rankings": []}\n```')
    assert payload == {"rankings": []}


def test_llm_matching_reranks_candidates() -> None:
    matches = [
        PropertyMatchResult(property=_property(property_id=1, title="3 BHK in Andheri"), score=0.8, reasons=["City match"]),
        PropertyMatchResult(property=_property(property_id=2, title="2 BHK in Borivali"), score=0.75, reasons=["City match"]),
    ]
    fake_openai = FakeOpenAIService(
        {
            "rankings": [
                {"property_id": 2, "score": 0.95, "reason": "Best match for Borivali search"},
                {"property_id": 1, "score": 0.4, "reason": "Different locality"},
            ]
        }
    )
    service = LLMMatchingService(openai_service=fake_openai)
    parsed = ParsedRequirement(raw_text="2 BHK in Borivali Mumbai", city="Mumbai", locality="Borivali")

    reranked, used = service.rerank(parsed, matches, limit=5)

    assert used is True
    assert reranked[0].property.id == 2
    assert "Borivali" in reranked[0].reasons[0]


def test_llm_matching_falls_back_when_openai_disabled() -> None:
    class DisabledOpenAI(OpenAIService):
        def is_enabled(self) -> bool:
            return False

    service = LLMMatchingService(openai_service=DisabledOpenAI())
    matches = [
        PropertyMatchResult(property=_property(property_id=1), score=0.8, reasons=[]),
        PropertyMatchResult(property=_property(property_id=2), score=0.7, reasons=[]),
    ]
    parsed = ParsedRequirement(raw_text="2 BHK in Mumbai", city="Mumbai")

    reranked, used = service.rerank(parsed, matches, limit=5)

    assert used is False
    assert reranked == matches
