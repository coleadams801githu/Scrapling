"""Resell Radar CLI — radar add-alert / list-alerts / run / check."""
from __future__ import annotations

import sys

import click

from resell_radar.database import get_db, init_db


@click.group()
@click.option("--db-url", envvar="DATABASE_URL", default=None, help="SQLAlchemy database URL.")
@click.pass_context
def main(ctx: click.Context, db_url: str | None) -> None:
    """Resell Radar — per-user price alert tracker for resale platforms."""
    ctx.ensure_object(dict)
    init_db(db_url)


@main.command("add-alert")
@click.argument("url")
@click.option("--email", required=True, help="User email address.")
@click.option("--price", "target_price", type=float, default=None, help="Target price threshold.")
@click.option(
    "--condition",
    type=click.Choice(["below", "above", "any_drop"]),
    default="below",
    show_default=True,
    help="Alert condition.",
)
@click.option("--interval", "check_interval_minutes", type=int, default=15, show_default=True, help="Check interval in minutes.")
@click.option("--name", "item_name", default=None, help="Optional item name label.")
def add_alert(
    url: str,
    email: str,
    target_price: float | None,
    condition: str,
    check_interval_minutes: int,
    item_name: str | None,
) -> None:
    """Add a price alert for URL."""
    from resell_radar.alerts import create_alert, create_user

    with get_db() as db:
        user = create_user(db, email=email)
        alert = create_alert(
            db,
            user_id=user.id,
            url=url,
            target_price=target_price,
            condition=condition,
            check_interval_minutes=check_interval_minutes,
            item_name=item_name,
        )
        click.echo(
            f"✓ Alert {alert.id} created for {email}: {alert.platform} "
            f"({alert.condition} {alert.target_price})"
        )


@main.command("list-alerts")
@click.option("--email", required=True, help="User email address.")
def list_alerts(email: str) -> None:
    """List active alerts for a user."""
    from resell_radar.models import User

    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            click.echo(f"No user found with email {email!r}.", err=True)
            sys.exit(1)
        if not user.alerts:
            click.echo("No active alerts.")
            return
        for a in user.alerts:
            if a.is_active:
                click.echo(
                    f"  [{a.id}] {a.platform} | {a.condition} {a.target_price} | "
                    f"{a.item_name or a.item_url[:60]}"
                )


@main.command("check")
@click.argument("alert_id", type=int)
def check(alert_id: int) -> None:
    """Run a one-shot check for ALERT_ID and print the result."""
    from resell_radar.alerts import check_alert
    from resell_radar.models import Alert

    with get_db() as db:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            click.echo(f"Alert {alert_id} not found.", err=True)
            sys.exit(1)
        triggered, snapshot = check_alert(db, alert)
        if snapshot:
            click.echo(
                f"Price: {snapshot.currency} {snapshot.price} | "
                f"Availability: {snapshot.availability} | "
                f"Triggered: {'YES 🔔' if triggered else 'no'}"
            )
        else:
            click.echo("Could not fetch price (scrape failed).")


@main.command("run")
@click.option("--interval", type=int, default=15, show_default=True, help="Scheduler refresh interval in minutes.")
def run(interval: int) -> None:
    """Start the background scheduler loop."""
    from resell_radar.scheduler import run_scheduler

    click.echo(f"Starting Resell Radar scheduler (refresh every {interval} min)…")
    run_scheduler(interval_minutes=interval)


if __name__ == "__main__":
    main()
