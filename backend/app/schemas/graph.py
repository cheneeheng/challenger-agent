from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator


class DimensionType(StrEnum):
    ROOT = "root"
    CONCEPT = "concept"
    REQUIREMENT = "requirement"
    GAP = "gap"
    BENEFIT = "benefit"
    DRAWBACK = "drawback"
    FEASIBILITY = "feasibility"
    FLAW = "flaw"
    ALTERNATIVE = "alternative"
    QUESTION = "question"


class NodePosition(BaseModel):
    x: float
    y: float


class AnalysisNode(BaseModel):
    id: str
    type: DimensionType
    label: str
    content: str
    score: float | None = None
    parent_id: str | None = None
    position: NodePosition = Field(default_factory=lambda: NodePosition(x=0, y=0))
    userPositioned: bool = False


class AnalysisEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None
    type: str | None = None


class AnalysisGraph(BaseModel):
    nodes: list[AnalysisNode] = Field(default_factory=list)
    edges: list[AnalysisEdge] = Field(default_factory=list)

    @field_validator("nodes")
    @classmethod
    def validate_node_count(cls, v: list[AnalysisNode]) -> list[AnalysisNode]:
        if len(v) > 200:
            raise ValueError("Graph cannot have more than 200 nodes")
        return v

    @field_validator("edges")
    @classmethod
    def validate_edge_count(cls, v: list[AnalysisEdge]) -> list[AnalysisEdge]:
        if len(v) > 400:
            raise ValueError("Graph cannot have more than 400 edges")
        return v


# --- LLM graph actions ---


class NodePayload(BaseModel):
    id: str
    type: DimensionType
    label: str
    content: str
    score: float | None = None
    parent_id: str | None = None


class AddNodeAction(BaseModel):
    action: Literal["add"]
    payload: NodePayload


class UpdateNodePayload(BaseModel):
    id: str
    label: str | None = None
    content: str | None = None


class UpdateNodeAction(BaseModel):
    action: Literal["update"]
    payload: UpdateNodePayload


class DeleteNodePayload(BaseModel):
    id: str


class DeleteNodeAction(BaseModel):
    action: Literal["delete"]
    payload: DeleteNodePayload


class ConnectPayload(BaseModel):
    source: str
    target: str
    label: str | None = None
    type: str | None = None


class ConnectAction(BaseModel):
    action: Literal["connect"]
    payload: ConnectPayload


LLMGraphAction = Annotated[
    Union[AddNodeAction, UpdateNodeAction, DeleteNodeAction, ConnectAction],
    Field(discriminator="action"),
]


class LLMResponse(BaseModel):
    message: str
    graph_actions: list[LLMGraphAction]
