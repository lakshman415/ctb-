"""
Scanner API endpoints.

Exposes the scanner results via REST.
Thin controller layer — validates requests, delegates to services, returns responses.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_scanner_service
from app.schemas.scanner import ScannerResultResponse
from app.services.scanner_service import ScannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.get("/results", response_model=ScannerResultResponse)
async def get_scanner_results() -> ScannerResultResponse:
    """
    Get the latest scanner results (ranked, filtered tokens).

    Returns the most recent scan output from the scheduler.
    If the scanner hasn't run yet, returns an empty result set.
    """
    from app.scheduler.jobs import get_latest_scan_result

    result = get_latest_scan_result()

    if result is None:
        # No scan has run yet — return empty result
        return ScannerResultResponse(
            scanned_at=datetime.now(tz=UTC),
            total_pairs_fetched=0,
            total_after_filter=0,
            tokens=[],
        )

    return result


@router.post("/trigger", response_model=ScannerResultResponse)
async def trigger_scan(
    scanner: ScannerService = Depends(get_scanner_service),
) -> ScannerResultResponse:
    """
    Manually trigger a scan cycle (useful for testing / on-demand refresh).

    Runs the full pipeline: fetch → parse → categorize → filter → score → store.
    Updates the latest result cache so GET /results returns fresh data.
    """

    try:
        result = await scanner.run_scan()

        # Update the cached results
        import app.scheduler.jobs as jobs_module

        jobs_module._latest_scan_result = result
        jobs_module._all_scanned_tokens = scanner.last_unfiltered_result

        logger.info(f"Manual scan triggered: {result.total_after_filter} tokens ranked")
        return result

    except Exception as e:
        logger.error(f"Manual scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
