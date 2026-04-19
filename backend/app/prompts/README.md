# System Prompt — IdeaLens

**File:** `analysis_system.py`
**Current version:** `PROMPT_VERSION = "1.0"`

---

## Purpose

The system prompt instructs Claude to act as a rigorous idea analyst. On every initial analysis it covers 9 structured dimensions and emits a mandatory `<GRAPH_ACTIONS>` JSON block that drives the frontend graph visualization.

---

## Analysis Dimensions

| ID | Type key | Description |
|----|----------|-------------|
| 1 | `concept` | Core concept — what the idea is fundamentally about |
| 2 | `requirement` | Resources, skills, capital, time, dependencies |
| 3 | `gap` | Unknown or missing information that affects success |
| 4 | `benefit` | Genuine positive outcomes if the idea succeeds |
| 5 | `drawback` | Real risks, costs, and negative consequences |
| 6 | `feasibility` | 0–10 score with reasoning (0 = impossible, 10 = trivial) |
| 7 | `flaw` | Logical inconsistencies or false assumptions in the premise |
| 8 | `alternative` | Other approaches that might achieve the same goal |
| 9 | `question` | Open questions that would significantly affect the outcome |

Plus `root` — the central idea node, created at session start, never modified by the LLM.

---

## Graph Action Schema

Every LLM response **must** include a `<GRAPH_ACTIONS>` block (JSON array). Supported actions:

### `add` — add a node
```json
{
  "action": "add",
  "payload": {
    "id": "slug-id",
    "type": "concept",
    "label": "Short title (≤60 chars)",
    "content": "1–3 sentence explanation",
    "score": null,
    "parent_id": "root"
  }
}
```

### `update` — update an existing node
```json
{
  "action": "update",
  "payload": {
    "id": "existing-id",
    "label": "Updated label",
    "content": "Updated content"
  }
}
```

### `delete` — remove a node (root is protected)
```json
{
  "action": "delete",
  "payload": { "id": "node-id" }
}
```

### `connect` — add an edge between nodes
```json
{
  "action": "connect",
  "payload": {
    "source": "node-a",
    "target": "node-b",
    "label": "relationship label",
    "type": "optional-edge-type"
  }
}
```

---

## Parsing

`llm_service.parse_llm_response()` extracts the `<GRAPH_ACTIONS>...</GRAPH_ACTIONS>` block via regex, JSON-parses it, then Pydantic-validates each action against the discriminated union in `app/schemas/graph.py`. Invalid actions are silently dropped; the remainder are included in the `graph_actions` field of `LLMResponse`.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-04-04 | Initial system prompt — 9 dimensions, graph action schema, reconnection notes |
