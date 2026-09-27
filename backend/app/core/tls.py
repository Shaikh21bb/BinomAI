"""Verified TLS shared by Supabase HTTP and JWT key requests."""

import os
import ssl

import certifi


def create_tls_context() -> ssl.SSLContext:
    # Include the OS trust store (e.g. locally installed issuer certificates).
    # OpenSSL also honours explicit SSL_CERT_FILE / SSL_CERT_DIR overrides.
    context = ssl.create_default_context()
    if not os.environ.get("SSL_CERT_FILE") and not os.environ.get("SSL_CERT_DIR"):
        # certifi supplies public roots when the OS bundle is absent or older.
        context.load_verify_locations(cafile=certifi.where())
    return context
