from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .effort_model import EffortDetail
from .effort_schema import EffortDetailCreate, EffortDetailKey, EffortDetailUpdate


class EffortDetailNotFoundError(Exception):
    pass


class EffortDetailDuplicateError(Exception):
    pass


def _key_conditions(key: EffortDetailKey):
    return and_(
        EffortDetail.dev_type == key.dev_type.value,
        EffortDetail.dev_sub_type == key.dev_sub_type.value,
        EffortDetail.change_type == key.change_type.value,
        EffortDetail.complexity == key.complexity.value,
    )


def list_effort_details(db, page, size, dev_type=None, dev_sub_type=None, change_type=None, complexity=None):
    filters = []
    if dev_type: filters.append(EffortDetail.dev_type == dev_type)
    if dev_sub_type: filters.append(EffortDetail.dev_sub_type == dev_sub_type)
    if change_type: filters.append(EffortDetail.change_type == change_type)
    if complexity: filters.append(EffortDetail.complexity == complexity)

    total = db.scalar(select(func.count()).select_from(EffortDetail).where(*filters)) or 0
    stmt = (
        select(EffortDetail)
        .where(*filters)
        .order_by(EffortDetail.dev_type, EffortDetail.dev_sub_type, EffortDetail.change_type, EffortDetail.complexity)
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(db.scalars(stmt).all()), total


def get_effort_detail(db: Session, key: EffortDetailKey):
    item = db.scalar(select(EffortDetail).where(_key_conditions(key)))
    if item is None: raise EffortDetailNotFoundError
    return item


def create_effort_detail(db: Session, payload: EffortDetailCreate):
    item = EffortDetail(**payload.model_dump(mode="json"))
    db.add(item)
    try:
        db.commit(); db.refresh(item); return item
    except IntegrityError as exc:
        db.rollback(); raise EffortDetailDuplicateError from exc


def update_effort_detail(db: Session, current_key: EffortDetailKey, payload: EffortDetailUpdate):
    item = get_effort_detail(db, current_key)
    for field, value in payload.model_dump(mode="json").items(): setattr(item, field, value)
    try:
        db.commit(); db.refresh(item); return item
    except IntegrityError as exc:
        db.rollback(); raise EffortDetailDuplicateError from exc


def delete_effort_detail(db: Session, key: EffortDetailKey):
    item = get_effort_detail(db, key)
    db.delete(item); db.commit()
