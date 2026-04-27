from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.auth import UserResponse
from app.schemas.user import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    SetApiKeyRequest,
    UpdateProfileRequest,
)
from app.services.auth_service import hash_password, verify_password
from app.services import encryption_service

router = APIRouter(prefix="/api/users")


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        has_api_key=user.encrypted_api_key is not None,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    current_user.name = body.name
    db.add(current_user)
    return _user_response(current_user)


@router.post("/me/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(body.new_password)
    db.add(current_user)


@router.post("/me/api-key", response_model=UserResponse)
async def set_api_key(
    body: SetApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # Validate against Anthropic before storing
    import anthropic

    try:
        client = anthropic.AsyncAnthropic(api_key=body.api_key)
        await client.models.list()
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Anthropic API key",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not validate API key. Check your connection.",
        )

    current_user.encrypted_api_key = encryption_service.encrypt_api_key(body.api_key)
    db.add(current_user)
    return _user_response(current_user)


@router.delete("/me/api-key", response_model=UserResponse)
async def delete_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    current_user.encrypted_api_key = None
    db.add(current_user)
    return _user_response(current_user)


@router.delete("/me", status_code=204)
async def delete_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(body.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
    await db.delete(current_user)
