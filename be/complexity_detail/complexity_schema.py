from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessType(str, Enum):
    ONLINE = "Online"
    BATCH = "Batch"


class ComplexityBase(BaseModel):
    process_type: ProcessType
    item_name: str = Field(min_length=1, max_length=255)
    c1_description: str | None = Field(default=None, max_length=4000)
    c2_description: str | None = Field(default=None, max_length=4000)
    c3_description: str | None = Field(default=None, max_length=4000)
    c4_description: str | None = Field(default=None, max_length=4000)
    c5_description: str | None = Field(default=None, max_length=4000)
    display_order: int = Field(default=0, ge=0)

    @field_validator(
        "item_name", "c1_description", "c2_description",
        "c3_description", "c4_description", "c5_description",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, value):
        if not value:
            raise ValueError("item_name không được để trống")
        return value


class ComplexityCreate(ComplexityBase):
    pass


class ComplexityUpdate(ComplexityBase):
    pass


class ComplexityResponse(ComplexityBase):
    model_config = ConfigDict(from_attributes=True)

    complexity_id: int
    created_at: datetime
    updated_at: datetime


class ComplexityListResponse(BaseModel):
    items: list[ComplexityResponse]
    total: int
