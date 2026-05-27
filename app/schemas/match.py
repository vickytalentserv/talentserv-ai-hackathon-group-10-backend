from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.property import PropertyRead
from app.schemas.requirement import ParsedRequirement


class PropertyMatchRequest(BaseModel):
    text: str | None = Field(default=None, min_length=3, max_length=2000)
    requirement_id: int | None = Field(default=None, ge=1)
    min_score: float = Field(default=0.15, ge=0.0, le=1.0)
    limit: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def validate_input_source(self) -> PropertyMatchRequest:
        has_text = self.text is not None and self.text.strip() != ""
        has_requirement = self.requirement_id is not None
        if has_text == has_requirement:
            raise ValueError("Provide exactly one of text or requirement_id")
        return self


class PropertyMatchItem(BaseModel):
    property: PropertyRead
    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class PropertyMatchResponse(BaseModel):
    items: list[PropertyMatchItem]
    parsed: ParsedRequirement
    total: int
    source: str = "database"
    relaxed: bool = False
