import logging
import time

import redis
from fastapi import HTTPException, Request, status

logger = logging.getLogger("cryptogo.api")


def increment_rate_limit(request: Request, key: str, window_seconds: int) -> int:
    client = request.app.state.redis
    try:
        return int(
            client.eval(
                "local count = redis.call('INCR', KEYS[1]); "
                "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
                "return count",
                1,
                key,
                window_seconds,
            )
        )
    except redis.RedisError as error:
        if request.app.state.settings.app_env != "development":
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "El control de solicitudes no está disponible.",
            ) from error

        return _increment_local_rate_limit(request, key, window_seconds)


def _increment_local_rate_limit(
    request: Request, key: str, window_seconds: int
) -> int:
    state = request.app.state
    now = time.monotonic()
    with state.local_rate_limits_lock:
        should_cleanup = (
            now >= state.local_rate_limit_cleanup_at
            or (
                key not in state.local_rate_limits
                and len(state.local_rate_limits) >= 10_000
            )
        )
        if should_cleanup:
            expired_keys = [
                cached_key
                for cached_key, (_, expires_at) in state.local_rate_limits.items()
                if expires_at <= now
            ]
            for cached_key in expired_keys:
                del state.local_rate_limits[cached_key]
            state.local_rate_limit_cleanup_at = now + 60

        if (
            key not in state.local_rate_limits
            and len(state.local_rate_limits) >= 10_000
        ):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "El control de solicitudes no está disponible.",
            )

        count, _expires_at = state.local_rate_limits.get(
            key, (0, now + window_seconds)
        )
        count += 1
        state.local_rate_limits[key] = (count, now + window_seconds)

        if not state.local_rate_limit_fallback_logged:
            logger.warning(
                "Redis rate limiting is unavailable; using process-local limits "
                "for development only."
            )
            state.local_rate_limit_fallback_logged = True

        return count
