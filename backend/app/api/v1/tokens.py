"""
Tokens API endpoints.

Returns all scanned token data for the frontend to filter client-side.
This is the DexScreener-style "show everything, user filters it" approach.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas.scanner import RankedTokenResponse, ScannerResultResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("/all", response_model=ScannerResultResponse)
async def get_all_tokens() -> ScannerResultResponse:
    """
    Get ALL scanned tokens — no server-side filtering.

    Returns every token from the latest scan with their scores.
    The frontend applies filters client-side for instant interaction.
    """
    from app.scheduler.jobs import get_latest_scan_result

    result = get_latest_scan_result()

    if result is None:
        return ScannerResultResponse(
            scanned_at=datetime.now(tz=UTC),
            total_pairs_fetched=0,
            total_after_filter=0,
            tokens=[],
        )

    return result


@router.get("/unfiltered", response_model=ScannerResultResponse)
async def get_unfiltered_tokens() -> ScannerResultResponse:
    """
    Get ALL scanned tokens scored but WITHOUT filter pipeline applied.

    This returns every token that was parsed from DexScreener, scored,
    regardless of whether it would pass the filter pipeline.
    Used by the frontend so users can apply their own filters.
    """
    from app.scheduler.jobs import get_all_scanned_tokens

    result = get_all_scanned_tokens()

    if result is None:
        return ScannerResultResponse(
            scanned_at=datetime.now(tz=UTC),
            total_pairs_fetched=0,
            total_after_filter=0,
            tokens=[],
        )

    return result
