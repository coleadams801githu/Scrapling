"""Unit tests for alert CRUD and condition evaluation (no network I/O)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from resell_radar.scrapers.base import ScrapedItem


# --------------------------------------------------------------------------- helpers


def _make_db():
    """Return a minimal in-memory SQLite session via SQLAlchemy."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from resell_radar.database import init_db
    from resell_radar.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return Session()


# --------------------------------------------------------------------------- CRUD


class TestUserCRUD:
    def test_create_user(self):
        from resell_radar.alerts import create_user

        db = _make_db()
        user = create_user(db, email="test@example.com", notification_preference="email")
        db.commit()
        assert user.id is not None
        assert user.email == "test@example.com"

    def test_create_user_idempotent(self):
        """Calling create_user twice with the same email returns the same record."""
        from resell_radar.alerts import create_user

        db = _make_db()
        u1 = create_user(db, email="dup@example.com")
        db.commit()
        u2 = create_user(db, email="dup@example.com")
        db.commit()
        assert u1.id == u2.id


class TestAlertCRUD:
    def _user_and_db(self):
        from resell_radar.alerts import create_user

        db = _make_db()
        user = create_user(db, email="alerts@example.com")
        db.commit()
        return db, user

    def test_create_alert(self):
        from resell_radar.alerts import create_alert

        db, user = self._user_and_db()
        alert = create_alert(
            db,
            user_id=user.id,
            url="https://stockx.com/nike-air-max-1",
            target_price=150.0,
            condition="below",
        )
        db.commit()
        assert alert.id is not None
        assert alert.platform == "stockx"
        assert alert.target_price == 150.0
        assert alert.is_active is True

    def test_create_alert_unknown_platform(self):
        from resell_radar.alerts import create_alert

        db, user = self._user_and_db()
        alert = create_alert(
            db,
            user_id=user.id,
            url="https://unknown-market.com/item/1",
        )
        db.commit()
        assert alert.platform == "unknown"

    def test_list_alerts_only_active(self):
        from resell_radar.alerts import create_alert, list_alerts

        db, user = self._user_and_db()
        a1 = create_alert(db, user_id=user.id, url="https://stockx.com/item-1")
        a2 = create_alert(db, user_id=user.id, url="https://goat.com/sneakers/item-2")
        db.commit()
        a2.is_active = False
        db.commit()
        alerts = list_alerts(db, user.id)
        assert len(alerts) == 1
        assert alerts[0].id == a1.id

    def test_update_alert(self):
        from resell_radar.alerts import create_alert, update_alert

        db, user = self._user_and_db()
        alert = create_alert(db, user_id=user.id, url="https://grailed.com/listings/111")
        db.commit()
        updated = update_alert(db, alert.id, target_price=200.0, condition="above")
        db.commit()
        assert updated.target_price == 200.0
        assert updated.condition == "above"

    def test_update_alert_not_found_returns_none(self):
        from resell_radar.alerts import update_alert

        db = _make_db()
        result = update_alert(db, 999, target_price=50.0)
        assert result is None

    def test_delete_alert(self):
        from resell_radar.alerts import create_alert, delete_alert, get_alert

        db, user = self._user_and_db()
        alert = create_alert(db, user_id=user.id, url="https://ebay.com/itm/9999")
        db.commit()
        assert delete_alert(db, alert.id) is True
        db.commit()
        assert get_alert(db, alert.id) is None

    def test_delete_alert_not_found_returns_false(self):
        from resell_radar.alerts import delete_alert

        db = _make_db()
        assert delete_alert(db, 9999) is False


# --------------------------------------------------------------------------- condition evaluation


