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
    assert done_events[0]["final_text"] == "No appliances are currently due for maintenance."


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


class FakeInterrupt:
    def __init__(self, tool_use_id):
        # Mirrors Strands' real format (v1:before_tool_call:{tool_use_id}:{uuid5}) —
        # confirmations.pending_requests() only relies on the 3rd ':'-segment.
        self.id = f"v1:before_tool_call:{tool_use_id}:fake-uuid-suffix"
        self.reason = 'Approve "submit_maintenance_request"?\n  Input: {"appliance_id": ...}'


class InterruptedResult:
    stop_reason = "interrupt"
    interrupts = [FakeInterrupt("call_1"), FakeInterrupt("call_2")]
    message = {
        "role": "assistant",
        "content": [
            {
                "toolUse": {
                    "toolUseId": "call_1",
                    "name": "submit_maintenance_request",
                    "input": {"appliance_id": "a1", "action": "repair", "notes": "repair needed"},
                }
            },
            {
                "toolUse": {
                    "toolUseId": "call_2",
                    "name": "submit_maintenance_request",
                    "input": {"appliance_id": "a2", "action": "replace", "notes": "replace needed"},
                }
            },
        ],
    }

    def __str__(self):
        return str([{"id": i.id} for i in self.interrupts])


class InterruptedAgent:
    """Mimics an agent paused mid-run by the submit_maintenance_request approval gate."""

    def take_snapshot(self, preset=None):
        class FakeSnapshot:
            def to_dict(self):
                return {"messages": []}

        return FakeSnapshot()

    async def stream_async(self, prompt):
        yield {"result": InterruptedResult()}


class FakeConfirmationStorage:
    def __init__(self):
        self.saved: dict = {}

    def save_confirmation(self, confirmation_id, data):
        self.saved[confirmation_id] = data


EXPECTED_REQUESTS = [
    {
        "interrupt_id": "v1:before_tool_call:call_1:fake-uuid-suffix",
        "appliance_id": "a1",
        "action": "repair",
        "notes": "repair needed",
    },
    {
        "interrupt_id": "v1:before_tool_call:call_2:fake-uuid-suffix",
        "appliance_id": "a2",
        "action": "replace",
        "notes": "replace needed",
    },
]


@pytest.mark.asyncio
async def test_confirmation_required_without_storage_has_no_confirmation_id():
    events = [e async for e in stream_events(InterruptedAgent(), "check maintenance")]
    assert events == [
        {
            "type": "confirmation_required",
            "confirmation_id": None,
            "requests": EXPECTED_REQUESTS,
        }
    ]


@pytest.mark.asyncio
async def test_confirmation_required_persists_and_yields_confirmation_id():
    storage = FakeConfirmationStorage()
    events = [
        e async for e in stream_events(InterruptedAgent(), "check maintenance", storage=storage)
    ]

    assert len(events) == 1
    event = events[0]
    assert event["type"] == "confirmation_required"
    assert event["requests"] == EXPECTED_REQUESTS
    assert event["confirmation_id"] in storage.saved
    assert storage.saved[event["confirmation_id"]]["requests"] == EXPECTED_REQUESTS
