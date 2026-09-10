"""Live tool-trace event stream — reduces Strands' verbose internal
streaming events (async-iterator, includes token-by-token deltas of tool
call arguments) down to a handful of clean, JSON-serializable events for a
frontend: tool_call, tool_result, text_delta, done.

This is the EventStream interface from ARCHITECTURE.md's "Live tool trace"
section, minus a formal ABC — there's only ever one implementation, and it's
a thin transform over Strands' own event stream rather than a pluggable
backend like Storage/VectorStore.
"""

from typing import Any, AsyncIterator

from strands import Agent


def _extract_tool_result_text(tool_result: dict[str, Any]) -> str:
    parts = [block["text"] for block in tool_result.get("content", []) if "text" in block]
    return "\n".join(parts)


async def stream_events(agent: Agent, prompt: str) -> AsyncIterator[dict[str, Any]]:
    """Run one agent turn, yielding simplified trace events as it executes.

    tool_call/tool_result carry the same tool_use_id, so a consumer can
    correlate them exactly rather than guessing by name+order — the same
    tool (e.g. draft_service_reminder) is typically called once per
    appliance in a batch, so name alone isn't a reliable key.
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
            yield {"type": "done", "final_text": str(event["result"])}
