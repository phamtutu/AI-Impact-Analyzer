from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .complexity_model import Complexity
from .complexity_schema import ComplexityCreate, ComplexityUpdate


class ComplexityNotFoundError(Exception):
    pass


class ComplexityDuplicateError(Exception):
    pass


def list_complexities(db: Session, process_type: str | None = None, keyword: str | None = None):
    filters = []
    if process_type:
        filters.append(Complexity.process_type == process_type)
    if keyword:
        filters.append(Complexity.item_name.ilike(f"%{keyword.strip()}%"))

    stmt = (
        select(Complexity)
        .where(*filters)
        .order_by(Complexity.process_type, Complexity.display_order, Complexity.complexity_id)
    )
    items = list(db.scalars(stmt).all())
    total = db.scalar(select(func.count()).select_from(Complexity).where(*filters)) or 0
    return items, total


def get_complexity(db: Session, complexity_id: int) -> Complexity:
    item = db.get(Complexity, complexity_id)
    if item is None:
        raise ComplexityNotFoundError
    return item


def create_complexity(db: Session, payload: ComplexityCreate) -> Complexity:
    item = Complexity(**payload.model_dump(mode="json"))
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError as exc:
        db.rollback()
        raise ComplexityDuplicateError from exc


def update_complexity(db: Session, complexity_id: int, payload: ComplexityUpdate) -> Complexity:
    item = get_complexity(db, complexity_id)
    for field, value in payload.model_dump(mode="json").items():
        setattr(item, field, value)
    try:
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError as exc:
        db.rollback()
        raise ComplexityDuplicateError from exc


def delete_complexity(db: Session, complexity_id: int) -> None:
    item = get_complexity(db, complexity_id)
    db.delete(item)
    db.commit()
