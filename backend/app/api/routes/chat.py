import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models.message import Message
from app.db.models.session import Session as DBSession
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.chat import ChatRequest
from app.services import encryption_service, llm_service

router = APIRouter()

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/api/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    result = await db.execute(
        select(DBSession)
        .where(DBSession.id == body.session_id)
        .options(selectinload(DBSession.messages))
    )
    session = result.scalar_one_or_none()

    if not session or session.user_id != current_user.id:

        async def forbidden():
            yield "event: error\ndata: Session not found.\n\n"
            yield "event: done\ndata: [DONE]\n\n"

        return StreamingResponse(forbidden(), media_type="text/event-stream")

    if not current_user.encrypted_api_key:

        async def no_key():
            yield "event: error\ndata: Please set your Anthropic API key in Settings.\n\n"
            yield "event: done\ndata: [DONE]\n\n"

        return StreamingResponse(no_key(), media_type="text/event-stream")

    api_key = encryption_service.decrypt_api_key(current_user.encrypted_api_key)

    # SSE reconnection check
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        msg_result = await db.execute(
            select(Message).where(
                Message.id == last_event_id,
                Message.role == "assistant",
                Message.session_id == body.session_id,
            )
        )
        completed = msg_result.scalar_one_or_none()
        if completed:
            return StreamingResponse(
                _replay_completed(completed),
                media_type="text/event-stream",
                headers=_SSE_HEADERS,
            )

    # Context management — capture messages and summary before any commit so
    # that accessing them later does not trigger an expired-attribute lazy-load.
    settings = get_settings()
    messages = list(session.messages)
    context_summary = session.context_summary
    context_summary_covers_up_to = session.context_summary_covers_up_to

    if len(messages) > settings.CONTEXT_WINDOW_MAX_MESSAGES and not context_summary:
        to_summarize = messages[: -settings.CONTEXT_WINDOW_MAX_MESSAGES]
        context_summary = await llm_service.summarize_messages(to_summarize, api_key)
        context_summary_covers_up_to = to_summarize[-1].message_index
        session.context_summary = context_summary
        session.context_summary_covers_up_to = context_summary_covers_up_to
        await db.commit()

    llm_messages = llm_service.build_messages(
        messages=messages,
        graph_state=body.graph_state,
        user_message=body.message,
        context_summary=context_summary,
        context_summary_covers_up_to=context_summary_covers_up_to,
    )

    message_uuid = str(uuid4())

    return StreamingResponse(
        _stream(db, session, body, llm_messages, api_key, message_uuid),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _stream(db, session, body, llm_messages, api_key, message_uuid):
    full_text = ""
    graph_actions = []
    had_error = False

    async for event_type, data in llm_service.stream_with_heartbeat(
        llm_messages, body.model, api_key
    ):
        if event_type == "token":
            full_text += data
            yield f"id: {message_uuid}\nevent: token\ndata: {data}\n\n"
        elif event_type == "parsed":
            graph_actions = data.graph_actions
            for action in data.graph_actions:
                yield f"id: {message_uuid}\nevent: graph_action\ndata: {json.dumps(action.model_dump())}\n\n"
        elif event_type == "ping":
            yield "event: ping\ndata: \n\n"
        elif event_type == "error":
            had_error = True
            yield f"event: error\ndata: {data}\n\n"
        elif event_type == "done":
            break

    if not had_error and full_text:
        await llm_service.persist_messages(
            db, session.id, body.message, full_text, graph_actions, message_uuid
        )

    yield f"id: {message_uuid}\nevent: done\ndata: [DONE]\n\n"


async def _replay_completed(message: Message):
    actions = (message.metadata_ or {}).get("graph_actions", [])
    for action in actions:
        yield f"id: {message.id}\nevent: graph_action\ndata: {json.dumps(action)}\n\n"
    yield f"id: {message.id}\nevent: done\ndata: [DONE]\n\n"
