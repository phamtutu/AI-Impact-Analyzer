from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Complexity(Base):
    __tablename__ = "tb_complexity"

    complexity_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    process_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    c1_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    c2_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    c3_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    c4_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    c5_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    )
