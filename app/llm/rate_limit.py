"""Simple rate limiter for Gemini free tier (15 requests per minute)."""
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

# 60 seconds / 15 requests = 4 seconds between requests
MIN_INTERVAL_SEC = 60.0 / 15.0

_last_call_time: float = 0.0
_lock = asyncio.Lock()


async def throttle_gemini() -> None:
    """Call before each Gemini request. Sleeps so we stay under 15 RPM."""
    global _last_call_time
    async with _lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < MIN_INTERVAL_SEC and _last_call_time > 0:
            sleep_for = MIN_INTERVAL_SEC - elapsed
            logger.debug("Throttling Gemini: sleeping %.1fs", sleep_for)
            await asyncio.sleep(sleep_for)
        _last_call_time = time.monotonic()
