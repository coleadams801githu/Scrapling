"""Alert management — CRUD operations and trigger evaluation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from resell_radar.models import Alert, AlertCondition, PriceSnapshot, User
from resell_radar.scrapers import ScrapedItem, ScraperError, get_scraper_for_url


# --------------------------------------------------------------------------- CRUD


def create_user(db: Session, email: str, **kwargs: Any) -> User:
    """Create or fetch an existing user by email."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, **kwargs)
        db.add(user)
        db.flush()
    return user


def create_alert(
    db: Session,
    user_id: int,
    url: str,
    target_price: float | None = None,
    condition: str = AlertCondition.below.value,
    check_interval_minutes: int = 15,
    item_name: str | None = None,
) -> Alert:
    """Create a new price alert."""
    try:
        scraper = get_scraper_for_url(url)
        platform = scraper.platform
    except ScraperError:
        platform = "unknown"

    alert = Alert(
        user_id=user_id,
        platform=platform,
        item_url=url,
        item_name=item_name,
        target_price=target_price,
        condition=condition,
        check_interval_minutes=check_interval_minutes,
    )
    db.add(alert)
    db.flush()
    return alert


def get_alert(db: Session, alert_id: int) -> Alert | None:
    return db.query(Alert).filter(Alert.id == alert_id).first()


def list_alerts(db: Session, user_id: int) -> list[Alert]:
    return db.query(Alert).filter(Alert.user_id == user_id, Alert.is_active.is_(True)).all()


def update_alert(db: Session, alert_id: int, **fields: Any) -> Alert | None:
    alert = get_alert(db, alert_id)
    if alert is None:
        return None
    for key, value in fields.items():
        if hasattr(alert, key):
            setattr(alert, key, value)
    db.flush()
    return alert


def delete_alert(db: Session, alert_id: int) -> bool:
    alert = get_alert(db, alert_id)
    if alert is None:
        return False
    db.delete(alert)
    db.flush()
    return True


# --------------------------------------------------------------------------- scrape + check


def record_snapshot(db: Session, alert: Alert, item: ScrapedItem) -> PriceSnapshot:
    """Persist a :class:`ScrapedItem` as a :class:`PriceSnapshot`."""
    snapshot = PriceSnapshot(
        alert_id=alert.id,
        price=item.price,
        currency=item.currency,
        title=item.title,
        availability=item.availability,
        scraped_at=item.scraped_at,
    )
    db.add(snapshot)
    if item.title and not alert.item_name:
        alert.item_name = item.title
    alert.last_checked_at = datetime.utcnow()
    db.flush()
    return snapshot


def check_alert(db: Session, alert: Alert) -> tuple[bool, PriceSnapshot | None]:
    """Scrape the item and evaluate whether the alert condition is triggered.

    Returns ``(triggered, snapshot)``.  *snapshot* may be ``None`` on scrape failure.
    """
    from resell_radar.scrapers import ScraperError

    try:
        scraper = get_scraper_for_url(alert.item_url)
        item = scraper.fetch(alert.item_url)
    except ScraperError:
        return False, None

    snapshot = record_snapshot(db, alert, item)

    if item.price is None:
        return False, snapshot

    triggered = _evaluate_condition(alert, item, db)
    return triggered, snapshot


def _evaluate_condition(alert: Alert, item: ScrapedItem, db: Session) -> bool:
    condition = alert.condition
    target = alert.target_price

    if condition == AlertCondition.below.value:
        return target is not None and item.price is not None and item.price <= target

    if condition == AlertCondition.above.value:
        return target is not None and item.price is not None and item.price >= target

    if condition == AlertCondition.any_drop.value:
        previous = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.alert_id == alert.id, PriceSnapshot.price.isnot(None))
            .order_by(PriceSnapshot.scraped_at.desc())
            .offset(1)
            .first()
        )
        if previous and previous.price and item.price:
            return item.price < previous.price

    return False
