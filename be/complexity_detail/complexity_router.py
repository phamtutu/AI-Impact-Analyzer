from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from .complexity_schema import (
    ComplexityCreate,
    ComplexityListResponse,
    ComplexityResponse,
    ComplexityUpdate,
    ProcessType,
)
from .complexity_service import (
    ComplexityDuplicateError,
    ComplexityNotFoundError,
    create_complexity,
    delete_complexity,
    get_complexity,
    list_complexities,
    update_complexity,
)

router = APIRouter(prefix="/api/v1/complexities", tags=["Complexity"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/options")
def get_options():
    return {
        "process_types": [item.value for item in ProcessType],
        "complexities": ["C1", "C2", "C3", "C4", "C5"],
    }


@router.get("", response_model=ComplexityListResponse)
def find_all(
    db: DbSession,
    process_type: ProcessType | None = None,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
):
    items, total = list_complexities(
        db,
        process_type.value if process_type else None,
        keyword,
    )
    return {"items": items, "total": total}


@router.get("/{complexity_id}", response_model=ComplexityResponse)
def find_one(complexity_id: int, db: DbSession):
    try:
        return get_complexity(db, complexity_id)
    except ComplexityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complexity item không tồn tại") from exc


@router.post("", response_model=ComplexityResponse, status_code=status.HTTP_201_CREATED)
def create(payload: ComplexityCreate, db: DbSession):
    try:
        return create_complexity(db, payload)
    except ComplexityDuplicateError as exc:
        raise HTTPException(status_code=409, detail="Process type và item name đã tồn tại") from exc


@router.put("/{complexity_id}", response_model=ComplexityResponse)
def update(complexity_id: int, payload: ComplexityUpdate, db: DbSession):
    try:
        return update_complexity(db, complexity_id, payload)
    except ComplexityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complexity item không tồn tại") from exc
    except ComplexityDuplicateError as exc:
        raise HTTPException(status_code=409, detail="Process type và item name đã tồn tại") from exc


@router.delete("/{complexity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(complexity_id: int, db: DbSession):
    try:
        delete_complexity(db, complexity_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ComplexityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complexity item không tồn tại") from exc
