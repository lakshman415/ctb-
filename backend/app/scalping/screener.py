"""
Candidate discovery + candle screening.

Pipeline:
  1. Pull candidate pairs per chain via the existing DexScreenerClient
     (same fetch the scanner uses).
  2. Screen them for scalp suitability on the cheap DexScreener aggregate
     data (liquidity floor, min 24h volume, balanced buy/sell, min txns,
     and a choppiness preference that avoids strongly trending tokens).
  3. For each survivor, map its chain to a GeckoTerminal network id, fetch
     candles, and run the backtest with a liquidity-scaled round-trip cost.
  4. Rank by a confidence-adjusted score (expectancy gated by trade count)
     and return the ranked list.

DB-free. No orders, no keys. Reuses the app's DexScreener client and mirrors
the scanner's quality thresholds, but does not persist to any database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from app.clients.dexscreener import DexScreenerClient
from app.clients.dexscreener_models import DexPair
from app.scalping.backtest import BacktestConfig, BacktestResult, run_backtest
from app.scalping.client import GeckoTerminalClient
from app.scalping.models import Candle
from app.scalping.movement import MovementProfile, analyze_movement
from app.scalping.store import CandleStore

logger = logging.getLogger(__name__)

# DexScreener chainId -> GeckoTerminal network id.
# Only chains we can actually fetch candles for. Unmapped chains are skipped.
CHAIN_TO_GT_NETWORK = {
    "ethereum": "eth",
    "solana": "solana",
    "base": "base",
    "bsc": "bsc",
    "arbitrum": "arbitrum",
    "polygon": "polygon_pos",
    "optimism": "optimism",
    "avalanche": "avax",
    "robinhood": "robinhood",  # served by GT even though not in /networks list
}

# Minimum trades before a backtest result is trustworthy. Below this, a token
# is treated as "not enough evidence" rather than ranked on a lucky handful.
MIN_TRADES_FOR_CONFIDENCE = 20


@dataclass
class ScalpScreenConfig:
    """Coarse pre-filter thresholds (on DexScreener aggregate data)."""

    # Liquidity band: deep enough to trade, NOT so deep the token is inert.
    # A $29M coin like PEPE barely moves in %; that's useless for scalping.
    min_liquidity_usd: float = 300_000.0
    max_liquidity_usd: float = 8_000_000.0
    min_volume_24h_usd: float = 300_000.0   # real activity
    min_txns_24h: int = 400                 # enough trades to form candles
    max_bs_ratio: float = 2.5               # not a one-sided pump
    min_bs_ratio: float = 0.5               # not a slow bleed
    # A scalper WANTS movement. Require meaningful recent volatility rather
    # than filtering it out. Measured on the 24h price change magnitude as a
    # coarse proxy; the real choppiness gate runs on candles after fetch.
    min_abs_24h_change: float = 8.0
    max_abs_24h_change: float = 60.0        # still exclude full-on moonshots/dumps
    # Candle-based movement gate (the real filter -- seeks chop, not trend).
    min_avg_range_pct: float = 0.25         # avg per-bar high-low swing
    max_directionality: float = 0.20        # net drift as fraction of total path
    max_candidates_to_backtest: int = 15    # cap candle requests
    chains: tuple[str, ...] = ("solana", "base", "ethereum")
    verify_ssl: bool = True                 # False for TLS-intercepting proxies


@dataclass
class ScreenedToken:
    symbol: str
    chain: str
    gt_network: str
    pair_address: str
    liquidity_usd: float
    volume_24h_usd: float
    round_trip_cost_pct: float
    result: BacktestResult
    candle_count: int
    movement: "MovementProfile"

    @property
    def expectancy(self) -> float:
        return self.result.expectancy_pct

    @property
    def has_confidence(self) -> bool:
        return self.result.n >= MIN_TRADES_FOR_CONFIDENCE

    @property
    def rank_score(self) -> float:
        """
        Confidence-adjusted expectancy.

        Expectancy alone would crown a token that made one lucky trade. We
        scale it by a confidence factor that saturates at MIN_TRADES: a token
        needs a real sample before its expectancy counts at full weight.
        """
        conf = min(self.result.n / MIN_TRADES_FOR_CONFIDENCE, 1.0)
        return self.expectancy * conf


def estimate_round_trip_cost(liquidity_usd: float) -> float:
    """
    Assumed all-in round-trip cost (%) as a function of pool depth.

    Deeper pools -> lower slippage. These are deliberately conservative;
    they exist so the ranking reflects what you'd actually pay per token
    rather than a flat guess. Not a substitute for measuring real fills.
    """
    if liquidity_usd >= 2_000_000:
        return 1.5
    if liquidity_usd >= 1_000_000:
        return 2.0
    if liquidity_usd >= 500_000:
        return 3.0
    if liquidity_usd >= 250_000:
        return 4.0
    return 5.0


def _bs_ratio(pair: DexPair) -> float | None:
    txns = pair.txns.get("h24")
    if not txns or txns.sells == 0:
        return None
    return txns.buys / txns.sells


def _txns_24h(pair: DexPair) -> int:
    txns = pair.txns.get("h24")
    return (txns.buys + txns.sells) if txns else 0


def _liq(pair: DexPair) -> float:
    return pair.liquidity.usd if pair.liquidity and pair.liquidity.usd else 0.0


def passes_scalp_screen(pair: DexPair, cfg: ScalpScreenConfig) -> bool:
    """Coarse suitability check on cheap aggregate data."""
    if pair.chainId not in CHAIN_TO_GT_NETWORK:
        return False
    if not pair.pairAddress:
        return False

    liq = _liq(pair)
    if liq < cfg.min_liquidity_usd or liq > cfg.max_liquidity_usd:
        return False

    if pair.volume.get("h24", 0.0) < cfg.min_volume_24h_usd:
        return False

    if _txns_24h(pair) < cfg.min_txns_24h:
        return False

    ratio = _bs_ratio(pair)
    if ratio is None or not (cfg.min_bs_ratio <= ratio <= cfg.max_bs_ratio):
        return False

    # A scalper needs movement. Require a meaningful 24h swing (but not a
    # full moonshot/dump). This is a coarse proxy; the candle-based movement
    # gate after fetch is what actually enforces "choppy, not trending".
    change_24h = pair.priceChange.get("h24")
    if change_24h is not None:
        mag = abs(change_24h)
        if mag < cfg.min_abs_24h_change or mag > cfg.max_abs_24h_change:
            return False

    return True


async def discover_candidates(
    client: DexScreenerClient, cfg: ScalpScreenConfig
) -> list[DexPair]:
    """Fetch pairs across chains and keep those passing the scalp screen."""
    candidates: dict[str, DexPair] = {}
    for chain in cfg.chains:
        try:
            raw = await client.fetch_pairs(chain)
        except Exception as exc:  # noqa: BLE001 - discovery is best-effort
            logger.warning("fetch_pairs(%s) failed: %s", chain, exc)
            continue

        kept = 0
        for raw_pair in raw:
            pair = DexPair.model_validate(raw_pair)
            if passes_scalp_screen(pair, cfg):
                key = f"{pair.chainId}:{pair.pairAddress}"
                existing = candidates.get(key)
                if existing is None or _liq(pair) > _liq(existing):
                    candidates[key] = pair
                    kept += 1
        logger.info("discover: %s -> %s pairs kept after screen", chain, kept)

    ranked = sorted(candidates.values(), key=_liq, reverse=True)
    return ranked[: cfg.max_candidates_to_backtest]


async def backtest_candidate(
    gt: GeckoTerminalClient,
    pair: DexPair,
    *,
    max_bars: int,
    base_backtest_cfg: BacktestConfig,
    persist: bool,
    screen_cfg_min_range: float,
    screen_cfg_max_dir: float,
) -> ScreenedToken | None:
    """Fetch candles for one pair and backtest it with a depth-scaled cost."""
    network = CHAIN_TO_GT_NETWORK[pair.chainId]
    symbol = pair.baseToken.symbol or "?"
    try:
        candles: list[Candle] = await gt.fetch_ohlcv_history(
            network, pair.pairAddress, timeframe="1m", max_bars=max_bars
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("candle fetch failed for %s/%s (%s): %s",
                       network, pair.pairAddress, symbol, exc)
        return None

    if len(candles) < 200:
        logger.info("skip %s: only %s candles (need >=200)", symbol, len(candles))
        return None

    # The real candidate gate: seek chop, reject trends. Computed from the
    # actual candles, not the coarse 24h proxy.
    move = analyze_movement(candles)
    if move is None:
        return None
    if not move.is_scalp_worthy(
        min_avg_range_pct=screen_cfg_min_range,
        max_directionality=screen_cfg_max_dir,
    ):
        logger.info(
            "skip %s: not scalp-worthy (avg_range=%.2f%% directionality=%.2f)",
            symbol, move.avg_range_pct, move.directionality,
        )
        return None

    if persist:
        CandleStore(network, pair.pairAddress, "1m").save(candles)

    liq = _liq(pair)
    cost = estimate_round_trip_cost(liq)
    cfg = replace(base_backtest_cfg, round_trip_cost_pct=cost)
    if len(candles) < cfg.lookback + 50:
        cfg = replace(cfg, lookback=max(50, len(candles) // 3))

    result = run_backtest(candles, cfg)
    return ScreenedToken(
        symbol=symbol,
        chain=pair.chainId,
        gt_network=network,
        pair_address=pair.pairAddress,
        liquidity_usd=liq,
        volume_24h_usd=pair.volume.get("h24", 0.0),
        round_trip_cost_pct=cost,
        result=result,
        candle_count=len(candles),
        movement=move,
    )


async def run_screen(
    screen_cfg: ScalpScreenConfig | None = None,
    backtest_cfg: BacktestConfig | None = None,
    *,
    max_bars: int = 3000,
    persist: bool = True,
) -> list[ScreenedToken]:
    """
    Full discovery + candle-backtest screen.

    Returns ScreenedToken list ranked by confidence-adjusted score (best first).
    """
    scfg = screen_cfg or ScalpScreenConfig()
    bcfg = backtest_cfg or BacktestConfig()

    ds_client = DexScreenerClient(
        base_url="https://api.dexscreener.com", verify_ssl=scfg.verify_ssl
    )
    try:
        candidates = await discover_candidates(ds_client, scfg)
    finally:
        await ds_client.close()

    logger.info("screen: %s candidates passed the coarse filter", len(candidates))
    if not candidates:
        return []

    screened: list[ScreenedToken] = []
    async with GeckoTerminalClient(verify_ssl=scfg.verify_ssl) as gt:
        for pair in candidates:
            token = await backtest_candidate(
                gt, pair, max_bars=max_bars, base_backtest_cfg=bcfg, persist=persist,
                screen_cfg_min_range=scfg.min_avg_range_pct,
                screen_cfg_max_dir=scfg.max_directionality,
            )
            if token and token.result.n > 0:
                screened.append(token)
                logger.info(
                    "backtested %s (%s): expectancy %.3f%% over %s trades (cost %.1f%%)",
                    token.symbol, token.chain, token.expectancy,
                    token.result.n, token.round_trip_cost_pct,
                )

    screened.sort(key=lambda t: t.rank_score, reverse=True)
    return screened
