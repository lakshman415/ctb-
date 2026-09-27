"""
GMGN.ai client — uses gmgn-cli for data access.

The GMGN API is behind Cloudflare which blocks direct HTTP calls.
The gmgn-cli (Node.js) handles authentication and Cloudflare bypass.
We call it as a subprocess and parse the JSON output.

Prerequisites:
    - npm install -g gmgn-cli
    - GMGN_API_KEY set in environment or .env
"""

import json
import logging
import os
import subprocess
from typing import Any

from app.core.chains import to_gmgn

logger = logging.getLogger(__name__)


class GMGNToken:
    """Parsed GMGN token data."""

    def __init__(self, data: dict[str, Any]):
        self.address: str = data.get("address", "")
        self.chain: str = data.get("chain", "")
        self.symbol: str = data.get("symbol", "")
        self.name: str = data.get("name", "")
        self.price: float = data.get("price", 0) or 0
        self.market_cap: float = data.get("market_cap", 0) or 0
        self.liquidity: float = data.get("liquidity", 0) or 0
        self.volume: float = data.get("volume", 0) or 0
        self.swaps: int = data.get("swaps", 0) or 0
        self.buys: int = data.get("buys", 0) or 0
        self.sells: int = data.get("sells", 0) or 0
        self.holder_count: int = data.get("holder_count", 0) or 0
        self.price_change_1h: float = data.get("price_change_percent1h", 0) or 0
        self.price_change_5m: float = data.get("price_change_percent5m", 0) or 0
        self.price_change_24h: float = data.get("price_change_percent", 0) or 0
        self.is_honeypot: bool = bool(data.get("is_honeypot", 0))
        self.is_open_source: bool = bool(data.get("is_open_source", 0))
        self.renounced: bool = bool(data.get("is_renounced", 0))
        self.buy_tax: str = data.get("buy_tax", "0") or "0"
        self.sell_tax: str = data.get("sell_tax", "0") or "0"
        self.sniper_count: int = data.get("sniper_count", 0) or 0
        self.smart_degen_count: int = data.get("smart_degen_count", 0) or 0
        self.renowned_count: int = data.get("renowned_count", 0) or 0
        self.website: str | None = data.get("website") or None
        self.twitter: str | None = data.get("twitter_username") or None
        self.telegram: str | None = data.get("telegram") or None

    @property
    def buy_sell_ratio(self) -> float | None:
        if self.sells == 0:
            return None if self.buys == 0 else 999.0
        return round(self.buys / self.sells, 2)


class GMGNClient:
    """
    Client for GMGN data via gmgn-cli subprocess.

    If no API key is configured, returns empty results.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        self._enabled = api_key is not None and len(api_key.strip()) > 0

        if not self._enabled:
            logger.info("GMGN client disabled (no API key)")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def get_trending(
        self,
        chain: str = "solana",
        interval: str = "24h",
        limit: int = 20,
    ) -> list[GMGNToken]:
        """
        Get trending tokens from GMGN.

        Args:
            chain: Canonical chain id ("solana", "ethereum", "bsc", "base",
                "robinhood"). GMGN's own short slugs are also accepted.
            interval: "1h", "6h", "24h"
            limit: Max tokens to return

        Returns:
            List of GMGNToken objects sorted by volume.
        """
        if not self._enabled:
            return []

        # GMGN uses short slugs ("sol"); the rest of the app uses canonical ids
        gmgn_chain = to_gmgn(chain)

        try:
            env = os.environ.copy()
            env["GMGN_API_KEY"] = self._api_key
            env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
            env["PATH"] = os.environ.get("PATH", "") + os.pathsep + os.path.expanduser("~\\AppData\\Roaming\\npm")

            cmd = f"gmgn-cli market trending --chain {gmgn_chain} --interval {interval} --raw"

            result = subprocess.run(
                cmd,
                capture_output=True,
                env=env,
                timeout=30,
                shell=True,
            )

            output = result.stdout.decode("utf-8", errors="ignore").strip()

            if not output or not output.startswith("{"):
                logger.warning(f"GMGN CLI returned no JSON for {chain}")
                return []

            data = json.loads(output)

            if data.get("code") != 0:
                logger.warning(f"GMGN error: {data.get('message')}")
                return []

            tokens = [GMGNToken(t) for t in data.get("data", {}).get("rank", [])]
            logger.info(f"GMGN: {len(tokens)} trending tokens for {chain}/{interval}")
            return tokens[:limit]

        except subprocess.TimeoutExpired:
            logger.warning(f"GMGN CLI timeout for {chain}")
            return []
        except Exception as e:
            logger.warning(f"GMGN fetch failed for {chain}: {e}")
            return []
