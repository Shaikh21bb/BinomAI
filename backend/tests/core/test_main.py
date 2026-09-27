from unittest.mock import patch

from app.core.config import settings
from app.main import create_app


def test_production_app_hides_interactive_api_schema():
    with patch.object(settings, "APP_ENV", "production"):
        production_app = create_app()

    assert production_app.openapi_url is None
    assert production_app.docs_url is None
    assert production_app.redoc_url is None
