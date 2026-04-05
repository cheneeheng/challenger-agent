from pydantic import BaseModel, field_validator

from app.schemas.graph import AnalysisGraph


class ChatRequest(BaseModel):
    session_id: str
    message: str
    graph_state: AnalysisGraph
    model: str

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        from app.core.config import get_settings

        allowed = get_settings().ALLOWED_CLAUDE_MODELS
        if v not in allowed:
            raise ValueError(f"Model must be one of: {allowed}")
        return v


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    message_index: int
    created_at: str

    model_config = {"from_attributes": True}
