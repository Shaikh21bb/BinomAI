"""Small Redis-backed fixed-window rate limiter for costly API operations."""

import hashlib
import re

import redis.asyncio as redis
from fastapi import HTTPException


_RATE = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour)s?\s*$", re.I)
_WINDOW_SECONDS = {"second": 1, "minute": 60, "hour": 3600}
_INCREMENT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {current, redis.call('TTL', KEYS[1])}
"""


def parse_rate(value: str) -> tuple[int, int]:
    match = _RATE.fullmatch(value)
    if not match or int(match.group(1)) < 1:
        raise ValueError(f"Invalid rate limit: {value!r}")
    return int(match.group(1)), _WINDOW_SECONDS[match.group(2).casefold()]


def rate_limit_subject(*parts: str) -> str:
    """Build a stable opaque key without storing emails or bearer tokens in Redis."""
    normalized = "\x1f".join(part.strip().casefold() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


async def enforce_rate_limit(
    client: redis.Redis,
    *,
    scope: str,
    subject: str,
    rate: str,
) -> None:
    """Increment a scoped counter atomically and reject requests over its limit."""
    limit, window = parse_rate(rate)
    count, ttl = await client.eval(
        _INCREMENT,
        1,
        f"rate-limit:{scope}:{subject}",
        window,
    )
    if int(count) > limit:
        retry_after = max(1, int(ttl))
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Повторите попытку позже.",
            headers={"Retry-After": str(retry_after)},
        )
