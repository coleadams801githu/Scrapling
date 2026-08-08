"""Notification dispatcher — email, webhook, and push backends."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from resell_radar.models import Alert, PriceSnapshot, User

logger = logging.getLogger(__name__)


def notify(user: User, alert: Alert, snapshot: PriceSnapshot) -> None:
    """Fire the user's configured notification backend."""
    pref = user.notification_preference
    if pref == "email":
        _send_email(user, alert, snapshot)
    elif pref == "webhook":
        _send_webhook(user, alert, snapshot)
    elif pref == "push":
        _send_push(user, alert, snapshot)
    else:
        logger.warning("[notify] unknown preference %r for user %s", pref, user.id)


# --------------------------------------------------------------------------- email


def _send_email(user: User, alert: Alert, snapshot: PriceSnapshot) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("EMAIL_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        logger.error("[notify] SMTP credentials not set; skipping email to %s", user.email)
        return

    subject = f"[Resell Radar] Price alert for {alert.item_name or alert.item_url}"
    body = (
        f"Your price alert has been triggered!\n\n"
        f"Item: {alert.item_name or alert.item_url}\n"
        f"Platform: {alert.platform}\n"
        f"Current price: {snapshot.currency} {snapshot.price}\n"
        f"Your target: {alert.target_price} ({alert.condition})\n"
        f"Availability: {snapshot.availability}\n\n"
        f"View listing: {alert.item_url}\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = user.email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [user.email], msg.as_string())
        logger.info("[notify] email sent to %s", user.email)
    except smtplib.SMTPException as exc:
        logger.error("[notify] failed to send email: %s", exc)


# --------------------------------------------------------------------------- webhook


def _send_webhook(user: User, alert: Alert, snapshot: PriceSnapshot) -> None:
    import json
    import urllib.request

    webhook_url = user.webhook_url
    if not webhook_url:
        logger.error("[notify] no webhook URL configured for user %s", user.id)
        return

    payload = json.dumps(
        {
            "event": "price_alert",
            "alert_id": alert.id,
            "item_name": alert.item_name,
            "item_url": alert.item_url,
            "platform": alert.platform,
            "price": snapshot.price,
            "currency": snapshot.currency,
            "availability": snapshot.availability,
            "target_price": alert.target_price,
            "condition": alert.condition,
        }
    ).encode()

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("[notify] webhook delivered; status %s", resp.status)
    except Exception as exc:
        logger.error("[notify] webhook delivery failed: %s", exc)


# --------------------------------------------------------------------------- push (Ntfy)


def _send_push(user: User, alert: Alert, snapshot: PriceSnapshot) -> None:
    import urllib.request

    push_url = os.environ.get("NTFY_URL", "https://ntfy.sh")
    topic = user.push_token
    if not topic:
        logger.error("[notify] no push_token (ntfy topic) set for user %s", user.id)
        return

    message = (
        f"{alert.item_name or alert.platform}: "
        f"{snapshot.currency} {snapshot.price} "
        f"({alert.condition} {alert.target_price})"
    ).encode()

    req = urllib.request.Request(
        f"{push_url}/{topic}",
        data=message,
        headers={"Title": "Resell Radar Alert", "Priority": "high"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            logger.info("[notify] push sent to topic %s", topic)
    except Exception as exc:
        logger.error("[notify] push delivery failed: %s", exc)
