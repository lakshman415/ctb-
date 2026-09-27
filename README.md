# CTB - Crypto Trading Brain

> A market-intelligence platform that scans crypto tokens across multiple blockchains,
> filters out the noise, scores what is left from 0 to 100, and surfaces the best
> candidates in a clean web dashboard.

CTB is a full-stack project: a **FastAPI (Python)** backend that fetches and analyzes
live market data on a timer, and a **React + TypeScript** frontend that presents it.

---

## What problem does it solve?

New crypto tokens (especially "memecoins") launch constantly, and most are noise or
scams. Manually watching them is impossible. CTB automates the boring part: it
continuously pulls market data, applies objective filters, and ranks tokens so a trader
can focus only on the handful worth a look.

**New to crypto?** Here is the minimum vocabulary to understand this project:

- **Blockchain** - a public network where tokens live (Solana, Ethereum, Base...).
- **Token / memecoin** - a small tradable coin on one of those networks.
- **Liquidity** - how easily you can buy or sell without moving the price. Low = risky.
- **Volume** - how much was traded recently. High = active interest.
- **Market cap** - the token's overall size (price x supply).
- **DexScreener** - a public data source for token prices on decentralized exchanges.

There is a fuller glossary and deeper explanation in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Screenshots

> The app is not deployed publicly. These screenshots show it running locally.
> (Add your images to `docs/screenshots/` - see that folder's README for names.)

### Trending
![Trending page](docs/screenshots/trending.png)

### Scanner
![Scanner page](docs/screenshots/scanner.png)

### Watchlist
![Watchlist page](docs/screenshots/watchlist.png)

### Trade Journal
![Journal page](docs/screenshots/journal.png)

---

## How it works

CTB has two halves that talk over a REST API. A scheduler inside the backend re-runs the
scan on a timer, so the dashboard always shows fresh data.

![System architecture](docs/diagrams/system-architecture.png)

A single scan turns raw market data into a ranked list:

![Scan pipeline](docs/diagrams/scan-pipeline-sequence.png)

1. The scheduler fires on a timer.
2. The scanner pulls live token data from DexScreener (trending from GMGN, optional).
3. The filter pipeline drops tokens that are too illiquid, too quiet, too new/old, or
   show weak buying.
4. The scoring service gives each survivor a weighted 0-100 score.
5. Results are stored and served to the frontend.

> The diagrams above are generated from PlantUML sources in
> [`docs/diagrams/`](docs/diagrams/). See
> [Rendering the diagrams](docs/ARCHITECTURE.md#rendering-the-diagrams) to produce the PNGs.

---

## Tech stack

**Backend**
- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy 2.0, Alembic (migrations)
- APScheduler (periodic scanning)
- Pydantic v2 / pydantic-settings (typed config)
- httpx (async HTTP), pandas
- SQLite for local dev, PostgreSQL for production

**Frontend**
- React 18 + TypeScript
- Vite (build/dev server)
- TailwindCSS
- TanStack Table

**Tooling**
- pytest, pytest-asyncio, pytest-cov
- ruff (lint/format)
- Docker Compose (Postgres for local prod-like runs)

---

## Modules

| Module | Status |
|--------|--------|
| Market Scanner | Working |
| Filtering Engine | Working |
| Scoring Engine | Working |
| Trending | Working |
| Watchlist | Working |
| Trade Journal | Working |
| Scam Detection | Planned |
| Technical Analysis | Planned |
| AI Trade Analysis | Planned |
| Performance Analytics | Planned |

## Supported chains

Solana - Ethereum - Base - BSC - Robinhood

---

## Getting started

### Prerequisites
- Python 3.12+
- Node.js 18+
- (Optional) PostgreSQL, if you don't want to use the built-in SQLite

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env    # Windows   (use: cp .env.example .env  on macOS/Linux)
# Edit .env if you like — it defaults to SQLite, so no database setup is needed.

uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite prints a local URL (usually `http://localhost:5173`). Open it in your browser.

### Configuration

All thresholds, scoring weights, chains, and scan interval live in `.env` (typed and
validated via `app/config.py`). You can retune the strategy without editing code.
**Never commit your real `.env`** - it is git-ignored. Commit `.env.example` instead.

---

## Project structure

```
ctb/
├── backend/            FastAPI app
│   └── app/
│       ├── api/v1/     REST endpoints
│       ├── services/   scanning, scoring, snapshots, alerts
│       ├── filters/    filter pipeline + individual filters
│       ├── clients/    DexScreener / GMGN HTTP clients
│       ├── models/     SQLAlchemy tables
│       ├── repositories/  data access
│       ├── scheduler/  periodic scan jobs
│       └── core/       db, logging, config, exceptions
├── frontend/           React + Vite + Tailwind UI
│   └── src/
│       ├── pages/      Trending, Scanner, Watchlist, Journal, Home
│       ├── components/ layout + shared UI
│       ├── hooks/      data-fetching hooks
│       └── services/   API client
├── docs/
│   ├── ARCHITECTURE.md
│   ├── diagrams/       PlantUML sources (+ rendered PNGs)
│   └── screenshots/    UI screenshots for this README
└── docker-compose.yml
```

---

## Roadmap

- Scam / rug detection heuristics
- Technical-analysis indicators on price candles
- AI-assisted trade analysis
- Performance analytics over the trade journal

---

## Disclaimer

CTB is a personal engineering project for learning and portfolio purposes. It is **not
financial advice** and makes no guarantee of accuracy. Trading crypto assets is risky.
