"""Unit tests for the notification dispatcher (no real network/email calls)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from resell_radar.models import Alert, PriceSnapshot, User


def _make_objects(notification_preference="email"):
    user = User(id=1, email="test@example.com", notification_preference=notification_preference)
    alert = Alert(id=1, user_id=1, platform="stockx", item_url="https://stockx.com/item",
                  item_name="Test Sneaker", target_price=150.0, condition="below",
                  is_active=True, check_interval_minutes=15)
    snapshot = PriceSnapshot(id=1, alert_id=1, price=120.0, currency="USD",
                             title="Test Sneaker", availability="active")
    return user, alert, snapshot


class TestNotify:
    def test_routes_to_email(self):
        from resell_radar import notifications

        user, alert, snapshot = _make_objects("email")
        with patch.object(notifications, "_send_email") as mock_email:
            notifications.notify(user, alert, snapshot)
            mock_email.assert_called_once_with(user, alert, snapshot)

    def test_routes_to_webhook(self):
        from resell_radar import notifications

        user, alert, snapshot = _make_objects("webhook")
        with patch.object(notifications, "_send_webhook") as mock_wh:
            notifications.notify(user, alert, snapshot)
            mock_wh.assert_called_once_with(user, alert, snapshot)

    def test_routes_to_push(self):
        from resell_radar import notifications

        user, alert, snapshot = _make_objects("push")
        with patch.object(notifications, "_send_push") as mock_push:
            notifications.notify(user, alert, snapshot)
            mock_push.assert_called_once_with(user, alert, snapshot)

    def test_unknown_preference_logs_warning(self, caplog):
        from resell_radar import notifications
        import logging

        user, alert, snapshot = _make_objects("sms")
        with caplog.at_level(logging.WARNING, logger="resell_radar.notifications"):
            notifications.notify(user, alert, snapshot)
        assert "unknown preference" in caplog.text.lower()


class TestSendEmail:
    def test_skips_when_no_smtp_credentials(self, caplog, monkeypatch):
        from resell_radar import notifications
        import logging

        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

        user, alert, snapshot = _make_objects()
        with caplog.at_level(logging.ERROR, logger="resell_radar.notifications"):
            notifications._send_email(user, alert, snapshot)
        assert "smtp" in caplog.text.lower() or "credentials" in caplog.text.lower()

    def test_sends_email_when_credentials_set(self, monkeypatch):
        from resell_radar import notifications

        monkeypatch.setenv("SMTP_USER", "sender@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("EMAIL_FROM", "sender@example.com")

        user, alert, snapshot = _make_objects()

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp
            notifications._send_email(user, alert, snapshot)
            mock_smtp.sendmail.assert_called_once()


class TestSendWebhook:
    def test_skips_when_no_webhook_url(self, caplog):
        from resell_radar import notifications
        import logging

        user, alert, snapshot = _make_objects("webhook")
        user.webhook_url = None
        with caplog.at_level(logging.ERROR, logger="resell_radar.notifications"):
            notifications._send_webhook(user, alert, snapshot)
        assert "webhook" in caplog.text.lower()

    def test_posts_json_payload(self, monkeypatch):
        from resell_radar import notifications

        user, alert, snapshot = _make_objects("webhook")
        user.webhook_url = "https://hooks.example.com/test"

        posted = {}

        def mock_urlopen(req, timeout=None):
            posted["url"] = req.full_url
            posted["data"] = req.data
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            notifications._send_webhook(user, alert, snapshot)

        import json
        payload = json.loads(posted["data"])
        assert payload["event"] == "price_alert"
        assert payload["price"] == 120.0
        assert payload["platform"] == "stockx"


class TestSendPush:
    def test_skips_when_no_push_token(self, caplog):
        from resell_radar import notifications
        import logging

        user, alert, snapshot = _make_objects("push")
        user.push_token = None
        with caplog.at_level(logging.ERROR, logger="resell_radar.notifications"):
            notifications._send_push(user, alert, snapshot)
        assert "push_token" in caplog.text.lower() or "push" in caplog.text.lower()
