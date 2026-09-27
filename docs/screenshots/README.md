# Screenshots

The main project README embeds the images from this folder to show the app in action
(the app is not deployed publicly). Save your PNGs here using the **exact file names**
in the tables below and they will appear in the README automatically.

The app has five sections, reached from the sidebar (grouped as Discover / Analyze /
Track). Capture each one, plus the sub-views listed, so the README tells the whole story.

## Required screenshots (one per section)

| File name | Section | What to show |
|-----------|---------|--------------|
| `trending.png` | Trending (Discover) | The ranked trending token table with the chain + interval filters visible |
| `scanner.png` | Scanner (Discover) | The scanner table with the market-cap category tabs (All / Early / Mid / Large) visible |
| `token-analysis.png` | Token Analysis (Analyze) | A token analyzed: the grade card, key metrics, and price-change cards above the fold |
| `watchlist.png` | Watchlist (Track) | A watchlist with a few tokens added |
| `journal.png` | Journal (Track) | The Trade Review tab of the journal |

## Recommended extra screenshots (sub-views)

These make the "technical analysis" and journal depth obvious to a reviewer. Optional
but strongly recommended for a portfolio.

| File name | Where | What to show |
|-----------|-------|--------------|
| `token-analysis-signals.png` | Token Analysis | The "Key Signals" panel + price chart |
| `token-analysis-assessment.png` | Token Analysis → Assessment tab | The grade breakdown (liquidity, volume, buy pressure, trend, volatility...) |
| `token-analysis-levels.png` | Token Analysis → S/R Levels tab | Support / resistance market-cap levels |
| `token-analysis-activity.png` | Token Analysis → Activity tab | Transactions, volume, and metadata columns |
| `journal-learnings.png` | Journal → Learnings tab | The learnings cards |
| `journal-checklist.png` | Journal → Checklist tab | The pre-trade checklist |
| `watchlist-alerts.png` | Watchlist | The "Triggered Alerts" panel (if you have alerts set) |

## Optional nice-to-haves

| File name | What to show |
|-----------|--------------|
| `dashboard-dark.png` | Any page in dark mode (toggle bottom-left) — shows theming |
| `dashboard-light.png` | The same page in light mode |
| `sidebar-collapsed.png` | The collapsed sidebar (collapse button, bottom-left) |

## How to capture good screenshots

1. Start the backend, then the frontend (see the root `README.md` -> "Getting started").
2. Open the app in your browser (Vite prints the URL, usually `http://localhost:5173`).
3. Let a scan run so the tables actually have rows.
4. Capture each view:
   - **Windows:** `Win + Shift + S` (Snipping Tool), or `Win + PrtScn` for full screen.
   - Crop to just the app window so it looks clean.
5. Save as PNG into this folder using the exact names above.

## Tips for a resume-ready look

- Use the same window size for every shot so the README looks consistent.
- Capture when tables have data (run a scan first).
- Prefer dark mode for the "hero" shots — it reads as a trading terminal.
- Blur or crop any personal wallet address before saving.
- Keep each file under ~1 MB so the repo stays light.
