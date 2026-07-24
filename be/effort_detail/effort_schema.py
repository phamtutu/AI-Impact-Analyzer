from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DevType(str, Enum):
    WEB = "WEB"
    BATCH = "BATCH"
    INTERFACE = "INTERFACE"
    REPORT = "REPORT"


class DevSubType(str, Enum):
    ONLINE_WEB = "Online_Web"
    BATCH_JOB = "Batch_Job"
    EXTERNAL_INTERFACE = "External_Interface"
    REPORT = "Report"


class ChangeType(str, Enum):
    NEW = "NEW"
    CHANGE = "CHANGE"


class Complexity(str, Enum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"


EffortValue = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class EffortDetailKey(BaseModel):
    dev_type: DevType
    dev_sub_type: DevSubType
    change_type: ChangeType
    complexity: Complexity


class EffortDetailCreate(EffortDetailKey):
    standard_effort: EffortValue


class EffortDetailUpdate(EffortDetailCreate):
    pass


class EffortDetailResponse(EffortDetailCreate):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime


class EffortDetailListResponse(BaseModel):
    items: list[EffortDetailResponse]
    total: int
    page: int
    size: int
