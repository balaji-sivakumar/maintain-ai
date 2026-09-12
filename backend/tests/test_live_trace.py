import pytest

from live_trace import stream_events


class FakeResult:
    stop_reason = "end_turn"
    interrupts = None

    def __str__(self):
        return "No appliances are currently due for maintenance."


class FakeAgent:
    """Mimics the subset of Strands' raw stream_async event shapes that
    stream_events() actually reads, captured from a real run."""

    async def stream_async(self, prompt):
        events = [
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "call_1",
                                "name": "check_due_maintenance",
                                "input": {},
                            }
                        }
                    ],
                }
            },
            {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "call_1",
                                "status": "success",
                                "content": [{"text": "[]"}],
                            }
                        }
                    ],
                }
            },
            {"data": "No appliances"},
            {"data": " are due."},
            {"result": FakeResult()},
        ]
        for event in events:
            yield event


@pytest.mark.asyncio
async def test_stream_events_transforms_tool_call_and_result():
    events = [e async for e in stream_events(FakeAgent(), "check maintenance")]

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    tool_results = [e for e in events if e["type"] == "tool_result"]

    assert tool_calls == [
        {"type": "tool_call", "tool_use_id": "call_1", "name": "check_due_maintenance", "input": {}}
    ]
    assert tool_results == [
        {
            "type": "tool_result",
            "tool_use_id": "call_1",
            "name": "check_due_maintenance",
            "status": "success",
            "output": "[]",
        }
    ]


@pytest.mark.asyncio
async def test_stream_events_forwards_text_deltas_and_done():
    events = [e async for e in stream_events(FakeAgent(), "check maintenance")]

    text_deltas = [e for e in events if e["type"] == "text_delta"]
    done_events = [e for e in events if e["type"] == "done"]

    assert [e["content"] for e in text_deltas] == ["No appliances", " are due."]
    assert len(done_events) == 1
    # The raw AgentResult, unmodified — stream_events doesn't shape a wire
    # payload, it just reports what happened. Turning it into
    # {"final_text": ...} (or a confirmation payload) is the caller's job.
    assert str(done_events[0]["result"]) == "No appliances are currently due for maintenance."


@pytest.mark.asyncio
async def test_tool_result_falls_back_to_unknown_name_if_call_never_seen():
    class OrphanResultAgent:
        async def stream_async(self, prompt):
            yield {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "call_missing",
                                "status": "success",
                                "content": [{"text": "ok"}],
                            }
                        }
                    ],
                }
            }

    events = [e async for e in stream_events(OrphanResultAgent(), "x")]
    assert events == [
        {
            "type": "tool_result",
            "tool_use_id": "call_missing",
            "name": "unknown",
            "status": "success",
            "output": "ok",
        }
    ]


@pytest.mark.asyncio
async def test_stream_events_reports_interrupted_without_touching_storage():
    """stream_events has no idea what a paused run means — it just tells the
    caller "interrupted" and hands back the raw result. Persisting a
    confirmation is confirmations.confirmation_required_response()'s job,
    exercised separately in test_confirmations.py."""

    class InterruptedResult:
        stop_reason = "interrupt"
        interrupts = ["fake-interrupt"]

    class InterruptedAgent:
        async def stream_async(self, prompt):
            yield {"result": InterruptedResult()}

    events = [e async for e in stream_events(InterruptedAgent(), "check maintenance")]

    assert len(events) == 1
    assert events[0]["type"] == "interrupted"
    assert events[0]["result"].stop_reason == "interrupt"
