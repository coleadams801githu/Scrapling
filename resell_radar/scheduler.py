"""APScheduler-based polling scheduler for Resell Radar alerts."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from resell_radar.alerts import check_alert
from resell_radar.database import get_db
from resell_radar.models import Alert
from resell_radar.notifications import notify

logger = logging.getLogger(__name__)


def _process_alert(alert_id: int) -> None:
    """Run a single alert check in its own DB session."""
    with get_db() as db:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert is None or not alert.is_active:
            return
        triggered, snapshot = check_alert(db, alert)
        if triggered and snapshot:
            user = alert.user
            logger.info(
                "[scheduler] alert %d triggered — price=%s %s",
                alert_id,
                snapshot.price,
                snapshot.currency,
            )
            try:
                notify(user, alert, snapshot)
            except Exception as exc:
                logger.error("[scheduler] notification failed for alert %d: %s", alert_id, exc)


def run_scheduler(interval_minutes: int = 15) -> None:
    """Start the blocking APScheduler loop.

    Each active alert uses its own ``check_interval_minutes`` setting;
    *interval_minutes* is the minimum polling granularity for scheduling.
    """
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError as exc:
        raise ImportError(
            "APScheduler is required to run the scheduler. "
            "Install it with: pip install apscheduler"
        ) from exc

    scheduler = BlockingScheduler(timezone="UTC")

    # Seed jobs from DB at startup, then refresh every cycle
    def _refresh_jobs() -> None:
        with get_db() as db:
            alerts: list[Alert] = db.query(Alert).filter(Alert.is_active.is_(True)).all()
            active_job_ids = {f"alert_{a.id}" for a in alerts}
            existing_job_ids = {job.id for job in scheduler.get_jobs()}

            # Remove jobs for alerts that are no longer active or have been deleted
            for job_id in existing_job_ids:
                if job_id.startswith("alert_") and job_id not in active_job_ids:
                    scheduler.remove_job(job_id)
                    logger.info("[scheduler] removed job %s (alert inactive/deleted)", job_id)

            for alert in alerts:
                job_id = f"alert_{alert.id}"
                minutes = max(alert.check_interval_minutes, 1)
                if job_id not in existing_job_ids:
                    scheduler.add_job(
                        _process_alert,
                        trigger="interval",
                        minutes=minutes,
                        id=job_id,
                        args=[alert.id],
                        next_run_time=datetime.now(tz=timezone.utc),
                        replace_existing=True,
                    )
                    logger.info("[scheduler] registered alert %d every %d min", alert.id, minutes)

    scheduler.add_job(_refresh_jobs, trigger="interval", minutes=interval_minutes, id="refresh_jobs")
    _refresh_jobs()

    logger.info("[scheduler] starting — press Ctrl+C to stop")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[scheduler] stopped")
