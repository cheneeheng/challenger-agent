"""Unit tests for Pydantic schemas — validation edge cases."""

import pytest
from pydantic import ValidationError

from app.schemas.graph import AnalysisEdge, AnalysisGraph, AnalysisNode, DimensionType
from app.schemas.user import SetApiKeyRequest
from app.schemas.chat import ChatRequest


# ---------------------------------------------------------------------------
# AnalysisGraph validators
# ---------------------------------------------------------------------------


def _make_node(node_id: str) -> dict:
    return {
        "id": node_id,
        "type": "concept",
        "label": "L",
        "content": "C",
        "position": {"x": 0, "y": 0},
    }


def _make_edge(edge_id: str) -> dict:
    return {"id": edge_id, "source": "a", "target": "b"}


def test_analysis_graph_valid():
    g = AnalysisGraph(nodes=[AnalysisNode(**_make_node("n1"))], edges=[])
    assert len(g.nodes) == 1


def test_analysis_graph_too_many_nodes():
    nodes = [AnalysisNode(**_make_node(f"n{i}")) for i in range(201)]
    with pytest.raises(ValidationError, match="200 nodes"):
        AnalysisGraph(nodes=nodes, edges=[])


def test_analysis_graph_exactly_200_nodes_ok():
    nodes = [AnalysisNode(**_make_node(f"n{i}")) for i in range(200)]
    g = AnalysisGraph(nodes=nodes, edges=[])
    assert len(g.nodes) == 200


def test_analysis_graph_too_many_edges():
    edges = [AnalysisEdge(**_make_edge(f"e{i}")) for i in range(401)]
    with pytest.raises(ValidationError, match="400 edges"):
        AnalysisGraph(nodes=[], edges=edges)


def test_analysis_graph_exactly_400_edges_ok():
    edges = [AnalysisEdge(**_make_edge(f"e{i}")) for i in range(400)]
    g = AnalysisGraph(nodes=[], edges=edges)
    assert len(g.edges) == 400


# ---------------------------------------------------------------------------
# SetApiKeyRequest validator
# ---------------------------------------------------------------------------


def test_set_api_key_valid():
    req = SetApiKeyRequest(api_key="sk-ant-abc123")
    assert req.api_key == "sk-ant-abc123"


def test_set_api_key_invalid_prefix():
    with pytest.raises(ValidationError, match="sk-ant-"):
        SetApiKeyRequest(api_key="sk-openai-123")


def test_set_api_key_empty_string():
    with pytest.raises(ValidationError, match="sk-ant-"):
        SetApiKeyRequest(api_key="")


# ---------------------------------------------------------------------------
# ChatRequest model validator — happy path (covers the `return v` branch)
# ---------------------------------------------------------------------------

_VALID_GRAPH = {
    "nodes": [
        {
            "id": "root",
            "type": "root",
            "label": "root",
            "content": "root",
            "position": {"x": 0, "y": 0},
        }
    ],
    "edges": [],
}


def test_chat_request_valid_model():
    req = ChatRequest(
        session_id="s1",
        message="hello",
        graph_state=_VALID_GRAPH,
        model="claude-sonnet-4-6",
    )
    assert req.model == "claude-sonnet-4-6"


def test_chat_request_all_allowed_models():
    from app.core.config import get_settings

    for model in get_settings().ALLOWED_CLAUDE_MODELS:
        req = ChatRequest(
            session_id="s1",
            message="hello",
            graph_state=_VALID_GRAPH,
            model=model,
        )
        assert req.model == model


def test_chat_request_invalid_model():
    with pytest.raises(ValidationError):
        ChatRequest(
            session_id="s1",
            message="hello",
            graph_state=_VALID_GRAPH,
            model="gpt-4o",
        )


# ---------------------------------------------------------------------------
# DimensionType enum coverage
# ---------------------------------------------------------------------------


def test_dimension_type_all_values():
    expected = {
        "root", "concept", "requirement", "gap", "benefit",
        "drawback", "feasibility", "flaw", "alternative", "question",
    }
    actual = {t.value for t in DimensionType}
    assert actual == expected
