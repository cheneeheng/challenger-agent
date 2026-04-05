from datetime import datetime

from pydantic import BaseModel

from app.schemas.chat import MessageResponse
from app.schemas.graph import AnalysisGraph


class CreateSessionRequest(BaseModel):
    idea: str
    selected_model: str = "claude-sonnet-4-6"


class UpdateSessionRequest(BaseModel):
    name: str | None = None
    selected_model: str | None = None


class SessionListItem(BaseModel):
    id: str
    name: str
    idea: str
    selected_model: str
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: str
    name: str
    idea: str
    selected_model: str
    graph_state: dict
    context_summary: str | None
    messages: list[MessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    items: list[SessionListItem]
    total: int
    page: int
    limit: int


class UpdateGraphRequest(BaseModel):
    graph_state: AnalysisGraph