class TestConditionEvaluation:
    """Test _evaluate_condition without any network calls."""

    def _setup(self, condition, target_price=100.0):
        from resell_radar.alerts import create_alert, create_user

        db = _make_db()
        user = create_user(db, email=f"cond_{condition}@example.com")
        db.commit()
        alert = create_alert(
            db,
            user_id=user.id,
            url="https://stockx.com/some-sneaker",
            target_price=target_price,
            condition=condition,
        )
        db.commit()
        return db, alert

    def test_below_triggered(self):
        from resell_radar.alerts import _evaluate_condition

        db, alert = self._setup("below", target_price=100.0)
        item = ScrapedItem(price=90.0)
        assert _evaluate_condition(alert, item, db) is True

    def test_below_not_triggered(self):
        from resell_radar.alerts import _evaluate_condition

        db, alert = self._setup("below", target_price=100.0)
        item = ScrapedItem(price=110.0)
        assert _evaluate_condition(alert, item, db) is False

    def test_below_at_threshold(self):
        from resell_radar.alerts import _evaluate_condition

        db, alert = self._setup("below", target_price=100.0)
        item = ScrapedItem(price=100.0)
        assert _evaluate_condition(alert, item, db) is True  # price <= target

    def test_above_triggered(self):
        from resell_radar.alerts import _evaluate_condition

        db, alert = self._setup("above", target_price=100.0)
        item = ScrapedItem(price=120.0)
        assert _evaluate_condition(alert, item, db) is True

    def test_above_not_triggered(self):
        from resell_radar.alerts import _evaluate_condition

        db, alert = self._setup("above", target_price=100.0)
        item = ScrapedItem(price=80.0)
        assert _evaluate_condition(alert, item, db) is False

    def test_any_drop_no_previous_snapshot(self):
        """Without a prior snapshot there's nothing to compare against."""
        from resell_radar.alerts import _evaluate_condition

        db, alert = self._setup("any_drop")
        item = ScrapedItem(price=80.0)
        assert _evaluate_condition(alert, item, db) is False

    def test_any_drop_with_drop(self):
        from resell_radar.alerts import _evaluate_condition, record_snapshot

        db, alert = self._setup("any_drop")
        # Record the old (higher-priced) snapshot first
        old_item = ScrapedItem(price=120.0)
        record_snapshot(db, alert, old_item)
        db.commit()
        # Record the new (lower-priced) snapshot — _evaluate_condition uses offset(1)
        # to look past the most-recent row, so the current snapshot must already exist.
        new_item = ScrapedItem(price=90.0)
        record_snapshot(db, alert, new_item)
        db.commit()
        assert _evaluate_condition(alert, new_item, db) is True

    def test_any_drop_no_drop(self):
        from resell_radar.alerts import _evaluate_condition, record_snapshot

        db, alert = self._setup("any_drop")
        old_item = ScrapedItem(price=80.0)
        record_snapshot(db, alert, old_item)
        db.commit()
        new_item = ScrapedItem(price=90.0)
        record_snapshot(db, alert, new_item)
        db.commit()
        assert _evaluate_condition(alert, new_item, db) is False


# --------------------------------------------------------------------------- check_alert


class TestCheckAlert:
    def _setup(self):
        from resell_radar.alerts import create_alert, create_user

        db = _make_db()
        user = create_user(db, email="check@example.com")
        db.commit()
        alert = create_alert(
            db, user_id=user.id, url="https://stockx.com/item", target_price=100.0, condition="below"
        )
        db.commit()
        return db, alert

    def test_check_alert_records_snapshot(self):
        from resell_radar.alerts import check_alert

        db, alert = self._setup()

        with patch("resell_radar.alerts.get_scraper_for_url") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.fetch.return_value = ScrapedItem(price=80.0, currency="USD")
            mock_get.return_value = mock_scraper

            triggered, snapshot = check_alert(db, alert)

        assert snapshot is not None
        assert snapshot.price == 80.0
        assert triggered is True

    def test_check_alert_scrape_failure_returns_none(self):
        from resell_radar.alerts import check_alert
        from resell_radar.scrapers.base import ScraperError

        db, alert = self._setup()

        with patch("resell_radar.alerts.get_scraper_for_url") as mock_get:
            mock_scraper = MagicMock()
            mock_scraper.fetch.side_effect = ScraperError("network error")
            mock_get.return_value = mock_scraper

            triggered, snapshot = check_alert(db, alert)

        assert snapshot is None
        assert triggered is False
