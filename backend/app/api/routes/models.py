from fastapi import APIRouter

from app.schemas.models import ModelInfo

router = APIRouter(prefix="/api/models")

MODELS: list[ModelInfo] = [
    ModelInfo(
        id="claude-haiku-4-5",
        display_name="Claude Haiku",
        description="Fastest — good for quick analysis and testing",
    ),
    ModelInfo(
        id="claude-sonnet-4-6",
        display_name="Claude Sonnet",
        description="Balanced — high quality, reliable (default)",
    ),
    ModelInfo(
        id="claude-opus-4-6",
        display_name="Claude Opus",
        description="Most thorough — highest quality, slower",
    ),
]


@router.get("", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    return MODELS
