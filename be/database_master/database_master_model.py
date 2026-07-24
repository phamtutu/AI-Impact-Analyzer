from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class DatabaseMaster(Base):
    __tablename__ = "tb_database_master"
    __table_args__ = (
        UniqueConstraint(
            "schema_name",
            "table_name",
            name="uk_tb_database_master_schema_table",
        ),
    )

    database_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    schema_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="effort_db",
    )
    table_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    columns_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    table_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    module_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    active_yn: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        default="Y",
    )
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
