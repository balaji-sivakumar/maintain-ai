"""Live tool-trace event stream — reduces Strands' verbose internal
streaming events (async-iterator, includes token-by-token deltas of tool
call arguments) down to a handful of clean, JSON-serializable events for a
frontend: tool_call, tool_result, text_delta, done, confirmation_required.

This is the EventStream interface from ARCHITECTURE.md's "Live tool trace"
section, minus a formal ABC — there's only ever one implementation, and it's
a thin transform over Strands' own event stream rather than a pluggable
backend like Storage/VectorStore.
"""

from typing import Any, AsyncIterator, Optional

from strands import Agent

from confirmations import pending_requests, persist_if_interrupted
from interfaces.storage import Storage


def _extract_tool_result_text(tool_result: dict[str, Any]) -> str:
    parts = [block["text"] for block in tool_result.get("content", []) if "text" in block]
    return "\n".join(parts)


async def stream_events(
    agent: Agent, prompt: str, storage: Optional[Storage] = None
) -> AsyncIterator[dict[str, Any]]:
    """Run one agent turn, yielding simplified trace events as it executes.

    tool_call/tool_result carry the same tool_use_id, so a consumer can
    correlate them exactly rather than guessing by name+order — the same
    tool (e.g. draft_service_reminder) is typically called once per
    appliance in a batch, so name alone isn't a reliable key.

    If the run pauses on the submit_maintenance_request approval gate (Day
    6) and `storage` is given, the paused state is snapshotted and persisted
    here (see confirmations.py) so a later, separate request can resume it
    — the yielded confirmation_id is what that request looks it up by.
    Without `storage` (e.g. in tests that don't care about persistence), the
    pause is still reported but confirmation_id is None.
    """
    tool_names: dict[str, str] = {}

    async for event in agent.stream_async(prompt):
        message = event.get("message")
        if message:
            role = message.get("role")
            for block in message.get("content", []):
                if role == "assistant" and "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_names[tool_use["toolUseId"]] = tool_use["name"]
                    yield {
                        "type": "tool_call",
                        "tool_use_id": tool_use["toolUseId"],
                        "name": tool_use["name"],
                        "input": tool_use.get("input", {}),
                    }
                elif role == "user" and "toolResult" in block:
                    tool_result = block["toolResult"]
                    yield {
                        "type": "tool_result",
                        "tool_use_id": tool_result["toolUseId"],
                        "name": tool_names.get(tool_result["toolUseId"], "unknown"),
                        "status": tool_result.get("status"),
                        "output": _extract_tool_result_text(tool_result),
                    }

        if "data" in event:
            yield {"type": "text_delta", "content": event["data"]}

        if "result" in event:
            result = event["result"]
            if result.stop_reason == "interrupt" and result.interrupts:
                confirmation = persist_if_interrupted(storage, agent, result) if storage else None
                yield {
                    "type": "confirmation_required",
                    "confirmation_id": confirmation["id"] if confirmation else None,
                    "requests": confirmation["requests"] if confirmation else pending_requests(result),
                }
            else:
                yield {"type": "done", "final_text": str(result)}
