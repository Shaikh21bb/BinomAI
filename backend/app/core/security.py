from datetime import datetime, timedelta
from typing import Any, Union
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_jwks_client = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """Lazy, cached JWKS client for the current Supabase project."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def verify_jwt_token(token: str) -> dict:
    """
    Verifies a JWT token.
    Prefers Supabase's public JWKS (RS256/ES256), falling back to the legacy
    HS256 verification against SUPABASE_JWT_SECRET. Returns the payload if valid.
    """
    try:
        try:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
        except (jwt.PyJWKClientError, jwt.DecodeError, HTTPException) as e:
            logger.debug("jwks_verification_failed_falling_back_to_secret", error=str(e))
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("jwt_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("jwt_invalid", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
