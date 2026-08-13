import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture(autouse=True)
def no_celery_publish():
    """Tests must never publish real Celery tasks (would poison the dev queue)."""
    with patch("app.tasks.document_tasks.process_document.delay"), \
         patch("app.tasks.document_tasks.run_analysis_task.delay"), \
         patch("app.tasks.analysis_tasks.run_analysis_task.delay"), \
         patch("app.api.v1.endpoints.analysis.run_analysis_task.delay"), \
         patch("app.api.v1.endpoints.products.search_products_task.delay"), \
         patch("app.services.document_service.process_document.delay"):
        yield

@pytest.fixture
def mock_db_session():
    """Mock for SQLAlchemy AsyncSession"""
    return AsyncMock()

@pytest.fixture
def mock_project_repo():
    """Mock for ProjectRepository"""
    with patch("app.services.project_service.project_repo") as mock:
        yield mock

@pytest.fixture
def mock_document_repo():
    """Mock for DocumentRepository"""
    with patch("app.services.document_service.document_repo") as mock:
        yield mock

@pytest.fixture
def mock_supabase_client():
    """Mock for Supabase HTTPX Client"""
    with patch("app.services.document_service.supabase_admin.get_client") as mock:
        yield mock


def scalar_first(obj):
    """MagicMock result where .scalars().first() returns obj (and
    .scalar_one_or_none() + .one() too, for endpoints that use them)."""
    r = MagicMock()
    r.scalars.return_value.first.return_value = obj
    r.scalars.return_value.one.return_value = obj
    r.scalar_one_or_none.return_value = obj
    r.scalar_one.return_value = obj
    return r


def scalars_all(objects):
    """MagicMock result where .scalars().all() returns objects."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = objects
    return r


def db_dispatch(rows):
    """Build an AsyncMock session whose execute() routes by target table.

    rows: dict mapping table name -> object to return via .scalars().first()
    (or a callable taking the stmt and returning a result object).
    A 'default' key is used for tables not listed; Delete statements return an
    empty result.
    """
    from sqlalchemy.sql.dml import Delete

    db = AsyncMock()

    async def execute(stmt, *a, **kw):
        if isinstance(stmt, Delete):
            return scalar_first(None)
        try:
            table = stmt.get_final_froms()[0].name
        except Exception:
            table = "default"
        entry = rows.get(table, rows.get("default", None))
        if callable(entry):
            return entry(stmt)
        if isinstance(entry, list):
            return scalars_all(entry)
        return scalar_first(entry)

    db.execute = execute
    return db
