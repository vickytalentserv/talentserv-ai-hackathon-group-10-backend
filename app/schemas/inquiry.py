from datetime import datetime

from pydantic import BaseModel, Field


class InquiryCreate(BaseModel):
    listing_key: str = Field(min_length=3, max_length=80)
    property_id: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    message: str = Field(min_length=10, max_length=2000)


class InquiryRead(BaseModel):
    id: int
    listing_key: str
    property_id: int | None
    name: str
    email: str
    phone: str | None
    message: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
