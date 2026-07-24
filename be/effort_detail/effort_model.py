from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class EffortDetail(Base):
    __tablename__ = "tb_effort_detail"

    dev_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    dev_sub_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    change_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    complexity: Mapped[str] = mapped_column(String(10), primary_key=True)
    standard_effort: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    )
