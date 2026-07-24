from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from .effort_schema import (
    ChangeType, Complexity, DevSubType, DevType,
    EffortDetailCreate, EffortDetailKey, EffortDetailListResponse,
    EffortDetailResponse, EffortDetailUpdate,
)
from .effort_service import (
    EffortDetailDuplicateError, EffortDetailNotFoundError,
    create_effort_detail, delete_effort_detail, get_effort_detail,
    list_effort_details, update_effort_detail,
)

router = APIRouter(prefix="/api/v1/effort-details", tags=["Effort Detail"])
DbSession = Annotated[Session, Depends(get_db)]


def build_key(dev_type: DevType, dev_sub_type: DevSubType, change_type: ChangeType, complexity: Complexity):
    return EffortDetailKey(
        dev_type=dev_type,
        dev_sub_type=dev_sub_type,
        change_type=change_type,
        complexity=complexity,
    )


@router.get("/options")
def get_options():
    return {
        "dev_type": [item.value for item in DevType],
        "dev_sub_type": [item.value for item in DevSubType],
        "change_type": [item.value for item in ChangeType],
        "complexity": [item.value for item in Complexity],
    }


@router.get("", response_model=EffortDetailListResponse)
def find_all(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    dev_type: DevType | None = None,
    dev_sub_type: DevSubType | None = None,
    change_type: ChangeType | None = None,
    complexity: Complexity | None = None,
):
    items, total = list_effort_details(
        db, page, size,
        dev_type.value if dev_type else None,
        dev_sub_type.value if dev_sub_type else None,
        change_type.value if change_type else None,
        complexity.value if complexity else None,
    )
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/detail", response_model=EffortDetailResponse)
def find_one(db: DbSession, key: Annotated[EffortDetailKey, Depends(build_key)]):
    try: return get_effort_detail(db, key)
    except EffortDetailNotFoundError as exc: raise HTTPException(404, "Effort detail không tồn tại") from exc


@router.post("", response_model=EffortDetailResponse, status_code=201)
def create(payload: EffortDetailCreate, db: DbSession):
    try: return create_effort_detail(db, payload)
    except EffortDetailDuplicateError as exc: raise HTTPException(409, "Tổ hợp 4 trường khóa đã tồn tại") from exc


@router.put("/detail", response_model=EffortDetailResponse)
def update(payload: EffortDetailUpdate, db: DbSession, current_key: Annotated[EffortDetailKey, Depends(build_key)]):
    try: return update_effort_detail(db, current_key, payload)
    except EffortDetailNotFoundError as exc: raise HTTPException(404, "Effort detail không tồn tại") from exc
    except EffortDetailDuplicateError as exc: raise HTTPException(409, "Tổ hợp khóa mới đã tồn tại") from exc


@router.delete("/detail", status_code=status.HTTP_204_NO_CONTENT)
def delete(db: DbSession, key: Annotated[EffortDetailKey, Depends(build_key)]):
    try:
        delete_effort_detail(db, key)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except EffortDetailNotFoundError as exc: raise HTTPException(404, "Effort detail không tồn tại") from exc
