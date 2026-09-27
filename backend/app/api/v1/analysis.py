"""
Token analysis endpoint.

Accepts a contract address + chain, fetches from DexScreener, returns full TA.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.clients.dexscreener import DexScreenerClient
from app.config import get_settings
from app.schemas.analysis import TokenAnalysisResponse
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/token", response_model=TokenAnalysisResponse)
async def analyze_token(
    chain: str = Query(..., description="Chain: solana, ethereum, base, robinhood"),
    address: str = Query(..., description="Token contract address"),
) -> TokenAnalysisResponse:
    """
    Analyze a token by contract address and chain.

    Fetches live data from DexScreener, runs technical analysis,
    and returns a comprehensive report.
    """
    settings = get_settings()
    client = DexScreenerClient(
        base_url=settings.dexscreener_base_url,
        verify_ssl=settings.dexscreener_verify_ssl,
    )

    try:
        service = AnalysisService(client)
        result = await service.analyze(chain=chain.lower(), address=address.strip())

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Token not found: {address} on {chain}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed for {address} on {chain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        await client.close()
