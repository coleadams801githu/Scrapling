# Resell Radar

**Resell Radar** is a price-alert and monitoring module bundled with [Scrapling](https://github.com/D4Vinci/Scrapling).  
It lets you track item prices across multiple luxury and streetwear resale platforms and receive notifications when your targets are hit.

---

## Supported Platforms

| Platform | Scraper class | Prefers |
|---|---|---|
| eBay | `EbayScraper` | Browse API → HTML |
| Grailed | `GrailedScraper` | GraphQL API → HTML |
| 1stDibs | `IstdibsScraper` | REST API → HTML |
| Poshmark | `PoshmarkScraper` | `__NEXT_DATA__` JSON → HTML |
| The RealReal | `TheRealRealScraper` | HTML (StealthyFetcher) |
| Vestiaire Collective | `VestiaireScraper` | HTML (StealthyFetcher) |
| StockX | `StockXScraper` | Product API → HTML |
| GOAT | `GoatScraper` | `__NEXT_DATA__` JSON → HTML |
| Depop | `DepopScraper` | REST API → HTML |

---

## Quick Start

### 1. Install dependencies

```bash
pip install "scrapling[radar]"
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///resell_radar.db` | SQLAlchemy connection string |
| `EBAY_APP_TOKEN` | _(none)_ | eBay Browse API OAuth2 token |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server for email alerts |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | _(none)_ | SMTP username / sender |
| `SMTP_PASSWORD` | _(none)_ | SMTP password or app password |
| `EMAIL_FROM` | _(none)_ | From address for email notifications |
| `NTFY_URL` | `https://ntfy.sh` | ntfy push notification server |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins for the API |

### 3. Use the CLI

```bash
# Add an alert: notify when a StockX listing drops below $200
radar add-alert https://stockx.com/nike-air-max-1-86-big-bubble-black \
  --email you@example.com \
  --price 200 \
  --condition below

# List your active alerts
radar list-alerts --email you@example.com

# Run a one-shot check on alert ID 1
radar check 1

# Start the background scheduler (polls every 15 minutes by default)
radar run --interval 15
```

### 4. Use the REST API

Start the server:

```bash
uvicorn resell_radar.server:app --reload
```

Interactive docs are available at `http://localhost:8000/docs`.

#### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/users` | Create a user |
| `GET` | `/users/{user_id}/alerts` | List active alerts for a user |
| `POST` | `/alerts` | Create a price alert |
| `GET` | `/alerts/{alert_id}` | Get alert details |
| `PATCH` | `/alerts/{alert_id}` | Update an alert |
| `DELETE` | `/alerts/{alert_id}` | Delete an alert |
| `POST` | `/alerts/{alert_id}/check` | Trigger a manual price check |
| `GET` | `/alerts/{alert_id}/history` | Price snapshot history |

#### Example: create a user and an alert

```bash
# Create user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "notification_preference": "email"}'

# Create alert (replace user_id with the ID returned above)
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "url": "https://www.goat.com/sneakers/air-max-1-86-big-bubble-black-dq3989-001",
    "target_price": 180.00,
    "condition": "below"
  }'
```

---

## Notification Backends

Set `notification_preference` when creating a user:

| Value | Requires |
|---|---|
| `"email"` | `SMTP_*` env vars |
| `"webhook"` | `webhook_url` on the user record |
| `"push"` | `push_token` (ntfy topic) + `NTFY_URL` |

---

## Alert Conditions

| Condition | Meaning |
|---|---|
| `below` | Trigger when current price ≤ `target_price` |
| `above` | Trigger when current price ≥ `target_price` |
| `any_drop` | Trigger whenever the price is lower than the previous snapshot |

---

## Architecture

```
resell_radar/
├── scrapers/          # Per-platform scraping logic (base + 9 platforms)
├── models.py          # SQLAlchemy ORM (User, Alert, PriceSnapshot)
├── database.py        # Engine / session factory
├── alerts.py          # CRUD + scrape-and-evaluate logic
├── notifications.py   # Email / webhook / push dispatch
├── scheduler.py       # APScheduler polling loop
├── cli.py             # Click CLI (radar add-alert / check / run …)
└── server.py          # FastAPI REST API
```

---

## Running Tests

```bash
pytest tests/resell_radar/ -v
```
