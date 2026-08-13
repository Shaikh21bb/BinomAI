import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.project import Project
from app.schemas.user import UserResponse
from app.schemas.chat import (
    ChatReplyRequest,
    ChatReplyOut,
    ChatSessionOut,
    ChatThreadOut,
    ChatMessageOut,
)
from app.ai.chat_agent import ChatAgent, classify_fields

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["chat"])


async def _ensure_project(db: AsyncSession, project_id: uuid.UUID, user: UserResponse) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == user.company_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")
    return project


def _to_out(message: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        message_type=message.message_type,
        created_at=message.created_at,
    )


async def _session_out(db: AsyncSession, session: ChatSession) -> ChatSessionOut:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.project_id == session.project_id)
    )
    count = len(result.scalars().all())
    return ChatSessionOut(
        is_complete=session.is_complete,
        message_count=count,
        clarification_context=session.context or {},
    )


async def _load_messages(db: AsyncSession, project_id: uuid.UUID):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at)
    )
    return result.scalars().all()


@router.get("/{project_id}/chat", response_model=ChatThreadOut)
async def get_chat(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(get_current_user),
):
    project = await _ensure_project(db, project_id, user)
    result = await db.execute(
        select(ChatSession).where(ChatSession.project_id == project.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        session = ChatSession(project_id=project.id, context={})
        db.add(session)
        await db.commit()

    messages = await _load_messages(db, project.id)
    return ChatThreadOut(
        messages=[_to_out(m) for m in messages],
        session=await _session_out(db, session),
    )


@router.post("/{project_id}/chat/message", response_model=ChatReplyOut)
async def send_message(
    project_id: uuid.UUID,
    payload: ChatReplyRequest,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(get_current_user),
):
    project = await _ensure_project(db, project_id, user)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Пустое сообщение")

    result = await db.execute(
        select(ChatSession).where(ChatSession.project_id == project.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        session = ChatSession(project_id=project.id, context={})
        db.add(session)

    user_message = ChatMessage(
        project_id=project.id,
        role="user",
        content=content,
        message_type="text",
    )
    db.add(user_message)
    await db.flush()

    messages = await _load_messages(db, project.id)
    reply = await ChatAgent.answer(
        db, project, str(user.company_id), content, session, messages
    )

    update = dict(classify_fields(content))
    if not update and reply.message_field:
        update = {reply.message_field: content}
    session.context = ChatAgent._merge_context(
        session.context, update, reply.message_field
    )
    session.is_complete = reply.is_complete
    session.message_count = len(messages) + 1

    if reply.is_complete and project.status in ("clarifying", "analyzing", "draft"):
        project.status = "generating"
        db.add(project)

    assistant_message = ChatMessage(
        project_id=project.id,
        role="assistant",
        content=reply.text,
        message_type="text",
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    result = await db.execute(
        select(ChatSession).where(ChatSession.project_id == project.id)
    )
    session = result.scalar_one()
    return ChatReplyOut(
        assistant_message=_to_out(assistant_message),
        session_status=await _session_out(db, session),
    )