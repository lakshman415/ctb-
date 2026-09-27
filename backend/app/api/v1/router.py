"""
V1 API router aggregator.

Collects all v1 endpoint routers into a single router
that gets mounted on the FastAPI app with the /api/v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.health import router as health_router
from app.api.v1.journal import router as journal_router
from app.api.v1.scanner import router as scanner_router
from app.api.v1.tokens import router as tokens_router
from app.api.v1.trending import router as trending_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.watchlist import router as watchlist_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(scanner_router)
api_v1_router.include_router(tokens_router)
api_v1_router.include_router(analysis_router)
api_v1_router.include_router(trending_router)
api_v1_router.include_router(wallet_router)
api_v1_router.include_router(journal_router)
api_v1_router.include_router(watchlist_router)
