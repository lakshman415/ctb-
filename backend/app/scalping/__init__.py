"""
Scalping analysis package (phase 1).

Self-contained, DB-free tooling for a single trading pair:
  - GeckoTerminal OHLCV ingestion (client.py)
  - local-file candle store (store.py)
  - swing/level detection (levels.py)
  - volume profile + VWAP (volume_profile.py)
  - backtest harness (backtest.py)

Nothing here places orders or holds keys. It exists to answer one question:
does a support/resistance scalping rule set have positive expectancy on this
pair once realistic round-trip costs are subtracted?
"""
