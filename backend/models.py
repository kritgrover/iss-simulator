from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, Text, Float, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, DateTime as SADateTime


class AwareDateTime(TypeDecorator):
    """
    Store datetimes and always return timezone-aware UTC datetimes to Python.
    For naive values provided by callers/DB, assume UTC.
    """
    impl = SADateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        # SQLAlchemy/dialect will handle conversion/storage; keep tzinfo
        return value

    def process_result_value(self, value: Optional[datetime], dialect):
        if value is None:
            return None
        # Some backends (e.g., SQLite) may return naive datetimes; assume UTC
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class Bundle(Base):
    __tablename__ = "bundles"

    bundle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_station: Mapped[str] = mapped_column(String(32), index=True)
    destination_station: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    ttl_hours: Mapped[int] = mapped_column(Integer)
    current_custodian: Mapped[str] = mapped_column(String(32), index=True)
    forwarded_to: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(AwareDateTime(), nullable=True, index=True)
    hops_json: Mapped[str] = mapped_column(Text, default="[]")
    size_bytes: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_bundle_queue", "status", "current_custodian", "priority", "created_at"),
    )


class Transmission(Base):
    __tablename__ = "transmissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(36), index=True)
    from_station: Mapped[str] = mapped_column(String(32), index=True)
    to_station: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    data_rate_bps: Mapped[float] = mapped_column(Float)
    bytes_transmitted: Mapped[float] = mapped_column(Float, default=0.0)
    expected_completion: Mapped[datetime] = mapped_column(AwareDateTime())
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class AckEvent(Base):
    __tablename__ = "ack_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(36), index=True)
    ack_type: Mapped[str] = mapped_column(String(32))
    from_station: Mapped[str] = mapped_column(String(32))
    to_station: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(AwareDateTime(), index=True)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)



