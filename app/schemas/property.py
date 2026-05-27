from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ListingStatus(str, Enum):
    FOR_SALE = "for_sale"
    FOR_RENT = "for_rent"


class PropertyType(str, Enum):
    HOUSE = "house"
    CONDO = "condo"
    APARTMENT = "apartment"
    TOWNHOME = "townhome"
    VILLA = "villa"
    FLAT = "flat"


class PropertyCsvRow(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=2)
    zip_code: str = Field(min_length=5, max_length=10)
    price: Decimal = Field(gt=0)
    bedrooms: int = Field(ge=0)
    bathrooms: Decimal = Field(gt=0)
    square_feet: int | None = Field(default=None, gt=0)
    property_type: PropertyType
    listing_status: ListingStatus
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    @field_validator("state")
    @classmethod
    def uppercase_state(cls, value: str) -> str:
        return value.upper()

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        HttpUrl(value)
        return value


class PropertyRead(BaseModel):
    id: int
    external_id: str
    source: str
    source_url: str
    title: str
    description: str | None
    address: str
    city: str
    state: str
    zip_code: str
    price: Decimal
    bedrooms: int
    bathrooms: Decimal
    square_feet: int | None
    property_type: str
    listing_status: str
    latitude: Decimal | None
    longitude: Decimal | None

    model_config = {"from_attributes": True}


class PropertyListResponse(BaseModel):
    items: list[PropertyRead]
    total: int
    page: int
    page_size: int
