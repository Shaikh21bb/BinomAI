import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatReplyOutput
from app.ai.chat_agent import classify_fields, ChatAgent
from tests.conftest import scalar_first, scalars_all, db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_PROJECT_ID = uuid.uuid4()


def make_project(status="draft"):
    return Project(
        id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Тендер",
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_shared_db(project, session, messages=None):
    """Fake db whose execute() routes by table; chat_sessions always returns
    the SAME session object (both .first() and .scalar_one() paths)."""
    db = AsyncMock()

    async def execute(stmt, *a, **kw):
        try:
            table = stmt.get_final_froms()[0].name
        except Exception:
            table = "default"
        if table == "projects":
            return scalar_first(project)
        if table == "chat_messages":
            return scalars_all(messages or [])
        if table == "chat_sessions":
            return scalar_first(session)
        return scalar_first(None)

    db.execute = execute
    return db


async def _make_client(db, user):
    async def override_get_db():
        yield db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()



def make_apply_db_defaults(db):
    """Factory of a fake commit/flush closure that emulates SQLAlchemy
    Python-side column defaults, PKs and timestamps for objects added to the
    session."""

    async def _apply():
        for call in db.add.call_args_list:
            obj = call.args[0]
            cls = type(obj)
            if cls.__name__ == "ChatSession":
                for attr, value in (("is_complete", False), ("message_count", 0), ("context", {})):
                    if getattr(obj, attr, None) is None:
                        setattr(obj, attr, value)
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)
        return None

    return _apply


def _user():
    return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")


@pytest.mark.asyncio
async def test_get_chat_returns_session_and_messages():
    project = make_project()
    db = db_dispatch({
        "projects": project,
        "chat_sessions": None,   # session missing -> created
        "chat_messages": [],
    })
    user = _user()

    db.commit = AsyncMock(side_effect=make_apply_db_defaults(db))
    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["session"]["is_complete"] is False
        assert data["session"]["clarification_context"] == {}
        db.add.assert_called()
        db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_chat_existing_session_returns_context():
    project = make_project(status="clarifying")
    session = ChatSession(project_id=project.id, context={"price": "12 млн"},
                          is_complete=False, message_count=0)
    db = db_dispatch({
        "projects": project,
        "chat_sessions": session,
        "chat_messages": [],
    })
    user = _user()

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session"]["clarification_context"] == {"price": "12 млн"}


@pytest.mark.asyncio
async def test_chat_foreign_project_404():
    db = db_dispatch({"projects": None})
    user = _user()

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_message_422_empty():
    db = db_dispatch({"projects": make_project()})
    user = _user()

    async for client in _make_client(db, user):
        resp = await client.post(
            f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat/message",
            json={"content": "   "},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_message_multi_field_context_update():
    """A message containing price + deadline + experience must fill ALL fields."""
    project = make_project(status="clarifying")
    session = ChatSession(project_id=project.id, context={})
    db = make_shared_db(project, session)
    db.flush = AsyncMock(side_effect=make_apply_db_defaults(db))
    db.commit = AsyncMock(side_effect=make_apply_db_defaults(db))
    user = _user()

    content = "Цена 12 млн тенге, срок 45 дней, опыт 10 проектов"
    with patch.object(
        ChatAgent, "answer",
        new_callable=AsyncMock,
        return_value=ChatReplyOutput(
            text="Есть ли лицензии?", message_field=None, is_complete=False
        ),
    ):
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat/message",
                json={"content": content},
            )
    assert resp.status_code == 200
    ctx = resp.json()["session_status"]["clarification_context"]
    assert ctx["price"] == content
    assert ctx["experience"] == content
    assert ctx["deadline_plan"] == content
    assert "licenses" not in ctx
    # project must NOT move to generating yet
    assert project.status == "clarifying"


@pytest.mark.asyncio
async def test_send_message_complete_moves_project_to_generating():
    project = make_project(status="clarifying")
    session = ChatSession(project_id=project.id, context={})
    db = make_shared_db(project, session)
    db.flush = AsyncMock(side_effect=make_apply_db_defaults(db))
    db.commit = AsyncMock(side_effect=make_apply_db_defaults(db))
    user = _user()

    with patch.object(
        ChatAgent, "answer",
        new_callable=AsyncMock,
        return_value=ChatReplyOutput(
            text="Спасибо! Вся информация собрана.",
            message_field="licenses",
            is_complete=True,
        ),
    ):
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat/message",
                json={"content": "Да, лицензии есть"},
            )
    assert resp.status_code == 200
    assert resp.json()["session_status"]["is_complete"] is True
    assert project.status == "generating"


@pytest.mark.asyncio
async def test_send_message_heuristic_fallback_on_llm_failure():
    """When the LLM is unavailable the endpoint still answers deterministically."""
    from app.ai.llm_client import AIServiceUnavailableError

    project = make_project(status="clarifying")
    session = ChatSession(project_id=project.id, context={})
    db = make_shared_db(project, session)
    db.flush = AsyncMock(side_effect=make_apply_db_defaults(db))
    db.commit = AsyncMock(side_effect=make_apply_db_defaults(db))
    user = _user()

    with patch("app.ai.chat_agent.call_llm", new_callable=AsyncMock,
              side_effect=AIServiceUnavailableError("quota")):
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/chat/message",
                json={"content": "Опыт: 5 проектов"},
            )
    assert resp.status_code == 200
    assert resp.json()["assistant_message"]["content"]
    assert "цену" in resp.json()["assistant_message"]["content"]


def test_classify_fields_multi_field():
    fields = classify_fields("Цена 12 млн тенге, срок 45 дней, опыт 10 проектов")
    assert set(fields) == {"experience", "price", "deadline_plan"}


def test_classify_fields_no_match_returns_empty():
    assert classify_fields("привет") == {}


def test_classify_fields_single_license():
    fields = classify_fields("Есть лицензия II категории")
    assert fields == {"licenses": "Есть лицензия II категории"}


def test_heuristic_reply_multi_field_advances_to_next_question():
    session = MagicMock()
    session.context = {}
    out = ChatAgent._heuristic_reply(
        session, "Цена 12 млн тенге, срок 45 дней, опыт 10 проектов", {}
    )
    assert out.is_complete is False
    assert "лицензи" in out.text
    assert out.message_field == "experience"


def test_heuristic_reply_complete_when_all_fields_present():
    session = MagicMock()
    session.context = {
        "experience": "5 проектов",
        "price": "12 млн",
        "deadline_plan": "45 дней",
        "licenses": "есть",
    }
    out = ChatAgent._heuristic_reply(session, "всё так", {})
    assert out.is_complete is True


def test_heuristic_reply_unknown_message_repeats_first_missing():
    session = MagicMock()
    session.context = {}
    out = ChatAgent._heuristic_reply(session, "не знаю", {})
    assert out.is_complete is False
    assert "опыт" in out.text