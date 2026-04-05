import asyncio
import json
import re

from anthropic import (
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message
from app.schemas.graph import AnalysisGraph, LLMGraphAction, LLMResponse
from app.core.config import get_settings

GRAPH_ACTIONS_RE = re.compile(
    r"<GRAPH_ACTIONS>(.*?)</GRAPH_ACTIONS>", re.DOTALL
)
_action_adapter: TypeAdapter[LLMGraphAction] = TypeAdapter(LLMGraphAction)


def build_messages(
    messages: list[Message],
    graph_state: AnalysisGraph,
    user_message: str,
    context_summary: str | None = None,
    context_summary_covers_up_to: int | None = None,
) -> list[dict]:
    settings = get_settings()
    result: list[dict] = []

    if context_summary and context_summary_covers_up_to is not None:
        result.append(
            {
                "role": "user",
                "content": f"[Previous conversation summary]: {context_summary}",
            }
        )
        result.append(
            {"role": "assistant", "content": "Understood. Continuing from the summary."}
        )
        messages = [
            m for m in messages if m.message_index > context_summary_covers_up_to
        ]

    recent = messages[-settings.CONTEXT_WINDOW_MAX_MESSAGES :]
    for m in recent:
        if m.role == "assistant":
            result.append({"role": "assistant", "content": m.content})
        else:
            prefix = "[Context]: " if m.role == "system" else ""
            result.append({"role": "user", "content": f"{prefix}{m.content}"})

    result.append(
        {
            "role": "user",
            "content": f"[Current graph state]:\n{graph_state.model_dump_json(indent=2)}",
        }
    )
    result.append({"role": "user", "content": user_message})
    return result


async def stream_with_heartbeat(
    messages: list[dict], model: str, api_key: str
):
    """Async generator yielding (event_type, data) tuples."""
    from app.prompts.analysis_system import SYSTEM_PROMPT

    queue: asyncio.Queue = asyncio.Queue()
    full_text = ""

    async def llm_producer() -> None:
        nonlocal full_text
        try:
            client = AsyncAnthropic(api_key=api_key)
            async with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                async for chunk in stream.text_stream:
                    full_text += chunk
                    await queue.put(("token", chunk))
            llm_response = parse_llm_response(full_text)
            await queue.put(("parsed", llm_response))
        except AuthenticationError:
            await queue.put(
                ("error", "Invalid API key. Please update it in Settings.")
            )
        except RateLimitError:
            await queue.put(("error", "Rate limit reached. Please wait a moment."))
        except APIStatusError as e:
            msg = (
                "Anthropic is overloaded. Please try again."
                if e.status_code == 529
                else "An error occurred with the Anthropic API."
            )
            await queue.put(("error", msg))
        except Exception:
            await queue.put(("error", "An unexpected error occurred."))
        finally:
            await queue.put(("done", None))

    async def ping_producer() -> None:
        while True:
            await asyncio.sleep(15)
            await queue.put(("ping", None))

    llm_task = asyncio.create_task(llm_producer())
    ping_task = asyncio.create_task(ping_producer())
    try:
        while True:
            event_type, data = await queue.get()
            yield event_type, data
            if event_type in ("done", "error"):
                break
    finally:
        ping_task.cancel()
        llm_task.cancel()


def parse_llm_response(raw_text: str) -> LLMResponse:
    match = GRAPH_ACTIONS_RE.search(raw_text)
    natural_language = GRAPH_ACTIONS_RE.sub("", raw_text).strip()
    if not match:
        return LLMResponse(message=natural_language, graph_actions=[])
    try:
        raw_actions = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return LLMResponse(message=natural_language, graph_actions=[])
    valid: list[LLMGraphAction] = []
    for raw in raw_actions:
        try:
            valid.append(_action_adapter.validate_python(raw))
        except ValidationError:
            pass
    return LLMResponse(message=natural_language, graph_actions=valid)


async def summarize_messages(messages: list[Message], api_key: str) -> str:
    client = AsyncAnthropic(api_key=api_key)
    content = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
    resp = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize concisely. Preserve key decisions, insights, "
                    "node modifications, open questions, and analysis direction.\n\n"
                    f"{content}"
                ),
            }
        ],
    )
    return resp.content[0].text  # type: ignore[union-attr]


async def persist_messages(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    assistant_text: str,
    graph_actions: list,
    message_uuid: str,
) -> None:
    async with db.begin_nested():
        result = await db.execute(
            select(func.max(Message.message_index))
            .where(Message.session_id == session_id)
            .with_for_update()
        )
        max_index = result.scalar() or -1

        db.add(
            Message(
                session_id=session_id,
                role="user",
                content=user_message,
                message_index=max_index + 1,
            )
        )
        db.add(
            Message(
                id=message_uuid,
                session_id=session_id,
                role="assistant",
                content=assistant_text,
                message_index=max_index + 2,
                metadata_={
                    "graph_actions": [a.model_dump() for a in graph_actions]
                },
            )
        )
