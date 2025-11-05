from typing import Optional
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Boolean, Text, Float, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ttl_hours: Mapped[int] = mapped_column(Integer)
    current_custodian: Mapped[str] = mapped_column(String(32), index=True)
    forwarded_to: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    data_rate_bps: Mapped[float] = mapped_column(Float)
    bytes_transmitted: Mapped[float] = mapped_column(Float, default=0.0)
    expected_completion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class AckEvent(Base):
    __tablename__ = "ack_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(36), index=True)
    ack_type: Mapped[str] = mapped_column(String(32))
    from_station: Mapped[str] = mapped_column(String(32))
    to_station: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)



