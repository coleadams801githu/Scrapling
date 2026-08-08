"""SQLAlchemy ORM models for Resell Radar."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class NotificationPreference(str, enum.Enum):
    email = "email"
    webhook = "webhook"
    push = "push"


class AlertCondition(str, enum.Enum):
    below = "below"
    above = "above"
    any_drop = "any_drop"


class Availability(str, enum.Enum):
    active = "active"
    sold = "sold"
    unavailable = "unavailable"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    notification_preference: Mapped[str] = mapped_column(
        String(20), default=NotificationPreference.email.value, nullable=False
    )
    webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    alerts: Mapped[list[Alert]] = relationship("Alert", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    item_url: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition: Mapped[str] = mapped_column(
        String(20), default=AlertCondition.below.value, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="alerts")
    snapshots: Mapped[list[PriceSnapshot]] = relationship(
        "PriceSnapshot", back_populates="alert", cascade="all, delete-orphan", order_by="PriceSnapshot.scraped_at"
    )

    def __repr__(self) -> str:
        return f"<Alert id={self.id} platform={self.platform!r} condition={self.condition!r} target={self.target_price}>"


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    availability: Mapped[str] = mapped_column(String(20), default=Availability.active.value, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    alert: Mapped[Alert] = relationship("Alert", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<PriceSnapshot id={self.id} price={self.price} {self.currency} availability={self.availability!r}>"
