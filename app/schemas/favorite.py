from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.property import PropertyRead


class FavoriteCreate(BaseModel):
    listing_key: str = Field(min_length=3, max_length=80)
    property_id: int | None = Field(default=None, ge=1)


class FavoriteRead(BaseModel):
    id: int
    listing_key: str
    property_id: int | None
    property: PropertyRead | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteListResponse(BaseModel):
    items: list[FavoriteRead]
    total: int
