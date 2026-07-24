from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database_master_model import DatabaseMaster
from .database_master_schema import DatabaseMasterCreate, DatabaseMasterUpdate


class DatabaseMasterNotFoundError(Exception):
    pass


class DatabaseMasterDuplicateError(Exception):
    pass


def list_database_masters(
    db: Session,
    schema_name: str | None = None,
    keyword: str | None = None,
    active_yn: str | None = None,
):
    filters = []
    if schema_name:
        filters.append(DatabaseMaster.schema_name == schema_name)
    if active_yn:
        filters.append(DatabaseMaster.active_yn == active_yn)
    if keyword:
        normalized = keyword.strip()
        filters.append(
            or_(
                DatabaseMaster.table_name.ilike(f"%{normalized}%"),
                DatabaseMaster.table_description.ilike(f"%{normalized}%"),
                DatabaseMaster.module_name.ilike(f"%{normalized}%"),
            )
        )

    statement = (
        select(DatabaseMaster)
        .where(*filters)
        .order_by(DatabaseMaster.schema_name, DatabaseMaster.table_name)
    )
    items = list(db.scalars(statement).all())
    total = db.scalar(
        select(func.count()).select_from(DatabaseMaster).where(*filters)
    ) or 0
    return items, total


def get_database_master(db: Session, database_id: int) -> DatabaseMaster:
    item = db.get(DatabaseMaster, database_id)
    if item is None:
        raise DatabaseMasterNotFoundError
    return item


def create_database_master(
    db: Session,
    payload: DatabaseMasterCreate,
) -> DatabaseMaster:
    item = DatabaseMaster(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError as exc:
        db.rollback()
        raise DatabaseMasterDuplicateError from exc


def update_database_master(
    db: Session,
    database_id: int,
    payload: DatabaseMasterUpdate,
) -> DatabaseMaster:
    item = get_database_master(db, database_id)
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    try:
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError as exc:
        db.rollback()
        raise DatabaseMasterDuplicateError from exc


def delete_database_master(db: Session, database_id: int) -> None:
    item = get_database_master(db, database_id)
    db.delete(item)
    db.commit()
