# Import all models so Alembic autogenerate can discover them.
from app.db.models.user import User  # noqa: F401
from app.db.models.refresh_token import RefreshToken  # noqa: F401
from app.db.models.session import Session  # noqa: F401
from app.db.models.message import Message  # noqa: F401
