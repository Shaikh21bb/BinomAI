# Supabase Python client integration
# Note: For backend operations we typically use the service_role key to bypass RLS,
# or we pass the user's JWT to authenticate as them.

import httpx
from app.core.config import settings

from contextlib import asynccontextmanager

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
        async with httpx.AsyncClient(base_url=self.url, headers=self.headers, timeout=timeout) as client:
            yield client

# Global singleton
supabase_admin = SupabaseClient()
