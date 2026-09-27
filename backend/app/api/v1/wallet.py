"""
Wallet API — fetch trade history and stats from GMGN.
"""

import json
import logging
import os
import subprocess

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/activity")
async def get_wallet_activity(
    chain: str = Query(..., description="sol, eth, bsc, base, robinhood"),
    wallet: str = Query(default=None, description="Wallet address (uses fixed if not provided)"),
    limit: int = Query(default=30, ge=1, le=100),
):
    """Get wallet trade activity (buys/sells) from GMGN."""
    settings = get_settings()
    if not settings.gmgn_api_key:
        raise HTTPException(status_code=400, detail="GMGN API key not configured")

    # Use fixed wallet if not provided
    if not wallet:
        wallet_map = {
            "sol": settings.wallet_sol,
            "eth": settings.wallet_eth,
            "bsc": settings.wallet_bsc,
            "robinhood": settings.wallet_robinhood,
            "base": settings.wallet_base,
        }
        wallet = wallet_map.get(chain, "")

    if not wallet:
        raise HTTPException(status_code=400, detail=f"No wallet configured for chain: {chain}")

    data = _call_gmgn_cli(
        f"portfolio activity --chain {chain} --wallet {wallet} --limit {limit} --type buy --type sell --raw"
    )
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch wallet activity")
    return data


@router.get("/stats")
async def get_wallet_stats(
    chain: str = Query(..., description="sol, eth, bsc, base, robinhood"),
    wallet: str = Query(..., description="Wallet address"),
    period: str = Query(default="30d", description="7d or 30d"),
):
    """Get wallet trading statistics (PnL, win rate, etc) from GMGN."""
    settings = get_settings()
    if not settings.gmgn_api_key:
        raise HTTPException(status_code=400, detail="GMGN API key not configured")

    data = _call_gmgn_cli(
        f"portfolio stats --chain {chain} --wallet {wallet} --period {period} --raw"
    )
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch wallet stats")
    return data


@router.get("/holdings")
async def get_wallet_holdings(
    chain: str = Query(..., description="sol, eth, bsc, base, robinhood"),
    wallet: str = Query(..., description="Wallet address"),
):
    """Get wallet current token holdings from GMGN."""
    settings = get_settings()
    if not settings.gmgn_api_key:
        raise HTTPException(status_code=400, detail="GMGN API key not configured")

    data = _call_gmgn_cli(
        f"portfolio holdings --chain {chain} --wallet {wallet} --raw"
    )
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch wallet holdings")
    return data


def _call_gmgn_cli(args: str) -> dict | None:
    """Call gmgn-cli and return parsed JSON."""
    settings = get_settings()

    env = os.environ.copy()
    env["GMGN_API_KEY"] = settings.gmgn_api_key or ""
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    # Ensure Node/npm global bin is on PATH
    env["PATH"] = os.environ.get("PATH", "") + os.pathsep + os.path.expanduser("~\\AppData\\Roaming\\npm")

    try:
        result = subprocess.run(
            f"gmgn-cli {args}",
            capture_output=True, env=env, timeout=30, shell=True,
        )
        output = result.stdout.decode("utf-8", errors="ignore").strip()
        if output and (output.startswith("{") or output.startswith("[")):
            return json.loads(output)

        logger.warning(f"gmgn-cli no JSON: {result.stderr.decode('utf-8', errors='ignore')[:200]}")
        return None

    except subprocess.TimeoutExpired:
        logger.error("gmgn-cli timeout")
        return None
    except Exception as e:
        logger.error(f"gmgn-cli error: {e}")
        return None
