from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from .database_master_schema import (
    DatabaseMasterCreate,
    DatabaseMasterListResponse,
    DatabaseMasterResponse,
    DatabaseMasterUpdate,
)
from .database_master_service import (
    DatabaseMasterDuplicateError,
    DatabaseMasterNotFoundError,
    create_database_master,
    delete_database_master,
    get_database_master,
    list_database_masters,
    update_database_master,
)

router = APIRouter(prefix="/api/v1/database-tables", tags=["Database Master"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/options")
def get_options():
    return {
        "active_options": ["Y", "N"],
    }


@router.get("", response_model=DatabaseMasterListResponse)
def find_all(
    db: DbSession,
    schema_name: Annotated[str | None, Query(max_length=100)] = None,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
    active_yn: Literal["Y", "N"] | None = None,
):
    items, total = list_database_masters(
        db,
        schema_name=schema_name,
        keyword=keyword,
        active_yn=active_yn,
    )
    return {"items": items, "total": total}


@router.get("/{database_id}", response_model=DatabaseMasterResponse)
def find_one(database_id: int, db: DbSession):
    try:
        return get_database_master(db, database_id)
    except DatabaseMasterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Database master không tồn tại") from exc


@router.post("", response_model=DatabaseMasterResponse, status_code=status.HTTP_201_CREATED)
def create(payload: DatabaseMasterCreate, db: DbSession):
    try:
        return create_database_master(db, payload)
    except DatabaseMasterDuplicateError as exc:
        raise HTTPException(
            status_code=409,
            detail="Schema name và table name đã tồn tại",
        ) from exc


@router.put("/{database_id}", response_model=DatabaseMasterResponse)
def update(database_id: int, payload: DatabaseMasterUpdate, db: DbSession):
    try:
        return update_database_master(db, database_id, payload)
    except DatabaseMasterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Database master không tồn tại") from exc
    except DatabaseMasterDuplicateError as exc:
        raise HTTPException(
            status_code=409,
            detail="Schema name và table name đã tồn tại",
        ) from exc


@router.delete("/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(database_id: int, db: DbSession):
    try:
        delete_database_master(db, database_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except DatabaseMasterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Database master không tồn tại") from exc
