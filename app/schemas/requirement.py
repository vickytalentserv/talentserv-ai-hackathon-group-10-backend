from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class RequirementParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class ParsedRequirement(BaseModel):
    raw_text: str
    intent: Literal["buy", "rent"] | None = None
    bedrooms: int | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    budget_currency: str = "INR"
    locality: str | None = None
    city: str | None = None
    property_type: str | None = None
    parser: str = "rules"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class RequirementParseResponse(BaseModel):
    parsed: ParsedRequirement


class RequirementSaveRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    parsed: ParsedRequirement


class RequirementRead(BaseModel):
    id: int
    user_id: int
    raw_text: str
    intent: str | None
    bedrooms: int | None
    budget_min: Decimal | None
    budget_max: Decimal | None
    budget_currency: str
    locality: str | None
    city: str | None
    property_type: str | None
    parser: str
    confidence: float

    model_config = {"from_attributes": True}
