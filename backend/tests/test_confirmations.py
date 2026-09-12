import pytest

from confirmations import (
    confirmation_required_response,
    pending_requests,
    persist_if_interrupted,
    resume_confirmation,
)


def _interrupt_id(tool_use_id: str) -> str:
    # Mirrors Strands' real format (v1:before_tool_call:{tool_use_id}:{uuid5}) —
    # pending_requests() only relies on tool_use_id being the 3rd ':'-segment.
    return f"v1:before_tool_call:{tool_use_id}:fake-uuid-suffix"


class FakeStorage:
    def __init__(self):
        self._confirmations: dict = {}

    def save_confirmation(self, confirmation_id, data):
        self._confirmations[confirmation_id] = data

    def get_confirmation(self, confirmation_id):
        return self._confirmations.get(confirmation_id)

    def delete_confirmation(self, confirmation_id):
        self._confirmations.pop(confirmation_id, None)


FAKE_SNAPSHOT_DICT = {
    "scope": "agent",
    "schema_version": "1.0",
    "created_at": "2026-01-01T00:00:00Z",
    "data": {},
    "app_data": {},
}


class FakeSnapshot:
    def to_dict(self):
        return FAKE_SNAPSHOT_DICT


class FakeInterrupt:
    def __init__(self, tool_use_id: str):
        self.id = _interrupt_id(tool_use_id)
        self.reason = f'Approve "submit_maintenance_request"?\n  Input: {{"appliance_id": ...}}'


def _tool_use_block(tool_use_id: str, appliance_id: str, action: str) -> dict:
    return {
        "toolUse": {
            "toolUseId": tool_use_id,
            "name": "submit_maintenance_request",
            "input": {"appliance_id": appliance_id, "action": action, "notes": f"{action} needed"},
        }
    }


class FakeResult:
    def __init__(self, stop_reason="end_turn", interrupts=None, content=None):
        self.stop_reason = stop_reason
        self.interrupts = interrupts
        self.message = {"role": "assistant", "content": content or []}


class FakeAgent:
    def __init__(self, resume_result=None):
        self.snapshot_taken = False
        self.loaded_snapshot = None
        self.resume_call = None
        self._resume_result = resume_result or FakeResult()

    def take_snapshot(self, preset=None):
        self.snapshot_taken = True
        return FakeSnapshot()

    def load_snapshot(self, snapshot):
        self.loaded_snapshot = snapshot

    def __call__(self, prompt):
        self.resume_call = prompt
        return self._resume_result


def test_pending_requests_matches_interrupts_to_structured_tool_input():
    content = [
        _tool_use_block("call_1", "a1", "repair"),
        _tool_use_block("call_2", "a2", "replace"),
    ]
    result = FakeResult(
        stop_reason="interrupt",
        interrupts=[FakeInterrupt("call_1"), FakeInterrupt("call_2")],
        content=content,
    )

    requests = pending_requests(result)

    assert requests == [
        {
            "interrupt_id": _interrupt_id("call_1"),
            "appliance_id": "a1",
            "action": "repair",
            "notes": "repair needed",
        },
        {
            "interrupt_id": _interrupt_id("call_2"),
            "appliance_id": "a2",
            "action": "replace",
            "notes": "replace needed",
        },
    ]


def test_persist_if_interrupted_returns_none_on_normal_completion():
    storage = FakeStorage()
    agent = FakeAgent()
    result = FakeResult(stop_reason="end_turn", interrupts=None)

    assert persist_if_interrupted(storage, agent, result) is None
    assert storage._confirmations == {}
    assert not agent.snapshot_taken


def test_persist_if_interrupted_saves_all_pending_requests_and_snapshot():
    storage = FakeStorage()
    agent = FakeAgent()
    content = [_tool_use_block("call_1", "a1", "repair"), _tool_use_block("call_2", "a2", "replace")]
    result = FakeResult(
        stop_reason="interrupt",
        interrupts=[FakeInterrupt("call_1"), FakeInterrupt("call_2")],
        content=content,
    )

    record = persist_if_interrupted(storage, agent, result)

    assert record is not None
    assert agent.snapshot_taken
    assert len(record["requests"]) == 2
    assert record["requests"][0]["appliance_id"] == "a1"
    assert record["requests"][1]["appliance_id"] == "a2"
    assert record["snapshot"] == FAKE_SNAPSHOT_DICT
    assert storage.get_confirmation(record["id"]) == record


def test_resume_confirmation_raises_on_unknown_id():
    storage = FakeStorage()
    agent = FakeAgent()

    with pytest.raises(KeyError):
        resume_confirmation(storage, agent, "does-not-exist", ["a1"])


def test_resume_confirmation_approves_selected_and_denies_the_rest():
    storage = FakeStorage()
    storage.save_confirmation(
        "c1",
        {
            "id": "c1",
            "requests": [
                {"interrupt_id": _interrupt_id("call_1"), "appliance_id": "a1", "action": "repair"},
                {"interrupt_id": _interrupt_id("call_2"), "appliance_id": "a2", "action": "replace"},
                {"interrupt_id": _interrupt_id("call_3"), "appliance_id": "a3", "action": "repair"},
            ],
            "snapshot": FAKE_SNAPSHOT_DICT,
        },
    )
    agent = FakeAgent(resume_result=FakeResult(stop_reason="end_turn"))

    result = resume_confirmation(storage, agent, "c1", ["a1", "a3"])

    assert agent.loaded_snapshot is not None
    assert agent.resume_call == [
        {"interruptResponse": {"interruptId": _interrupt_id("call_1"), "response": True}},
        {"interruptResponse": {"interruptId": _interrupt_id("call_2"), "response": False}},
        {"interruptResponse": {"interruptId": _interrupt_id("call_3"), "response": True}},
    ]
    assert result.stop_reason == "end_turn"
    assert storage.get_confirmation("c1") is None  # deleted after resume


def test_confirmation_required_response_returns_none_on_normal_completion():
    storage = FakeStorage()
    agent = FakeAgent()
    result = FakeResult(stop_reason="end_turn", interrupts=None)

    assert confirmation_required_response(storage, agent, result) is None
    assert storage._confirmations == {}


def test_confirmation_required_response_persists_and_shapes_the_wire_payload():
    """The one shape every HTTP/WS surface sends when a run pauses — this is
    what used to be hand-rolled separately in /check, /ws/check (formerly
    inside live_trace.py itself), and POST /confirmations/{id}/respond."""
    storage = FakeStorage()
    agent = FakeAgent()
    content = [_tool_use_block("call_1", "a1", "repair")]
    result = FakeResult(stop_reason="interrupt", interrupts=[FakeInterrupt("call_1")], content=content)

    response = confirmation_required_response(storage, agent, result)

    assert response["confirmation_required"] is True
    assert response["confirmation_id"] in storage._confirmations
    assert response["requests"] == storage._confirmations[response["confirmation_id"]]["requests"]
    assert response["requests"][0]["appliance_id"] == "a1"


def test_resume_confirmation_with_no_approved_ids_denies_everything():
    storage = FakeStorage()
    storage.save_confirmation(
        "c1",
        {
            "id": "c1",
            "requests": [
                {"interrupt_id": _interrupt_id("call_1"), "appliance_id": "a1", "action": "repair"},
            ],
            "snapshot": FAKE_SNAPSHOT_DICT,
        },
    )
    agent = FakeAgent()

    resume_confirmation(storage, agent, "c1", [])

    assert agent.resume_call == [
        {"interruptResponse": {"interruptId": _interrupt_id("call_1"), "response": False}},
    ]
