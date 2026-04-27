from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings


_settings = get_settings()

# Neon PostgreSQL requires SSL; asyncpg connect_args is the safest injection point
# because it avoids URL-parsing edge cases with query strings.
_connect_args: dict = {}
if "neon.tech" in _settings.DATABASE_URL:
    _connect_args["ssl"] = True

engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.ENVIRONMENT == "development",
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
