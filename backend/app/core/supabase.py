# Supabase Python client integration
# Note: For backend operations we typically use the service_role key to bypass RLS,
# or we pass the user's JWT to authenticate as them.

import httpx
import structlog
from fastapi import HTTPException
from app.core.config import settings
from app.core.tls import create_tls_context

from contextlib import asynccontextmanager

logger = structlog.get_logger(__name__)


def create_supabase_http_client(**kwargs) -> httpx.AsyncClient:
    """Retry connection failures once, always verifying the certificate/host.

    Transport retries happen before an HTTP request is sent. In particular,
    registration is not replayed after a read timeout or a server response.
    """
    context = create_tls_context()
    return httpx.AsyncClient(
        verify=context,
        transport=httpx.AsyncHTTPTransport(verify=context, retries=1),
        timeout=kwargs.pop("timeout", 20.0),
        **kwargs,
    )


@asynccontextmanager
async def supabase_auth_errors():
    """Keep transport details out of user-facing authentication errors."""
    try:
        yield
    except httpx.RequestError as exc:
        logger.warning("supabase_auth_unavailable", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Сервис авторизации временно недоступен. Попробуйте ещё раз.",
        ) from exc


class SupabaseClient:
    """
    A lightweight wrapper for interacting with Supabase Admin API and Storage.
    In the backend, we primarily use the DB via SQLAlchemy and only use Supabase APIs for:
    - Auth (Admin user creation)
    - Storage (File uploads)
    """
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_SERVICE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
        
    @asynccontextmanager
    async def get_client(self, timeout: float = 20.0):
        """Provides a managed HTTPX async client for Supabase Admin API calls."""
        async with create_supabase_http_client(base_url=self.url, headers=self.headers, timeout=timeout) as client:
            yield client

# Global singleton
supabase_admin = SupabaseClient()
