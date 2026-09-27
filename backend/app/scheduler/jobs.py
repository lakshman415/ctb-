"""
APScheduler job definitions.

Defines periodic background jobs (e.g., the market scanner running every minute).
Jobs are registered at application startup and torn down on shutdown.

The scheduler is decoupled from the scan logic — it only triggers the service
with a fresh DB session and assembled dependencies.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# Module-level scheduler instance — initialized once at app startup.
scheduler: AsyncIOScheduler | None = None

# Stores the latest scan result for the API to serve
_latest_scan_result = None
_all_scanned_tokens = None


def get_latest_scan_result():
    """Return the most recent scan result (or None if no scan has run yet)."""
    return _latest_scan_result


def get_all_scanned_tokens():
    """Return ALL scanned tokens (unfiltered) from the most recent scan."""
    return _all_scanned_tokens


def init_scheduler(interval_seconds: int) -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Args:
        interval_seconds: How often the scanner job runs (from settings).

    Returns:
        Configured (but not yet started) AsyncIOScheduler.
    """
    global scheduler
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _scan_job,
        "interval",
        seconds=interval_seconds,
        id="market_scanner",
        name="Market Scanner",
        replace_existing=True,
    )

    logger.info(f"Scheduler configured: scanner runs every {interval_seconds}s")
    return scheduler


async def _scan_job() -> None:
    """
    Periodic scan job executed by APScheduler.

    Creates a fresh DB session, assembles all dependencies, runs the scan pipeline,
    and stores the result for the API to serve.
    """
    global _latest_scan_result, _all_scanned_tokens

    logger.info("Scanner job triggered")

    try:
        from app.clients.dexscreener import DexScreenerClient
        from app.clients.dexscreener_parser import DexScreenerParser
        from app.config import get_settings
        from app.core.database import SessionLocal
        from app.repositories.snapshot_repository import SnapshotRepository
        from app.repositories.token_repository import TokenRepository
        from app.services.categorizer import MarketCapCategorizer
        from app.services.scanner_service import ScannerService
        from app.services.scoring_service import ScoringService

        settings = get_settings()

        if SessionLocal is None:
            logger.error("Database not initialized, skipping scan")
            return

        # Create a fresh DB session for this scan cycle
        db = SessionLocal()
        client = None

        try:
            # Assemble dependencies
            client = DexScreenerClient(
                base_url=settings.dexscreener_base_url,
                verify_ssl=settings.dexscreener_verify_ssl,
            )
            parser = DexScreenerParser()
            categorizer = MarketCapCategorizer(settings)
            scoring_service = ScoringService(settings)
            token_repo = TokenRepository(db)
            snapshot_repo = SnapshotRepository(db)

            scanner = ScannerService(
                client=client,
                parser=parser,
                categorizer=categorizer,
                scoring_service=scoring_service,
                token_repo=token_repo,
                snapshot_repo=snapshot_repo,
                settings=settings,
            )

            # Run the full scan pipeline
            result = await scanner.run_scan()
            _latest_scan_result = result
            _all_scanned_tokens = scanner.last_unfiltered_result

            # Evaluate watchlist alerts against fresh data
            try:
                from app.services.alert_service import AlertService

                unfiltered = scanner.last_unfiltered_result
                if unfiltered and unfiltered.tokens:
                    fired = AlertService(db).evaluate(unfiltered.tokens)
                    if fired:
                        logger.info(f"{fired} alert(s) triggered")
            except Exception as e:
                logger.warning(f"Alert evaluation failed: {e}")

            logger.info(
                f"Scanner job complete: {result.total_after_filter} tokens ranked"
            )

        finally:
            db.close()
            if client is not None:
                await client.close()

    except Exception as e:
        logger.error(f"Scanner job failed: {e}", exc_info=True)


def start_scheduler() -> None:
    """Start the scheduler (call after init_scheduler)."""
    if scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
