"""FastAPI REST API for Resell Radar — Replit / server compatible."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from resell_radar.database import get_db as _get_db_ctx, init_db
from resell_radar.models import Alert, User


# --------------------------------------------------------------------------- lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Resell Radar API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- DB dependency


def get_db():
    with _get_db_ctx() as db:
        yield db


# --------------------------------------------------------------------------- Pydantic schemas


class UserCreate(BaseModel):
    email: EmailStr
    notification_preference: str = "email"
    webhook_url: str | None = None
    push_token: str | None = None


class AlertCreate(BaseModel):
    user_id: int
    url: str
    target_price: float | None = None
    condition: str = "below"
    check_interval_minutes: int = 15
    item_name: str | None = None


class AlertUpdate(BaseModel):
    target_price: float | None = None
    condition: str | None = None
    check_interval_minutes: int | None = None
    is_active: bool | None = None
    item_name: str | None = None


class AlertOut(BaseModel):
    id: int
    user_id: int
    platform: str
    item_url: str
    item_name: str | None
    target_price: float | None
    condition: str
    is_active: bool
    check_interval_minutes: int

    class Config:
        from_attributes = True


class SnapshotOut(BaseModel):
    id: int
    alert_id: int
    price: float | None
    currency: str
    title: str | None
    availability: str

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------- routes


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/users", status_code=201)
def create_user_endpoint(body: UserCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    from resell_radar.alerts import create_user
    user = create_user(db, email=body.email, notification_preference=body.notification_preference,
                       webhook_url=body.webhook_url, push_token=body.push_token)
    return {"id": user.id, "email": user.email}


@app.get("/users/{user_id}/alerts", response_model=list[AlertOut])
def list_user_alerts(user_id: int, db: Session = Depends(get_db)):
    from resell_radar.alerts import list_alerts
    return list_alerts(db, user_id)


@app.post("/alerts", response_model=AlertOut, status_code=201)
def create_alert_endpoint(body: AlertCreate, db: Session = Depends(get_db)):
    from resell_radar.alerts import create_alert
    return create_alert(
        db,
        user_id=body.user_id,
        url=body.url,
        target_price=body.target_price,
        condition=body.condition,
        check_interval_minutes=body.check_interval_minutes,
        item_name=body.item_name,
    )


@app.get("/alerts/{alert_id}", response_model=AlertOut)
def get_alert_endpoint(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@app.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert_endpoint(alert_id: int, body: AlertUpdate, db: Session = Depends(get_db)):
    from resell_radar.alerts import update_alert
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    alert = update_alert(db, alert_id, **fields)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@app.delete("/alerts/{alert_id}", status_code=204)
def delete_alert_endpoint(alert_id: int, db: Session = Depends(get_db)):
    from resell_radar.alerts import delete_alert
    if not delete_alert(db, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")


@app.post("/alerts/{alert_id}/check", response_model=SnapshotOut)
def check_alert_endpoint(alert_id: int, db: Session = Depends(get_db)):
    from resell_radar.alerts import check_alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    triggered, snapshot = check_alert(db, alert)
    if not snapshot:
        raise HTTPException(status_code=502, detail="Scrape failed; could not fetch price")
    return snapshot


@app.get("/alerts/{alert_id}/history", response_model=list[SnapshotOut])
def alert_history(alert_id: int, limit: int = 50, db: Session = Depends(get_db)):
    from resell_radar.models import PriceSnapshot
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.alert_id == alert_id)
        .order_by(PriceSnapshot.scraped_at.desc())
        .limit(limit)
        .all()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
