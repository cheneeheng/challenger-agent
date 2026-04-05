from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.session import Session as DBSession
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.session import (
    CreateSessionRequest,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
    UpdateGraphRequest,
    UpdateSessionRequest,
)

router = APIRouter(prefix="/api/sessions")


def _build_initial_graph(idea: str) -> dict:
    return {
        "nodes": [
            {
                "id": "root",
                "type": "root",
                "label": idea[:80],
                "content": idea,
                "score": None,
                "parent_id": None,
                "position": {"x": 400, "y": 300},
                "userPositioned": False,
            }
        ],
        "edges": [],
    }


def _to_response(session: DBSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        name=session.name,
        idea=session.idea,
        selected_model=session.selected_model,
        graph_state=session.graph_state,
        context_summary=session.context_summary,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    offset = (page - 1) * limit

    total_result = await db.execute(
        select(func.count(DBSession.id)).where(DBSession.user_id == current_user.id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(DBSession)
        .where(DBSession.user_id == current_user.id)
        .order_by(DBSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    sessions = result.scalars().all()

    return SessionListResponse(
        items=[SessionListItem.model_validate(s) for s in sessions],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    session = DBSession(
        user_id=current_user.id,
        idea=body.idea,
        name=body.idea[:60],
        selected_model=body.selected_model,
        graph_state=_build_initial_graph(body.idea),
    )
    db.add(session)
    await db.flush()
    return _to_response(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(
        select(DBSession)
        .where(DBSession.id == session_id)
        .options(selectinload(DBSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return _to_response(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    session = await db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if body.name is not None:
        session.name = body.name
    if body.selected_model is not None:
        from app.core.config import get_settings
        if body.selected_model not in get_settings().ALLOWED_CLAUDE_MODELS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid model",
            )
        session.selected_model = body.selected_model

    db.add(session)
    return _to_response(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    session = await db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    await db.delete(session)


@router.put("/{session_id}/graph", status_code=204)
async def update_graph(
    session_id: str,
    body: UpdateGraphRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    session = await db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    session.graph_state = body.graph_state.model_dump()
    db.add(session)
