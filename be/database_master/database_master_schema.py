from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatabaseMasterBase(BaseModel):
    schema_name: str = Field(default="effort_db", min_length=1, max_length=100)
    table_name: str = Field(min_length=1, max_length=150)
    columns_info: str | None = Field(default=None, max_length=10000)
    table_description: str | None = Field(default=None, max_length=4000)
    module_name: str | None = Field(default=None, max_length=150)
    active_yn: Literal["Y", "N"] = "Y"

    @field_validator(
        "schema_name",
        "table_name",
        "columns_info",
        "table_description",
        "module_name",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("schema_name", "table_name")
    @classmethod
    def required_text(cls, value):
        if not value:
            raise ValueError("Giá trị không được để trống")
        return value


class DatabaseMasterCreate(DatabaseMasterBase):
    pass


class DatabaseMasterUpdate(DatabaseMasterBase):
    pass


class DatabaseMasterResponse(DatabaseMasterBase):
    model_config = ConfigDict(from_attributes=True)

    database_id: int
    created_at: datetime
    updated_at: datetime


class DatabaseMasterListResponse(BaseModel):
    items: list[DatabaseMasterResponse]
    total: int
