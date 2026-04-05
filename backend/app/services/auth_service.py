from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": user_id, "exp": exp}, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM
    )


def create_refresh_token(user_id: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "exp": exp, "type": "refresh"},
        s.JWT_SECRET,
        algorithm=s.JWT_ALGORITHM,
    )


def verify_token(token: str, expected_type: str = "access") -> str:
    """Returns user_id. Raises JWTError on invalid/expired token."""
    s = get_settings()
    payload = jwt.decode(token, s.JWT_SECRET, algorithms=[s.JWT_ALGORITHM])
    if expected_type == "refresh" and payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    user_id = payload.get("sub")
    if not user_id:
        raise JWTError("Missing sub claim")
    return user_id
