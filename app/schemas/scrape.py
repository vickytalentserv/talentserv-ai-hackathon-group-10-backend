from typing import Literal

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    sources: list[str] = Field(min_length=1, max_length=4)
    city: str = Field(default="Pune", min_length=2, max_length=100)
    listing_status: Literal["for_sale", "for_rent"] = "for_sale"
    max_results: int = Field(default=20, ge=1, le=50)


class ScrapeSourceResult(BaseModel):
    source: str
    fetched: int
    parsed: int
    blocked_by_robots: bool
    errors: list[str] = Field(default_factory=list)


class ScrapeResponse(BaseModel):
    city: str
    listing_status: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    sources: list[ScrapeSourceResult]
    errors: list[str] = Field(default_factory=list)
