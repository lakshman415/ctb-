"""
Health check endpoint.

Provides a simple liveness probe for monitoring and load balancers.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Basic health check.

    Returns 200 if the application is running.
    Does NOT verify database connectivity (that would be a readiness probe).
    """
    return {"status": "healthy"}
