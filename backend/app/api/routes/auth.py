from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)


router = APIRouter(prefix="/auth")
limiter = Limiter(key_func=get_remote_address)


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * settings.REFRESH_TOKEN_EXPIRE_DAYS,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/auth")


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/15minutes")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    settings = get_settings()
    refresh_token = create_refresh_token(user.id)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    db.add(RefreshToken(token=refresh_token, user_id=user.id, expires_at=expires_at))

    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    settings = get_settings()
    refresh_token = create_refresh_token(user.id)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    db.add(RefreshToken(token=refresh_token, user_id=user.id, expires_at=expires_at))

    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token"
        )

    try:
        user_id = verify_token(refresh_token, expected_type="refresh")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == refresh_token)
    )
    stored = result.scalar_one_or_none()
    if not stored or stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )

    # Rotate token
    settings = get_settings()
    new_refresh = create_refresh_token(user_id)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await db.delete(stored)
    db.add(RefreshToken(token=new_refresh, user_id=user_id, expires_at=expires_at))

    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=create_access_token(user_id))


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> None:
    if refresh_token:
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        stored = result.scalar_one_or_none()
        if stored:
            await db.delete(stored)
    _clear_refresh_cookie(response)
